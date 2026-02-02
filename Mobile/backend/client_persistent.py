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
import time
import threading
import asyncio
import aiohttp
import sys
import os
import ssl
import certifi
import nacl.utils
import nacl.pwhash
import nacl.secret
from hashlib import sha256
from db import DageDB
from key_utils import get_npub_abbr
from nostr_crypto import NostrCrypto
from lang_utils import tr
import urllib.request
import urllib.parse
import base64
from nacl.secret import SecretBox
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
OFFICIAL_GROUP_CONFIG = {'id': 'feb75fb664b41f95', 'key': '0f01f4613e3f194bdcf5a0863e46bde7297df2304865ec2df9e48ade53ae6dbc', 'name': 'DageChat 测试频道', 'owner': 'f76e2a9bb1bb2cc65ef572382102d309c3efd2641081888a91e029138e8044de'}
OFFICIAL_GROUP_POW_DIFFICULTY = 16
NORMAL_GROUP_POW_DIFFICULTY = 8
DEFAULT_RELAYS = ['wss://relay.damus.io', 'wss://relay.primal.net', 'wss://relay.snort.social']

class AsyncRelayWorker:

    def __init__(self, url, manager):
        self.url = url
        self.manager = manager
        self.ws = None
        self.status = 0
        self.latency = -1
        self.should_exit = False
        self.reconnect_delay = 5
        self.ping_start = 0
        self._logged_auto_proxy = False
        self._logged_disabled_hint = False

    async def connect_loop(self, session):
        print(f'🔧 [Worker] Starting loop for: {self.url}')
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        while not self.should_exit:
            proxy_url = None
            target_hostname = ''
            try:
                parsed = urllib.parse.urlparse(self.url)
                target_hostname = parsed.hostname or ''
            except:
                pass
            try:
                if self.manager and self.manager.user_obj:
                    if hasattr(self.manager.user_obj, 'network_config'):
                        cfg = self.manager.user_obj.network_config
                        val = cfg.get('proxy_disabled', False)
                        is_disabled = str(val) == '1' or val is True
                        if is_disabled:
                            proxy_url = None
                        else:
                            bypass_list = cfg.get('proxy_bypass', [])
                            if isinstance(bypass_list, str):
                                bypass_list = [x.strip() for x in bypass_list.replace(';', ',').split(',') if x.strip()]
                            is_bypass = False
                            if bypass_list and target_hostname:
                                for rule in bypass_list:
                                    rule = rule.strip()
                                    if not rule:
                                        continue
                                    if '://' in rule:
                                        rule_host = rule.split('://')[1].split('/')[0]
                                    else:
                                        rule_host = rule.split(':')[0]
                                    if target_hostname == rule_host or target_hostname.endswith(rule_host):
                                        is_bypass = True
                                        break
                            if is_bypass:
                                proxy_url = None
                            else:
                                proxy_url = cfg.get('proxy_url', '')
            except:
                pass
            self._update_status(1)
            try:
                is_secure = self.url.startswith('wss://')
                final_ssl = ssl_ctx if is_secure else None
                async with session.ws_connect(self.url, heartbeat=30, proxy=proxy_url, ssl=final_ssl) as ws:
                    self.ws = ws
                    self._update_status(2)
                    print(tr('LOG_CONNECTED').format(url=self.url))
                    self.manager._on_relay_connected(self)
                    self.ping_start = time.time()
                    await self.send_str(json.dumps(['REQ', 'PING_TEST', {'limit': 0}]))
                    async for msg in ws:
                        if self.should_exit:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
            except Exception as e:
                pass
            finally:
                self.ws = None
                self._update_status(0)
            if not self.should_exit:
                await asyncio.sleep(self.reconnect_delay)

    async def trigger_manual_ping(self):
        if self.status != 2:
            return False
        self.ping_start = time.time()
        sub_id = f'MANUAL_PING_{int(self.ping_start)}'
        return await self.send_str(json.dumps(['REQ', sub_id, {'limit': 0}]))

    async def _handle_message(self, data):
        if self.ping_start > 0:
            rtt = (time.time() - self.ping_start) * 1000
            self.latency = int(rtt)
            self.ping_start = 0
            self.manager._notify_status_change()
        if self.manager.on_message_callback:
            try:
                self.manager.on_message_callback(self, data)
            except Exception as e:
                print(f'❌ 消息回调异常: {e}')

    async def send_str(self, data):
        if self.ws and (not self.ws.closed):
            try:
                await self.ws.send_str(data)
                return True
            except:
                return False
        return False

    def _update_status(self, new_status):
        if self.status != new_status:
            self.status = new_status
            self.manager._notify_status_change()

    def is_connected(self):
        return self.status == 2

    def stop(self):
        self.should_exit = True
        self._update_status(0)
        if self.ws and self.manager.loop and self.manager.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.manager.loop)

