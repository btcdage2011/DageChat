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
import json
import threading
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty
from kivy.uix.modalview import ModalView
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.app import MDApp
from kivy.core.clipboard import Clipboard
from kivy.uix.modalview import ModalView as ToastView
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import dp
from backend.client_persistent import DEFAULT_RELAYS
KV = '\n<RelayItem>:\n    orientation: "vertical"\n    size_hint_y: None\n    height: "90dp"\n    padding: "10dp"\n    spacing: "5dp"\n\n    # 增加一个底部分割线效果 (可选)\n    canvas.before:\n        Color:\n            rgba: 0.2, 0.2, 0.2, 1\n        Line:\n            points: self.x, self.y, self.right, self.y\n            width: 1\n\n    # 第一行：地址 + 状态\n    MDBoxLayout:\n        orientation: "horizontal"\n        size_hint_y: None\n        height: "30dp"\n        spacing: "10dp"\n\n        MDLabel:\n            text: root.url\n            font_style: "Subtitle1"\n            theme_text_color: "Primary"\n            shorten: True\n            shorten_from: "right"\n            font_name: "GlobalFont"\n            valign: "center"\n\n        MDLabel:\n            text: root.status_text\n            font_style: "Caption"\n            theme_text_color: "Custom"\n            text_color: root.status_color\n            halign: "right"\n            valign: "center"\n            size_hint_x: None\n            width: "80dp"\n            font_name: "GlobalFont"\n\n    # 第二行：操作按钮栏\n    MDBoxLayout:\n        orientation: "horizontal"\n        size_hint_y: None\n        height: "40dp"\n        spacing: "10dp"\n\n        # 占位符，把按钮推到右边 (或者去掉占位符让按钮左对齐/居中，这里设为右对齐符合习惯)\n        Widget:\n            size_hint_x: 1\n\n        MDIconButton:\n            icon: "content-copy"\n            theme_text_color: "Custom"\n            text_color: [0.6, 0.6, 0.6, 1]\n            on_release: root.copy_item()\n\n        MDIconButton:\n            icon: "access-point-network"\n            theme_text_color: "Custom"\n            text_color: [0.2, 0.6, 0.2, 1]\n            on_release: root.ping_item()\n\n        MDIconButton:\n            icon: "delete"\n            theme_text_color: "Custom"\n            text_color: [0.8, 0, 0, 1]\n            on_release: root.delete_item()\n\n<RelayEditor>:\n    size_hint: .95, .9\n    auto_dismiss: False\n    background_color: 0, 0, 0, .6\n\n    MDCard:\n        orientation: "vertical"\n        padding: "15dp"\n        spacing: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [15, 15, 15, 15]\n\n        MDLabel:\n            text: "Network Settings"\n            font_style: "H6"\n            size_hint_y: None\n            height: self.texture_size[1]\n            theme_text_color: "Primary"\n            font_name: "GlobalFont"\n\n        # --- 代理设置区域 ---\n        MDBoxLayout:\n            orientation: "vertical"\n            size_hint_y: None\n            height: self.minimum_height\n            spacing: "5dp"\n\n            MDTextField:\n                id: input_proxy\n                hint_text: "Proxy URL (http://127.0.0.1:7890)"\n                helper_text: "Leave empty to use system proxy"\n                mode: "rectangle"\n                font_name: "GlobalFont"\n                size_hint_y: None\n                height: "40dp"\n\n            MDTextField:\n                id: input_bypass\n                hint_text: "Bypass List (e.g. 127.0.0.1, localhost)"\n                helper_text: "Comma separated domains"\n                mode: "rectangle"\n                font_name: "GlobalFont"\n                size_hint_y: None\n                height: "40dp"\n\n            MDBoxLayout:\n                size_hint_y: None\n                height: "40dp"\n                MDLabel:\n                    text: "Disable All Proxies"\n                    theme_text_color: "Secondary"\n                    font_name: "GlobalFont"\n                MDSwitch:\n                    id: switch_disable\n                    pos_hint: {\'center_y\': .5}\n\n        MDSeparator:\n\n        # --- Relay 设置区域 ---\n        MDLabel:\n            text: "Relay Servers"\n            font_style: "Subtitle1"\n            size_hint_y: None\n            height: self.texture_size[1]\n            theme_text_color: "Primary"\n            font_name: "GlobalFont"\n\n        MDBoxLayout:\n            size_hint_y: None\n            height: "50dp"\n            spacing: "5dp"\n\n            MDTextField:\n                id: input_relay\n                hint_text: "ws://..."\n                mode: "rectangle"\n                font_name: "GlobalFont"\n\n            MDRaisedButton:\n                text: "Add"\n                on_release: root.add_relay()\n                font_name: "GlobalFont"\n\n        ScrollView:\n            MDList:\n                id: relay_list\n\n        # --- 底部按钮 ---\n        MDBoxLayout:\n            size_hint_y: None\n            height: "50dp"\n            spacing: "10dp"\n\n            MDRectangleFlatButton:\n                text: "Cancel"\n                size_hint_x: .5\n                on_release: root.dismiss()\n                font_name: "GlobalFont"\n\n            MDRaisedButton:\n                text: "Save & Apply"\n                size_hint_x: .5\n                on_release: root.save_and_close()\n                font_name: "GlobalFont"\n'
Builder.load_string(KV)

