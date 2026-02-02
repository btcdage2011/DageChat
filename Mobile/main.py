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
import shutil
import threading
import time
import json
import configparser
from datetime import datetime
from kivy.config import Config
Config.set('graphics', 'width', '360')
Config.set('graphics', 'height', '760')
Config.set('graphics', 'resizable', '0')
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.text import LabelBase
from kivy.utils import platform
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.toast import toast
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui'))
from backend.lang_utils import tr
from ui.login_screen import LoginScreen
from ui.relay_editor import RelayEditor
from ui.main_screen import MainScreen
from ui.chat_screen import ChatScreen
from kivy.core.window import Window
Window.softinput_mode = 'resize'
APP_VERSION = 'v0.6.2'

def _get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _resolve_data_root():
    base_dir = _get_exe_dir()
    ini_path = os.path.join(base_dir, 'setup.ini')
    default_root = base_dir
    if os.path.exists(ini_path):
        try:
            config = configparser.ConfigParser()
            config.read(ini_path, encoding='utf-8')
            if 'Setup' in config and 'DbPath' in config['Setup']:
                custom_path = config['Setup']['DbPath'].strip()
                if not os.path.isabs(custom_path):
                    custom_path = os.path.join(base_dir, custom_path)
                custom_path = os.path.abspath(custom_path)
                if not os.path.exists(custom_path):
                    os.makedirs(custom_path, exist_ok=True)
                return custom_path
        except:
            pass
    return default_root

class WindowManager(ScreenManager):
    pass

