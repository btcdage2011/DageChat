import json
import asyncio
import time
import sys
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import asyncio as aioredis

# --- 1. 配置加载 ---
def load_config():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(application_path, 'dagechat-relay.json')

    default_config = {
        "server": {"host": "0.0.0.0", "port": 3008, "name": "DageChat Redis Relay (NIP-01)"},
        "redis": {"host": "localhost", "port": 6379, "password": None, "db": 0},
        "limits": {"max_message_size": 2097152, "rate_limit_window": 60, "rate_limit_count": 200, "data_ttl": 2592000}
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if "server" in user_config: default_config['server'].update(user_config['server'])
                if "redis" in user_config: default_config['redis'].update(user_config['redis'])
                if "limits" in user_config: default_config['limits'].update(user_config['limits'])
            print(f"✅ 已加载配置文件: {config_path}")
    except Exception as e:
        print(f"❌ 配置文件读取错误: {e}")

    return default_config

CONF = load_config()

# 必须与客户端配置一致
OFFICIAL_GROUP_ID = "feb75fb664b41f95"
MIN_POW_OFFICIAL = 16
MIN_POW_NORMAL = 8

# --- 2. FastAPI Setup ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis = aioredis.Redis(
    host=CONF['redis']['host'],
    port=CONF['redis']['port'],
    password=CONF['redis']['password'],
    db=CONF['redis']['db'],
    decode_responses=True
)

