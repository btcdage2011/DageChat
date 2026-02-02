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

import sys
import os
import threading
from kivy.clock import Clock
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from client_persistent import PersistentChatUser

class MobileChatUser(PersistentChatUser):

    def __init__(self, db_filename, ui_callback, nickname=None):
        self.kivy_ui_callback = ui_callback
        self.data_cache = {}
        super().__init__(db_filename, nickname)

    def preload_data(self, chat_ids):
        threading.Thread(target=self._bg_preload, args=(chat_ids,), daemon=True).start()

    def _bg_preload(self, chat_ids):
        try:
            for cid in chat_ids:
                if cid in self.data_cache:
                    continue
                history = self.db.get_history(cid, limit=20)
                history.sort(key=lambda x: x[4])
                self.data_cache[cid] = history
        except Exception as e:
            print(f'Preload error: {e}')

    def _update_cache(self, msg_type, data):
        if msg_type not in ['group', 'dm']:
            return
        try:
            target_id = data.get('group_id')
            if not target_id:
                target_id = data.get('sender_pk')
            if target_id and target_id in self.data_cache:
                is_me_int = 1 if data.get('is_me') else 0
                content = data.get('text', '')
                img = data.get('image')
                if img:
                    import json
                    content = json.dumps({'text': content, 'image': img})
                elif data.get('text', '').startswith('{'):
                    content = data.get('text')
                msg_tuple = (data.get('id'), data.get('group_id'), data.get('real_sender') or data.get('sender_pk'), content, data.get('time'), is_me_int, data.get('reply_to_id'))
                self.data_cache[target_id].append(msg_tuple)
        except Exception as e:
            print(f'Cache update error: {e}')

    def _print_to_ui(self, msg_type, data):
        self._update_cache(msg_type, data)
        if self.kivy_ui_callback:
            Clock.schedule_once(lambda dt: self.kivy_ui_callback(msg_type, data), 0)

    def _handle_metadata(self, event):
        super()._handle_metadata(event)
        self._print_to_ui('contact_update', {'pubkey': event['pubkey']})