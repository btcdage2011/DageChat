# -*- coding: utf-8 -*-
"""
-------------------------------------------------
Project:   DageChat (Nostr Protocol Client Research)
Author:    @BTCDage
Nostr:     npub17ahz4xa3hvkvvhh4wguzzqknp8p7l5nyzzqc3z53uq538r5qgn0q40z7pw
License:   MIT License
Source:    https://github.com/btcdage2011/DageChat
-------------------------------------------------

Disclaimer / 免责声明:
1. This software is for technical research, cryptography study, and protocol testing purposes only.
   本软件仅供计算机网络技术研究、密码学学习及协议测试使用。
2. The author assumes no liability for any misuse of this software.
   作者不对使用本软件产生的任何后果负责。
3. Illegal use of this software is strictly prohibited.
   严禁将本软件用于任何违反当地法律法规的用途。
-------------------------------------------------
"""

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

def load_config():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(application_path, 'dagechat-relay.json')
    default_config = {'server': {'host': '0.0.0.0', 'port': 3008, 'name': 'DageChat Relay (NIP-01 Compatible)'}, 'sqlite': {'db_file': 'relay.db'}, 'limits': {'max_message_size': 2097152, 'rate_limit_window': 60, 'rate_limit_count': 200, 'data_ttl': 2592000, 'ttl_config': {'default': 259200, 'kinds': {'0': 31536000, '3': 31536000, '30078': 31536000, '3000': 31536000, '1059': 2592000, '4': 2592000, '14': 2592000, '42': 604800, '5': 604800}}}}
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                if 'server' in user_config:
                    default_config['server'].update(user_config['server'])
                if 'limits' in user_config:
                    for k, v in user_config['limits'].items():
                        if k == 'ttl_config' and isinstance(v, dict):
                            if 'kinds' in v:
                                default_config['limits']['ttl_config']['kinds'].update(v['kinds'])
                            if 'default' in v:
                                default_config['limits']['ttl_config']['default'] = v['default']
                        else:
                            default_config['limits'][k] = v
                if 'sqlite' in user_config:
                    default_config['sqlite'].update(user_config['sqlite'])
            print(f'✅ 已加载配置文件: {config_path}')
    except Exception as e:
        print(f'❌ 配置文件读取错误: {e}')
    return default_config
CONF = load_config()
DB_FILE = CONF['sqlite']['db_file']
OFFICIAL_GROUP_ID = 'feb75fb664b41f95'
MIN_POW_OFFICIAL = 16
MIN_POW_NORMAL = 8

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