# --- 3. Redis 存储核心逻辑 (NIP-01) ---
class StorageManager:
    """
    Redis Schema Design:
    - event:{id} -> JSON string (TTL)
    - idx:kind:{kind} -> ZSET(score=created_at, member=id)
    - idx:author:{pubkey} -> ZSET(score=created_at, member=id)
    - idx:tag:{char}:{val} -> ZSET(score=created_at, member=id)  (e.g., idx:tag:p:abcd...)
    - replaceable:{kind}:{pubkey} -> event_id (用于快速查找旧的可替换事件)
    - param_replaceable:{kind}:{pubkey}:{d_tag} -> event_id (用于 NIP-33)
    """

    async def save_event(self, event):
        eid = event['id']
        pk = event['pubkey']
        kind = event['kind']
        ts = event['created_at']
        tags = event.get('tags', [])

        # 1. 检查是否存在
        if await redis.exists(f"event:{eid}"):
            return False

        pipeline = redis.pipeline()
        ttl = CONF['limits']['data_ttl']

        # 2. 处理可替换事件 (NIP-01 / NIP-33)
        # NIP-01 Replaceable: 0, 3, 10000-19999
        is_replaceable = (kind in [0, 3]) or (10000 <= kind < 20000)
        # NIP-33 Parameterized: 30000-39999
        is_param = (30000 <= kind < 40000)

        old_eid = None

        if is_replaceable:
            rep_key = f"replaceable:{kind}:{pk}"
            old_eid = await redis.get(rep_key)
            pipeline.set(rep_key, eid, ex=ttl)

        elif is_param:
            d_tag = next((t[1] for t in tags if len(t) >= 2 and t[0] == 'd'), "")
            rep_key = f"param_replaceable:{kind}:{pk}:{d_tag}"
            old_eid = await redis.get(rep_key)
            pipeline.set(rep_key, eid, ex=ttl)

        # 如果存在旧版本，从所有索引中移除旧ID (物理删除 event:{old_id} 可选，这里为了节省空间也删)
        if old_eid:
            await self._delete_event_from_indexes(old_eid, pipeline)

        # 3. 保存新事件
        pipeline.set(f"event:{eid}", json.dumps(event), ex=ttl)

        # 4. 建立索引 (ZSET)
        # Kind Index
        pipeline.zadd(f"idx:kind:{kind}", {eid: ts})
        pipeline.expire(f"idx:kind:{kind}", ttl)

        # Author Index
        pipeline.zadd(f"idx:author:{pk}", {eid: ts})
        pipeline.expire(f"idx:author:{pk}", ttl)

        # Tag Index (索引所有单字符 Tag)
        for t in tags:
            if len(t) >= 2 and len(t[0]) == 1:
                tag_char = t[0]
                tag_val = t[1]
                # 限制索引长度，防止恶意 Tag 攻击
                if len(tag_val) < 200:
                    k = f"idx:tag:{tag_char}:{tag_val}"
                    pipeline.zadd(k, {eid: ts})
                    pipeline.expire(k, ttl)

        await pipeline.execute()
        return True

    async def _delete_event_from_indexes(self, eid, pipeline):
        # 注意：彻底清理索引需要知道 Event 的内容（Kind, Tags）。
        # 如果 Redis 里 event:{eid} 还在，我们可以读出来然后清理。
        # 如果已经过期了，索引可能残留，但这不影响查询正确性（查询时会检查 event 是否存在）。
        # 这里做一个简单的“尝试读取并清理”

        raw = await redis.get(f"event:{eid}")
        if raw:
            evt = json.loads(raw)
            pipeline.delete(f"event:{eid}")
            pipeline.zrem(f"idx:kind:{evt['kind']}", eid)
            pipeline.zrem(f"idx:author:{evt['pubkey']}", eid)
            for t in evt.get('tags', []):
                if len(t) >= 2 and len(t[0]) == 1:
                    pipeline.zrem(f"idx:tag:{t[0]}:{t[1]}", eid)

    async def query_events(self, filters, limit=100):
        """
        NIP-01 查询策略:
        为了性能，我们不使用全量的 ZINTERSTORE (开销大)。
        策略：
        1. 找到 Filter 中“最具选择性”的条件（Tag > Author > Kind）。
        2. 从该条件的索引中拉取 Candidate IDs。
        3. 在内存中过滤剩下的条件。
        """
        result_events = {}

        for flt in filters:
            # 1. 确定查询锚点 (Candidate Source)
            candidate_ids = set()
            use_source = None # 'ids', 'tags', 'authors', 'kinds', 'all'

            # 优先查 IDs
            if "ids" in flt:
                candidate_ids = set(flt["ids"])
                use_source = 'ids'

            # 其次查 Tags (#p, #g, #d...)
            elif any(k.startswith("#") and len(k) == 2 for k in flt):
                # 收集所有涉及的 Tag 索引 Key
                tag_keys = []
                for k, v in flt.items():
                    if k.startswith("#") and len(k) == 2 and isinstance(v, list):
                        char = k[1]
                        for val in v:
                            tag_keys.append(f"idx:tag:{char}:{val}")

                # 联合查询所有 Tag 索引 (使用 ZREVRANGE 获取最新的)
                # 限制每个 Tag 索引取 limit 条，防止内存爆炸
                for tk in tag_keys:
                    ids = await redis.zrevrange(tk, 0, limit - 1)
                    candidate_ids.update(ids)
                use_source = 'tags'

            # 再次查 Authors
            elif "authors" in flt:
                for pk in flt["authors"]:
                    ids = await redis.zrevrange(f"idx:author:{pk}", 0, limit - 1)
                    candidate_ids.update(ids)
                use_source = 'authors'

            # 最后查 Kinds (如果只有 kinds 过滤，可能会很慢，需限制)
            elif "kinds" in flt:
                for k in flt["kinds"]:
                    ids = await redis.zrevrange(f"idx:kind:{k}", 0, limit - 1)
                    candidate_ids.update(ids)
                use_source = 'kinds'

            else:
                # 空 Filter？通常不允许，或者只返回最新的全局消息
                # 这里为了安全，不返回任何东西，或者你可以实现 idx:all
                continue

            # 2. 获取 Event 内容并二次过滤
            if not candidate_ids: continue

            # 批量获取 JSON
            # 注意：Redis Cluster 不支持跨 Slot 的 MGET，但在单机/主从模式下没问题
            # 这里的 eid 列表可能包含已过期的，mget 会返回 None
            keys = [f"event:{eid}" for eid in candidate_ids]
            # 分批 MGET 防止包过大
            chunk_size = 100
            for i in range(0, len(keys), chunk_size):
                chunk = keys[i:i+chunk_size]
                json_strs = await redis.mget(chunk)

                for js in json_strs:
                    if not js: continue
                    try:
                        evt = json.loads(js)
                        if self._match_filter(evt, flt):
                            result_events[evt['id']] = evt
                    except: pass

        # 排序并截取 Limit
        sorted_evts = sorted(result_events.values(), key=lambda x: x['created_at'])
        # Nostr 协议通常要求返回最新的，所以可能是倒序。
        # 但客户端通常按时间正序处理。这里按 created_at 排序比较安全。
        return sorted_evts

    def _match_filter(self, event, flt):
        if "ids" in flt and event['id'] not in flt['ids']: return False
        if "kinds" in flt and event['kind'] not in flt['kinds']: return False
        if "authors" in flt and event['pubkey'] not in flt['authors']: return False

        since = flt.get("since", 0)
        until = flt.get("until", int(time.time()) + 3600)
        if event['created_at'] < since or event['created_at'] > until: return False

        # Tags 匹配
        for k, v in flt.items():
            if k.startswith("#") and len(k) == 2:
                char = k[1]
                # 只要 Event 的 tags 中有一个匹配 v 列表中的任意值即可
                has_match = False
                for t in event.get('tags', []):
                    if len(t) >= 2 and t[0] == char and t[1] in v:
                        has_match = True
                        break
                if not has_match: return False

        return True

    async def delete_events_by_ids(self, ids):
        pipeline = redis.pipeline()
        for eid in ids:
            # 标记删除或真删除？Nostr Kind 5 是“请求删除”。
            # 简单起见，我们真删除
            await self._delete_event_from_indexes(eid, pipeline)
        await pipeline.execute()
        return len(ids)

storage = StorageManager()

