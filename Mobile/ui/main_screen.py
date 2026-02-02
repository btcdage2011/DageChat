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
import threading
import time
import base64
from io import BytesIO
from PIL import Image as PILImage
from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineAvatarIconListItem
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget
from kivy.core.clipboard import Clipboard
from kivymd.uix.card import MDCard
from kivymd.toast import toast
from ui.components import AvatarFactory, generate_qr_texture, get_kivy_image_from_base64, CircularAvatarImage, LeftAvatarContainer
from backend.key_utils import to_hex_pubkey, to_npub, to_nsec
from backend.lang_utils import tr
from ui.relay_editor import RelayEditor
from ui.dialogs import UserProfileDialog
from kivymd.uix.button import MDFlatButton
from ui.dialogs import DataManageDialog
LIST_ITEM_KV = '\n<ChatListItem>:\n    RightContainer:\n        id: container\n        size_hint: None, None\n        size: "40dp", "40dp"\n        pos_hint: {"center_y": .5}\n\n        MDCard:\n            id: badge\n            size_hint: None, None\n            size: "24dp", "24dp"\n            radius: "12dp"\n            md_bg_color: [1, 0, 0, 1]\n            pos_hint: {"center_x": .5, "center_y": .5}\n            opacity: 0\n            elevation: 0\n\n            MDLabel:\n                id: badge_text\n                text: "0"\n                halign: "center"\n                valign: "center"\n                theme_text_color: "Custom"\n                text_color: [1, 1, 1, 1]\n                font_style: "Caption"\n                bold: True\n'
from kivy.lang import Builder
from kivymd.uix.list import IRightBodyTouch
Builder.load_string(LIST_ITEM_KV)

class RightContainer(IRightBodyTouch, MDBoxLayout):
    pass

class ChatListItem(TwoLineAvatarIconListItem):

    def set_unread(self, count):
        badge = self.ids.badge
        label = self.ids.badge_text
        if count > 0:
            badge.opacity = 1
            label.text = str(count) if count < 99 else '99+'
        else:
            badge.opacity = 0