class DatabaseManager:

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute('PRAGMA journal_mode=WAL;')
        await self.conn.execute('PRAGMA synchronous=NORMAL;')
        await self.conn.execute('\n            CREATE TABLE IF NOT EXISTS events (\n                id TEXT PRIMARY KEY,\n                pubkey TEXT,\n                kind INTEGER,\n                created_at INTEGER,\n                content TEXT,\n                tags TEXT  -- 存储 JSON 格式的 tags，方便后续扩展\n            )\n        ')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind)')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_events_pubkey ON events(pubkey)')
        await self.conn.execute('\n            CREATE TABLE IF NOT EXISTS index_map (\n                filter_key TEXT,\n                event_id TEXT,\n                created_at INTEGER,\n                kind INTEGER,\n                PRIMARY KEY (filter_key, event_id)\n            )\n        ')
        await self.conn.execute('CREATE INDEX IF NOT EXISTS idx_map_query ON index_map(filter_key, created_at)')
        await self.conn.commit()
        asyncio.create_task(self.ttl_task())

    async def ttl_task(self):
        while True:
            try:
                await asyncio.sleep(3600)
                now = int(time.time())
                limits = CONF['limits']
                ttl_conf = limits.get('ttl_config', {})
                default_ttl = ttl_conf.get('default', limits.get('data_ttl', 259200))
                kind_ttls = ttl_conf.get('kinds', {})
                specific_kinds = {}
                for k, v in kind_ttls.items():
                    try:
                        specific_kinds[int(k)] = int(v)
                    except:
                        pass
                total_deleted = 0
                handled_kinds = []
                for k_val, seconds in specific_kinds.items():
                    cutoff = now - seconds
                    await self.conn.execute('DELETE FROM index_map WHERE kind = ? AND created_at < ?', (k_val, cutoff))
                    cursor = await self.conn.execute('DELETE FROM events WHERE kind = ? AND created_at < ?', (k_val, cutoff))
                    if cursor.rowcount > 0:
                        total_deleted += cursor.rowcount
                    handled_kinds.append(k_val)
                default_cutoff = now - default_ttl
                if handled_kinds:
                    placeholders = ','.join(map(str, handled_kinds))
                    sql_idx = f'DELETE FROM index_map WHERE kind NOT IN ({placeholders}) AND created_at < ?'
                    sql_evt = f'DELETE FROM events WHERE kind NOT IN ({placeholders}) AND created_at < ?'
                    await self.conn.execute(sql_idx, (default_cutoff,))
                    cursor = await self.conn.execute(sql_evt, (default_cutoff,))
                    if cursor.rowcount > 0:
                        total_deleted += cursor.rowcount
                else:
                    await self.conn.execute('DELETE FROM index_map WHERE created_at < ?', (default_cutoff,))
                    cursor = await self.conn.execute('DELETE FROM events WHERE created_at < ?', (default_cutoff,))
                    if cursor.rowcount > 0:
                        total_deleted += cursor.rowcount
                await self.conn.commit()
                if total_deleted > 0:
                    print(f'🧹 [TTL] 精细化清理完成，共删除 {total_deleted} 条过期记录')
            except Exception as e:
                print(f'❌ TTL Task Error: {e}')
                try:
                    await self.conn.rollback()
                except:
                    pass

    async def save_event(self, event):
        eid = event['id']
        pk = event['pubkey']
        kind = event['kind']
        ts = event['created_at']
        content = event['content']
        tags = event.get('tags', [])
        is_replaceable = kind in [0, 3] or 10000 <= kind < 20000
        is_param_replaceable = 30000 <= kind < 40000
        async with self.conn.cursor() as cursor:
            if is_replaceable:
                await self._delete_old_replaceable(cursor, pk, kind)
            elif is_param_replaceable:
                d_tag = next((t[1] for t in tags if len(t) >= 2 and t[0] == 'd'), '')
                await self._delete_old_param_replaceable(cursor, pk, kind, d_tag)
            try:
                await cursor.execute('INSERT OR IGNORE INTO events (id, pubkey, kind, created_at, content, tags) VALUES (?, ?, ?, ?, ?, ?)', (eid, pk, kind, ts, content, json.dumps(tags)))
                await self._add_index(cursor, pk, eid, ts, kind)
                for tag in tags:
                    if len(tag) >= 2 and len(tag[0]) == 1:
                        tag_name = tag[0]
                        tag_val = tag[1]
                        await self._add_index(cursor, tag_val, eid, ts, kind)
                await self.conn.commit()
                return True
            except Exception as e:
                print(f'Save Error: {e}')
                return False

    async def _add_index(self, cursor, key, eid, ts, kind):
        await cursor.execute('INSERT OR IGNORE INTO index_map (filter_key, event_id, created_at, kind) VALUES (?, ?, ?, ?)', (key, eid, ts, kind))

    async def _delete_old_replaceable(self, cursor, pubkey, kind):
        await cursor.execute('SELECT id FROM events WHERE pubkey = ? AND kind = ?', (pubkey, kind))
        rows = await cursor.fetchall()
        for row in rows:
            old_eid = row[0]
            await cursor.execute('DELETE FROM events WHERE id = ?', (old_eid,))
            await cursor.execute('DELETE FROM index_map WHERE event_id = ?', (old_eid,))

    async def _delete_old_param_replaceable(self, cursor, pubkey, kind, d_tag_val):
        await cursor.execute('SELECT id, tags FROM events WHERE pubkey = ? AND kind = ?', (pubkey, kind))
        rows = await cursor.fetchall()
        for row in rows:
            old_eid, tags_json = (row[0], row[1])
            try:
                old_tags = json.loads(tags_json)
                old_d = next((t[1] for t in old_tags if len(t) >= 2 and t[0] == 'd'), '')
                if old_d == d_tag_val:
                    await cursor.execute('DELETE FROM events WHERE id = ?', (old_eid,))
                    await cursor.execute('DELETE FROM index_map WHERE event_id = ?', (old_eid,))
            except:
                pass

    async def query_events(self, filters, limit=100):
        if not filters:
            return []
        result_events = {}
        for flt in filters:
            candidate_keys = set()
            has_key_filter = False
            if 'ids' in flt:
                has_key_filter = True
                for i in flt['ids']:
                    candidate_keys.add(i)
            if 'authors' in flt:
                has_key_filter = True
                for a in flt['authors']:
                    candidate_keys.add(a)
            for k, v in flt.items():
                if k.startswith('#') and len(k) == 2 and isinstance(v, list):
                    has_key_filter = True
                    for tag_val in v:
                        candidate_keys.add(tag_val)
            since = flt.get('since', 0)
            until = flt.get('until', int(time.time()) + 3600)
            kinds = flt.get('kinds', [])
            local_limit = flt.get('limit', limit)
            async with self.conn.cursor() as cursor:
                query = '\n                    SELECT e.id, e.pubkey, e.kind, e.created_at, e.content, e.tags\n                    FROM events e\n                '
                params = []
                where_clauses = ['e.created_at >= ?', 'e.created_at <= ?']
                params.append(since)
                params.append(until)
                if kinds:
                    placeholders = ','.join(('?' for _ in kinds))
                    where_clauses.append(f'e.kind IN ({placeholders})')
                    params.extend(kinds)
                if has_key_filter:
                    query = '\n                        SELECT DISTINCT e.id, e.pubkey, e.kind, e.created_at, e.content, e.tags\n                        FROM index_map i\n                        JOIN events e ON i.event_id = e.id\n                    '
                    where_clauses = ['e.created_at >= ?', 'e.created_at <= ?']
                    if kinds:
                        where_clauses.append(f'e.kind IN ({placeholders})')
                    key_list = list(candidate_keys)
                    if key_list:
                        k_holders = ','.join(('?' for _ in key_list))
                        where_clauses.append(f'i.filter_key IN ({k_holders})')
                        params.extend(key_list)
                full_sql = f"{query} WHERE {' AND '.join(where_clauses)} ORDER BY e.created_at DESC LIMIT ?"
                params.append(local_limit)
                try:
                    await cursor.execute(full_sql, params)
                    rows = await cursor.fetchall()
                    for r in rows:
                        evt = {'id': r[0], 'pubkey': r[1], 'kind': r[2], 'created_at': r[3], 'content': r[4], 'tags': json.loads(r[5]) if r[5] else []}
                        if self._match_filter(evt, flt):
                            result_events[evt['id']] = evt
                except Exception as e:
                    print(f'Query Error: {e}')
        sorted_events = sorted(result_events.values(), key=lambda x: x['created_at'])
        return sorted_events

    def _match_filter(self, event, flt):
        if 'ids' in flt and event['id'] not in flt['ids']:
            return False
        if 'kinds' in flt and event['kind'] not in flt['kinds']:
            return False
        if 'authors' in flt and event['pubkey'] not in flt['authors']:
            return False
        if 'since' in flt and event['created_at'] < flt['since']:
            return False
        if 'until' in flt and event['created_at'] > flt['until']:
            return False
        for k, v in flt.items():
            if k.startswith('#') and len(k) == 2:
                tag_char = k[1]
                found = False
                for t in event['tags']:
                    if len(t) >= 2 and t[0] == tag_char and (t[1] in v):
                        found = True
                        break
                if not found:
                    return False
        return True

    async def delete_events(self, target_ids):
        count = 0
        try:
            for tid in target_ids:
                await self.conn.execute('DELETE FROM events WHERE id = ?', (tid,))
                await self.conn.execute('DELETE FROM index_map WHERE event_id = ?', (tid,))
                count += 1
            await self.conn.commit()
        except:
            pass
        return count

    async def close(self):
        if self.conn:
            try:
                await self.conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
                await self.conn.close()
                print('✅ [DB] 数据库连接已安全关闭 (WAL Checkpointed)')
            except Exception as e:
                print(f'❌ [DB] 关闭失败: {e}')