class DageChatApp(MDApp):
    current_chat_id = None
    current_chat_name = ''
    current_chat_type = ''
    current_chat_screen = None
    client = None
    current_user_nick = ''
    app_data_dir = ''

    def build(self):
        from kivy.core.window import Window
        Window.softinput_mode = 'resize'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(current_dir, 'assets', 'fonts', 'msyh.ttf')
        if os.path.exists(font_path):
            LabelBase.register(name='GlobalFont', fn_regular=font_path)
            self.theme_cls.font_styles.update({'H1': ['GlobalFont', 96, False, -1.5], 'H2': ['GlobalFont', 60, False, -0.5], 'H3': ['GlobalFont', 48, False, 0], 'H4': ['GlobalFont', 34, False, 0.25], 'H5': ['GlobalFont', 24, False, 0], 'H6': ['GlobalFont', 20, False, 0.15], 'Subtitle1': ['GlobalFont', 16, False, 0.15], 'Subtitle2': ['GlobalFont', 14, False, 0.1], 'Body1': ['GlobalFont', 16, False, 0.5], 'Body2': ['GlobalFont', 14, False, 0.25], 'Button': ['GlobalFont', 14, True, 1.25], 'Caption': ['GlobalFont', 12, False, 0.4], 'Overline': ['GlobalFont', 10, True, 1.5]})
        self.theme_cls.theme_style = 'Dark'
        self.theme_cls.primary_palette = 'Blue'
        self.kv_str = '\nWindowManager:\n    LoginScreen:\n    MainScreen:\n    ChatScreen:\n\n<MainScreen>:\n    name: "main"\n\n    MDBottomNavigation:\n        id: bottom_nav  # [修改] 增加 ID 方便代码控制\n        panel_color: app.theme_cls.bg_dark\n        selected_color_background: 0, 0, 0, 0\n        text_color_active: app.theme_cls.primary_color\n\n        # 1. 消息 Tab\n        MDBottomNavigationItem:\n            name: "tab_chats"\n            text: "消息"\n            icon: "message-processing"\n\n            MDBoxLayout:\n                orientation: "vertical"\n                MDBoxLayout:\n                    size_hint_y: None\n                    height: "50dp"\n                    padding: "10dp"\n                    spacing: "10dp"\n                    MDIconButton:\n                        icon: "magnify"\n                        pos_hint: {"center_y": .5}\n                    MDTextField:\n                        hint_text: "搜索..."\n                        mode: "rectangle"\n                        size_hint_y: None\n                        height: "36dp"\n                        pos_hint: {"center_y": .5}\n                        on_text: root.refresh_chats(self.text)\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n                ScrollView:\n                    MDList:\n                        id: chat_list\n                MDFloatingActionButton:\n                    icon: "plus"\n                    pos_hint: {"right": .95, "bottom": .95}\n                    on_release: root.show_add_menu()\n\n        # 2. 通讯录 Tab\n        MDBottomNavigationItem:\n            name: "tab_contacts"\n            text: "通讯录"\n            icon: "account-box-multiple"\n\n            MDBoxLayout:\n                orientation: "vertical"\n                MDBoxLayout:\n                    size_hint_y: None\n                    height: "50dp"\n                    padding: "10dp"\n                    MDTextField:\n                        hint_text: "搜索..."\n                        mode: "rectangle"\n                        on_text: root.refresh_contacts(self.text)\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n                ScrollView:\n                    MDList:\n                        id: contact_list\n\n            MDFloatingActionButton:\n                icon: "plus"\n                pos_hint: {"right": .95, "bottom": .95}\n                on_release: root.show_add_menu()\n\n        # 3. 我的 Tab (资料编辑版)\n        MDBottomNavigationItem:\n            name: "tab_me"\n            text: "我"\n            icon: "account"\n\n            ScrollView:\n                MDBoxLayout:\n                    orientation: "vertical"\n                    padding: "20dp"\n                    spacing: "15dp"\n                    adaptive_height: True\n\n                    # --- 1. 头像区域 ---\n                    MDRelativeLayout:\n                        size_hint: None, None\n                        size: "110dp", "110dp"\n                        pos_hint: {"center_x": .5}\n\n                        # 头像容器\n                        MDBoxLayout:\n                            id: my_avatar_container\n                            size_hint: None, None\n                            size: "100dp", "100dp"\n                            pos_hint: {"center_x": .5, "center_y": .5}\n\n                        # 相机图标\n                        MDIconButton:\n                            icon: "camera"\n                            md_bg_color: app.theme_cls.primary_color\n                            theme_text_color: "Custom"\n                            text_color: [1, 1, 1, 1]\n                            size_hint: None, None\n                            size: "36dp", "36dp"\n                            pos_hint: {"right": 1, "bottom": 0}\n                            on_release: root.pick_avatar()\n\n                    # --- 2. 资料编辑表单 ---\n                    MDTextField:\n                        id: field_name\n                        hint_text: "昵称 (Name)"\n                        icon_right: "account"\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n\n                    MDTextField:\n                        id: field_about\n                        hint_text: "简介 (About)"\n                        icon_right: "text"\n                        mode: "rectangle"\n                        multiline: True\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n\n                    MDTextField:\n                        id: field_website\n                        hint_text: "网站 (Website)"\n                        icon_right: "web"\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n\n                    MDTextField:\n                        id: field_lud16\n                        hint_text: "闪电网络地址 (LN URL)"\n                        icon_right: "flash"\n                        mode: "rectangle"\n                        font_name: "GlobalFont"\n                        font_name_hint_text: "GlobalFont"\n\n                    MDRaisedButton:\n                        text: "保存并广播 (Save & Broadcast)"\n                        size_hint_x: 1\n                        height: "50dp"\n                        font_name: "GlobalFont"\n                        md_bg_color: [0.2, 0.6, 0.2, 1]\n                        on_release: root.save_profile()\n\n                    MDFlatButton:\n                        text: "网络与中继设置 (Network Settings)"\n                        size_hint_x: 1\n                        height: "40dp"\n                        font_name: "GlobalFont"\n                        theme_text_color: "Custom"\n                        text_color: app.theme_cls.primary_color\n                        on_release: root.open_relay_editor()\n\n                    MDSeparator:\n\n                    # --- 3. 密钥安全区 ---\n                    MDLabel:\n                        text: "密钥管理 (Key Management)"\n                        theme_text_color: "Secondary"\n                        font_name: "GlobalFont"\n                        bold: True\n\n                    MDLabel:\n                        text: "我的公钥 (Public Key)"\n                        halign: "center"\n                        theme_text_color: "Secondary"\n                        font_name: "GlobalFont"\n                        font_style: "Caption"\n\n                    MDCard:\n                        size_hint: None, None\n                        size: "200dp", "200dp"\n                        pos_hint: {"center_x": .5}\n                        padding: "5dp"\n                        md_bg_color: [1, 1, 1, 1]\n\n                        Image:\n                            id: img_pub_qr\n                            allow_stretch: True\n                            keep_ratio: True\n                            nocache: True\n\n                    MDRaisedButton:\n                        id: btn_pub_key\n                        text: "复制公钥 (npub)"\n                        font_name: "GlobalFont"\n                        size_hint_x: 1\n                        md_bg_color: [0.2, 0.2, 0.2, 1]\n                        on_release: root.copy_pubkey()\n\n                    MDSeparator:\n\n                    MDLabel:\n                        text: "私钥 (Private Key)"\n                        halign: "center"\n                        theme_text_color: "Error"\n                        font_name: "GlobalFont"\n                        bold: True\n\n                    MDBoxLayout:\n                        id: layout_unlock\n                        orientation: "vertical"\n                        adaptive_height: True\n                        spacing: "10dp"\n\n                        MDTextField:\n                            id: input_unlock_pwd\n                            hint_text: "Enter Password to Unlock Key"\n                            password: True\n                            mode: "rectangle"\n                            font_name: "GlobalFont"\n                            size_hint_x: 1\n\n                        MDRaisedButton:\n                            text: "显示私钥二维码"\n                            font_name: "GlobalFont"\n                            size_hint_x: 1\n                            md_bg_color: [0.8, 0, 0, 1]\n                            on_release: root.unlock_private_key()\n\n                    MDBoxLayout:\n                        id: layout_priv_show\n                        orientation: "vertical"\n                        adaptive_height: True\n                        spacing: "10dp"\n                        opacity: 0\n                        size_hint_y: None\n                        height: 0\n                        disabled: True\n\n                        MDCard:\n                            size_hint: None, None\n                            size: "200dp", "200dp"\n                            pos_hint: {"center_x": .5}\n                            padding: "5dp"\n                            md_bg_color: [1, 1, 1, 1]\n\n                            Image:\n                                id: img_priv_qr\n                                allow_stretch: True\n                                keep_ratio: True\n                                nocache: True\n\n                        MDLabel:\n                            text: "⚠️ 严禁泄露私钥！"\n                            halign: "center"\n                            theme_text_color: "Error"\n                            font_name: "GlobalFont"\n\n                        MDRaisedButton:\n                            text: "复制私钥 (nsec)"\n                            font_name: "GlobalFont"\n                            size_hint_x: 1\n                            md_bg_color: [0.5, 0, 0, 1]\n                            on_release: root.copy_privkey()\n\n                        MDFlatButton:\n                            text: "重新隐藏"\n                            font_name: "GlobalFont"\n                            size_hint_x: 1\n                            on_release: root.hide_private_key()\n\n                    MDSeparator:\n\n                    MDRaisedButton:\n                        text: "退出登录"\n                        size_hint_x: 1\n                        md_bg_color: app.theme_cls.bg_darkest\n                        on_release: app.on_logout()\n                        font_name: "GlobalFont"\n'
        return Builder.load_string(self.kv_str)

    def show_toast_compat(self, text):
        try:
            toast(text)
        except:
            pass

    def on_start(self):
        self.app_data_dir = _resolve_data_root()
        self.request_android_permissions()
        Window.softinput_mode = 'resize'
        Window.bind(on_keyboard=self.on_keyboard_down)
        self.load_global_config()
        Clock.schedule_interval(self.process_gui_queue, 0.2)

    def on_keyboard_down(self, window, key, scancode, codepoint, modifier):
        if key == 27:
            screen_mgr = self.root
            if screen_mgr.current == 'chat':
                screen_mgr.get_screen('chat').go_back()
                return True
            elif screen_mgr.current == 'login':
                return False
            elif screen_mgr.current == 'main':
                main_screen = screen_mgr.get_screen('main')
                if 'bottom_nav' in main_screen.ids:
                    nav = main_screen.ids.bottom_nav
                    current_tab_name = nav.previous_tab.name if nav.previous_tab else 'tab_chats'
                    if current_tab_name != 'tab_chats':
                        nav.switch_tab('tab_chats')
                        return True
                return False
        return False

    def request_android_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission

            def callback(permissions, results):
                if all(results):
                    print('✅ [Android] Permissions granted')
                else:
                    print('❌ [Android] Permissions denied')
            request_permissions([Permission.INTERNET, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_MEDIA_IMAGES, Permission.READ_MEDIA_VIDEO, Permission.READ_MEDIA_AUDIO], callback)

    def load_global_config(self):
        pass

    def on_logout(self):
        if self.client:
            try:
                self.client.db.close()
            except:
                pass
        self.root.current = 'login'
        self.show_toast_compat('Logged out')

    def process_gui_queue(self, dt):
        if not self.client:
            return
        try:
            while not self.client.gui_queue.empty():
                msg_type, data = self.client.gui_queue.get_nowait()
                if msg_type == 'refresh':
                    self.refresh_ui()
                elif msg_type in ['group', 'dm']:
                    self.refresh_ui()
                    if self.current_chat_screen:
                        self.current_chat_screen.on_new_message(data)
        except:
            pass

    def refresh_ui(self, contact_keyword=None, chat_keyword=None):
        if not self.client:
            return
        try:
            main_screen = self.root.get_screen('main')
            if hasattr(main_screen, 'refresh_chats'):
                main_screen.refresh_chats(chat_keyword)
            if hasattr(main_screen, 'refresh_contacts'):
                main_screen.refresh_contacts(contact_keyword)
            if hasattr(main_screen, 'refresh_profile'):
                main_screen.refresh_profile()
        except Exception as e:
            pass
if __name__ == '__main__':
    DageChatApp().run()