class AsyncRelayManager:

    def __init__(self, on_message_callback, user_obj):
        self.on_message_callback = on_message_callback
        self.user_obj = user_obj
        self.workers = {}
        self.loop = None
        self.thread = None
        self.workers_lock = threading.Lock()
        self._pending_urls = set()

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        def _thread_entry():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._main_task())
        self.thread = threading.Thread(target=_thread_entry, daemon=True)
        self.thread.start()

    async def _main_task(self):
        while True:
            if self._pending_urls:
                urls_to_add = list(self._pending_urls)
                self._pending_urls.clear()
                for url in urls_to_add:
                    if url not in self.workers:
                        await self._add_relay_coro(url)
            await asyncio.sleep(1)

    def add_relay_dynamic(self, url):
        clean_url = url.strip()
        if not clean_url:
            return
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._add_relay_coro(clean_url), self.loop)
        else:
            self._pending_urls.add(clean_url)

    async def _add_relay_coro(self, url):
        if url in self.workers:
            return
        worker = AsyncRelayWorker(url, self)
        self.workers[url] = worker

        async def _independent_worker_run():
            async with aiohttp.ClientSession(trust_env=False) as session:
                await worker.connect_loop(session)
        asyncio.create_task(_independent_worker_run())

    def broadcast_send(self, message):
        if not self.loop:
            return 0
        asyncio.run_coroutine_threadsafe(self._broadcast_coro(message), self.loop)
        return True

    async def _broadcast_coro(self, message):
        for w in list(self.workers.values()):
            if w.status == 2:
                await w.send_str(message)

    def _on_relay_connected(self, worker):
        self.user_obj._do_subscriptions_for_worker(worker)

    def _notify_status_change(self):
        if self.user_obj.on_relay_status_callback:
            self.user_obj.on_relay_status_callback(self.get_status_snapshot())

    def get_status_snapshot(self):
        details = []
        connected_count = 0
        for url, w in list(self.workers.items()):
            if w.status == 2:
                connected_count += 1
            details.append({'url': url, 'status': w.status})
        return {'total': len(details), 'connected': connected_count, 'details': details}

    def stop_all(self):
        for w in self.workers.values():
            w.stop()

    def trigger_ping(self, url):
        clean_url = url.strip()
        if clean_url in self.workers:
            worker = self.workers[clean_url]
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(worker.trigger_manual_ping(), self.loop)
                return True
        return False

