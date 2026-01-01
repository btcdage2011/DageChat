import json
import asyncio
import time
import sys
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aiosqlite
from contextlib import asynccontextmanager

# --- 1. 配置加载模块 ---
def load_config():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(application_path, 'dagechat-relay.json')

    # 默认配置
    default_config = {
        "server": {"host": "0.0.0.0", "port": 3008, "name": "DageChat Relay (NIP-01 Compatible)"},
        "sqlite": {"db_file": "relay.db"},
        "limits": {"max_message_size": 2097152, "rate_limit_window": 60, "rate_limit_count": 200, "data_ttl": 2592000}
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if "server" in user_config: default_config['server'].update(user_config['server'])
                if "limits" in user_config: default_config['limits'].update(user_config['limits'])
                if "sqlite" in user_config: default_config['sqlite'].update(user_config['sqlite'])
            print(f"✅ 已加载配置文件: {config_path}")
    except Exception as e:
        print(f"❌ 配置文件读取错误: {e}")

    return default_config

CONF = load_config()
DB_FILE = CONF['sqlite']['db_file']


# 必须与客户端配置一致
OFFICIAL_GROUP_ID = "feb75fb664b41f95"
MIN_POW_OFFICIAL = 16
MIN_POW_NORMAL = 8


# --- 2. 内存速率限制器 ---
class RateLimiter:
    def __init__(self):
        self.requests = {}
        self.window = CONF['limits']['rate_limit_window']
        self.limit = CONF['limits']['rate_limit_count']

    def check(self, ip):
        now = time.time()
        if ip not in self.requests:
            self.requests[ip] = []
        self.requests[ip] = [t for t in self.requests[ip] if t > now - self.window]
        if len(self.requests[ip]) < self.limit:
            self.requests[ip].append(now)
            return True
        return False

rate_limiter = RateLimiter()

# --- 3. 数据库核心 (支持 NIP-01 查询) ---
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA synchronous=NORMAL;")

        # 1. Events 表: 存储消息本体
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                pubkey TEXT,
                kind INTEGER,
                created_at INTEGER,
                content TEXT,
                tags TEXT  -- 存储 JSON 格式的 tags，方便后续扩展
            )
        ''')
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind)")
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_pubkey ON events(pubkey)")

        # 2. Index Map 表: 倒排索引 (Tag -> EventID)
        # filter_key 存储: pubkey (authors), tag_value (#p, #g, #d)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS index_map (
                filter_key TEXT,
                event_id TEXT,
                created_at INTEGER,
                kind INTEGER,
                PRIMARY KEY (filter_key, event_id)
            )
        ''')
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_map_query ON index_map(filter_key, created_at)")

        await self.conn.commit()

        # 启动 TTL 清理任务
        asyncio.create_task(self.ttl_task())

    async def ttl_task(self):
        while True:
            try:
                await asyncio.sleep(3600) # 每小时检查一次
                ttl = CONF['limits']['data_ttl']
                cutoff = int(time.time()) - ttl
                # 清理过期索引和事件 (保留 Kind 0, 3, 30000+ 的元数据不清理？这里暂统一清理，因为客户端有备份)
                # 改进：Kind 0, 3, 30078 这种元数据通常不应被 TTL 清理，除非有更新的。
                # 简单起见，这里先只清理普通聊天消息 (Kind 1, 4, 42, 1059)
                chat_kinds = [1, 4, 42, 1059]
                placeholders = ','.join(map(str, chat_kinds))

                await self.conn.execute(f"DELETE FROM index_map WHERE created_at < ? AND kind IN ({placeholders})", (cutoff,))
                await self.conn.execute(f"DELETE FROM events WHERE created_at < ? AND kind IN ({placeholders})", (cutoff,))
                await self.conn.commit()
                print(f"🧹 [TTL] 清理了 {cutoff} 之前的聊天记录")
            except Exception as e:
                print(f"❌ TTL Error: {e}")

    async def save_event(self, event):
        """保存事件并建立索引"""
        eid = event['id']
        pk = event['pubkey']
        kind = event['kind']
        ts = event['created_at']
        content = event['content']
        tags = event.get('tags', [])

        # --- 1. 处理可替换事件 (Replaceable Events) ---
        # NIP-01: Kind 0, 3, 10000-19999
        # NIP-33: Kind 30000-39999 (Parameterized)

        is_replaceable = (kind in [0, 3]) or (10000 <= kind < 20000)
        is_param_replaceable = (30000 <= kind < 40000)

        async with self.conn.cursor() as cursor:
            # 如果是可替换事件，先删除旧的
            if is_replaceable:
                # 范围: 同 pubkey + 同 kind
                await self._delete_old_replaceable(cursor, pk, kind)

            elif is_param_replaceable:
                # 范围: 同 pubkey + 同 kind + 同 'd' tag
                d_tag = next((t[1] for t in tags if len(t) >= 2 and t[0] == 'd'), "")
                await self._delete_old_param_replaceable(cursor, pk, kind, d_tag)

            # --- 2. 插入新事件 ---
            try:
                await cursor.execute(
                    "INSERT OR IGNORE INTO events (id, pubkey, kind, created_at, content, tags) VALUES (?, ?, ?, ?, ?, ?)",
                    (eid, pk, kind, ts, content, json.dumps(tags))
                )

                # --- 3. 建立索引 ---
                # A. 作者索引 (authors)
                await self._add_index(cursor, pk, eid, ts, kind)

                # B. 标签索引 (#p, #g, #d, #e ...)
                # 标准 Relay 会索引所有单字符标签
                for tag in tags:
                    if len(tag) >= 2 and len(tag[0]) == 1:
                        tag_name = tag[0] # p, g, d, e ...
                        tag_val = tag[1]
                        # 索引值 (注意：为了区分不同 tag，通常 key 不需要加前缀，因为 Filter 指定了 #p)
                        # 但在 index_map 里我们混存了。
                        # 查询时: WHERE filter_key = 'value' AND checking event tags contains this value
                        # 为了简单，直接存 tag_val。Nostr ID 和 Pubkey 冲突概率极低。
                        await self._add_index(cursor, tag_val, eid, ts, kind)

                await self.conn.commit()
                return True
            except Exception as e:
                print(f"Save Error: {e}")
                return False

    async def _add_index(self, cursor, key, eid, ts, kind):
        await cursor.execute(
            "INSERT OR IGNORE INTO index_map (filter_key, event_id, created_at, kind) VALUES (?, ?, ?, ?)",
            (key, eid, ts, kind)
        )

    async def _delete_old_replaceable(self, cursor, pubkey, kind):
        # 查找旧事件 ID
        await cursor.execute("SELECT id FROM events WHERE pubkey = ? AND kind = ?", (pubkey, kind))
        rows = await cursor.fetchall()
        for row in rows:
            old_eid = row[0]
            await cursor.execute("DELETE FROM events WHERE id = ?", (old_eid,))
            await cursor.execute("DELETE FROM index_map WHERE event_id = ?", (old_eid,))

    async def _delete_old_param_replaceable(self, cursor, pubkey, kind, d_tag_val):
        # 查找旧事件 (需要解析 JSON tags，比较慢，但为了准确性)
        # SQLite 的 JSON 支持可能因版本而异，这里用 Python 过滤
        await cursor.execute("SELECT id, tags FROM events WHERE pubkey = ? AND kind = ?", (pubkey, kind))
        rows = await cursor.fetchall()
        for row in rows:
            old_eid, tags_json = row[0], row[1]
            try:
                old_tags = json.loads(tags_json)
                old_d = next((t[1] for t in old_tags if len(t) >= 2 and t[0] == 'd'), "")
                if old_d == d_tag_val:
                    await cursor.execute("DELETE FROM events WHERE id = ?", (old_eid,))
                    await cursor.execute("DELETE FROM index_map WHERE event_id = ?", (old_eid,))
            except: pass

    async def query_events(self, filters, limit=100):
        """
        NIP-01 核心查询逻辑
        filters: list of dicts [{"kinds":..., "#p":...}, ...]
        """
        if not filters: return []

        result_events = {} # 使用 dict 去重: {eid: event_dict}

        for flt in filters:
            # 1. 确定查询候选集 (Keys to look up)
            # 如果 Filter 为空，Nostr 标准是返回所有，但我们这里为了性能可以限制
            candidate_keys = set()

            has_key_filter = False

            # IDs
            if "ids" in flt:
                has_key_filter = True
                for i in flt["ids"]: candidate_keys.add(i)

            # Authors
            if "authors" in flt:
                has_key_filter = True
                for a in flt["authors"]: candidate_keys.add(a)

            # Tags (#p, #g, #d...)
            for k, v in flt.items():
                if k.startswith("#") and len(k) == 2 and isinstance(v, list):
                    has_key_filter = True
                    for tag_val in v: candidate_keys.add(tag_val)

            # Time range
            since = flt.get("since", 0)
            until = flt.get("until", int(time.time()) + 3600)
            kinds = flt.get("kinds", [])
            local_limit = flt.get("limit", limit)

            # 执行查询
            async with self.conn.cursor() as cursor:
                # 构造 SQL
                query = """
                    SELECT e.id, e.pubkey, e.kind, e.created_at, e.content, e.tags
                    FROM events e
                """
                params = []
                where_clauses = ["e.created_at >= ?", "e.created_at <= ?"]
                params.append(since)
                params.append(until)

                # Kinds 过滤
                if kinds:
                    placeholders = ','.join('?' for _ in kinds)
                    where_clauses.append(f"e.kind IN ({placeholders})")
                    params.extend(kinds)

                # Key 过滤 (利用 Index Map 加速)
                if has_key_filter:
                    # 如果有 key，联表查询 index_map
                    # 优化：如果 key 太多，可能需要分批。这里简化处理。
                    query = """
                        SELECT DISTINCT e.id, e.pubkey, e.kind, e.created_at, e.content, e.tags
                        FROM index_map i
                        JOIN events e ON i.event_id = e.id
                    """
                    # 重建 WHERE
                    where_clauses = ["e.created_at >= ?", "e.created_at <= ?"]
                    if kinds:
                        where_clauses.append(f"e.kind IN ({placeholders})")

                    key_list = list(candidate_keys)
                    if key_list:
                        k_holders = ','.join('?' for _ in key_list)
                        where_clauses.append(f"i.filter_key IN ({k_holders})")
                        params.extend(key_list)

                full_sql = f"{query} WHERE {' AND '.join(where_clauses)} ORDER BY e.created_at DESC LIMIT ?"
                params.append(local_limit)

                try:
                    await cursor.execute(full_sql, params)
                    rows = await cursor.fetchall()
                    for r in rows:
                        evt = {
                            "id": r[0], "pubkey": r[1], "kind": r[2],
                            "created_at": r[3], "content": r[4],
                            "tags": json.loads(r[5]) if r[5] else []
                        }
                        # 二次校验 (Double Check) - 确保精准匹配
                        if self._match_filter(evt, flt):
                            result_events[evt['id']] = evt
                except Exception as e:
                    print(f"Query Error: {e}")

        # 排序并返回
        sorted_events = sorted(result_events.values(), key=lambda x: x['created_at'])
        return sorted_events

    def _match_filter(self, event, flt):
        """Python 层的精准过滤器匹配"""
        if "ids" in flt and event['id'] not in flt['ids']: return False
        if "kinds" in flt and event['kind'] not in flt['kinds']: return False
        if "authors" in flt and event['pubkey'] not in flt['authors']: return False
        if "since" in flt and event['created_at'] < flt['since']: return False
        if "until" in flt and event['created_at'] > flt['until']: return False

        # Tag 匹配 (所有指定的 #tag 都必须存在至少一个匹配值)
        for k, v in flt.items():
            if k.startswith("#") and len(k) == 2:
                tag_char = k[1] # 'p', 'g'
                # 检查 event tags 里是否有 ['p', 'val'] 且 val 在 v 中
                found = False
                for t in event['tags']:
                    if len(t) >= 2 and t[0] == tag_char and t[1] in v:
                        found = True
                        break
                if not found: return False
        return True

    async def delete_events(self, target_ids):
        """处理撤回 (Kind 5)"""
        count = 0
        try:
            for tid in target_ids:
                await self.conn.execute("DELETE FROM events WHERE id = ?", (tid,))
                await self.conn.execute("DELETE FROM index_map WHERE event_id = ?", (tid,))
                count += 1
            await self.conn.commit()
        except: pass
        return count

    # [新增] 优雅关闭数据库
    async def close(self):
        if self.conn:
            try:
                # 优化：退出前强制将 WAL 日志合并到主数据库 (Checkpoint)
                # TRUNCATE 会清空 wal 文件，节省磁盘空间
                await self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                await self.conn.close()
                print("✅ [DB] 数据库连接已安全关闭 (WAL Checkpointed)")
            except Exception as e:
                print(f"❌ [DB] 关闭失败: {e}")