# --- 4. Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections = {} # {ws: set(sub_ids)}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def add_subscription(self, websocket: WebSocket, sub_id: str, filters: list):
        if websocket in self.active_connections:
            self.active_connections[websocket].add(sub_id)

            # 查询历史
            events = await storage.query_events(filters, limit=200)

            # 推送
            for evt in events:
                await websocket.send_text(json.dumps(["EVENT", sub_id, evt]))

            # 结束信号
            await websocket.send_text(json.dumps(["EOSE", sub_id]))

    async def broadcast(self, event: dict):
        # 简单广播：推给所有连接？
        # 标准 Relay 应该根据 Subscription 的 Filter 进行精确路由。
        # 这里的实现：为了 Redis 版的高性能，我们可以引入 Redis Pub/Sub，或者简单的内存遍历。
        # 为了保持 Python 脚本的简单性（无额外 Redis PubSub 进程），我们在内存中做简单匹配。
        # 但注意：这个脚本如果是多进程部署 (gunicorn -w 4)，内存广播是不通的。
        # 如果你需要多进程广播，必须用 Redis Pub/Sub。
        # 鉴于 DageChat 目前可能是单实例运行，先做内存匹配。

        # TODO: 生产环境请使用 Redis PubSub 实现跨进程广播

        # 这里暂时只做“无差别”或者“简单”广播，让客户端自己去重？
        # 不，Nostr 协议要求按需推送。
        # 由于我们无法在 Redis 侧存储复杂的 Filter 对象（序列化麻烦），
        # 我们这里做一个折衷：如果是单进程，我们遍历 Filter。
        pass
        # (注：广播逻辑在 WebSocket 循环中直接调用 manager.broadcast_local)

    async def broadcast_local(self, event):
        """仅在当前进程内广播"""
        # 注意：这需要 ConnectionManager 存储每个连接的 Filters。
        # 现在的架构里，add_subscription 没有存 filters。
        # 为了 Redis 版的高并发，通常不建议在 Python 层做复杂的 Filter 匹配。
        # 但为了功能完整，我们需要存一下。
        pass

# 为了支持广播，我们需要稍微修改一下 ConnectionManager
# 重新定义:
class SmartConnectionManager:
    def __init__(self):
        # {ws: {sub_id: filters}}
        self.conns = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns[ws] = {}

    def disconnect(self, ws: WebSocket):
        if ws in self.conns: del self.conns[ws]

    async def add_subscription(self, ws: WebSocket, sub_id: str, filters: list):
        if ws in self.conns:
            self.conns[ws][sub_id] = filters
            # 查询历史
            events = await storage.query_events(filters, limit=200)
            for evt in events:
                try: await ws.send_text(json.dumps(["EVENT", sub_id, evt]))
                except: pass
            try: await ws.send_text(json.dumps(["EOSE", sub_id]))
            except: pass

    async def remove_subscription(self, ws: WebSocket, sub_id: str):
        if ws in self.conns and sub_id in self.conns[ws]:
            del self.conns[ws][sub_id]

    async def broadcast_event(self, event):
        """遍历所有连接的过滤器，匹配则推送"""
        for ws, subs in self.conns.items():
            for sub_id, filters in subs.items():
                match = False
                for flt in filters:
                    if storage._match_filter(event, flt):
                        match = True
                        break
                if match:
                    try: await ws.send_text(json.dumps(["EVENT", sub_id, event]))
                    except: pass

manager = SmartConnectionManager()

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


# --- 5. WebSocket Endpoint ---
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
                if not isinstance(msg, list) or len(msg) < 2: continue

                msg_type = msg[0]

                if msg_type == "EVENT":
                    event = msg[1]
                    eid = event.get('id')
                    kind = event.get('kind')
                    tags = event.get('tags', [])

                    if not eid: continue

                    # === [新增] PoW 核心拦截层 ===

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

                    if kind == 5:
                        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
                        deleted_count = await storage.delete_events_by_ids(target_ids)
                        # 广播 Kind 5 本身
                        await manager.broadcast_event(event)
                        await websocket.send_text(json.dumps(["OK", eid, True, f"deleted {deleted_count}"]))
                        continue

                    # 保存
                    if await storage.save_event(event):
                        await manager.broadcast_event(event)
                        await websocket.send_text(json.dumps(["OK", eid, True, ""]))
                    else:
                        await websocket.send_text(json.dumps(["OK", eid, True, "duplicate"]))

                elif msg_type == "REQ":
                    if len(msg) >= 3:
                        sub_id = msg[1]
                        filters = msg[2:]
                        await manager.add_subscription(websocket, sub_id, filters)
                    else:
                        await websocket.send_text(json.dumps(["NOTICE", "Invalid REQ"]))

                elif msg_type == "CLOSE":
                    if len(msg) >= 2:
                        sub_id = msg[1]
                        await manager.remove_subscription(websocket, sub_id)

            except Exception as e:
                print(f"Error: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def info():
    return JSONResponse({
        "name": CONF['server']['name'],
        "software": "dagechat-redis",
        "supported_nips": [1, 33],
        "version": "2.0.0"
    })

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