db = DatabaseManager(DB_FILE)

@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    print(f'🚀 SQLite Relay (Standard) Starting...')
    await db.init()
    yield
    print('👋 Relay Shutting down...')
    await db.close()
app = FastAPI(lifespan=lifespan_handler)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

class ConnectionManager:

    def __init__(self):
        self.subscriptions = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.subscriptions[websocket] = {}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]

    async def add_subscription(self, websocket: WebSocket, sub_id: str, filters: list):
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = {}
        self.subscriptions[websocket][sub_id] = filters
        events = await db.query_events(filters, limit=200)
        for evt in events:
            await websocket.send_text(json.dumps(['EVENT', sub_id, evt]))
        await websocket.send_text(json.dumps(['EOSE', sub_id]))

    async def broadcast(self, event: dict):
        for ws, subs in self.subscriptions.items():
            for sub_id, filters in subs.items():
                should_send = False
                for flt in filters:
                    if db._match_filter(event, flt):
                        should_send = True
                        break
                if should_send:
                    try:
                        await ws.send_text(json.dumps(['EVENT', sub_id, event]))
                    except:
                        pass
manager = ConnectionManager()

@app.get('/')
async def get_info():
    return JSONResponse({'name': CONF['server']['name'], 'software': 'dagechat-relay-standard', 'version': '2.0.0', 'supported_nips': [1, 2, 9, 11, 12, 15, 16, 20, 33], 'limitation': CONF['limits']})