db = DatabaseManager(DB_FILE)

# --- 4. Lifespan ---
@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    print(f"🚀 SQLite Relay (Standard) Starting...")
    await db.init()
    yield
    # --- 这里的代码会在关闭时运行 ---
    print("👋 Relay Shutting down...")
    await db.close() # [新增] 调用关闭逻辑

app = FastAPI(lifespan=lifespan_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 5. Connection Manager ---
class ConnectionManager:
    def __init__(self):
        # {ws: {"id1": [filters...], "id2": [...]}}
        self.subscriptions = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.subscriptions[websocket] = {}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    async def add_subscription(self, websocket: WebSocket, sub_id: str, filters: list):
        # 1. 存储订阅状态 (用于后续广播)
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = {}
        self.subscriptions[websocket][sub_id] = filters

        # 2. 查询历史数据
        events = await db.query_events(filters, limit=200) # 限制单次返回

        # 3. 推送
        for evt in events:
            await websocket.send_text(json.dumps(["EVENT", sub_id, evt]))

        # 4. 发送 EOSE
        await websocket.send_text(json.dumps(["EOSE", sub_id]))

    async def broadcast(self, event: dict):
        """收到新 Event 后，广播给所有匹配的订阅者"""
        for ws, subs in self.subscriptions.items():
            for sub_id, filters in subs.items():
                # 检查此 Event 是否匹配该订阅的 Filter
                # 利用 db._match_filter 逻辑 (虽然是 private method 但这里为了复用逻辑)
                should_send = False
                for flt in filters:
                    if db._match_filter(event, flt):
                        should_send = True
                        break

                if should_send:
                    try:
                        await ws.send_text(json.dumps(["EVENT", sub_id, event]))
                    except:
                        # 连接可能断开，将在 disconnect 中清理
                        pass

manager = ConnectionManager()

# --- 6. HTTP Info ---
@app.get("/")
async def get_info():
    return JSONResponse({
        "name": CONF['server']['name'],
        "software": "dagechat-relay-standard",
        "version": "2.0.0",
        "supported_nips": [1, 2, 9, 11, 12, 15, 16, 20, 33],
        "limitation": CONF['limits']
    })

# --- 辅助函数：PoW 校验 ---
def verify_pow(event_id, min_difficulty):
    """
    验证 EventID 是否满足最小难度要求
    算法：将 Hex ID 转为整数，检查是否小于 2^(256 - difficulty)
    """
    try:
        # NIP-13 标准检查
        target = 1 << (256 - min_difficulty)
        id_val = int(event_id, 16)
        return id_val < target
    except:
        return False


# --- 7. WebSocket Endpoint ---
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    client_ip = websocket.client.host if websocket.client else "unknown"

    try:
        while True:
            data = await websocket.receive_text()
            if len(data) > CONF['limits']['max_message_size']: continue
            if not rate_limiter.check(client_ip):
                await websocket.send_text(json.dumps(["NOTICE", "Rate limit exceeded"]))
                continue

            try:
                msg = json.loads(data)

                # 严格校验基础格式
                if not isinstance(msg, list) or len(msg) < 2:
                    continue

                msg_type = msg[0]

                if msg_type == "EVENT":
                    # 标准 EVENT: ["EVENT", <event_dict>]
                    if len(msg) < 2: continue
                    event = msg[1]

                    eid = event.get('id')
                    kind = event.get('kind')
                    tags = event.get('tags', []) # 记得获取 tags
                    if not eid or kind is None: continue
                    # ================= [插入 PoW 校验代码] =================
                    # 仅针对群聊消息 (Kind 42) 进行拦截
                    if kind == 42:
                        # 1. 获取目标群 ID (g tag)
                        gid = next((t[1] for t in tags if len(t) >= 2 and t[0] == 'g'), None)

                        required_diff = 0
                        reject_reason = ""

                        if gid == OFFICIAL_GROUP_ID:
                            # 官方大厅：高难度
                            required_diff = MIN_POW_OFFICIAL
                            reject_reason = f"Official Lobby requires PoW difficulty >= {MIN_POW_OFFICIAL}"
                        elif gid:
                            # 普通群：低难度
                            required_diff = MIN_POW_NORMAL
                            reject_reason = f"Group chat requires PoW difficulty >= {MIN_POW_NORMAL}"

                        # 2. 执行校验
                        if required_diff > 0:
                            if not verify_pow(eid, required_diff):
                                # 校验失败，直接拒绝！
                                print(f"🛡️ [Anti-Spam] 拦截未挖矿消息: {eid[:6]} (Req: {required_diff})")
                                await websocket.send_text(json.dumps(["OK", eid, False, f"pow: {reject_reason}"]))
                                continue # 跳过后续保存逻辑，直接进入下一次循环
                    # ======================================================
                    # Kind 5: 撤回
                    if kind == 5:
                        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
                        deleted = await db.delete_events(target_ids)
                        await db.save_event(event)
                        await manager.broadcast(event)
                        await websocket.send_text(json.dumps(["OK", eid, True, f"deleted {deleted} events"]))
                        continue

                    # 保存并广播
                    saved = await db.save_event(event)
                    if saved:
                        await manager.broadcast(event)
                        await websocket.send_text(json.dumps(["OK", eid, True, "stored"]))
                    else:
                        await websocket.send_text(json.dumps(["OK", eid, False, "duplicate or error"]))

                elif msg_type == "REQ":
                    # 严格标准 REQ: ["REQ", <sub_id>, <filter1>, ...]
                    # 必须 >= 3 元素，否则直接丢弃/报错
                    if len(msg) >= 3:
                        sub_id = msg[1]
                        filters = msg[2:]
                        await manager.add_subscription(websocket, sub_id, filters)
                    else:
                        await websocket.send_text(json.dumps(["NOTICE", "Invalid REQ format: missing sub_id or filters"]))

                elif msg_type == "CLOSE":
                    # 标准 CLOSE: ["CLOSE", <sub_id>]
                    if len(msg) >= 2:
                        sub_id = msg[1]
                        if websocket in manager.subscriptions:
                            manager.subscriptions[websocket].pop(sub_id, None)

            except Exception as e:
                print(f"Relay Protocol Error: {e}")
                # 不打印 traceback 避免刷屏，除非调试

    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # DageChat ASCII Art Banner
    banner = r"""
 /$$$$$$$                                 /$$$$$$  /$$                   /$$     /$$$$$$$            /$$
| $$__  $$                               /$$__  $$| $$                  | $$    | $$__  $$          | $$
| $$  \ $$  /$$$$$$   /$$$$$$   /$$$$$$ | $$  \__/| $$$$$$$   /$$$$$$  /$$$$$$  | $$  \ $$  /$$$$$$ | $$  /$$$$$$  /$$   /$$
| $$  | $$ |____  $$ /$$__  $$ /$$__  $$| $$      | $$__  $$ |____  $$|_  $$_/  | $$$$$$$/ /$$__  $$| $$ |____  $$| $$  | $$
| $$  | $$  /$$$$$$$| $$  \ $$| $$$$$$$$| $$      | $$  \ $$  /$$$$$$$  | $$    | $$__  $$| $$$$$$$$| $$  /$$$$$$$| $$  | $$
| $$  | $$ /$$__  $$| $$  | $$| $$_____/| $$    $$| $$  | $$ /$$__  $$  | $$ /$$| $$  \ $$| $$_____/| $$ /$$__  $$| $$  | $$
| $$$$$$$/|  $$$$$$$|  $$$$$$$|  $$$$$$$|  $$$$$$/| $$  | $$|  $$$$$$$  |  $$$$/| $$  | $$|  $$$$$$$| $$|  $$$$$$$|  $$$$$$$
|_______/  \_______/ \____  $$ \_______/ \______/ |__/  |__/ \_______/   \___/  |__/  |__/ \_______/|__/ \_______/ \____  $$
                     /$$  \ $$                                                                                     /$$  | $$
                    |  $$$$$$/                                                                                    |  $$$$$$/
                     \______/                                                                                      \______/
    """

    print(banner)
    print("-" * 120)
    print(f"Author:  @BTCDage")
    print(f"Nostr:   npub17ahz4xa3hvkvvhh4wguzzqknp8p7l5nyzzqc3z53uq538r5qgn0q40z7pw")
    print(f"Donate:  bc1qzemaa3lc92f2x0q72e5jdx045ss6rm4hzazgde")
    print("-" * 120)

    # Status messages (Keep your existing mode indication here)
    mode_name = "SQLite" if "sqlite" in CONF else "Redis"
    print(f"🚀 {CONF['server']['name']} ({mode_name} Mode) starting on port {CONF['server']['port']}...")
    if mode_name == "SQLite":
        print(f"📂 Database: {DB_FILE} (WAL Enabled)")

    print("-" * 120)
    uvicorn.run(app, host=CONF['server']['host'], port=CONF['server']['port'])