class PersistentChatUser:

    def __init__(self, db_filename, nickname=None):
        self.db = DageDB(db_filename)
        self.lock = threading.Lock()
        self.is_running = True
        import os
        db_folder = os.path.dirname(os.path.abspath(db_filename))
        app_data_root = os.path.dirname(db_folder)
        if not os.path.exists(app_data_root):
            try:
                os.makedirs(app_data_root)
            except:
                app_data_root = db_folder
        self.config_file = os.path.join(app_data_root, 'global_relays.json')
        self.network_config = {'relays': [], 'proxy_url': '', 'proxy_disabled': False, 'proxy_bypass': []}
        file_exists = os.path.exists(self.config_file)
        loaded_success = False
        if file_exists:
            loaded_success = self._load_config_from_disk()
        if not file_exists:
            print('⚠️ [Config] New install detected. Loading DEFAULT relays.')
            self.network_config['relays'] = list(DEFAULT_RELAYS)
            self._save_config_to_disk()
        elif loaded_success:
            print(f"✅ [Config] Loaded {len(self.network_config['relays'])} relays.")
        else:
            print('⚠️ [Config] Load failed or empty, keeping current state.')
        self.relay_manager = AsyncRelayManager(self.on_message, self)
        self.groups = {}
        from collections import deque
        self.my_ghost_nonces = deque(maxlen=50)
        self.processed_events = set()
        self.last_sync_time = 0
        self.pk = None
        self.priv_k = None
        self.on_relay_status_callback = None

    def _load_config_from_disk(self):
        import os
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if isinstance(data, dict):
                            self.network_config.update(data)
                            return True
        except Exception as e:
            print(f'❌ [Config] Load error: {e}')
        return False

    def disconnect(self):
        print('🔌 [System] Stopping network layer...')
        self.is_running = False
        if self.relay_manager:
            self.relay_manager.stop_all()

    def _save_config_to_disk(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.network_config, f, indent=4)
            return True
        except:
            return False

    def connect(self):
        print(f'🚀 [System] Starting Network Layer...')
        self.relay_manager.start()
        relays = self.network_config.get('relays', [])
        for url in relays:
            self.relay_manager.add_relay_dynamic(url)

    def add_relay_persistent(self, url):
        clean_url = url.strip()
        if not clean_url:
            return False
        self.relay_manager.add_relay_dynamic(clean_url)
        current_list = self.network_config['relays']
        if clean_url not in current_list:
            current_list.append(clean_url)
            self.network_config['relays'] = current_list
            self._save_config_to_disk()
            return True
        return True

    def remove_relay_persistent(self, url):
        with self.lock:
            if url in self.relay_manager.workers:
                worker = self.relay_manager.workers[url]
                worker.stop()
                del self.relay_manager.workers[url]
        current_list = self.network_config['relays']
        if url in current_list:
            current_list.remove(url)
            self.network_config['relays'] = current_list
            self._save_config_to_disk()
            return True
        return False

    def save_proxy_settings(self, proxy_url, is_disabled, bypass_str=None):
        self.network_config['proxy_url'] = proxy_url.strip()
        self.network_config['proxy_disabled'] = bool(is_disabled)
        if bypass_str is not None:
            bypass_list = [x.strip() for x in bypass_str.replace(';', ',').split(',') if x.strip()]
            self.network_config['proxy_bypass'] = bypass_list
        return self._save_config_to_disk()

    def add_bypass_rule(self, rule):
        clean_rule = rule.strip()
        if not clean_rule:
            return False
        current_list = self.network_config.get('proxy_bypass', [])
        if clean_rule not in current_list:
            current_list.append(clean_rule)
            self.network_config['proxy_bypass'] = current_list
            self._save_config_to_disk()
            return True
        return True

    def remove_bypass_rule(self, rule):
        current_list = self.network_config.get('proxy_bypass', [])
        if rule in current_list:
            current_list.remove(rule)
            self.network_config['proxy_bypass'] = current_list
            self._save_config_to_disk()
            return True
        return False

    def reconnect_all_relays(self):
        print('🔄 [Net] Reconnecting sequence started...')
        with self.lock:
            current_urls = list(self.relay_manager.workers.keys())
            for url in current_urls:
                self.relay_manager.workers[url].stop()
                del self.relay_manager.workers[url]
        time.sleep(0.5)
        self._load_config_from_disk()
        new_relays = self.network_config.get('relays', [])
        proxy_url = self.network_config.get('proxy_url', 'None')
        print(f'🔄 [Net] Restarting with {len(new_relays)} relays. Proxy: {proxy_url}')
        for url in new_relays:
            self.relay_manager.add_relay_dynamic(url)
        if self.on_relay_status_callback:
            self.on_relay_status_callback(self.get_connection_status())

    def reset_network_settings(self):
        with self.lock:
            current_urls = list(self.relay_manager.workers.keys())
            for url in current_urls:
                self.relay_manager.workers[url].stop()
                del self.relay_manager.workers[url]
        self.network_config = {'relays': list(DEFAULT_RELAYS), 'proxy_url': '', 'proxy_disabled': False, 'proxy_bypass': []}
        self._save_config_to_disk()
        for url in DEFAULT_RELAYS:
            self.relay_manager.add_relay_dynamic(url)
        return True

    def get_connection_status(self):
        mgr_snapshot = self.relay_manager.get_status_snapshot()
        active_status_map = {item['url']: item['status'] for item in mgr_snapshot.get('details', [])}
        config_urls = self.network_config.get('relays', [])
        all_urls = set(config_urls) | set(active_status_map.keys())
        final_details = []
        connected_count = 0
        for url in all_urls:
            status = active_status_map.get(url, 0)
            if status == 2:
                connected_count += 1
            final_details.append({'url': url, 'status': status})
        final_details.sort(key=lambda x: x['url'])
        return {'total': len(final_details), 'connected': connected_count, 'details': final_details}

    def _do_subscriptions_for_worker(self, worker):
        if not worker.is_connected():
            return
        safe_now = int(time.time()) - 24 * 3600
        if self.last_sync_time > 0:
            safe_now = max(safe_now, int(self.last_sync_time))
        sub_id = 'dage-sync-v1'
        req_payload = ['REQ', sub_id]
        filter_real_me = {'kinds': [4, 1059], '#p': [self.pk], 'since': safe_now}
        req_payload.append(filter_real_me)
        ghost_gids = [gid for gid, g in self.groups.items() if str(g.get('type')) == '1']
        if ghost_gids:
            filter_ghosts = {'kinds': [1059], '#p': ghost_gids, 'since': safe_now}
            req_payload.append(filter_ghosts)
        official_gid = OFFICIAL_GROUP_CONFIG['id']
        standard_gids = [gid for gid, g in self.groups.items() if str(g.get('type')) == '0' and gid != official_gid]
        if standard_gids:
            filter_groups = {'kinds': [42, 30078], '#g': standard_gids, 'since': safe_now}
            req_payload.append(filter_groups)
        if official_gid in self.groups:
            filter_official = {'kinds': [42, 30078], '#g': [official_gid], 'limit': 20}
            req_payload.append(filter_official)
        asyncio.run_coroutine_threadsafe(worker.send_str(json.dumps(req_payload)), self.relay_manager.loop)
        last_db_ts = self.db.get_last_broadcast_time()
        now = int(time.time())
        if now - last_db_ts > 86400:
            self._announce_presence(target_worker=worker)
            self.sync_backup_to_cloud(target_worker=worker)
            self.db.update_last_broadcast_time(now)

    def _ensure_official_group(self):
        gid = OFFICIAL_GROUP_CONFIG['id']
        if gid in self.groups:
            return
        has_exited = self.db.get_setting('exited_official_lobby')
        if has_exited == '1':
            return
        print(f'🏛️ [System] 正在连接测试频道: {gid}...')
        self.db.save_group(gid, OFFICIAL_GROUP_CONFIG['name'], OFFICIAL_GROUP_CONFIG['key'], owner_pubkey=OFFICIAL_GROUP_CONFIG['owner'], group_type=0)
        self.groups[gid] = {'name': OFFICIAL_GROUP_CONFIG['name'], 'key_hex': OFFICIAL_GROUP_CONFIG['key'], 'type': 0}

    def on_message(self, worker, message_str):
        if not self.is_running:
            return
        try:
            if 'PING' not in message_str:
                log_str = message_str if len(message_str) < 150 else message_str[:150] + '...'
                print(f'🔥 [Net] RAW: {log_str}')
            data = json.loads(message_str)
            if not isinstance(data, list) or len(data) < 2:
                return
            msg_type = data[0]
            if msg_type == 'EVENT':
                event = data[2]
                eid = event['id']
                kind = event['kind']
                if eid in self.processed_events:
                    return
                self.processed_events.add(eid)
                if len(self.processed_events) > 2000:
                    self.processed_events.pop()
                if self.db.event_exists(eid):
                    return
                if kind == 1059:
                    p_tags = [t[1] for t in event.get('tags', []) if t[0] == 'p']
                    if not p_tags:
                        return
                    recipient = p_tags[0]
                    rumor_dict = None
                    if recipient == self.pk:
                        _, rumor_dict = NostrCrypto.unwrap_gift(self.priv_k, event)
                    elif recipient in self.groups:
                        grp = self.groups[recipient]
                        if str(grp.get('type')) == '1':
                            _, g_rumor = NostrCrypto.unwrap_gift(grp['key_hex'], event)
                            if g_rumor:
                                rumor_dict = g_rumor
                                rumor_dict['_is_ghost'] = True
                                rumor_dict['_actual_gid'] = recipient
                                print(f'✅ [Debug] 分享密钥群 [{recipient[:6]}] 解包成功!')
                    if rumor_dict:
                        if self.db.event_exists(rumor_dict['id']):
                            return
                        self._handle_dm(rumor_dict)
                    return
                if kind == 0:
                    self._handle_metadata(event)
                    if event['pubkey'] in self.groups:
                        self._handle_group_beacon(event)
                elif kind == 4:
                    self._handle_dm(event)
                elif kind == 14:
                    self._handle_dm(event)
                elif kind == 42:
                    self._handle_group_msg(event)
                elif kind == 30078:
                    self._handle_group_beacon(event)
                elif kind == 3:
                    self._handle_backup_restore(event)
                elif kind == 5:
                    self._handle_deletion(event)
                elif kind == 3000:
                    self._handle_group_member_list(event)
            elif msg_type == 'EOSE':
                print(f'✅ [Relay] 历史同步完成 ({data[1]})')
        except Exception as e:
            if 'closed database' in str(e):
                return
            print(f'❌ [Fatal] on_message 崩溃: {e}')

    def _handle_group_beacon(self, event):
        content_dict = {}
        try:
            content_dict = json.loads(event['content'])
        except:
            return
        new_name = content_dict.get('name')
        if not new_name:
            return
        gid = None
        kind = event['kind']
        if kind == 0:
            if event['pubkey'] in self.groups:
                gid = event['pubkey']
        elif kind == 30078:
            gid = next((t[1] for t in event.get('tags', []) if t[0] == 'g'), None)
        if not gid or gid not in self.groups:
            return
        if self.groups[gid].get('type', 0) == 0:
            owner = self.db.get_group_owner(gid)
            if owner and event['pubkey'] != owner:
                return
        if new_name != self.groups[gid]['name']:
            self.db.update_group_name_local(gid, new_name)
            self.groups[gid]['name'] = new_name
            print(f'♻️ [System] 群 [{gid[:6]}] 名称更新为: {new_name}')

    def _parse_reply_tag(self, tags):
        e_tags = [t for t in tags if t[0] == 'e']
        if not e_tags:
            return None
        for t in e_tags:
            if len(t) >= 4 and t[3] == 'reply':
                return t[1]
        return e_tags[-1][1]

    def _handle_metadata(self, event):
        try:
            content = json.loads(event['content'])
            self.db.save_contact(event['pubkey'], content.get('name'), enc_key=event['pubkey'], extra_info=content)
            if event['pubkey'] == self.pk:
                self.db.update_my_profile(content)
        except:
            pass

    def _handle_dm(self, event):
        sender_pk = event['pubkey']
        kind = event['kind']
        payload = None
        is_ghost = event.get('_is_ghost', False)
        print(f'📥 [Debug] 处理 DM 消息 Kind={kind} 来自 {sender_pk[:6]}...')
        if kind == 14:
            try:
                content_str = event['content']
                if content_str.strip().startswith('{'):
                    payload = json.loads(content_str)
                else:
                    payload = {'text': content_str}
            except:
                return
        elif kind == 4:
            decrypted_content = None
            try:
                target_pk = next((t[1] for t in event['tags'] if t[0] == 'p'), None)
                if target_pk == self.pk:
                    decrypted_content = NostrCrypto.decrypt_nip44(self.priv_k, sender_pk, event['content'])
                elif sender_pk == self.pk and target_pk:
                    decrypted_content = NostrCrypto.decrypt_nip44(self.priv_k, target_pk, event['content'])
            except:
                pass
            if decrypted_content:
                try:
                    payload = json.loads(decrypted_content)
                except:
                    payload = {'text': decrypted_content}
            else:
                return
        if not payload:
            return
        print(f'✅ [Debug] 消息解析成功: {str(payload)[:50]}...')
        if is_ghost or (sender_pk in self.groups and str(self.groups[sender_pk].get('type')) == '1'):
            self._process_ghost_payload(event, payload, sender_pk, sender_pk)
            return
        if payload.get('type') == 'invite':
            self._handle_invite_logic(payload)
            return
        text = payload.get('text', '')
        img = payload.get('image')
        content = json.dumps({'text': text, 'image': img}) if img else text
        nk = payload.get('name')
        self.db.save_contact(sender_pk, nk, enc_key=sender_pk)
        reply_id = self._parse_reply_tag(event.get('tags', []))
        group_id = sender_pk
        if sender_pk == self.pk:
            p_tag = next((t[1] for t in event.get('tags', []) if t[0] == 'p'), None)
            if p_tag:
                group_id = p_tag
        self.db.save_message(event['id'], group_id, sender_pk, content, event['created_at'], False, reply_to_id=reply_id)
        display_name = self._format_sender_info(sender_pk)
        self._print_to_ui('dm', {'sender_pk': group_id, 'text': content, 'id': event['id'], 'time': event['created_at'], 'real_sender': sender_pk, 'nickname': display_name, 'reply_to_id': reply_id})

    def _handle_invite_logic(self, payload):
        try:
            gid = payload.get('group_id')
            name = payload.get('name', '未知群组')
            key = payload.get('key')
            owner = payload.get('owner')
            gtype = payload.get('gtype', 0)
            if not gid or not key:
                return
            if self.db.is_group_blocked(gid):
                return
            if gid in self.groups:
                if self.groups[gid]['key_hex'] == key:
                    return
            print(f'📩 [System] 接受群组邀请: {name} ({gid[:8]}...)')
            self.db.save_group(gid, name, key, owner_pubkey=owner, group_type=gtype)
            self.groups[gid] = {'name': name, 'key_hex': key, 'type': gtype}
            req_msg = json.dumps(['REQ', gid])
            self.relay_manager.broadcast_send(req_msg)
            self._print_to_ui('system', f'已通过邀请加入群聊: {name}')
            self._print_to_ui('refresh', None)
        except:
            pass

    def _process_ghost_payload(self, event, payload, sender_pk, origin_event_pubkey):
        try:
            group_id = event.get('_actual_gid', sender_pk)
            text = payload.get('text', '')
            img = payload.get('image')
            alias = payload.get('alias', 'Anon')
            nonce = payload.get('nonce')
            content_to_save = json.dumps({'text': text, 'image': img, 'alias': alias})
            reply_id = self._parse_reply_tag(event.get('tags', []))
            is_me = False
            if nonce and nonce in self.my_ghost_nonces:
                is_me = True
            print(f'👻 [Debug] 分享密钥群消息入库: GID={group_id[:6]} Msg={text[:10]}... Me={is_me}')
            self.db.save_message(event['id'], group_id, sender_pk, content_to_save, event['created_at'], is_me, reply_to_id=reply_id)
            self._print_to_ui('group', {'id': event['id'], 'group_id': group_id, 'sender_pk': sender_pk, 'text': content_to_save, 'time': event['created_at'], 'nickname': alias, 'is_me': is_me, 'reply_to_id': reply_id, 'is_ghost': True})
        except:
            pass

    def _handle_group_msg(self, event):
        gid = None
        for t in event.get('tags', []):
            if len(t) >= 2 and t[0] == 'g':
                gid = t[1]
                break
        if not gid or gid not in self.groups:
            return
        try:
            grp_info = self.groups[gid]
            g_type = grp_info.get('type', 0)
            is_ghost = str(g_type) == '1'
            key_hex = grp_info['key_hex']
            decrypted_json = NostrCrypto.decrypt_group_msg(key_hex, event['content'])
            if not decrypted_json:
                return
            payload = json.loads(decrypted_json)
            msg_type = payload.get('type')
            if not is_ghost and msg_type in ['ban', 'unban']:
                owner = self.db.get_group_owner(gid)
                if event['pubkey'] == owner:
                    tpk = payload.get('pubkey')
                    if msg_type == 'ban':
                        self.db.add_group_ban(gid, tpk, payload.get('text'))
                        sys_msg = f'🛡️ Banned: {tpk[:6]}'
                        self.db.save_message(event['id'], gid, owner, sys_msg, event['created_at'], False)
                        self._print_to_ui('system_center', {'group_id': gid, 'text': sys_msg})
                    else:
                        self.db.remove_group_ban(gid, tpk)
                        sys_msg = f'📢 Unbanned: {tpk[:6]}'
                        self.db.save_message(event['id'], gid, owner, sys_msg, event['created_at'], False)
                        self._print_to_ui('system_center', {'group_id': gid, 'text': sys_msg})
                return
            if self.db.is_banned_in_group(gid, event['pubkey']):
                return
            if self.db.is_group_blocked(gid):
                return
            text = payload.get('text', '')
            img = payload.get('image')
            content = json.dumps({'text': text, 'image': img}) if img else text
            nk = payload.get('name')
            if nk:
                self.db.save_contact(event['pubkey'], nk, enc_key=event['pubkey'])
            reply_id = self._parse_reply_tag(event.get('tags', []))
            is_me = event['pubkey'] == self.pk
            self.db.save_message(event['id'], gid, event['pubkey'], content, event['created_at'], is_me, reply_to_id=reply_id)
            dn = self._format_sender_info(event['pubkey'])
            self._print_to_ui('group', {'id': event['id'], 'group_id': gid, 'sender_pk': event['pubkey'], 'text': content, 'time': event['created_at'], 'nickname': dn, 'is_me': is_me, 'reply_to_id': reply_id})
        except:
            pass

    def _handle_deletion(self, event):
        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
        for tid in target_ids:
            msg = self.db.get_message(tid)
            if msg and msg[2] == event['pubkey']:
                txt = tr('MSG_RECALLED')
                self.db.update_message_content(tid, txt)
                self._print_to_ui('delete', {'ids': target_ids})

    def _handle_backup_restore(self, event):
        try:
            if event['pubkey'] != self.pk:
                return
            json_str = NostrCrypto.decrypt_nip44(self.priv_k, self.pk, event['content'])
            if not json_str:
                return
            data = json.loads(json_str)
            for g in data.get('groups', []):
                self.db.save_group(g['id'], g['name'], g['key'], group_type=g.get('type', 0))
                if g['id'] not in self.groups:
                    self.groups[g['id']] = {'name': g['name'], 'key_hex': g['key'], 'type': g.get('type', 0)}
                    self.relay_manager.broadcast_send(json.dumps(['REQ', g['id']]))
            for c in data.get('contacts', []):
                self.db.save_contact(c['pubkey'], c['name'], c.get('enc_key'))
            self._load_groups_from_db()
        except:
            pass

    def _handle_group_member_list(self, event):
        gid = next((t[1] for t in event['tags'] if t[0] == 'd'), None)
        if not gid:
            return
        owner = self.db.get_group_owner(gid)
        if not owner or event['pubkey'] != owner:
            return
        pks = [t[1] for t in event['tags'] if t[0] == 'p']
        if pks:
            self.db.add_group_members_batch(gid, pks)

    def _print_to_ui(self, msg_type, data):
        if hasattr(self, 'ui_callback') and self.ui_callback:
            self.ui_callback(msg_type, data)

    def _send_event(self, kind, content, tags=[], priv_key_hex=None, pre_mined_event=None):
        if pre_mined_event:
            evt = pre_mined_event
            event_id = evt['id']
        else:
            signer_priv = priv_key_hex if priv_key_hex else self.priv_k
            signer_pub = NostrCrypto.get_public_key_hex(signer_priv)
            evt = {'pubkey': signer_pub, 'created_at': int(time.time()), 'kind': kind, 'tags': tags, 'content': content}
            evt_str = json.dumps([0, evt['pubkey'], evt['created_at'], evt['kind'], evt['tags'], evt['content']], separators=(',', ':'), ensure_ascii=False)
            event_id = sha256(evt_str.encode('utf-8')).hexdigest()
            evt['id'] = event_id
            evt['sig'] = NostrCrypto.sign_event_id(signer_priv, event_id)
        self.relay_manager.broadcast_send(json.dumps(['EVENT', evt]))
        return event_id

    def _send_event_to_worker(self, worker, kind, content, tags=[]):
        signer_priv = self.priv_k
        signer_pub = self.pk
        evt = {'pubkey': signer_pub, 'created_at': int(time.time()), 'kind': kind, 'tags': tags, 'content': content}
        evt_str = json.dumps([0, evt['pubkey'], evt['created_at'], evt['kind'], evt['tags'], evt['content']], separators=(',', ':'), ensure_ascii=False)
        evt['id'] = sha256(evt_str.encode('utf-8')).hexdigest()
        evt['sig'] = NostrCrypto.sign_event_id(signer_priv, evt['id'])
        msg_str = json.dumps(['EVENT', evt])
        if hasattr(worker, 'send_str'):
            asyncio.run_coroutine_threadsafe(worker.send_str(msg_str), self.relay_manager.loop)

    def unlock_account(self, password):
        row = self.db.load_account()
        if not row:
            return (False, '账号不存在')
        try:
            self.pk = row[0]
            crypto_data = json.loads(row[1])
            salt = bytes.fromhex(crypto_data['salt'])
            nonce = bytes.fromhex(crypto_data['nonce'])
            ciphertext = bytes.fromhex(crypto_data['ciphertext'])
            secret_key = nacl.pwhash.argon2i.kdf(nacl.secret.SecretBox.KEY_SIZE, password.encode('utf-8'), salt, opslimit=nacl.pwhash.argon2i.OPSLIMIT_INTERACTIVE, memlimit=nacl.pwhash.argon2i.MEMLIMIT_INTERACTIVE)
            box = nacl.secret.SecretBox(secret_key)
            self.priv_k = box.decrypt(ciphertext, nonce).decode('utf-8')
            self._ensure_official_group()
            self.enc_pk = self.pk
            self._load_groups_from_db()
            return (True, 'Success')
        except Exception as e:
            return (False, f'解锁失败: {e}')

    def create_new_account(self, nickname, password):
        try:
            priv_hex = NostrCrypto.generate_private_key_hex()
            pub_hex = NostrCrypto.get_public_key_hex(priv_hex)
            self._encrypt_and_save(pub_hex, priv_hex, password)
            self.db.save_contact(pub_hex, nickname, enc_key=pub_hex, is_friend=1)
            self.db.update_my_profile({'name': nickname})
            self.unlock_account(password)
            return (True, 'Success')
        except Exception as e:
            return (False, str(e))

    def import_account(self, priv_hex, nickname, password):
        try:
            pub_hex = NostrCrypto.get_public_key_hex(priv_hex)
            if not pub_hex:
                return (False, '无效私钥')
            self._encrypt_and_save(pub_hex, priv_hex, password)
            if not self.db.get_contact_name(pub_hex):
                self.db.save_contact(pub_hex, nickname, enc_key=pub_hex, is_friend=1)
            self.unlock_account(password)
            return (True, 'Success')
        except Exception as e:
            return (False, f'导入失败: {e}')

    def _encrypt_and_save(self, pubkey, priv_hex, password):
        salt = nacl.utils.random(nacl.pwhash.argon2i.SALTBYTES)
        secret_key = nacl.pwhash.argon2i.kdf(nacl.secret.SecretBox.KEY_SIZE, password.encode('utf-8'), salt, opslimit=nacl.pwhash.argon2i.OPSLIMIT_INTERACTIVE, memlimit=nacl.pwhash.argon2i.MEMLIMIT_INTERACTIVE)
        box = nacl.secret.SecretBox(secret_key)
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        ciphertext = box.encrypt(priv_hex.encode('utf-8'), nonce).ciphertext
        blob = {'salt': salt.hex(), 'nonce': nonce.hex(), 'ciphertext': ciphertext.hex()}
        self.db.save_account(pubkey, json.dumps(blob))

    def verify_password(self, password_input):
        row = self.db.load_account()
        if not row:
            return False
        try:
            crypto_data = json.loads(row[1])
            salt = bytes.fromhex(crypto_data['salt'])
            nonce = bytes.fromhex(crypto_data['nonce'])
            ciphertext = bytes.fromhex(crypto_data['ciphertext'])
            secret_key = nacl.pwhash.argon2i.kdf(nacl.secret.SecretBox.KEY_SIZE, password_input.encode('utf-8'), salt, opslimit=nacl.pwhash.argon2i.OPSLIMIT_INTERACTIVE, memlimit=nacl.pwhash.argon2i.MEMLIMIT_INTERACTIVE)
            nacl.secret.SecretBox(secret_key).decrypt(ciphertext, nonce)
            return True
        except:
            return False

    def _load_groups_from_db(self):
        rows = self.db.get_all_groups()
        count = 0
        for row in rows:
            if len(row) >= 3:
                gid, name, k_hex = (row[0], row[1], row[2])
                g_type = row[8] if len(row) > 8 else 0
                self.groups[gid] = {'name': name, 'key_hex': k_hex, 'type': g_type}
                count += 1
        print(f'📚 [System] 从数据库加载了 {count} 个群组')

    def get_safety_fingerprint(self, target_id, chat_type):
        try:
            if chat_type == 'group':
                grp = self.groups.get(target_id)
                if not grp:
                    return ('???', False)
                key_hex = grp.get('key_hex', '')
                fp = sha256(key_hex.encode()).hexdigest()[:6].upper()
                if grp.get('type') == 1:
                    return (f'👻 {fp}', False)
                return (f'🔑 {fp}', False)
            elif chat_type == 'dm':
                fp = sha256(target_id.encode()).hexdigest()[:6].upper()
                return (f'🔒 {fp}', False)
        except:
            return ('ERROR', False)
        return ('', False)

    def _format_sender_info(self, pubkey):
        if not pubkey:
            return '未知'
        if len(pubkey) < 12:
            return pubkey
        short_pk = get_npub_abbr(pubkey)
        if pubkey == self.pk:
            return f'我({short_pk})'
        name = self.db.get_contact_name(pubkey)
        return f'{name}({short_pk})' if name else f'用户({short_pk})'

    def send_dm(self, target_pk, text, target_enc_unused=None, reply_to_id=None, image_base64=None):
        payload = {'text': text}
        if image_base64:
            payload['image'] = image_base64
        payload['name'] = self.db.get_contact_name(self.pk) or 'Me'
        payload['k'] = self.pk
        payload_json = json.dumps(payload)
        tags = []
        if reply_to_id:
            tags.append(['e', reply_to_id, '', 'reply'])
        wrap_event, rumor_id = NostrCrypto.make_gift_wrap(self.priv_k, target_pk, payload_json, kind=14, extra_tags=tags)
        if not wrap_event:
            return
        self.relay_manager.broadcast_send(json.dumps(['EVENT', wrap_event]))
        ts = wrap_event['created_at']
        self.db.save_message(rumor_id, target_pk, self.pk, payload_json, ts, True, reply_to_id=reply_to_id)
        display_name = self._format_sender_info(target_pk)
        self._print_to_ui('dm', {'sender_pk': target_pk, 'text': payload_json, 'id': rumor_id, 'time': ts, 'real_sender': self.pk, 'nickname': 'Me', 'reply_to_id': reply_to_id, 'is_me': True})

    def send_ghost_msg(self, gid, text, image_base64=None, reply_to_id=None):
        print(f'👻 [Debug] 准备发送匿名消息 GID={gid[:6]}...')
        if gid not in self.groups:
            print(f'❌ [Debug] 发送失败: 本地找不到群组 {gid}')
            return None
        try:
            grp = self.groups[gid]
            grp_priv = grp['key_hex']
            grp_pub = NostrCrypto.get_public_key_hex(grp_priv)
            if not grp_pub:
                print('❌ [Debug] 发送失败: 公钥推导失败')
                return None
            nonce = nacl.utils.random(8).hex()
            self.my_ghost_nonces.append(nonce)
            alias = 'Anon'
            try:
                alias = self.db.get_contact_name(self.pk) or 'Anon'
            except:
                pass
            data = {'text': text, 'alias': alias, 'nonce': nonce, 'ts': int(time.time())}
            if image_base64:
                data['image'] = image_base64
            payload_json = json.dumps(data)
            tags = []
            if reply_to_id:
                tags.append(['e', reply_to_id, '', 'reply'])
            wrap_event, rumor_id = NostrCrypto.make_gift_wrap(grp_priv, grp_pub, payload_json, kind=14, extra_tags=tags)
            if not wrap_event:
                return None
            self.relay_manager.broadcast_send(json.dumps(['EVENT', wrap_event]))
            ts = wrap_event['created_at']
            self.db.save_message(rumor_id, gid, grp_pub, payload_json, ts, True, reply_to_id=reply_to_id)
            self._print_to_ui('group', {'id': rumor_id, 'group_id': gid, 'sender_pk': grp_pub, 'text': payload_json, 'time': ts, 'nickname': alias, 'is_me': True, 'reply_to_id': reply_to_id, 'is_ghost': True})
            return rumor_id
        except Exception as e:
            print(f'❌ [Debug] Ghost Send Error: {e}')
            return None

    def send_group_msg(self, gid, text, reply_to_id=None, image_base64=None, mention_pks=None):
        if gid not in self.groups:
            return
        data = {'text': text, 'name': self.db.get_contact_name(self.pk) or 'Me', 'k': self.pk}
        if image_base64:
            data['image'] = image_base64
        if mention_pks and isinstance(mention_pks, list):
            data['at'] = mention_pks
        key_hex = self.groups[gid]['key_hex']
        cipher = NostrCrypto.encrypt_group_msg(key_hex, json.dumps(data))
        if not cipher:
            return
        tags = [['g', gid]]
        if reply_to_id:
            tags.append(['e', reply_to_id, '', 'reply'])
        target_diff = OFFICIAL_GROUP_POW_DIFFICULTY if gid == OFFICIAL_GROUP_CONFIG['id'] else NORMAL_GROUP_POW_DIFFICULTY
        mined_evt = None
        if target_diff > 0:
            mined_evt = NostrCrypto.mine_pow_and_sign(self.priv_k, 42, cipher, tags, target_diff)
        eid = self._send_event(42, cipher, tags, pre_mined_event=mined_evt)
        ts = int(time.time())
        content = text
        if image_base64:
            content = json.dumps({'text': text, 'image': image_base64})
        self.db.save_message(eid, gid, self.pk, content, ts, True, reply_to_id=reply_to_id)
        self._print_to_ui('group', {'id': eid, 'group_id': gid, 'sender_pk': self.pk, 'text': content, 'time': ts, 'nickname': 'Me', 'is_me': True, 'reply_to_id': reply_to_id})

    def _announce_presence(self, target_worker=None):
        acc = self.db.load_account()
        if not acc:
            return
        profile = {'name': acc[2], 'picture': acc[3], 'about': acc[4], 'website': acc[5], 'lud16': acc[6], 'nip05': ''}
        content = json.dumps(profile)
        if target_worker:
            self._send_event_to_worker(target_worker, 0, content, tags=[])
        else:
            self._send_event(0, content, tags=[])

    def sync_backup_to_cloud(self, target_worker=None):
        now = time.time()
        if now - self.last_sync_time < 2.0 and (not target_worker):
            return
        if not target_worker:
            self.last_sync_time = now
        groups = [{'id': r[0], 'name': r[1], 'key': r[2], 'type': r[8] if len(r) > 8 else 0} for r in self.db.get_all_groups()]
        contacts = self.db.get_all_contacts()
        raw_payload = json.dumps({'groups': groups, 'contacts': contacts, 'ts': int(now)})
        cipher = NostrCrypto.encrypt_nip44(self.priv_k, self.pk, raw_payload)
        if not cipher:
            return
        tags = [['p', self.pk]]
        if target_worker:
            self._send_event_to_worker(target_worker, 3, cipher, tags=tags)
        else:
            self._send_event(3, cipher, tags=tags)

    def set_profile(self, profile):
        self.db.update_my_profile(profile)
        self.db.save_contact(self.pk, profile.get('name'), self.pk, is_friend=1, extra_info=profile)
        self._announce_presence()
        self.sync_backup_to_cloud()
        self.db.update_last_broadcast_time(int(time.time()))

    def set_nickname(self, name):
        self.set_profile({'name': name})

    def fetch_user_profile(self, pk):
        self.relay_manager.broadcast_send(json.dumps(['REQ', pk]))

    def create_group(self, name, is_ghost=False):
        if is_ghost:
            key_hex = NostrCrypto.generate_private_key_hex()
            g_type = 1
            gid = NostrCrypto.get_public_key_hex(key_hex)
        else:
            key_hex = NostrCrypto.generate_group_key()
            g_type = 0
            gid = sha256(f'{name}{self.pk}'.encode()).hexdigest()[:16]
        self.db.save_group(gid, name, key_hex, owner_pubkey=self.pk, created_at=int(time.time()), group_type=g_type)
        self.groups[gid] = {'name': name, 'key_hex': key_hex, 'type': g_type}
        self.relay_manager.broadcast_send(json.dumps(['REQ', gid]))
        threading.Thread(target=self.sync_backup_to_cloud, daemon=True).start()
        if not is_ghost:
            self._publish_group_beacon(gid)
        return gid

    def invite_user(self, gid, friend_pk):
        if gid not in self.groups:
            return
        grp = self.groups[gid]
        self.db.add_group_member(gid, friend_pk)
        try:
            name = grp['name']
            key = grp['key_hex']
            gtype = grp.get('type', 0)
            owner = self.db.get_group_owner(gid) or ''
            salt = 'DAGE_SECURE_V1'
            raw_sum = f'{gid}{key}{gtype}{salt}'
            checksum = sha256(raw_sum.encode()).hexdigest()[:6]
            safe_name = base64.urlsafe_b64encode(name.encode()).decode()
            raw_data = f'{gid}|{key}|{owner}|{safe_name}|{gtype}|{checksum}'
            final_link = ''
            if str(gtype) == '1':
                obfuscate_key = sha256('dagechat'.encode()).digest()
                box = SecretBox(obfuscate_key)
                encrypted = box.encrypt(raw_data.encode('utf-8'))
                b64_payload = base64.urlsafe_b64encode(encrypted).decode('utf-8')
                final_link = f'dage://invite/ghost/{b64_payload}'
            else:
                b64_payload = base64.urlsafe_b64encode(raw_data.encode('utf-8')).decode('utf-8')
                final_link = f'dage://invite/normal/{b64_payload}'
            invite_text = f'邀请加入群聊【{name}】\n点击链接加入:\n{final_link}'
            enc_key = self.db.get_contact_enc_key(friend_pk)
            if not enc_key:
                enc_key = friend_pk
            self.send_dm(friend_pk, invite_text, enc_key)
            print(f'📨 [Invite] Sent link to {friend_pk[:6]}')
        except Exception as e:
            print(f'❌ [Invite] Error generating link: {e}')
            import traceback
            traceback.print_exc()

    def _publish_group_members(self, gid):
        owner = self.db.get_group_owner(gid)
        if owner != self.pk:
            return
        members = self.db.get_group_members(gid)
        if self.pk not in members:
            members.append(self.pk)
        tags = [['d', gid]] + [['p', m] for m in members]
        self._send_event(3000, json.dumps({'name': 'members'}), tags)

    def _publish_group_beacon(self, gid, target_worker=None):
        if gid not in self.groups:
            return
        info = self.groups[gid]
        kh = sha256(info['key_hex'].encode()).hexdigest()
        meta_content = json.dumps({'name': info['name'], 'key_hash': kh, 'ver': int(time.time()), 'about': 'DageChat Group', 'picture': ''})
        g_type = info.get('type', 0)
        if g_type == 1:
            grp_priv = info['key_hex']
            grp_pub = gid
            evt = {'pubkey': grp_pub, 'created_at': int(time.time()), 'kind': 0, 'tags': [], 'content': meta_content}
            evt_str = json.dumps([0, evt['pubkey'], evt['created_at'], evt['kind'], evt['tags'], evt['content']], separators=(',', ':'), ensure_ascii=False)
            evt['id'] = sha256(evt_str.encode('utf-8')).hexdigest()
            evt['sig'] = NostrCrypto.sign_event_id(grp_priv, evt['id'])
            msg = json.dumps(['EVENT', evt])
            if target_worker:
                self._send_raw_msg(target_worker, msg)
            else:
                self.relay_manager.broadcast_send(msg)
        else:
            tags = [['d', f'group-meta-{gid}'], ['g', gid]]
            if target_worker:
                self._send_event_to_worker(target_worker, 30078, meta_content, tags=tags)
            else:
                self._send_event(30078, meta_content, tags=tags)

    def _send_raw_msg(self, worker, msg_str):
        try:
            asyncio.run_coroutine_threadsafe(worker.send_str(msg_str), self.relay_manager.loop)
        except:
            pass

    def mark_session_read(self, tid, is_grp):
        self.db.mark_read(tid, is_grp)

    def ban_group_member(self, gid, tpk):
        if gid not in self.groups:
            return
        owner = self.db.get_group_owner(gid)
        if owner != self.pk:
            return
        self.db.add_group_ban(gid, tpk, 'Owner')
        nm = self.db.get_contact_name(tpk) or ''
        pl = json.dumps({'type': 'ban', 'pubkey': tpk, 'target_name': nm, 'text': 'Banned'})
        key_hex = self.groups[gid]['key_hex']
        cipher = NostrCrypto.encrypt_group_msg(key_hex, pl)
        self._send_event(42, cipher, [['g', gid]])

    def unban_group_member(self, gid, tpk):
        if gid not in self.groups:
            return
        owner = self.db.get_group_owner(gid)
        if owner != self.pk:
            return
        self.db.remove_group_ban(gid, tpk)
        nm = self.db.get_contact_name(tpk) or ''
        pl = json.dumps({'type': 'unban', 'pubkey': tpk, 'target_name': nm, 'text': 'Unbanned'})
        key_hex = self.groups[gid]['key_hex']
        cipher = NostrCrypto.encrypt_group_msg(key_hex, pl)
        self._send_event(42, cipher, [['g', gid]])

    def recall_message(self, tid):
        msg = self.db.get_message(tid)
        if not msg:
            return
        tags = [['e', tid]]
        if msg[1] in self.groups:
            tags.append(['g', msg[1]])
        else:
            tags.append(['p', msg[1]])
        self._send_event(5, 'recall', tags)
        self.db.update_message_content(tid, tr('MSG_RECALLED'))

    def ping_relay(self, url):
        return self.relay_manager.trigger_ping(url)

    @property
    def relays(self):
        return self.relay_manager.workers