def verify_pow(event_id, min_difficulty):
    try:
        target = 1 << 256 - min_difficulty
        id_val = int(event_id, 16)
        return id_val < target
    except:
        return False

@app.websocket('/')
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    client_ip = websocket.client.host if websocket.client else 'unknown'
    try:
        while True:
            data = await websocket.receive_text()
            if len(data) > CONF['limits']['max_message_size']:
                continue
            if not rate_limiter.check(client_ip):
                await websocket.send_text(json.dumps(['NOTICE', 'Rate limit exceeded']))
                continue
            try:
                msg = json.loads(data)
                if not isinstance(msg, list) or len(msg) < 2:
                    continue
                msg_type = msg[0]
                if msg_type == 'EVENT':
                    if len(msg) < 2:
                        continue
                    event = msg[1]
                    eid = event.get('id')
                    kind = event.get('kind')
                    tags = event.get('tags', [])
                    if not eid or kind is None:
                        continue
                    if kind == 42:
                        gid = next((t[1] for t in tags if len(t) >= 2 and t[0] == 'g'), None)
                        required_diff = 0
                        reject_reason = ''
                        if gid == OFFICIAL_GROUP_ID:
                            required_diff = MIN_POW_OFFICIAL
                            reject_reason = f'Official Lobby requires PoW difficulty >= {MIN_POW_OFFICIAL}'
                        elif gid:
                            required_diff = MIN_POW_NORMAL
                            reject_reason = f'Group chat requires PoW difficulty >= {MIN_POW_NORMAL}'
                        if required_diff > 0:
                            if not verify_pow(eid, required_diff):
                                print(f'🛡️ [Anti-Spam] 拦截未挖矿消息: {eid[:6]} (Req: {required_diff})')
                                await websocket.send_text(json.dumps(['OK', eid, False, f'pow: {reject_reason}']))
                                continue
                    if kind == 5:
                        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
                        deleted = await db.delete_events(target_ids)
                        await db.save_event(event)
                        await manager.broadcast(event)
                        await websocket.send_text(json.dumps(['OK', eid, True, f'deleted {deleted} events']))
                        continue
                    saved = await db.save_event(event)
                    if saved:
                        await manager.broadcast(event)
                        await websocket.send_text(json.dumps(['OK', eid, True, 'stored']))
                    else:
                        await websocket.send_text(json.dumps(['OK', eid, False, 'duplicate or error']))
                elif msg_type == 'REQ':
                    if len(msg) >= 3:
                        sub_id = msg[1]
                        filters = msg[2:]
                        await manager.add_subscription(websocket, sub_id, filters)
                    else:
                        await websocket.send_text(json.dumps(['NOTICE', 'Invalid REQ format: missing sub_id or filters']))
                elif msg_type == 'CLOSE':
                    if len(msg) >= 2:
                        sub_id = msg[1]
                        if websocket in manager.subscriptions:
                            manager.subscriptions[websocket].pop(sub_id, None)
            except Exception as e:
                print(f'Relay Protocol Error: {e}')
    # === 异常处理区域更新 ===
    except WebSocketDisconnect:
        manager.disconnect(websocket)

    except OSError as e:
        # 专门捕获 Windows [WinError 121] 信号灯超时 以及其他网络IO错误
        # 这些通常是客户端非正常断开导致的，不需要打印堆栈，视为断开即可
        # print(f"⚠️ [Network] Client connection dropped: {e}")
        manager.disconnect(websocket)

    except RuntimeError as e:
        # 捕获 Uvicorn/Starlette 的状态错误 (如 WebSocket is not connected)
        manager.disconnect(websocket)

    except Exception as e:
        # 只有真正的未知代码错误才打印堆栈
        print(f"❌ [System] Unexpected error in websocket_endpoint: {e}")
        import traceback
        traceback.print_exc()
        manager.disconnect(websocket)
        
