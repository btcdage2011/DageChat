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
from client_persistent import PersistentChatUser

class GuiChatUser(PersistentChatUser):

    def __init__(self, db_filename, on_message_callback=None, nickname=None):
        self.ui_callback = on_message_callback
        super().__init__(db_filename, nickname=nickname)

    def _print_to_ui(self, msg_type, data):
        if self.ui_callback:
            self.ui_callback(msg_type, data)
        else:
            print(f'[{msg_type}] {data}')

    def _handle_metadata(self, event):
        super()._handle_metadata(event)
        self._print_to_ui('contact_update', {'pubkey': event['pubkey']})

    def _handle_deletion(self, event):
        super()._handle_deletion(event)
        target_ids = [t[1] for t in event.get('tags', []) if t[0] == 'e']
        if target_ids:
            self._print_to_ui('delete', {'ids': target_ids})