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

import time
import json
import threading
import base64
from io import BytesIO
from PIL import Image as PILImage
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivy.core.clipboard import Clipboard
from kivymd.uix.button import MDIconButton, MDFlatButton
from kivymd.toast import toast
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.uix.image import Image
from kivy.core.window import Window
from kivy.uix.widget import Widget
from ui.components import MessageBubble, AvatarFactory, get_kivy_image_from_base64
from ui.image_viewer import FullScreenImageViewer
from ui.dialogs import SelectSessionDialog, ForwardConfirmDialog, SearchMessageDialog, TopInputView
KV = '\n<ChatScreen>:\n    name: "chat"\n\n    MDBoxLayout:\n        id: root_layout\n        orientation: "vertical"\n        md_bg_color: app.theme_cls.bg_dark\n\n        MDTopAppBar:\n            id: top_bar\n            title: "Chat"\n            anchor_title: "left"\n            left_action_items: [["arrow-left", lambda x: root.go_back()]]\n            right_action_items: [["dots-vertical", lambda x: root.show_menu(x)]]\n            elevation: 2\n\n        MDFloatLayout:\n            ScrollView:\n                id: msg_scroll\n                do_scroll_x: False\n                # [修改] 这里不再硬编码 MDBoxLayout，由代码动态 add_widget\n\n            MDSpinner:\n                id: loading_spinner\n                size_hint: None, None\n                size: dp(46), dp(46)\n                pos_hint: {\'center_x\': .5, \'center_y\': .5}\n                active: False\n                palette: [app.theme_cls.primary_color,]\n\n        MDBoxLayout:\n            id: bottom_container\n            orientation: "vertical"\n            adaptive_height: True\n            md_bg_color: [0.15, 0.15, 0.15, 1]\n\n            MDBoxLayout:\n                id: reply_bar\n                size_hint_y: None\n                height: 0\n                opacity: 0\n                padding: "10dp"\n                md_bg_color: [0.2, 0.2, 0.2, 1]\n\n                MDLabel:\n                    id: reply_label\n                    text: "正在回复..."\n                    text_color: [0.7, 0.7, 0.7, 1]\n                    font_name: "GlobalFont"\n                    shorten: True\n                    shorten_from: \'right\'\n\n                MDIconButton:\n                    icon: "close"\n                    on_release: root.cancel_reply()\n\n            MDBoxLayout:\n                id: preview_bar\n                size_hint_y: None\n                height: 0\n                opacity: 0\n                padding: "10dp"\n                spacing: "10dp"\n                md_bg_color: [0.18, 0.18, 0.18, 1]\n\n                Image:\n                    id: preview_img\n                    size_hint: None, None\n                    size: "60dp", "60dp"\n                    allow_stretch: True\n                    keep_ratio: True\n\n                MDLabel:\n                    text: "待发送图片"\n                    font_name: "GlobalFont"\n                    theme_text_color: "Secondary"\n\n                MDIconButton:\n                    icon: "delete"\n                    on_release: root.clear_pending_image()\n\n            MDBoxLayout:\n                id: multi_op_bar\n                size_hint_y: None\n                height: 0\n                opacity: 0\n                padding: "5dp"\n                spacing: "10dp"\n                md_bg_color: [0.15, 0.15, 0.15, 1]\n\n                MDIconButton:\n                    icon: "delete"\n                    text: "删除"\n                    on_release: root.do_batch_delete()\n\n                MDLabel:\n                    id: multi_count_lbl\n                    text: "已选: 0"\n                    halign: "center"\n                    font_name: "GlobalFont"\n\n                MDIconButton:\n                    icon: "share"\n                    on_release: root.do_batch_forward()\n\n                MDIconButton:\n                    icon: "close"\n                    on_release: root.exit_multi_select()\n\n            MDBoxLayout:\n                id: input_bar\n                size_hint_y: None\n                height: "60dp"\n                padding: "5dp"\n                spacing: "5dp"\n                md_bg_color: [0.15, 0.15, 0.15, 1]\n\n                MDIconButton:\n                    icon: "image"\n                    theme_text_color: "Custom"\n                    text_color: [0.6, 0.6, 0.6, 1]\n                    pos_hint: {"center_y": .5}\n                    on_release: root.pick_image()\n\n                MDRelativeLayout:\n                    size_hint: 1, 1\n\n                    MDTextField:\n                        id: input_box\n                        hint_text: "点击输入..."\n                        mode: "rectangle"\n                        fill_color_normal: [0.2, 0.2, 0.2, 1]\n                        text_color_normal: [1, 1, 1, 1]\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n                        size_hint: 1, 1\n                        readonly: True\n\n                    Button:\n                        background_color: 0, 0, 0, 0\n                        size_hint: 1, 1\n                        on_release: root.open_input_modal()\n\n                MDIconButton:\n                    icon: "send"\n                    theme_text_color: "Custom"\n                    text_color: app.theme_cls.primary_color\n                    pos_hint: {"center_y": .5}\n                    on_release: root.send_message()\n'
Builder.load_string(KV)