class MainScreen(MDScreen):
    dialog = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.current_avatar_b64 = None
        self._temp_nsec = None
        self.chat_widgets_map = {}
        self.contact_widgets_map = {}

    def on_enter(self):
        if not self.app:
            self.app = MDApp.get_running_app()
        Clock.schedule_once(lambda dt: self.refresh_all(), 0.35)
        if self.app.client:
            self.app.client.kivy_ui_callback = self.on_backend_message

    def on_login_success(self):
        if not self.app.client:
            return
        self.app.client._ensure_official_group()
        my_pk = self.app.client.pk
        if not self.app.client.db.get_contact_name(my_pk):
            nick = self.app.current_user_nick or 'Me'
            self.app.client.db.save_contact(my_pk, nick, enc_key=my_pk, is_friend=1)
        Clock.schedule_once(lambda dt: self.refresh_all(), 0.5)

    def on_backend_message(self, msg_type, data):
        if msg_type in ['group', 'dm', 'refresh', 'contact_update']:
            if msg_type == 'contact_update':
                pubkey = data.get('pubkey')
                if pubkey:
                    AvatarFactory.clear_cache(pubkey)
            now = time.time()
            if now - getattr(self, '_last_refresh_ts', 0) > 1.0:
                self._last_refresh_ts = now
                Clock.schedule_once(lambda dt: self.refresh_all(), 0)
        if msg_type == 'system':
            self.show_toast(str(data))
            return
        if self.app.current_chat_screen and msg_type in ['group', 'dm']:
            self.app.current_chat_screen.on_new_message(data)
        if msg_type == 'delete':
            ids = data.get('ids', [])
            if self.app.current_chat_screen and ids:
                self.app.current_chat_screen.on_message_delete(ids)

    def refresh_all(self):
        self.refresh_chats()
        self.refresh_contacts()
        self.refresh_profile()

    def refresh_profile(self):
        if not self.app or not self.app.client:
            return
        my_pk = self.app.client.pk
        info = self.app.client.db.get_contact_info(my_pk)
        name = 'Me'
        about = ''
        website = ''
        lud16 = ''
        pic_b64 = None
        if info:
            name = info[1] or ''
            if len(info) > 6:
                pic_b64 = info[6]
            if len(info) > 7:
                about = info[7] or ''
            if len(info) > 8:
                website = info[8] or ''
            if len(info) > 9:
                lud16 = info[9] or ''
        self.current_avatar_b64 = pic_b64
        if 'label_my_name' in self.ids:
            self.ids.label_my_name.text = name or 'User'
        if 'field_name' in self.ids:
            self.ids.field_name.text = name
        if 'field_about' in self.ids:
            self.ids.field_about.text = about
        if 'field_website' in self.ids:
            self.ids.field_website.text = website
        if 'field_lud16' in self.ids:
            self.ids.field_lud16.text = lud16
        if 'my_avatar_container' in self.ids:
            container = self.ids.my_avatar_container
            container.clear_widgets()
            avatar = AvatarFactory.get_avatar(my_pk, name, 'dm', self.app.client)
            avatar.size_hint = (1, 1)
            avatar.bind(on_touch_down=self._on_avatar_touch)
            container.add_widget(avatar)
        npub = to_npub(my_pk)
        if 'btn_pub_key' in self.ids:
            self.ids.btn_pub_key.text = f'复制公钥 ({npub[:8]}...)'
        if 'img_pub_qr' in self.ids and (not self.ids.img_pub_qr.texture):
            threading.Thread(target=self._gen_pub_qr_task, args=(npub,), daemon=True).start()
        if 'field_lud16' in self.ids:
            lud16_field = self.ids.field_lud16
            parent_box = lud16_field.parent
            has_data_btn = False
            for child in parent_box.children:
                if isinstance(child, MDFlatButton) and child.text == '数据管理 (Data Management)':
                    has_data_btn = True
                    break
            if not has_data_btn:
                data_btn = MDFlatButton(text='数据管理 (Data Management)', size_hint_x=1, height=dp(40), font_name='GlobalFont', theme_text_color='Custom', text_color=self.app.theme_cls.primary_color, on_release=lambda x: self.open_data_management(), pos_hint={'center_x': 0.5})
                target_index = 0
                for i, child in enumerate(parent_box.children):
                    if isinstance(child, MDFlatButton) and '网络与中继设置' in child.text:
                        target_index = i
                        break
                parent_box.add_widget(data_btn, index=target_index + 1)

    def open_data_management(self):
        DataManageDialog().open()

    def _on_avatar_touch(self, widget, touch):
        if widget.collide_point(*touch.pos):
            self.pick_avatar()
            return True
        return False

    def pick_avatar(self):

        def _process_image(file_path):
            if not file_path:
                return
            try:
                img = PILImage.open(file_path)
                w, h = img.size
                min_side = min(w, h)
                left = (w - min_side) / 2
                top = (h - min_side) / 2
                img = img.crop((left, top, left + min_side, top + min_side))
                img.thumbnail((200, 200))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=70)
                b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                self.current_avatar_b64 = b64_str
                Clock.schedule_once(lambda dt: self._update_avatar_preview(b64_str), 0)
                self.show_toast('🖼️ 图片已就绪，记得点击保存')
            except Exception as e:
                self.show_toast(f'图片处理失败: {e}')
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=lambda paths: _process_image(paths[0] if paths else None))
        except:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            path = filedialog.askopenfilename(filetypes=[('Images', '*.jpg;*.jpeg;*.png')])
            root.destroy()
            _process_image(path)

    def _update_avatar_preview(self, b64_str):
        if 'my_avatar_container' in self.ids:
            container = self.ids.my_avatar_container
            container.clear_widgets()
            texture = get_kivy_image_from_base64(b64_str)
            if texture:
                img_widget = CircularAvatarImage(texture=texture)
                img_widget.size_hint = (1, 1)
                img_widget.bind(on_touch_down=self._on_avatar_touch)
                container.add_widget(img_widget)

    def save_profile(self):
        name = self.ids.field_name.text.strip()
        about = self.ids.field_about.text.strip()
        website = self.ids.field_website.text.strip()
        lud16 = self.ids.field_lud16.text.strip()
        if not name:
            self.show_toast('❌ 昵称不能为空')
            return
        profile = {'name': name, 'about': about, 'website': website, 'lud16': lud16, 'picture': self.current_avatar_b64 or ''}
        try:
            self.app.client.set_profile(profile)
            self.show_toast('✅ 资料已保存并广播！')
            self.refresh_profile()
        except Exception as e:
            self.show_toast(f'保存失败: {e}')

    def _gen_pub_qr_task(self, data):
        b64 = generate_qr_texture(data)
        if b64:
            Clock.schedule_once(lambda dt: self._apply_qr_texture(b64, 'img_pub_qr'), 0)

    def _apply_qr_texture(self, b64, img_id):
        texture = get_kivy_image_from_base64(b64)
        if texture and img_id in self.ids:
            self.ids[img_id].texture = texture

    def copy_pubkey(self):
        if not self.app.client:
            return
        npub = to_npub(self.app.client.pk)
        Clipboard.copy(npub)
        self.show_toast('✅ 公钥已复制')

    def unlock_private_key(self):
        pwd = self.ids.input_unlock_pwd.text
        if not pwd:
            self.show_toast('请输入密码')
            return
        if self.app.client.verify_password(pwd):
            priv_hex = self.app.client.priv_k
            nsec = to_nsec(priv_hex)
            b64 = generate_qr_texture(nsec)
            if b64:
                self._apply_qr_texture(b64, 'img_priv_qr')
            self._temp_nsec = nsec
            self.ids.input_unlock_pwd.text = ''
            self.ids.layout_unlock.opacity = 0
            self.ids.layout_unlock.height = 0
            self.ids.layout_unlock.disabled = True
            self.ids.layout_priv_show.opacity = 1
            self.ids.layout_priv_show.height = dp(350)
            self.ids.layout_priv_show.disabled = False
            self.show_toast('🔓 私钥已解锁')
        else:
            self.show_toast('❌ 密码错误')

    def copy_privkey(self):
        if hasattr(self, '_temp_nsec') and self._temp_nsec:
            Clipboard.copy(self._temp_nsec)
            self.show_toast('⚠️ 私钥已复制，请注意安全！')

    def hide_private_key(self):
        self._temp_nsec = None
        self.ids.img_priv_qr.texture = None
        self.ids.layout_priv_show.opacity = 0
        self.ids.layout_priv_show.height = 0
        self.ids.layout_priv_show.disabled = True
        self.ids.layout_unlock.opacity = 1
        self.ids.layout_unlock.height = dp(100)
        self.ids.layout_unlock.disabled = False

    def refresh_chats(self, keyword=None):
        if not self.app or not self.app.client:
            return
        chat_list = self.ids.chat_list
        sessions = self.app.client.db.get_session_list()
        chat_list.clear_widgets()
        active_ids = set()
        preload_ids = []
        for i, s in enumerate(sessions):
            sid, name, stype, unread = (s['id'], s['name'], s['type'], s['unread'])
            if not keyword and i < 10:
                preload_ids.append(sid)
            if keyword and keyword.lower() not in name.lower():
                continue
            active_ids.add(sid)
            final_type = 'group'
            if stype == 'group':
                grp = self.app.client.groups.get(sid)
                if grp and str(grp.get('type')) == '1':
                    final_type = 'ghost'
            else:
                final_type = 'dm'
            display_text = name
            secondary_text = f'{final_type.upper()}'
            if sid in self.chat_widgets_map:
                item = self.chat_widgets_map[sid]
                if item.text != display_text:
                    item.text = display_text
                item.set_unread(unread)
                target_container = None
                if hasattr(item, 'ids') and '_left_container' in item.ids:
                    for child in item.ids._left_container.children:
                        if isinstance(child, LeftAvatarContainer):
                            target_container = child
                            break
                if not target_container:
                    for child in item.children:
                        if isinstance(child, LeftAvatarContainer):
                            target_container = child
                            break
                new_avatar = AvatarFactory.get_avatar(sid, name, final_type, self.app.client)
                if target_container:
                    target_container.clear_widgets()
                    target_container.add_widget(new_avatar)
                else:
                    container = LeftAvatarContainer(size_hint=(None, None), size=(dp(40), dp(40)))
                    container.add_widget(new_avatar)
                    item.add_widget(container)
                chat_list.add_widget(item)
            else:
                item = ChatListItem(text=display_text, secondary_text=secondary_text, on_release=lambda x, i=sid, n=name, t=final_type: self.open_chat(i, n, t))
                item.set_unread(unread)
                avatar = AvatarFactory.get_avatar(sid, name, final_type, self.app.client)
                container = LeftAvatarContainer(size_hint=(None, None), size=(dp(40), dp(40)))
                container.add_widget(avatar)
                item.add_widget(container)
                chat_list.add_widget(item)
                self.chat_widgets_map[sid] = item
        to_remove = []
        for sid in self.chat_widgets_map:
            if sid not in active_ids:
                to_remove.append(sid)
        for sid in to_remove:
            del self.chat_widgets_map[sid]
        if preload_ids:
            self.app.client.preload_data(preload_ids)

    def refresh_contacts(self, keyword=None):
        if not self.app or not self.app.client:
            return
        friends = self.app.client.db.get_friends()
        groups = self.app.client.groups
        active_ids = set()
        for f in friends:
            pk = f['pubkey']
            name = f['name'] or f['pubkey'][:8]
            if keyword and keyword.lower() not in name.lower():
                continue
            active_ids.add(pk)
            self._update_or_add_contact_item(pk, name, 'friend')
        for gid, info in groups.items():
            name = info['name']
            if keyword and keyword.lower() not in name.lower():
                continue
            gtype = info.get('type', 0)
            stype = 'ghost' if str(gtype) == '1' else 'group'
            active_ids.add(gid)
            self._update_or_add_contact_item(gid, name, stype)
        contact_list = self.ids.contact_list
        to_remove = []
        for cid, widget in self.contact_widgets_map.items():
            if cid not in active_ids:
                if widget.parent == contact_list:
                    contact_list.remove_widget(widget)
                to_remove.append(cid)
        for cid in to_remove:
            del self.contact_widgets_map[cid]

    def _update_or_add_contact_item(self, cid, name, ctype):
        secondary_text = 'Friend'
        avatar_type = 'dm'
        if ctype == 'group':
            secondary_text = 'Group'
            avatar_type = 'group'
        elif ctype == 'ghost':
            secondary_text = 'Ghost'
            avatar_type = 'ghost'
        if cid in self.contact_widgets_map:
            item = self.contact_widgets_map[cid]
            if item.text != name:
                item.text = name
            if item.secondary_text != secondary_text:
                item.secondary_text = secondary_text
            if hasattr(item, 'ids') and '_left_container' in item.ids:
                item.ids._left_container.clear_widgets()
            av = AvatarFactory.get_avatar(cid, name, avatar_type, self.app.client)
            c = LeftAvatarContainer(size_hint=(None, None), size=(dp(40), dp(40)))
            c.add_widget(av)
            item.add_widget(c)
            if item.parent != self.ids.contact_list:
                self.ids.contact_list.add_widget(item)
            return
        item = TwoLineAvatarIconListItem(text=name, secondary_text=secondary_text, on_release=lambda x, i=cid, n=name, t='dm' if ctype == 'friend' else ctype: self.open_chat(i, n, t))
        av = AvatarFactory.get_avatar(cid, name, avatar_type, self.app.client)
        c = LeftAvatarContainer(size_hint=(None, None), size=(dp(40), dp(40)))
        c.add_widget(av)
        item.add_widget(c)
        self.contact_widgets_map[cid] = item
        self.ids.contact_list.add_widget(item)

    def open_chat(self, chat_id, chat_name, chat_type):
        self.app.current_chat_id = chat_id
        self.app.current_chat_name = chat_name
        self.app.current_chat_type = chat_type
        self.manager.current = 'chat'

    def show_scan_dialog(self):
        from ui.dialogs import QRScannerDialog
        QRScannerDialog(callback=self._on_scan_result).open()

    def _on_scan_result(self, result_text):
        if not result_text:
            return
        result_text = result_text.strip()
        print(f'Scan Result: {result_text}')
        if result_text.startswith('dage://invite/'):
            self.process_join_link(result_text)
            return
        hex_pk = to_hex_pubkey(result_text)
        if hex_pk and len(hex_pk) == 64:
            if hex_pk == self.app.client.pk:
                self.show_toast('这是你自己的公钥')
            else:
                self.app.client.db.save_contact(hex_pk, '新好友', enc_key=hex_pk, is_friend=1)
                self.app.client.fetch_user_profile(hex_pk)
                self.show_toast('✅ 扫码成功，已添加好友')
                self.refresh_contacts()
            return
        self.show_toast(f'未识别的二维码内容:\n{result_text[:20]}...')

    def show_add_menu(self):
        from kivy.uix.modalview import ModalView
        content_layout = MDBoxLayout(orientation='vertical', adaptive_height=True, padding=('0dp', '10dp', '0dp', '10dp'), radius=[20, 20, 0, 0])
        content_layout.md_bg_color = self.app.theme_cls.bg_dark
        menu_items = [(tr('添加好友 (Add Friend)'), 'account-plus', self.show_add_contact_dialog), (tr('创建群组 (Create Group)'), 'account-multiple-plus', self.show_create_group_dialog), (tr('加入群组 (Join Group)'), 'login', self.show_join_group_dialog)]
        self.menu_view = ModalView(size_hint=(1, None), anchor_y='bottom', background_color=(0, 0, 0, 0.5), auto_dismiss=True)
        for text, icon, callback in menu_items:
            item = OneLineIconListItem(text=text)
            item.bg_color = (0, 0, 0, 0)
            icon_widget = IconLeftWidget(icon=icon)
            item.add_widget(icon_widget)
            item.bind(on_release=lambda x, cb=callback: (self.menu_view.dismiss(), cb()))
            content_layout.add_widget(item)

        def update_height(*args):
            self.menu_view.height = content_layout.height
        content_layout.bind(height=update_height)
        self.menu_view.add_widget(content_layout)
        self.menu_view.open()
        Clock.schedule_once(update_height, 0)

    def show_add_contact_dialog(self):
        content = MDBoxLayout(orientation='vertical', spacing='12dp', size_hint_y=None, height='80dp')
        tf = MDTextField(hint_text='输入公钥 (Hex/npub)', font_name='GlobalFont')
        content.add_widget(tf)

        def _on_confirm(*args):
            raw = tf.text.strip()
            if not raw:
                return
            hex_pk = to_hex_pubkey(raw)
            if hex_pk and len(hex_pk) == 64:
                if hex_pk == self.app.client.pk:
                    self.show_toast('不能添加自己')
                else:
                    self.app.client.db.save_contact(hex_pk, '新好友', enc_key=hex_pk, is_friend=1)
                    self.app.client.fetch_user_profile(hex_pk)
                    self.show_toast('✅ 好友已添加，正在同步资料...')
                    self.refresh_contacts()
                    self.dialog.dismiss()
            else:
                self.show_toast('❌ 无效的公钥')
        self.dialog = MDDialog(title='添加好友', type='custom', content_cls=content, buttons=[MDFlatButton(text='取消', on_release=lambda x: self.dialog.dismiss()), MDRaisedButton(text='添加', on_release=_on_confirm)])
        self.dialog.open()

    def show_create_group_dialog(self):
        content = MDBoxLayout(orientation='vertical', spacing='10dp', size_hint_y=None, height='120dp')
        tf_name = MDTextField(hint_text='群名称', font_name='GlobalFont')
        content.add_widget(tf_name)
        chk_box = MDBoxLayout(orientation='horizontal', spacing='10dp', size_hint_y=None, height='40dp')
        chk = MDCheckbox(size_hint=(None, None), size=('40dp', '40dp'), pos_hint={'center_y': 0.5})
        lbl = MDLabel(text='创建为匿名群 (Ghost Group)', font_name='GlobalFont', theme_text_color='Secondary')
        chk_box.add_widget(chk)
        chk_box.add_widget(lbl)
        content.add_widget(chk_box)

        def _on_create(*args):
            name = tf_name.text.strip()
            is_ghost = chk.active
            if not name:
                self.show_toast('请输入群名称')
                return
            self.dialog.dismiss()
            self.show_toast(f'⏳ 正在创建 {name}...')

            def _bg_create():
                try:
                    gid = self.app.client.create_group(name, is_ghost=is_ghost)
                    gtype = 1 if is_ghost else 0
                    if gid not in self.app.client.groups:
                        self.app.client.groups[gid] = {'name': name, 'type': gtype}
                    time.sleep(0.2)
                    if not is_ghost:
                        self.app.client.send_group_msg(gid, '👋 群组创建成功！')

                    def _finish_ui(dt):
                        self.show_toast('✅ 创建成功')
                        self.refresh_contacts()
                        self.refresh_chats()
                        self.open_chat(gid, name, 'group')
                    Clock.schedule_once(_finish_ui, 0.5)
                except Exception as e:
                    print(e)
            threading.Thread(target=_bg_create, daemon=True).start()
        self.dialog = MDDialog(title='新建群组', type='custom', content_cls=content, buttons=[MDFlatButton(text='取消', on_release=lambda x: self.dialog.dismiss()), MDRaisedButton(text='创建', on_release=_on_create)])
        self.dialog.open()

    def show_join_group_dialog(self):
        content = MDBoxLayout(orientation='vertical', spacing='12dp', size_hint_y=None, height='80dp')
        tf_code = MDTextField(hint_text='粘贴邀请码/链接', font_name='GlobalFont')
        content.add_widget(tf_code)

        def _on_join(*args):
            code = tf_code.text.strip()
            if not code:
                return
            self.dialog.dismiss()
            if code.startswith('dage://invite/'):
                self.process_join_link(code)
                return
            if '|' in code:
                try:
                    parts = code.split('|')
                    gid, key = (parts[0], parts[1])
                    gtype = int(parts[4]) if len(parts) > 4 else 0
                    self.app.client.db.save_group(gid, 'New Group', key, group_type=gtype)
                    self.app.client.groups[gid] = {'name': 'New Group', 'key_hex': key, 'type': gtype}
                    req = json.dumps(['REQ', f'sub_join_{gid[:8]}', {'kinds': [42, 30078], '#g': [gid]}])
                    self.app.client.relay_manager.broadcast_send(req)
                    self.show_toast('✅ 已加入 (请刷新)')
                    self.refresh_chats()
                except Exception as e:
                    self.show_toast(f'格式错误: {e}')
            else:
                self.show_toast('❌ 无效邀请码')
        self.dialog = MDDialog(title='加入群组', type='custom', content_cls=content, buttons=[MDFlatButton(text='取消', on_release=lambda x: self.dialog.dismiss()), MDRaisedButton(text='加入', on_release=_on_join)])
        self.dialog.open()

    def process_join_link(self, link):
        import base64
        from hashlib import sha256
        from nacl.secret import SecretBox
        try:
            parts = link.replace('dage://invite/', '').split('/')
            invite_type, payload = (parts[0], parts[1])
            raw_str = ''
            if invite_type == 'ghost':
                key = sha256('dagechat'.encode()).digest()
                box = SecretBox(key)
                raw_str = box.decrypt(base64.urlsafe_b64decode(payload)).decode('utf-8')
            else:
                raw_str = base64.urlsafe_b64decode(payload).decode('utf-8')
            data = raw_str.split('|')
            gid, key, _, safe_name, g_type = (data[0], data[1], data[2], data[3], data[4])
            try:
                name = base64.urlsafe_b64decode(safe_name).decode()
            except:
                name = 'Unknown'
            self.app.client.db.save_group(gid, name, key, group_type=int(g_type))
            self.app.client.groups[gid] = {'name': name, 'key_hex': key, 'type': int(g_type)}
            sub_id = f'sub_join_{gid[:8]}'
            filter_obj = {'kinds': [1059], '#p': [gid]} if str(g_type) == '1' else {'kinds': [42, 30078], '#g': [gid]}
            self.app.client.relay_manager.broadcast_send(json.dumps(['REQ', sub_id, filter_obj]))
            self.show_toast(f'✅ 已加入: {name}')
            self.refresh_chats()
            self.open_chat(gid, name, 'group')
        except Exception as e:
            self.show_toast(f'解析失败: {e}')

    def show_toast(self, text):
        from kivymd.toast import toast
        toast(text)

    def show_user_profile(self, pubkey):
        UserProfileDialog(pubkey).open()

    def open_relay_editor(self):
        RelayEditor().open()