class RelayItem(MDBoxLayout):
    url = StringProperty('')
    status_text = StringProperty('')
    status_color = ListProperty([0.5, 0.5, 0.5, 1])

    def __init__(self, url_text, callbacks, **kwargs):
        super().__init__(**kwargs)
        self.url = url_text
        self.callbacks = callbacks

    def delete_item(self):
        if self.callbacks and 'delete' in self.callbacks:
            self.callbacks['delete'](self.url)

    def copy_item(self):
        if self.callbacks and 'copy' in self.callbacks:
            self.callbacks['copy'](self.url)

    def ping_item(self):
        if self.callbacks and 'ping' in self.callbacks:
            self.callbacks['ping'](self.url)

class RelayEditor(ModalView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        if self.app.client:
            self.config_path = self.app.client.config_file
        else:
            self.config_path = os.path.join(self.app.app_data_dir, 'global_relays.json')
        self.temp_relays = []
        self.relay_widgets_map = {}
        Clock.schedule_once(lambda dt: self.load_config(), 0.1)

    def show_toast(self, text):
        try:
            from kivymd.toast import toast
            toast(text)
        except:
            pass

    def load_config(self):
        data = {}
        if self.app.client:
            data = self.app.client.network_config
        elif os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
            except:
                pass
        self.temp_relays = data.get('relays', [])
        if not self.temp_relays and (not self.app.client):
            self.temp_relays = list(DEFAULT_RELAYS)
        proxy_url = data.get('proxy_url', '')
        proxy_bypass = data.get('proxy_bypass', [])
        proxy_disabled = data.get('proxy_disabled', False)
        self.ids.input_proxy.text = proxy_url
        if isinstance(proxy_bypass, list):
            self.ids.input_bypass.text = ', '.join(proxy_bypass)
        else:
            self.ids.input_bypass.text = str(proxy_bypass)
        self.ids.switch_disable.active = proxy_disabled
        self.refresh_list()
        self.start_auto_refresh()

    def start_auto_refresh(self):
        if not self.parent:
            return
        self.refresh_list()
        self.after_event = Clock.schedule_once(lambda dt: self.start_auto_refresh(), 1.0)

    def dismiss(self, *args, **kwargs):
        if hasattr(self, 'after_event'):
            self.after_event.cancel()
        super().dismiss(*args, **kwargs)

    def refresh_list(self):
        status_map = {}
        if self.app.client:
            status_data = self.app.client.get_connection_status()
            for item in status_data.get('details', []):
                u = item['url']
                latency = -1
                try:
                    with self.app.client.lock:
                        if hasattr(self.app.client, 'relays') and u in self.app.client.relays:
                            latency = self.app.client.relays[u].latency
                except:
                    pass
                status_map[u] = {'status': item['status'], 'latency': latency}
        current_urls = set(self.temp_relays)
        for url in self.temp_relays:
            state_info = status_map.get(url, {'status': 0, 'latency': -1})
            status_code = state_info['status']
            lat = state_info['latency']
            s_color = [0.5, 0.5, 0.5, 1]
            s_text = 'Disconnect'
            if status_code == 2:
                s_text = 'Online'
                s_color = [0.2, 0.55, 0.23, 1]
                if lat >= 0:
                    s_text = f'{lat}ms'
                    if lat > 300:
                        s_color = [1, 0.6, 0, 1]
                    if lat > 800:
                        s_color = [0.82, 0.18, 0.18, 1]
            elif status_code == 1:
                s_text = 'Connecting...'
                s_color = [1, 0.6, 0, 1]
            if url in self.relay_widgets_map:
                item = self.relay_widgets_map[url]
                if item.status_text != s_text:
                    item.status_text = s_text
                if item.status_color != s_color:
                    item.status_color = s_color
                if item.parent != self.ids.relay_list:
                    self.ids.relay_list.add_widget(item)
            else:
                cbs = {'delete': self.remove_relay, 'copy': self.copy_relay, 'ping': self.ping_relay}
                item = RelayItem(url, cbs)
                item.status_text = s_text
                item.status_color = s_color
                self.ids.relay_list.add_widget(item)
                self.relay_widgets_map[url] = item
        to_remove = []
        for url, widget in self.relay_widgets_map.items():
            if url not in current_urls:
                self.ids.relay_list.remove_widget(widget)
                to_remove.append(url)
        for url in to_remove:
            del self.relay_widgets_map[url]

    def add_relay(self):
        url = self.ids.input_relay.text.strip()
        if not url:
            return
        if not (url.startswith('ws://') or url.startswith('wss://')):
            self.show_toast('Must start with ws:// or wss://')
            return
        if url not in self.temp_relays:
            self.temp_relays.append(url)
            self.refresh_list()
            self.ids.input_relay.text = ''
            if self.app.client:
                self.app.client.add_relay_persistent(url)
        else:
            self.show_toast('Relay already exists')

    def remove_relay(self, url):
        if url in self.temp_relays:
            self.temp_relays.remove(url)
            self.refresh_list()
            if self.app.client:
                self.app.client.remove_relay_persistent(url)

    def copy_relay(self, url):
        Clipboard.copy(url)
        self.show_toast('URL Copied')

    def ping_relay(self, url):
        if not self.app.client:
            self.show_toast('Please login first')
            return
        if url in self.relay_widgets_map:
            item = self.relay_widgets_map[url]
            item.status_text = 'Pinging...'
            item.status_color = [0.2, 0.6, 0.8, 1]
        if not self.app.client.ping_relay(url):
            self.app.client.add_relay_dynamic(url)
            self.show_toast('Connecting first...')
        else:
            self.show_toast('Ping sent...')

    def save_and_close(self):
        try:
            proxy_url = self.ids.input_proxy.text.strip()
            bypass_str = self.ids.input_bypass.text.strip()
            is_disabled = self.ids.switch_disable.active
            bypass_list = []
            if bypass_str:
                bypass_list = [x.strip() for x in bypass_str.replace(';', ',').split(',') if x.strip()]
            data = {'relays': self.temp_relays, 'proxy_url': proxy_url, 'proxy_disabled': is_disabled, 'proxy_bypass': bypass_list}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            if self.app.client:
                print('🔄 [UI] Relay config saved. Triggering reconnect...')
                self.app.client.network_config.update(data)
                threading.Thread(target=self.app.client.reconnect_all_relays, daemon=True).start()
            self.show_toast('Settings Saved & Reconnecting...')
            self.dismiss()
        except Exception as e:
            self.show_toast(f'Save failed: {e}')