class ChatSessionView(MDBoxLayout):

    def __init__(self, chat_id, chat_screen, **kwargs):
        super().__init__(**kwargs)
        self.chat_id = chat_id
        self.chat_screen = chat_screen
        self.app = MDApp.get_running_app()
        self.orientation = 'vertical'
        self.adaptive_height = True
        self.padding = ['10dp', '15dp', '10dp', '80dp']
        self.spacing = '15dp'
        self.bubble_map = {}
        self.is_loaded = False
        self.min_ts = 0

    def load_initial_history(self):
        if self.is_loaded:
            return
        self.is_loaded = True
        if self.chat_id in self.app.client.data_cache:
            msgs = self.app.client.data_cache[self.chat_id]
            self._start_render(msgs)
        else:
            Clock.schedule_once(self._step_fetch, 0)

    def _render_messages(self, messages):
        is_active = False
        if self.chat_screen and self.chat_screen.ids.msg_scroll.children:
            if self.chat_screen.ids.msg_scroll.children[0] == self:
                is_active = True
        if is_active:
            self.chat_screen.ids.loading_spinner.active = False
            self.chat_screen.ids.msg_scroll.opacity = 1
        if not messages:
            return
        self.min_ts = messages[0][4]
        limit = 20
        if len(messages) >= limit:
            btn = MDFlatButton(text='⬆️ 查看更多历史消息', size_hint_x=1, height=dp(40), font_name='GlobalFont', theme_text_color='Custom', text_color=self.app.theme_cls.primary_color, on_release=lambda x: self.load_more_history())
            self.add_widget(btn)
        first_batch = messages[-6:]
        remaining = messages[:-6]
        for msg in first_batch:
            self.add_bubble_from_db(msg)
        self.scroll_to_bottom()
        if remaining:
            Clock.schedule_once(lambda dt: self._step_render_batch(remaining, 0), 0.1)

    def add_bubble_from_db(self, msg_data, insert_at_top=False):
        msg_id = msg_data[0]
        content = msg_data[3]
        created_at = msg_data[4]
        if msg_id in self.bubble_map:
            return
        is_me = msg_data[5] == 1
        sender_pk = msg_data[2]
        reply_id = msg_data[6] if len(msg_data) > 6 else None
        text = content
        image_b64 = None
        alias = None
        if content.strip().startswith('{'):
            try:
                d = json.loads(content)
                text = d.get('text', '')
                image_b64 = d.get('image')
                alias = d.get('alias')
            except:
                pass
            if d.get('type') == 'history':
                text = content
                image_b64 = None
        is_ghost = False
        if self.chat_id in self.app.client.groups:
            grp = self.app.client.groups[self.chat_id]
            if str(grp.get('type')) == '1':
                is_ghost = True
        sender_name = 'User'
        if is_me:
            sender_name = 'Me'
        elif is_ghost:
            sender_name = alias if alias else 'Anon'
        else:
            sender_name = self.app.client.db.get_contact_name(sender_pk) or sender_pk[:8]
        reply_info = self.chat_screen._get_reply_info(reply_id) if self.chat_screen else None
        self.add_bubble(text, is_me, sender_name, sender_pk, image_b64, msg_id, reply_info, created_at, insert_at_top=insert_at_top)

    def add_bubble(self, text, is_me, sender_name, sender_pk, image_b64=None, msg_id=None, reply_info=None, timestamp=0, avatar_callback=None, insert_at_top=False):
        ctype = 'dm'
        if self.chat_id in self.app.client.groups:
            grp = self.app.client.groups[self.chat_id]
            if str(grp.get('type')) == '1':
                ctype = 'ghost'
            else:
                ctype = 'group'
        avatar_cb = None
        if ctype != 'ghost' and sender_pk and self.chat_screen:
            avatar_cb = lambda: self.chat_screen._on_avatar_click(sender_pk)
        avatar = AvatarFactory.get_avatar(self.app.client.pk if is_me else sender_pk, sender_name, 'dm', self.app.client, callback=avatar_cb)
        texture = get_kivy_image_from_base64(image_b64) if image_b64 else None

        def _open_viewer(tex):
            if tex:
                FullScreenImageViewer(texture=tex).open()

        def _on_bubble_long_press(card_widget, touch=None):
            if self.chat_screen and (not self.chat_screen.is_multi_select):
                self.chat_screen.show_bubble_menu(card_widget, text, sender_name, msg_id, is_me, image_b64)
        bubble = MessageBubble(text=text, is_me=is_me, sender_name=sender_name, avatar_widget=avatar, image_texture=texture, viewer_callback=_open_viewer, menu_callback=_on_bubble_long_press, reply_info=reply_info, timestamp=timestamp, avatar_callback=avatar_cb)
        if msg_id:
            self.bubble_map[msg_id] = bubble
            if self.chat_screen:
                bubble.checkbox.bind(active=lambda chk, val: self.chat_screen.on_check_msg(msg_id, val))
                if self.chat_screen.is_multi_select:
                    bubble.set_select_mode(True)
        if insert_at_top:
            self.add_widget(bubble, index=len(self.children))
        else:
            self.add_widget(bubble)

    def _step_fetch(self, dt):
        try:
            limit = 20
            history = self.app.client.db.get_history(self.chat_id, limit=limit)
            history.sort(key=lambda x: x[4])
            self._start_render(history)
        except Exception as e:
            print(f'Fetch error: {e}')
            self._stop_spinner()

    def _start_render(self, messages):
        if messages:
            self.min_ts = messages[0][4]
        self._stop_spinner()
        if len(messages) >= 20:
            btn = MDFlatButton(text='⬆️ 查看更多历史消息', size_hint_x=1, height=dp(40), font_name='GlobalFont', theme_text_color='Custom', text_color=self.app.theme_cls.primary_color, on_release=lambda x: self.load_more_history())
            self.add_widget(btn)
        if messages:
            first_batch = messages[:5]
            for m in first_batch:
                self.add_bubble_from_db(m)
            self.scroll_to_bottom()
            if len(messages) > 5:
                Clock.schedule_once(lambda dt: self._step_render_batch(messages, 5), 0.05)

    def _step_render_batch(self, all_msgs, start_index):
        batch_size = 5
        end_index = min(start_index + batch_size, len(all_msgs))
        current_batch = all_msgs[start_index:end_index]
        for msg in current_batch:
            self.add_bubble_from_db(msg)
        self.scroll_to_bottom()
        if end_index < len(all_msgs):
            Clock.schedule_once(lambda d: self._step_render_batch(all_msgs, end_index), 0.02)

    def sync_latest(self):
        try:
            history = self.app.client.db.get_history(self.chat_id, limit=10)
            history.sort(key=lambda x: x[4])
            added = 0
            for msg in history:
                if msg[0] not in self.bubble_map:
                    self.add_bubble_from_db(msg)
                    added += 1
            if added > 0:
                self.scroll_to_bottom()
        except Exception as e:
            print(f'Sync error: {e}')

    def _stop_spinner(self):
        is_active = False
        if self.chat_screen and self.chat_screen.ids.msg_scroll.children:
            if self.chat_screen.ids.msg_scroll.children[0] == self:
                is_active = True
        if is_active:
            self.chat_screen.ids.loading_spinner.active = False
            self.chat_screen.ids.msg_scroll.opacity = 1

    def scroll_to_bottom(self):
        if self.chat_screen:
            Clock.schedule_once(lambda dt: setattr(self.chat_screen.ids.msg_scroll, 'scroll_y', 0), 0.1)

    def load_more_history(self):
        for child in self.children:
            if isinstance(child, MDFlatButton) and '更多' in child.text:
                self.remove_widget(child)
                break
        try:
            if self.min_ts == 0:
                self.min_ts = int(time.time())
            limit = 20
            older_msgs = self.app.client.db.get_history(self.chat_id, limit=limit, before_ts=self.min_ts)
            if not older_msgs:
                toast('没有更多消息了')
                return
            self.min_ts = older_msgs[0][4]
            older_msgs.reverse()
            for msg in older_msgs:
                self.add_bubble_from_db(msg, insert_at_top=True)
            if len(older_msgs) >= limit:
                btn = MDFlatButton(text='⬆️ 查看更多历史消息', size_hint_x=1, height=dp(40), font_name='GlobalFont', theme_text_color='Custom', text_color=self.app.theme_cls.primary_color, on_release=lambda x: self.load_more_history())
                self.add_widget(btn, index=len(self.children))
            else:
                pass
        except Exception as e:
            print(f'Load more error: {e}')
            toast(f'加载失败: {e}')

