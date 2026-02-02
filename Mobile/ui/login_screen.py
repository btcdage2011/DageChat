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

import os
import shutil
import threading
import time
import sys
import json
import glob
import sqlite3
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.modalview import ModalView
from kivy.uix.label import Label
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from backend.lang_utils import tr
from backend.key_utils import to_hex_privkey, to_hex_pubkey, to_npub, to_nsec
from backend.nostr_crypto import NostrCrypto
from ui.relay_editor import RelayEditor
KV = '\n<LoginScreen>:\n    name: "login"\n\n    MDBoxLayout:\n        orientation: "vertical"\n        md_bg_color: app.theme_cls.bg_dark\n\n        # Top Bar\n        MDTopAppBar:\n            title: "DageChat Mobile"\n            anchor_title: "center"\n            right_action_items: [["cog", lambda x: root.open_settings()]]\n            elevation: 0\n\n        MDBottomNavigation:\n            panel_color: app.theme_cls.bg_dark\n            selected_color_background: 0, 0, 0, 0\n            text_color_active: app.theme_cls.primary_color\n\n            # --- Tab 1: Login ---\n            MDBottomNavigationItem:\n                name: "nav_login"\n                text: "Login"\n                icon: "login"\n                on_tab_press: root.refresh_user_list()\n\n                MDFloatLayout:\n\n                    MDLabel:\n                        text: "Local Account"\n                        pos_hint: {"center_x": .5, "center_y": .8}\n                        halign: "center"\n                        font_name: "GlobalFont"\n                        theme_text_color: "Secondary"\n\n                    # [布局修改] 使用 MDRelativeLayout 包裹输入框和透明按钮\n                    MDBoxLayout:\n                        orientation: "horizontal"\n                        size_hint_x: .85\n                        adaptive_height: True\n                        pos_hint: {"center_x": .5, "center_y": .65}\n                        spacing: "5dp"\n\n                        MDRelativeLayout:\n                            size_hint_x: 1\n                            size_hint_y: None\n                            height: "64dp"  # 固定高度以适应 MDTextField\n\n                            MDTextField:\n                                id: field_login_user\n                                hint_text: "Select Account"\n                                mode: "rectangle"\n                                font_name: "GlobalFont"\n                                readonly: True\n                                pos_hint: {"center_y": .5}\n\n                            # [关键修复] 透明按钮遮罩\n                            # 拦截所有点击事件，直接触发菜单\n                            Button:\n                                background_color: 0, 0, 0, 0\n                                size_hint: 1, 1\n                                pos_hint: {"center_x": .5, "center_y": .5}\n                                on_release: root.open_user_menu()\n\n                        MDIconButton:\n                            icon: "delete"\n                            theme_text_color: "Custom"\n                            text_color: [0.8, 0, 0, 1]\n                            pos_hint: {"center_y": .5}\n                            on_release: root.confirm_delete_user()\n\n                    MDTextField:\n                        id: field_login_pwd\n                        hint_text: "Password"\n                        password: True\n                        pos_hint: {"center_x": .5, "center_y": .5}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDRaisedButton:\n                        text: "Login"\n                        pos_hint: {"center_x": .5, "center_y": .35}\n                        size_hint_x: .8\n                        height: "50dp"\n                        font_name: "GlobalFont"\n                        on_release: root.do_login_existing()\n\n            # --- Tab 2: Create ---\n            MDBottomNavigationItem:\n                name: "nav_create"\n                text: "Create"\n                icon: "account-plus"\n\n                MDFloatLayout:\n                    MDTextField:\n                        id: field_create_nick\n                        hint_text: "Nickname (Public)"\n                        helper_text: "Your public identity name"\n                        pos_hint: {"center_x": .5, "center_y": .8}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDTextField:\n                        id: field_create_pwd\n                        hint_text: "Password (Min 8 chars)"\n                        password: True\n                        pos_hint: {"center_x": .5, "center_y": .65}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDTextField:\n                        id: field_create_pwd2\n                        hint_text: "Confirm Password"\n                        password: True\n                        pos_hint: {"center_x": .5, "center_y": .5}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDRaisedButton:\n                        text: "Create & Login"\n                        pos_hint: {"center_x": .5, "center_y": .35}\n                        size_hint_x: .8\n                        md_bg_color: [0.2, 0.6, 0.2, 1]\n                        font_name: "GlobalFont"\n                        on_release: root.do_create_new()\n\n            # --- Tab 3: Import ---\n            MDBottomNavigationItem:\n                name: "nav_import"\n                text: "Import"\n                icon: "key-variant"\n\n                MDFloatLayout:\n                    MDTextField:\n                        id: field_import_key\n                        hint_text: "Private Key (nsec / hex)"\n                        helper_text: "Paste your Nostr private key here"\n                        pos_hint: {"center_x": .5, "center_y": .8}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDTextField:\n                        id: field_import_pwd\n                        hint_text: "New Password"\n                        password: True\n                        pos_hint: {"center_x": .5, "center_y": .65}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDTextField:\n                        id: field_import_pwd2\n                        hint_text: "Confirm Password"\n                        password: True\n                        pos_hint: {"center_x": .5, "center_y": .5}\n                        size_hint_x: .8\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n\n                    MDLabel:\n                        text: "* Profile (Name/Avatar) will sync from Relay"\n                        pos_hint: {"center_x": .5, "center_y": .42}\n                        halign: "center"\n                        theme_text_color: "Hint"\n                        font_style: "Caption"\n                        font_name: "GlobalFont"\n\n                    MDRaisedButton:\n                        text: "Import & Login"\n                        pos_hint: {"center_x": .5, "center_y": .32}\n                        size_hint_x: .8\n                        md_bg_color: [0.2, 0.2, 0.7, 1]\n                        font_name: "GlobalFont"\n                        on_release: root.do_import_existing()\n'
Builder.load_string(KV)