if __name__ == '__main__':
    import uvicorn
    banner = '\n /$$$$$$$                                 /$$$$$$  /$$                   /$$     /$$$$$$$            /$$\n| $$__  $$                               /$$__  $$| $$                  | $$    | $$__  $$          | $$\n| $$  \\ $$  /$$$$$$   /$$$$$$   /$$$$$$ | $$  \\__/| $$$$$$$   /$$$$$$  /$$$$$$  | $$  \\ $$  /$$$$$$ | $$  /$$$$$$  /$$   /$$\n| $$  | $$ |____  $$ /$$__  $$ /$$__  $$| $$      | $$__  $$ |____  $$|_  $$_/  | $$$$$$$/ /$$__  $$| $$ |____  $$| $$  | $$\n| $$  | $$  /$$$$$$$| $$  \\ $$| $$$$$$$$| $$      | $$  \\ $$  /$$$$$$$  | $$    | $$__  $$| $$$$$$$$| $$  /$$$$$$$| $$  | $$\n| $$  | $$ /$$__  $$| $$  | $$| $$_____/| $$    $$| $$  | $$ /$$__  $$  | $$ /$$| $$  \\ $$| $$_____/| $$ /$$__  $$| $$  | $$\n| $$$$$$$/|  $$$$$$$|  $$$$$$$|  $$$$$$$|  $$$$$$/| $$  | $$|  $$$$$$$  |  $$$$/| $$  | $$|  $$$$$$$| $$|  $$$$$$$|  $$$$$$$\n|_______/  \\_______/ \\____  $$ \\_______/ \\______/ |__/  |__/ \\_______/   \\___/  |__/  |__/ \\_______/|__/ \\_______/ \\____  $$\n                     /$$  \\ $$                                                                                     /$$  | $$\n                    |  $$$$$$/                                                                                    |  $$$$$$/\n                     \\______/                                                                                      \\______/\n    '
    print(banner)
    print('-' * 120)
    print(f'Author:  @BTCDage')
    print(f'Nostr:   npub17ahz4xa3hvkvvhh4wguzzqknp8p7l5nyzzqc3z53uq538r5qgn0q40z7pw')
    print('-' * 120)
    mode_name = 'SQLite' if 'sqlite' in CONF else 'Redis'
    print(f"🚀 {CONF['server']['name']} ({mode_name} Mode) starting on port {CONF['server']['port']}...")
    if mode_name == 'SQLite':
        print(f'📂 Database: {DB_FILE} (WAL Enabled)')
    print('-' * 120)
    uvicorn.run(app, host=CONF['server']['host'], port=CONF['server']['port'])