class ChatScreen(MDScreen):
    reply_target_id = None
    is_multi_select = False
    selected_msgs = set()
    pending_image_b64 = None
    view_cache = {}
    lru_list = []
    CACHE_LIMIT = 10
    is_search_mode = False
    last_loaded_id = None

    def show_invite_dialog(self):
        self.top_menu.dismiss()
        gid = self.app.current_chat_id
        if not gid:
            return
        from ui.dialogs import MultiSelectDialog
        friends = self.app.client.db.get_friends()
        MultiSelectDialog(friends, lambda pks: self._do_invite(gid, pks)).open()

    def _do_invite(self, gid, selected_pks):
        if not selected_pks:
            return
        grp = self.app.client.groups[gid]
        from hashlib import sha256
        from nacl.secret import SecretBox
        import base64
        name = grp['name']
        key = grp['key_hex']
        gtype = grp.get('type', 0)
        owner = self.app.client.db.get_group_owner(gid)
        try:
            salt = 'DAGE_SECURE_V1'
            final_owner = owner if str(gtype) != '1' else ''
            raw_sum = f'{gid}{key}{gtype}{salt}'
            checksum = sha256(raw_sum.encode()).hexdigest()[:6]
            safe_name = base64.urlsafe_b64encode(name.encode()).decode()
            raw_data = f"{gid}|{key}|{final_owner or ''}|{safe_name}|{gtype}|{checksum}"
            link = ''
            if str(gtype) == '1':
                k = sha256('dagechat'.encode()).digest()
                box = SecretBox(k)
                enc = box.encrypt(raw_data.encode('utf-8'))
                b64 = base64.urlsafe_b64encode(enc).decode('utf-8')
                link = f'dage://invite/ghost/{b64}'
            else:
                b64 = base64.urlsafe_b64encode(raw_data.encode('utf-8')).decode('utf-8')
                link = f'dage://invite/normal/{b64}'
            text = f'邀请加入群聊【{name}】\n点击链接加入:\n{link}'
            count = 0
            for pk in selected_pks:
                enc_k = self.app.client.db.get_contact_enc_key(pk)
                if enc_k:
                    self.app.client.send_dm(pk, text, enc_k)
                    count += 1
            toast(f'已发送 {count} 份邀请')
        except Exception as e:
            toast(f'邀请生成失败: {e}')

    def on_pre_enter(self):
        self.app = MDApp.get_running_app()
        target_id = self.app.current_chat_id
        self.ids.top_bar.title = self.app.current_chat_name or 'Chat'
        view = self._get_or_create_view(target_id)
        scroll = self.ids.msg_scroll
        scroll.clear_widgets()
        scroll.add_widget(view)
        if not view.is_loaded:
            scroll.opacity = 0
            self.ids.loading_spinner.active = True
        else:
            scroll.opacity = 1
            self.ids.loading_spinner.active = False
        self.exit_multi_select()
        self.cancel_reply()
        self.clear_pending_image()

    def on_enter(self):
        target_id = self.app.current_chat_id
        from kivy.core.window import Window
        Window.softinput_mode = ''
        try:
            is_group = self.app.current_chat_type in ['group', 'ghost']
            self.app.client.mark_session_read(target_id, is_group)
        except:
            pass
        self.app.current_chat_screen = self
        view = self.view_cache.get(target_id)
        if view:
            if not view.is_loaded:
                Clock.schedule_once(lambda dt: view.load_initial_history(), 0.35)
            else:
                Clock.schedule_once(lambda dt: view.sync_latest(), 0)

    def on_leave(self):
        if hasattr(self.app, 'current_chat_screen'):
            self.app.current_chat_screen = None

    def _get_or_create_view(self, chat_id):
        if chat_id in self.view_cache:
            if chat_id in self.lru_list:
                self.lru_list.remove(chat_id)
            self.lru_list.append(chat_id)
            return self.view_cache[chat_id]
        new_view = ChatSessionView(chat_id=chat_id, chat_screen=self)
        self.view_cache[chat_id] = new_view
        self.lru_list.append(chat_id)
        if len(self.lru_list) > self.CACHE_LIMIT:
            oldest_id = self.lru_list.pop(0)
            if oldest_id in self.view_cache:
                del self.view_cache[oldest_id]
        return new_view

    def on_new_message(self, data):
        if self.is_search_mode:
            return
        msg_gid = data.get('group_id')
        sender = data.get('sender_pk')
        is_me = data.get('is_me', False)
        target_chat_id = None
        if msg_gid:
            target_chat_id = msg_gid
        elif sender:
            if is_me:
                if self.app.current_chat_id:
                    target_chat_id = self.app.current_chat_id
            else:
                target_chat_id = sender
        if not target_chat_id:
            return
        if target_chat_id in self.view_cache:
            view = self.view_cache[target_chat_id]
            raw_text = data.get('text', '')
            text = raw_text
            image_b64 = None
            alias = None
            if raw_text.startswith('{'):
                try:
                    j = json.loads(raw_text)
                    if j.get('type') == 'history':
                        text = raw_text
                    else:
                        text = j.get('text', '')
                        image_b64 = j.get('image')
                        alias = j.get('alias')
                except:
                    pass
            nick = alias if alias else data.get('nickname', 'User')
            reply_info = self._get_reply_info(data.get('reply_to_id'))
            view.add_bubble(text, is_me, nick, sender, image_b64, data.get('id'), reply_info, timestamp=data.get('time', 0))
            view.scroll_to_bottom()

    def send_message(self, image_b64=None):
        text = self.ids.input_box.text.strip()
        img_b64 = image_b64 if image_b64 else self.pending_image_b64
        if not text and (not img_b64):
            return
        chat_id = self.app.current_chat_id
        chat_type = self.app.current_chat_type
        rid = self.reply_target_id
        reply_info = self._get_reply_info(rid)
        now = int(time.time())
        self.ids.input_box.text = ''
        self.cancel_reply()
        self.clear_pending_image()

        def _bg_send():
            try:
                if chat_type in ['group', 'ghost']:
                    grp = self.app.client.groups.get(chat_id)
                    if grp and (grp.get('type') == 1 or str(grp.get('type')) == '1'):
                        self.app.client.send_ghost_msg(chat_id, text, image_base64=img_b64, reply_to_id=rid)
                    else:
                        eid = self.app.client.send_group_msg(chat_id, text, reply_to_id=rid, image_base64=img_b64)
                        if eid:
                            content = text
                            if img_b64:
                                content = json.dumps({'text': text, 'image': img_b64})
                            self.app.client.db.save_message(eid, chat_id, self.app.client.pk, content, now, True, reply_to_id=rid)
                else:
                    enc = self.app.client.db.get_contact_enc_key(chat_id)
                    if enc:
                        self.app.client.send_dm(chat_id, text, enc, reply_to_id=rid, image_base64=img_b64)
            except Exception as e:
                print(f'Send error: {e}')
        threading.Thread(target=_bg_send, daemon=True).start()

    def _on_keyboard_height(self, window, height):
        self.ids.keyboard_spacer.height = height
        if height > 0:
            if self.app.current_chat_id in self.view_cache:
                self.view_cache[self.app.current_chat_id].scroll_to_bottom()
        else:
            self.ids.input_box.focus = False

    def _get_reply_info(self, reply_id):
        if not reply_id:
            return None
        if not hasattr(self, 'app') or not self.app:
            self.app = MDApp.get_running_app()
        if not self.app or not self.app.client:
            return None
        orig_msg = self.app.client.db.get_message(reply_id)
        if not orig_msg:
            return None
        o_content = orig_msg[3]
        o_sender_pk = orig_msg[2]
        o_text = o_content
        o_img_b64 = None
        if o_content.strip().startswith('{'):
            try:
                od = json.loads(o_content)
                o_text = od.get('text', '')
                o_img_b64 = od.get('image')
            except:
                pass
        o_name = 'Unknown'
        if orig_msg[5] == 1:
            o_name = 'Me'
        else:
            o_name = self.app.client.db.get_contact_name(o_sender_pk) or o_sender_pk[:6]
        return {'sender': o_name, 'text': o_text, 'has_image': bool(o_img_b64), 'image_b64': o_img_b64}

    def _on_avatar_click(self, pubkey):
        if not pubkey:
            return
        from ui.dialogs import UserProfileDialog
        UserProfileDialog(pubkey).open()

    def show_bubble_menu(self, caller_widget, text_content, sender_name, msg_id, is_me, image_b64):
        menu_items = []
        if image_b64:
            menu_items.append({'text': '💾 保存图片', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_save_image(image_b64)})
        else:
            menu_items.append({'text': '复制', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_copy(text_content)})
        menu_items.append({'text': '回复', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_reply(text_content, sender_name, msg_id)})
        menu_items.append({'text': '多选', 'viewclass': 'OneLineListItem', 'on_release': lambda: self.enter_multi_select(msg_id)})
        menu_items.append({'text': '转发', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_forward(text_content, image_b64)})
        menu_items.append({'text': '删除(本地)', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_delete_local(msg_id)})
        if is_me:
            menu_items.append({'text': '撤回', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._menu_recall(msg_id)})
        self.bubble_menu = MDDropdownMenu(caller=caller_widget, items=menu_items, width_mult=3)
        self.bubble_menu.open()

    def _menu_save_image(self, b64_str):
        self.bubble_menu.dismiss()
        if not b64_str:
            return
        try:
            from PIL import Image as PILImage
            from io import BytesIO
            import os
            from kivy.utils import platform
            data = base64.b64decode(b64_str)
            pil_img = PILImage.open(BytesIO(data))
            filename = f'IMG_{int(time.time())}.jpg'
            if platform == 'android':
                save_dir = '/storage/emulated/0/Pictures/DageChat'
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)
                full_path = os.path.join(save_dir, filename)
            else:
                save_dir = os.path.expanduser('~/Downloads')
                full_path = os.path.join(save_dir, filename)
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            pil_img.save(full_path, quality=95)
            toast('✅ 图片已保存')
            if platform == 'android':
                try:
                    from jnius import autoclass
                    MediaScannerConnection = autoclass('android.media.MediaScannerConnection')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    activity = PythonActivity.mActivity
                    MediaScannerConnection.scanFile(activity, [full_path], None, None)
                except:
                    pass
        except Exception as e:
            toast(f'保存失败: {e}')

    def _menu_copy(self, text):
        self.bubble_menu.dismiss()
        Clipboard.copy(text)
        toast('已复制')

    def _menu_reply(self, text, name, msg_id):
        self.bubble_menu.dismiss()
        self.reply_target_id = msg_id
        self.ids.reply_bar.height = dp(40)
        self.ids.reply_bar.opacity = 1
        self.ids.reply_label.text = f'回复 @{name}: {text[:15]}...'
        self.ids.input_box.focus = True

    def cancel_reply(self):
        self.reply_target_id = None
        self.ids.reply_bar.height = 0
        self.ids.reply_bar.opacity = 0

    def _menu_forward(self, text, image_b64):
        self.bubble_menu.dismiss()
        content_json = text
        if image_b64:
            content_json = json.dumps({'text': text, 'image': image_b64})

        def _on_target_selected(sid, stype, name):
            preview = text[:50] + '...' if len(text) > 50 else text
            if image_b64:
                preview = '[图片] ' + preview

            def _send():
                self._perform_forward(sid, stype, content_json)
            ForwardConfirmDialog(name, preview, _send).open()
        SelectSessionDialog(_on_target_selected).open()

    def _perform_forward(self, sid, stype, content):
        current_cid = self.app.current_chat_id
        client_pk = self.app.client.pk

        def _bg():
            text = content
            img = None
            if content.strip().startswith('{'):
                try:
                    d = json.loads(content)
                    if d.get('type') == 'history':
                        text = content
                        img = None
                    else:
                        text = d.get('text', '')
                        img = d.get('image')
                except:
                    pass
            if stype == 'group':
                self.app.client.send_group_msg(sid, text, image_base64=img)
            else:
                enc = self.app.client.db.get_contact_enc_key(sid)
                if enc:
                    self.app.client.send_dm(sid, text, enc, image_base64=img)
            if sid == current_cid and sid in self.view_cache:
                now = int(time.time())

                def _ui_update(dt):
                    self.view_cache[sid].add_bubble(text=text, is_me=True, sender_name='Me', sender_pk=client_pk, image_b64=img, timestamp=now)
                    self.view_cache[sid].scroll_to_bottom()
                Clock.schedule_once(_ui_update, 0.1)
            Clock.schedule_once(lambda dt: toast('已转发'), 0)
        threading.Thread(target=_bg, daemon=True).start()

    def _menu_delete_local(self, msg_id):
        self.bubble_menu.dismiss()
        if self.app.client:
            self.app.client.db.delete_message(msg_id)
            chat_id = self.app.current_chat_id
            if chat_id in self.view_cache:
                self.view_cache[chat_id].clear_widgets()
                self.view_cache[chat_id].is_loaded = False
                self.view_cache[chat_id].bubble_map = {}
                self.view_cache[chat_id].load_initial_history()
            toast('已删除')

    def _menu_recall(self, msg_id):
        self.bubble_menu.dismiss()
        if self.app.client:
            self.app.client.recall_message(msg_id)
            toast('已发送撤回请求')
            self.on_message_delete([msg_id])

    def enter_multi_select(self, initial_msg_id=None):
        if hasattr(self, 'bubble_menu'):
            self.bubble_menu.dismiss()
        self.is_multi_select = True
        self.selected_msgs.clear()
        if initial_msg_id:
            self.selected_msgs.add(initial_msg_id)
        self.ids.input_bar.height = 0
        self.ids.input_bar.opacity = 0
        self.ids.multi_op_bar.height = dp(60)
        self.ids.multi_op_bar.opacity = 1
        self.update_multi_count()
        chat_id = self.app.current_chat_id
        if chat_id in self.view_cache:
            for bubble in self.view_cache[chat_id].children:
                if isinstance(bubble, MessageBubble):
                    bubble.set_select_mode(True)

    def exit_multi_select(self):
        self.is_multi_select = False
        self.selected_msgs.clear()
        self.ids.input_bar.height = dp(60)
        self.ids.input_bar.opacity = 1
        self.ids.multi_op_bar.height = 0
        self.ids.multi_op_bar.opacity = 0
        chat_id = self.app.current_chat_id
        if chat_id in self.view_cache:
            for bubble in self.view_cache[chat_id].children:
                if isinstance(bubble, MessageBubble):
                    bubble.set_select_mode(False)

    def on_check_msg(self, msg_id, is_active):
        if is_active:
            self.selected_msgs.add(msg_id)
        else:
            self.selected_msgs.discard(msg_id)
        self.update_multi_count()

    def update_multi_count(self):
        self.ids.multi_count_lbl.text = f'已选: {len(self.selected_msgs)}'

    def do_batch_delete(self):
        if not self.selected_msgs:
            return
        count = len(self.selected_msgs)
        if self.app.client:
            self.app.client.db.delete_messages_batch(list(self.selected_msgs))
            toast(f'已删除 {count} 条')
            self.exit_multi_select()
            chat_id = self.app.current_chat_id
            if chat_id in self.view_cache:
                self.view_cache[chat_id].clear_widgets()
                self.view_cache[chat_id].is_loaded = False
                self.view_cache[chat_id].bubble_map = {}
                self.view_cache[chat_id].load_initial_history()

    def do_batch_forward(self):
        if not self.selected_msgs:
            return
        items = []
        msgs = []
        for mid in self.selected_msgs:
            m = self.app.client.db.get_message(mid)
            if m:
                msgs.append(m)
        msgs.sort(key=lambda x: x[4])
        for m in msgs:
            raw = m[3]
            sender = self.app.client.db.get_contact_name(m[2]) or 'User'
            if m[5] == 1:
                sender = 'Me'
            txt = raw
            img = None
            if raw.strip().startswith('{'):
                try:
                    d = json.loads(raw)
                    if d.get('type') == 'history':
                        title = d.get('title', 'Chat History')
                        txt = f'[聊天记录] {title}'
                        img = None
                    else:
                        txt = d.get('text', '')
                        img = d.get('image')
                except:
                    pass
            if not txt and img:
                txt = '[图片]'
            elif not txt and (not img):
                txt = '[消息]'
            items.append({'n': sender, 't': m[4], 'c': txt, 'i': img})
        chat_name = self.app.current_chat_name or 'Chat'
        history_data = {'type': 'history', 'title': f'{chat_name}的聊天记录', 'items': items}
        final_json = json.dumps(history_data)

        def _on_target(sid, stype, name):

            def _send():
                self._perform_forward(sid, stype, final_json)
            ForwardConfirmDialog(name, '[聊天记录]', _send).open()
            self.exit_multi_select()
        SelectSessionDialog(_on_target).open()

    def on_message_delete(self, msg_ids):
        for view in self.view_cache.values():
            for mid in msg_ids:
                if mid in view.bubble_map:
                    view.bubble_map[mid].set_recalled()

    def pick_image(self):
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._on_image_selected)
        except:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            path = filedialog.askopenfilename(filetypes=[('Images', '*.jpg;*.jpeg;*.png')])
            root.destroy()
            if path:
                self._on_image_selected([path])

    def _on_image_selected(self, selection):
        if not selection:
            return
        file_path = selection[0]
        import logging
        logging.getLogger('PIL').setLevel(logging.WARNING)
        from PIL import ImageOps

        def _process():
            try:
                Clock.schedule_once(lambda dt: toast('1/5 正在读取图片...'), 0)
                img = PILImage.open(file_path)
                if img.format == 'JPEG':
                    img.draft('RGB', (1024, 1024))
                Clock.schedule_once(lambda dt: toast('2/5 修正方向...'), 0)
                try:
                    img = ImageOps.exif_transpose(img)
                except:
                    pass
                Clock.schedule_once(lambda dt: toast('3/5 调整尺寸...'), 0)
                w, h = img.size
                max_side = 1024
                if max(w, h) > max_side:
                    ratio = max_side / max(w, h)
                    resample = getattr(PILImage, 'Resampling', PILImage).LANCZOS
                    img = img.resize((int(w * ratio), int(h * ratio)), resample)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                Clock.schedule_once(lambda dt: toast('4/5 正在压缩...'), 0)
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=65)
                self.pending_image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                Clock.schedule_once(lambda dt: toast('5/5 准备就绪'), 0)
                Clock.schedule_once(self._show_preview, 0)
            except Exception as e:
                err = str(e)
                Clock.schedule_once(lambda dt: toast(f'图片处理错误: {err}'), 0)
        threading.Thread(target=_process, daemon=True).start()

    def _show_preview(self, dt):
        tex = get_kivy_image_from_base64(self.pending_image_b64)
        if tex:
            self.ids.preview_img.texture = tex
            self.ids.preview_bar.height = dp(80)
            self.ids.preview_bar.opacity = 1

    def clear_pending_image(self):
        self.pending_image_b64 = None
        self.ids.preview_bar.height = 0
        self.ids.preview_bar.opacity = 0
        self.ids.preview_img.texture = None

    def open_input_modal(self):
        current_text = self.ids.input_box.text

        def _on_send(text):
            self.ids.input_box.text = text
            self.send_message()

        def _on_draft(text):
            self.ids.input_box.text = text
        TopInputView(callback=_on_send, draft_callback=_on_draft, default_text=current_text).open()

    def on_scroll_move(self, instance, y):
        pass

    def go_back(self):
        self.app.current_chat_id = None
        self.manager.current = 'main'

    def show_menu(self, caller_widget):
        if not self.app.client or not self.app.current_chat_id:
            return
        menu_items = []
        is_group = self.app.current_chat_type in ['group', 'ghost']
        if is_group:
            menu_items.append({'text': '👥 群聊信息', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._open_info()})
            menu_items.append({'text': '➕ 邀请好友', 'viewclass': 'OneLineListItem', 'on_release': lambda: self.show_invite_dialog()})
        else:
            menu_items.append({'text': '👤 详细资料', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._open_info()})
        menu_items.append({'text': '🔍 查找内容', 'viewclass': 'OneLineListItem', 'on_release': lambda: self._open_search()})
        menu_items.append({'text': '🧹 清空记录', 'viewclass': 'OneLineListItem', 'on_release': lambda: self.clear_history()})
        self.top_menu = MDDropdownMenu(caller=caller_widget, items=menu_items, width_mult=3)
        self.top_menu.open()

    def _open_search(self):
        self.top_menu.dismiss()
        SearchMessageDialog(self.app.current_chat_id).open()

    def _open_info(self):
        self.top_menu.dismiss()
        chat_id = self.app.current_chat_id
        if self.app.current_chat_type in ['group', 'ghost']:
            from ui.dialogs import GroupInfoDialog
            GroupInfoDialog(chat_id).open()
        else:
            from ui.dialogs import UserProfileDialog
            UserProfileDialog(chat_id).open()