class CustomToast(ModalView):

    def __init__(self, text, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(300), dp(50))
        self.pos_hint = {'center_x': 0.5, 'y': 0.1}
        self.background_color = (0.2, 0.2, 0.2, 0.9)
        self.auto_dismiss = False
        self.overlay_color = [0, 0, 0, 0]
        lbl = Label(text=text, font_name='GlobalFont', color=(1, 1, 1, 1))
        self.add_widget(lbl)

    def show(self, duration=2.0):
        self.open()
        Clock.schedule_once(lambda dt: self.dismiss(), duration)

class LoginScreen(MDScreen):
    menu = None
    local_users = []
    user_folder_map = {}

    def on_enter(self):
        Clock.schedule_once(lambda dt: self.refresh_user_list(), 0)

    def show_alert(self, text):
        if threading.current_thread() != threading.main_thread():
            Clock.schedule_once(lambda dt: self.show_alert(text), 0)
            return
        try:
            from ui.login_screen import CustomToast
            toast = CustomToast(text)
            toast.show()
        except:
            print(f'[Toast] {text}')

    def open_settings(self):
        RelayEditor().open()

    def refresh_user_list(self):
        app = MDApp.get_running_app()
        data_root = app.app_data_dir
        self.local_users = []
        self.user_folder_map = {}
        try:
            paths = glob.glob(os.path.join(data_root, 'user_*'))
            for p in paths:
                if os.path.isdir(p):
                    folder_name = os.path.basename(p)
                    db_path = os.path.join(p, 'user.db')
                    if os.path.exists(db_path):
                        display_name = folder_name
                        try:
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            cursor.execute('SELECT name, pubkey FROM account LIMIT 1')
                            row = cursor.fetchone()
                            conn.close()
                            if row:
                                db_nick = row[0]
                                db_pk = row[1]
                                npub_short = to_npub(db_pk)[:12] + '...' if db_pk else '???'
                                if db_nick:
                                    display_name = f'{db_nick} ({npub_short})'
                                else:
                                    display_name = f'No Nickname ({npub_short})'
                        except Exception as e:
                            print(f'Read DB name error: {e}')
                        self.local_users.append(display_name)
                        self.user_folder_map[display_name] = folder_name
        except Exception as e:
            print(f'Scan users error: {e}')
        if 'field_login_user' in self.ids:
            if self.local_users:
                self.ids.field_login_user.text = self.local_users[0]
            else:
                self.ids.field_login_user.text = ''
            self.ids.field_login_user.focus = False

    def open_user_menu(self):
        if not self.local_users:
            self.show_alert('No accounts found. Please Create one.')
            return
        menu_items = [{'viewclass': 'OneLineListItem', 'text': user, 'on_release': lambda x=user: self.set_user(x)} for user in self.local_users]
        self.menu = MDDropdownMenu(caller=self.ids.field_login_user, items=menu_items, width_mult=4)
        self.menu.open()

    def _on_menu_dismiss(self, *args):
        self.ids.field_login_user.focus = False

    def set_user(self, text_item):
        self.ids.field_login_user.text = text_item
        self.menu.dismiss()

    def do_login_existing(self):
        display_name = self.ids.field_login_user.text.strip()
        pwd = self.ids.field_login_pwd.text.strip()
        if not display_name or display_name not in self.user_folder_map:
            self.show_alert('Please select a valid account')
            return
        if not pwd:
            self.show_alert('Please enter password')
            return
        real_folder_name = self.user_folder_map[display_name]
        folder_suffix = real_folder_name.replace('user_', '')
        self._perform_backend_start(folder_suffix, pwd, 'LOGIN')

    def do_create_new(self):
        nick = self.ids.field_create_nick.text.strip()
        p1 = self.ids.field_create_pwd.text.strip()
        p2 = self.ids.field_create_pwd2.text.strip()
        if not nick:
            self.show_alert('Nickname required')
            return
        if len(p1) < 8:
            self.show_alert('Password must be >= 8 chars')
            return
        if p1 != p2:
            self.show_alert('Passwords do not match')
            return
        try:
            priv_hex = NostrCrypto.generate_private_key_hex()
            pub_hex = NostrCrypto.get_public_key_hex(priv_hex)
            npub = to_npub(pub_hex)
            folder_name = npub[:12]
            app = MDApp.get_running_app()
            user_dir = os.path.join(app.app_data_dir, f'user_{folder_name}')
            if os.path.exists(user_dir):
                self.show_alert('Account conflict (Rare!). Try again.')
                return
            self._perform_backend_start(folder_name, p1, 'IMPORT', priv_key=priv_hex, nickname=nick)
        except Exception as e:
            self.show_alert(f'Create Error: {e}')

    def do_import_existing(self):
        raw_key = self.ids.field_import_key.text.strip()
        p1 = self.ids.field_import_pwd.text.strip()
        p2 = self.ids.field_import_pwd2.text.strip()
        if not raw_key:
            return self.show_alert('Private Key required')
        hex_key = to_hex_privkey(raw_key)
        if not hex_key:
            return self.show_alert('Invalid Private Key')
        if len(p1) < 8:
            return self.show_alert('Password min 8 chars')
        if p1 != p2:
            return self.show_alert('Passwords mismatch')
        try:
            real_pub = NostrCrypto.get_public_key_hex(hex_key)
            if not real_pub:
                return self.show_alert('Invalid Key')
            npub = to_npub(real_pub)
            folder_name = npub[:12]
            app = MDApp.get_running_app()
            user_dir = os.path.join(app.app_data_dir, f'user_{folder_name}')
            if os.path.exists(user_dir):
                self.show_alert(f'Account already exists on device')
                return
            self._perform_backend_start(folder_name, p1, 'IMPORT', priv_key=hex_key)
        except Exception as e:
            self.show_alert(f'Import Error: {e}')

    def _perform_backend_start(self, folder_suffix, pwd, mode, priv_key=None, nickname=None):
        app = MDApp.get_running_app()
        user_dir = os.path.join(app.app_data_dir, f'user_{folder_suffix}')
        db_path = os.path.join(user_dir, 'user.db')
        if not os.path.exists(user_dir):
            os.makedirs(user_dir, exist_ok=True)
        self.show_alert('Starting Engine...')

        def _bg_task():
            try:
                from backend.client_mobile import MobileChatUser
                init_nick = nickname if nickname else folder_suffix
                client = MobileChatUser(db_path, ui_callback=None, nickname=init_nick)
                success, msg = (False, '')
                if mode == 'LOGIN':
                    success, msg = client.unlock_account(pwd)
                elif mode == 'IMPORT':
                    success, msg = client.import_account(priv_key, init_nick, pwd)
                    if success and nickname:
                        client.db.update_my_profile({'name': nickname})
                        client.db.save_contact(client.pk, nickname, enc_key=client.pk, is_friend=1)
                if success:
                    print(f'🚀 [{mode}] Starting network thread...')
                    t = threading.Thread(target=client.connect, daemon=True)
                    t.start()
                    if mode == 'IMPORT':
                        client.fetch_user_profile(client.pk)
                    final_display = nickname if nickname else folder_suffix
                    Clock.schedule_once(lambda dt: self._on_login_success(app, client, final_display), 0)
                else:
                    Clock.schedule_once(lambda dt: self.show_alert(f'Failed: {msg}'), 0)
                    try:
                        client.db.close()
                    except:
                        pass
            except Exception as e:
                import traceback
                traceback.print_exc()
                Clock.schedule_once(lambda dt: self.show_alert(f'System Error: {e}'), 0)
        threading.Thread(target=_bg_task, daemon=True).start()

    def _on_login_success(self, app, client, nick):
        app.client = client
        app.current_user_nick = nick
        self.show_alert(f'Welcome back')
        if 'field_create_nick' in self.ids:
            self.ids.field_create_nick.text = ''
        if 'field_create_pwd' in self.ids:
            self.ids.field_create_pwd.text = ''
        if 'field_create_pwd2' in self.ids:
            self.ids.field_create_pwd2.text = ''
        if 'field_import_key' in self.ids:
            self.ids.field_import_key.text = ''
        if 'field_import_pwd' in self.ids:
            self.ids.field_import_pwd.text = ''
        if 'field_import_pwd2' in self.ids:
            self.ids.field_import_pwd2.text = ''
        if 'field_login_pwd' in self.ids:
            self.ids.field_login_pwd.text = ''
        self.manager.current = 'main'
        main_screen = self.manager.get_screen('main')
        if hasattr(main_screen, 'on_login_success'):
            main_screen.on_login_success()
        if hasattr(main_screen, 'refresh_all'):
            main_screen.refresh_all()

    def confirm_delete_user(self):
        display_name = self.ids.field_login_user.text
        no_acc_text = tr('LOGIN_NO_ACCOUNT')
        if not display_name or display_name == '(暂无账号)' or display_name == no_acc_text:
            self.show_alert('请先选择一个账号')
            return
        if display_name not in self.user_folder_map:
            self.show_alert('账号映射错误')
            return
        real_folder = self.user_folder_map[display_name]
        self.dialog = MDDialog(title='删除账号', text=f'确定要永久删除本地账号 [{display_name}] 及其所有数据吗？\n此操作不可恢复。', buttons=[MDFlatButton(text='取消', font_name='GlobalFont', on_release=lambda x: self.dialog.dismiss()), MDRaisedButton(text='确认删除', font_name='GlobalFont', md_bg_color=(0.8, 0, 0, 1), on_release=lambda x: self._do_delete_user(real_folder))])
        self.dialog.open()

    def _do_delete_user(self, folder_name):
        self.dialog.dismiss()
        app = MDApp.get_running_app()
        user_dir = os.path.join(app.app_data_dir, folder_name)
        try:
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
                self.show_alert(f'账号数据已删除')
                self.ids.field_login_user.text = ''
                self.refresh_user_list()
            else:
                self.show_alert('账号目录不存在')
        except Exception as e:
            self.show_alert(f'删除失败: {e}')