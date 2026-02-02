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

from kivymd.uix.list import OneLineAvatarIconListItem, IconRightWidget, IconLeftWidget, TwoLineListItem, TwoLineAvatarIconListItem
import json
import threading
import base64
import os
from hashlib import sha256
from nacl.secret import SecretBox
from datetime import datetime
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.uix.modalview import ModalView
from kivy.properties import StringProperty, ObjectProperty
from kivy.core.clipboard import Clipboard
from kivy.uix.image import Image
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.list import OneLineAvatarIconListItem, IconRightWidget, TwoLineListItem, TwoLineAvatarIconListItem
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.toast import toast
from kivymd.uix.textfield import MDTextField
from kivymd.uix.tab import MDTabsBase
from backend.lang_utils import tr
from backend.key_utils import to_npub, get_npub_abbr
from ui.image_viewer import FullScreenImageViewer
from ui.components import AvatarFactory, LeftAvatarContainer, get_kivy_image_from_base64, ClickableImage, generate_qr_texture
from backend.backup_manager import BackupManager
from kivymd.uix.progressbar import MDProgressBar
from jnius import autoclass, cast
from android import activity as android_activity
KV = '\n<GroupInfoDialog>:\n    size_hint: .9, .85\n    auto_dismiss: True\n    background_color: 0, 0, 0, .6\n    MDCard:\n        orientation: "vertical"\n        padding: "15dp"\n        spacing: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [15, 15, 15, 15]\n        MDBoxLayout:\n            size_hint_y: None\n            height: "40dp"\n            MDLabel:\n                text: root.title\n                font_style: "H6"\n                theme_text_color: "Primary"\n                font_name: "GlobalFont"\n            MDIconButton:\n                icon: "close"\n                on_release: root.dismiss()\n        MDSeparator:\n        ScrollView:\n            MDBoxLayout:\n                id: info_container\n                orientation: "vertical"\n                adaptive_height: True\n                padding: "5dp"\n                spacing: "15dp"\n        MDSeparator:\n        MDBoxLayout:\n            id: button_container\n            size_hint_y: None\n            height: "50dp"\n            spacing: "10dp"\n            adaptive_height: True\n\n<UserProfileDialog>:\n    size_hint: .9, .75\n    auto_dismiss: True\n    background_color: 0, 0, 0, .6\n    MDCard:\n        orientation: "vertical"\n        padding: "20dp"\n        spacing: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [15, 15, 15, 15]\n        MDBoxLayout:\n            size_hint_y: None\n            height: "90dp"\n            orientation: "horizontal"\n            spacing: "15dp"\n            MDBoxLayout:\n                id: avatar_box\n                size_hint: None, None\n                size: "80dp", "80dp"\n                pos_hint: {"center_y": .5}\n            MDBoxLayout:\n                orientation: "vertical"\n                pos_hint: {"center_y": .5}\n                adaptive_height: True\n                MDLabel:\n                    id: label_name\n                    text: "Loading..."\n                    font_style: "H5"\n                    theme_text_color: "Primary"\n                    font_name: "GlobalFont"\n                    adaptive_height: True\n                MDLabel:\n                    text: "User Profile"\n                    font_style: "Caption"\n                    theme_text_color: "Secondary"\n                    font_name: "GlobalFont"\n                    adaptive_height: True\n        MDSeparator:\n        ScrollView:\n            MDBoxLayout:\n                id: info_list\n                orientation: "vertical"\n                adaptive_height: True\n                padding: "5dp"\n                spacing: "15dp"\n        MDSeparator:\n        MDBoxLayout:\n            id: action_area\n            size_hint_y: None\n            height: "50dp"\n            spacing: "10dp"\n            adaptive_height: True\n            padding: [0, "10dp", 0, 0]\n\n<SelectableContactItem>:\n    IconRightWidget:\n        icon: "checkbox-blank-circle-outline"\n        id: check_icon\n        on_release: root.toggle_selection()\n\n<SelectSessionDialog>:\n    size_hint: .9, .85\n    auto_dismiss: True\n    background_color: 0, 0, 0, .6\n    MDCard:\n        orientation: "vertical"\n        padding: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [15,]\n        MDLabel:\n            text: "选择发送对象"\n            font_style: "H6"\n            size_hint_y: None\n            height: "40dp"\n            font_name: "GlobalFont"\n        MDTabs:\n            id: tabs\n            background_color: app.theme_cls.bg_dark\n            text_color_normal: 0.5, 0.5, 0.5, 1\n            text_color_active: 1, 1, 1, 1\n            indicator_color: app.theme_cls.primary_color\n\n<ForwardConfirmDialog>:\n    size_hint: .85, None\n    height: "300dp"\n    auto_dismiss: False\n    background_color: 0, 0, 0, .6\n    MDCard:\n        orientation: "vertical"\n        padding: "20dp"\n        spacing: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [15,]\n        MDLabel:\n            text: "发送给:"\n            theme_text_color: "Secondary"\n            font_name: "GlobalFont"\n        MDLabel:\n            text: root.target_name\n            font_style: "H5"\n            bold: True\n            font_name: "GlobalFont"\n        MDCard:\n            md_bg_color: [0.2, 0.2, 0.2, 1]\n            padding: "10dp"\n            radius: [8,]\n            MDLabel:\n                text: root.msg_preview\n                font_name: "GlobalFont"\n                theme_text_color: "Custom"\n                text_color: [0.9, 0.9, 0.9, 1]\n        MDBoxLayout:\n            adaptive_height: True\n            spacing: "10dp"\n            padding: [0, "20dp", 0, 0]\n            MDFlatButton:\n                text: "取消"\n                on_release: root.dismiss()\n                font_name: "GlobalFont"\n            MDRaisedButton:\n                text: "发送"\n                on_release: root.confirm()\n                font_name: "GlobalFont"\n\n<TopInputView>:\n    size_hint: 1, None\n    height: "200dp"\n    pos_hint: {\'top\': 1}\n    auto_dismiss: True\n    background_color: 0, 0, 0, 0.8\n\n    MDCard:\n        orientation: "vertical"\n        padding: "10dp"\n        spacing: "10dp"\n        md_bg_color: app.theme_cls.bg_dark\n        radius: [0, 0, 15, 15]\n\n        MDLabel:\n            text: "输入消息 (Input)"\n            font_style: "Subtitle2"\n            theme_text_color: "Secondary"\n            size_hint_y: None\n            height: "20dp"\n            font_name: "GlobalFont"\n\n        MDTextField:\n            id: input_field\n            mode: "rectangle"\n            multiline: True\n            font_name: "GlobalFont"\n            hint_text: "在此输入..."\n            size_hint_y: 1\n            focus: True\n            # 开启原生交互特性\n            use_bubble: True\n            use_handles: True\n            allow_copy: True\n            allow_cut: True\n            allow_paste: True\n\n        MDBoxLayout:\n            adaptive_height: True\n            spacing: "10dp"\n\n            MDFlatButton:\n                text: "取消"\n                font_name: "GlobalFont"\n                on_release: root.dismiss()\n\n            Widget:\n                size_hint_x: 1\n\n            MDRaisedButton:\n                text: "发送"\n                font_name: "GlobalFont"\n                md_bg_color: app.theme_cls.primary_color\n                on_release: root.confirm_send()\n\n<QRDisplayDialog>:\n    size_hint: .8, None\n    height: "400dp"\n    auto_dismiss: True\n    background_color: 0, 0, 0, 0.8\n\n    MDCard:\n        orientation: "vertical"\n        padding: "20dp"\n        spacing: "10dp"\n        md_bg_color: [1, 1, 1, 1]\n        radius: [15,]\n\n        MDLabel:\n            text: root.title_text\n            halign: "center"\n            font_style: "H6"\n            theme_text_color: "Custom"\n            text_color: [0, 0, 0, 1]\n            size_hint_y: None\n            height: "40dp"\n            font_name: "GlobalFont"\n\n        Image:\n            id: qr_image\n            allow_stretch: True\n            keep_ratio: True\n\n        MDLabel:\n            text: root.bottom_text\n            halign: "center"\n            theme_text_color: "Hint"\n            font_style: "Caption"\n            font_name: "GlobalFont"\n\n        MDRaisedButton:\n            text: "关闭"\n            pos_hint: {"center_x": .5}\n            on_release: root.dismiss()\n            font_name: "GlobalFont"\n'
Builder.load_string(KV)

class QRDisplayDialog(ModalView):
    title_text = StringProperty('二维码')
    bottom_text = StringProperty('DageChat Group Invite')

    def __init__(self, data, title='群邀请码', desc='扫码加入群聊', **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.bottom_text = desc
        b64 = generate_qr_texture(data)
        if b64:
            tex = get_kivy_image_from_base64(b64)
            if tex:
                self.ids.qr_image.texture = tex

class QRScannerDialog(ModalView):

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.camera = None
        self.scan_event = None
        self.rot_instruction = None
        self.scale_instruction = None
        self.cv2 = None
        self.np = None
        self.decode_ready = False
        try:
            import cv2
            import numpy as np
            self.cv2 = cv2
            self.np = np
            self.detector = cv2.QRCodeDetector()
            self.decode_ready = True
        except ImportError:
            print('❌ OpenCV or Numpy not found. Scanning disabled.')

    def on_open(self):
        Clock.schedule_once(self._start_camera, 0.5)

    def _start_camera(self, dt):
        try:
            self.camera = Camera(index=0, resolution=(1280, 720), play=True)
            self.camera.keep_ratio = True
            self.camera.allow_stretch = True
            with self.camera.canvas.before:
                PushMatrix()
                self.rot_instruction = Rotate(angle=-90, origin=self.camera.center)
                self.scale_instruction = Scale(1.8, 1.8, 1, origin=self.camera.center)
            with self.camera.canvas.after:
                PopMatrix()
            self.camera.bind(pos=self._update_transform, size=self._update_transform)
            self.ids.camera_container.add_widget(self.camera)
            if self.decode_ready:
                self.scan_event = Clock.schedule_interval(self._try_decode, 0.2)
            else:
                toast('未安装解码库 (OpenCV)，仅预览')
        except Exception as e:
            toast(f'相机启动失败: {e}')
            self.dismiss()

    def _update_transform(self, instance, value):
        if self.rot_instruction:
            self.rot_instruction.origin = instance.center
        if self.scale_instruction:
            self.scale_instruction.origin = instance.center

    def _try_decode(self, dt):
        if not self.camera or not self.camera.texture:
            return
        try:
            tex = self.camera.texture
            w, h = tex.size
            pixels = tex.pixels
            nparr = self.np.frombuffer(pixels, dtype=self.np.uint8)
            img = nparr.reshape((h, w, 4))
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_RGBA2GRAY)
            rotations = [self.cv2.ROTATE_90_CLOCKWISE, self.cv2.ROTATE_90_COUNTERCLOCKWISE, self.cv2.ROTATE_180, None]
            for rot_code in rotations:
                if rot_code is not None:
                    curr_img = self.cv2.rotate(gray, rot_code)
                else:
                    curr_img = gray
                data, bbox, _ = self.detector.detectAndDecode(curr_img)
                if data:
                    self._on_success(data)
                    return
                binary = self.cv2.adaptiveThreshold(curr_img, 255, self.cv2.ADAPTIVE_THRESH_GAUSSIAN_C, self.cv2.THRESH_BINARY, 11, 2)
                data, bbox, _ = self.detector.detectAndDecode(binary)
                if data:
                    self._on_success(data)
                    return
        except Exception as e:
            pass

    def _on_success(self, data):
        print(f'✅ QR Code Detected: {data}')
        try:
            from plyer import vibrator
            vibrator.vibrate(0.1)
        except:
            pass
        self.stop_scan()
        self.callback(data)

class TopInputView(ModalView):

    def __init__(self, callback, draft_callback=None, default_text='', **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.draft_callback = draft_callback
        self.default_text = default_text
        self.is_sending = False
        self.size_hint = (1, None)
        self.height = dp(200)
        self.pos_hint = {'top': 1}
        self.auto_dismiss = True
        self.background_color = (0, 0, 0, 0.8)
        card = MDCard(orientation='vertical', padding='10dp', spacing='10dp', md_bg_color=MDApp.get_running_app().theme_cls.bg_dark, radius=[0, 0, 15, 15])
        card.add_widget(MDLabel(text='输入消息 (Input)', font_style='Subtitle2', theme_text_color='Secondary', size_hint_y=None, height='20dp', font_name='GlobalFont'))
        self.input_field = MDTextField(text=default_text, hint_text='在此输入...', mode='rectangle', multiline=True, font_name='GlobalFont', font_name_hint_text='GlobalFont', size_hint_y=1)
        card.add_widget(self.input_field)
        btn_box = MDBoxLayout(adaptive_height=True, spacing='10dp')
        btn_cancel = MDFlatButton(text='取消', font_name='GlobalFont', on_release=self.dismiss)
        btn_box.add_widget(btn_cancel)
        btn_box.add_widget(MDLabel())
        btn_send = MDRaisedButton(text='发送', font_name='GlobalFont', md_bg_color=MDApp.get_running_app().theme_cls.primary_color, on_release=self.confirm_send)
        btn_box.add_widget(btn_send)
        card.add_widget(btn_box)
        self.add_widget(card)

    def on_open(self):
        super().on_open()
        Clock.schedule_once(self._init_focus, 0.1)

    def _init_focus(self, dt):
        self.input_field.focus = True

    def on_dismiss(self):
        if not self.is_sending and self.draft_callback:
            self.draft_callback(self.input_field.text)
        super().on_dismiss()

    def confirm_send(self, *args):
        self.is_sending = True
        text = self.input_field.text
        self.dismiss()
        if self.callback:
            self.callback(text)

class TaskProgressDialog(ModalView):

    def __init__(self, title, task_func, *args, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.85, None)
        self.height = dp(180)
        self.auto_dismiss = False
        self.background_color = (0, 0, 0, 0.7)
        self.task_func = task_func
        self.task_args = args
        card = MDCard(orientation='vertical', padding='20dp', spacing='15dp', radius=[15], md_bg_color=MDApp.get_running_app().theme_cls.bg_dark)
        self.lbl_title = MDLabel(text=title, font_style='H6', theme_text_color='Primary', font_name='GlobalFont')
        card.add_widget(self.lbl_title)
        self.lbl_status = MDLabel(text='Preparing...', theme_text_color='Secondary', font_name='GlobalFont')
        card.add_widget(self.lbl_status)
        self.progress = MDProgressBar(value=0)
        card.add_widget(self.progress)
        self.btn_cancel = MDFlatButton(text='Cancel', on_release=self.cancel_task, font_name='GlobalFont', theme_text_color='Error')
        card.add_widget(self.btn_cancel)
        self.add_widget(card)
        self.manager_ref = None
        threading.Thread(target=self._run_bg, daemon=True).start()

    def update_ui(self, percent, text):
        self.progress.value = percent
        self.lbl_status.text = text

    def cancel_task(self, *args):
        if self.manager_ref and hasattr(self.manager_ref, 'cancel'):
            self.manager_ref.cancel()
            self.lbl_status.text = 'Cancelling...'
            self.btn_cancel.disabled = True

    def _run_bg(self):
        if self.task_args and len(self.task_args) > 0:
            self.manager_ref = self.task_args[0]

        def _cb(p, t):
            Clock.schedule_once(lambda dt: self.update_ui(p, t), 0)
        try:
            success, msg = self.task_func(*self.task_args, _cb)
        except Exception as e:
            success, msg = (False, str(e))
        Clock.schedule_once(lambda dt: self._finish(success, msg), 0.5)

    def _finish(self, success, msg):
        self.dismiss()
        if success:
            toast(f'✅ {msg}')
            if 'Msg:' in msg or '恢复完成' in msg or 'Restore Complete' in msg:
                try:
                    app = MDApp.get_running_app()
                    client = app.client
                    if client:
                        client._load_groups_from_db()
                        with client.lock:
                            c = client.db.conn.cursor()
                            c.execute('UPDATE contacts SET is_hidden=0 WHERE is_friend=1')
                            c.execute('UPDATE groups SET is_hidden=0')
                            c.execute('UPDATE contacts SET is_hidden=0 WHERE pubkey IN (SELECT DISTINCT group_id FROM messages)')
                            client.db.conn.commit()
                            c.close()
                    if app.root:
                        main_screen = app.root.get_screen('main')
                        if main_screen:
                            Clock.schedule_once(lambda dt: main_screen.refresh_all(), 0.5)
                except Exception as e:
                    print(f'Post-restore refresh failed: {e}')
                    toast('数据已恢复，请尝试重启APP')
        else:
            toast(f'⚠️ {msg}')

class BackupOptionsDialog(ModalView):

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.size_hint = (0.85, None)
        self.height = dp(240)
        self.auto_dismiss = True
        self.background_color = (0, 0, 0, 0.6)
        card = MDCard(orientation='vertical', padding='20dp', spacing='15dp', radius=[15], md_bg_color=MDApp.get_running_app().theme_cls.bg_dark)
        card.add_widget(MDLabel(text='选择备份模式', font_style='H6', theme_text_color='Primary', font_name='GlobalFont'))
        btn_contacts = MDRaisedButton(text='👤 仅备份联系人 & 群组', size_hint_x=1, md_bg_color=(0.3, 0.3, 0.3, 1), font_name='GlobalFont', on_release=lambda x: self.select_mode(False))
        card.add_widget(btn_contacts)
        btn_full = MDRaisedButton(text='📦 全量备份 (含聊天记录)', size_hint_x=1, md_bg_color=MDApp.get_running_app().theme_cls.primary_color, font_name='GlobalFont', on_release=lambda x: self.select_mode(True))
        card.add_widget(btn_full)
        btn_cancel = MDFlatButton(text='取消', size_hint_x=1, font_name='GlobalFont', on_release=self.dismiss)
        card.add_widget(btn_cancel)
        self.add_widget(card)

    def select_mode(self, include_messages):
        self.dismiss()
        if self.callback:
            self.callback(include_messages)

class DataManageDialog(ModalView):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.9, None)
        self.height = dp(280)
        self.auto_dismiss = True
        self.app = MDApp.get_running_app()
        card = MDCard(orientation='vertical', padding='20dp', spacing='15dp', radius=[15], md_bg_color=self.app.theme_cls.bg_dark)
        card.add_widget(MDLabel(text='数据管理 (Data Management)', font_style='H6', font_name='GlobalFont'))
        card.add_widget(MDLabel(text='备份与恢复 (.dgbk 文件)\n兼容 PC 端格式，加密存储。', theme_text_color='Secondary', font_name='GlobalFont', font_size='12sp'))
        btn_bkp = MDRaisedButton(text='📤 备份 (Backup)', size_hint_x=1, md_bg_color=self.app.theme_cls.primary_color, font_name='GlobalFont', on_release=self.do_backup)
        card.add_widget(btn_bkp)
        btn_rst = MDRaisedButton(text='📥 恢复 (Restore)', size_hint_x=1, md_bg_color=(0.2, 0.6, 0.2, 1), font_name='GlobalFont', on_release=self.do_restore)
        card.add_widget(btn_rst)
        btn_close = MDFlatButton(text='关闭', size_hint_x=1, font_name='GlobalFont', on_release=self.dismiss)
        card.add_widget(btn_close)
        self.add_widget(card)

    def do_backup(self, *args):
        self.dismiss()
        BackupOptionsDialog(self._start_backup_flow).open()

    def _start_backup_flow(self, include_messages):
        import re
        my_pk = self.app.client.pk
        raw_nick = self.app.client.db.get_contact_name(my_pk) or 'User'
        safe_nick = re.sub('[\\\\/*?:"<>|]', '_', raw_nick).strip()
        if not safe_nick:
            safe_nick = 'User'
        time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f'DageChat_Backup_{safe_nick}_{time_str}.dgbk'
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity
                private_dir = context.getExternalFilesDir(None).getAbsolutePath()
                target_path = os.path.join(private_dir, default_name)
                self._run_backup_task(target_path, include_messages)
            except Exception as e:
                toast(f'Init Path Error: {e}')
        else:
            try:
                from plyer import filechooser
                filechooser.save_file(on_selection=lambda paths: self._on_backup_path(paths, include_messages), title='Save Backup', filters=['*.dgbk'], default_name=default_name)
            except Exception as e:
                toast(f'File chooser error: {e}')

    def _proceed_backup(self):
        default_name = f"DageChat_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dgbk"
        if platform == 'android':
            try:
                download_dir = '/storage/emulated/0/Download'
                if not os.path.exists(download_dir):
                    os.makedirs(download_dir, exist_ok=True)
                target_path = os.path.join(download_dir, default_name)
                self._run_backup_task(target_path)
            except Exception as e:
                toast(f'Android Backup Error: {e}')
        else:
            try:
                from plyer import filechooser
                filechooser.save_file(on_selection=self._on_backup_path, title='Save Backup', filters=['*.dgbk'], default_name=default_name)
            except Exception as e:
                toast(f'File chooser error: {e}')

    @mainthread
    def _on_backup_path(self, selection, include_messages):
        if not selection:
            return
        path = selection[0]
        if not path.endswith('.dgbk'):
            path += '.dgbk'
        self._run_backup_task(path, include_messages)

    def _run_backup_task(self, path, include_messages):
        manager = BackupManager(self.app.client)
        mode_str = '全量' if include_messages else '仅联系人'

        def _wrapped_task(cb):
            success, msg = manager.run_backup(path, None, cb, include_messages=include_messages)
            if success and platform == 'android':
                try:
                    cb(90, 'Exporting to Downloads...')
                    filename = os.path.basename(path)
                    final_uri = self._export_to_downloads(path, filename)
                    try:
                        os.remove(path)
                    except:
                        pass
                    return (True, f'{msg}\n已保存至系统下载目录')
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return (False, f'Backup OK but Export Failed: {e}')
            return (success, msg)
        TaskProgressDialog(f'Backing up ({mode_str})...', _wrapped_task).open()

    def _export_to_downloads(self, private_path, filename):
        import os
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Environment = autoclass('android.os.Environment')
        ContentValues = autoclass('android.content.ContentValues')
        MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
        MediaStoreDownloads = autoclass('android.provider.MediaStore$Downloads')
        context = cast('android.content.Context', PythonActivity.mActivity)
        resolver = context.getContentResolver()
        values = ContentValues()
        values.put(MediaColumns.DISPLAY_NAME, filename)
        values.put(MediaColumns.MIME_TYPE, 'application/octet-stream')
        values.put(MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
        uri = resolver.insert(MediaStoreDownloads.EXTERNAL_CONTENT_URI, values)
        if not uri:
            raise Exception('Failed to create MediaStore entry')
        try:
            pfd = resolver.openFileDescriptor(uri, 'w')
            if not pfd:
                raise Exception('Failed to open output FD')
            fd = pfd.getFd()
            with open(private_path, 'rb') as f_in:
                while True:
                    chunk = f_in.read(1024 * 1024)
                    if not chunk:
                        break
                    to_write = chunk
                    while to_write:
                        written = os.write(fd, to_write)
                        to_write = to_write[written:]
            os.fsync(fd)
            pfd.close()
            return uri
        except Exception as e:
            try:
                resolver.delete(uri, None, None)
            except:
                pass
            raise e

    def do_restore(self, *args):
        self.dismiss()
        if platform == 'android':
            NativeFilePicker(self._on_restore_path).open()
        else:
            try:
                from plyer import filechooser
                filechooser.open_file(on_selection=self._on_restore_path, title='Select Backup', filters=['*.dgbk'])
            except Exception as e:
                toast(f'File chooser error: {e}')

    @mainthread
    def _on_restore_path(self, selection):
        if not selection:
            return
        path = selection[0]

        def _confirm():
            manager = BackupManager(self.app.client)
            TaskProgressDialog('Restoring...', BackupManager.run_restore, manager, path).open()
        ConfirmationDialog('确认恢复', '这将执行增量恢复。\n现有数据不会被删除，仅补充缺失数据。\n是否继续？', _confirm).open()

def add_info_item_to_container(container, key, value, copyable=False):
    if not value:
        return
    box = MDBoxLayout(orientation='vertical', adaptive_height=True, spacing='2dp')
    box.add_widget(MDLabel(text=key, font_style='Caption', theme_text_color='Secondary', font_name='GlobalFont'))
    val_box = MDBoxLayout(adaptive_height=True, spacing='5dp')
    lbl = MDLabel(text=str(value), font_name='GlobalFont', adaptive_height=True, theme_text_color='Primary')
    val_box.add_widget(lbl)
    if copyable:
        btn = MDIconButton(icon='content-copy', theme_text_color='Hint', icon_size='16sp', size_hint=(None, None), size=('24dp', '24dp'), pos_hint={'center_y': 0.5})
        btn.bind(on_release=lambda x: _copy_text(value))
        val_box.add_widget(btn)
    box.add_widget(val_box)
    container.add_widget(box)

def _copy_text(text):
    Clipboard.copy(text)
    toast('已复制到剪贴板')

class ConfirmationDialog(ModalView):

    def __init__(self, title, text, on_confirm, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.85, None)
        self.height = dp(200)
        self.auto_dismiss = True
        self.background_color = (0, 0, 0, 0.6)
        self.on_confirm_cb = on_confirm
        card = MDCard(orientation='vertical', padding='20dp', spacing='10dp', radius=[15], md_bg_color=MDApp.get_running_app().theme_cls.bg_dark)
        card.add_widget(MDLabel(text=title, font_style='H6', theme_text_color='Error', font_name='GlobalFont'))
        card.add_widget(MDLabel(text=text, theme_text_color='Primary', font_name='GlobalFont'))
        btns = MDBoxLayout(adaptive_height=True, spacing='10dp', padding=[0, '10dp', 0, 0])
        btns.add_widget(MDFlatButton(text='取消', on_release=lambda x: self.dismiss(), font_name='GlobalFont'))
        btns.add_widget(MDRaisedButton(text='确认', md_bg_color=(0.8, 0, 0, 1), on_release=lambda x: self.confirm(), font_name='GlobalFont'))
        card.add_widget(btns)
        self.add_widget(card)

    def confirm(self):
        self.dismiss()
        self.on_confirm_cb()

class GroupInfoDialog(ModalView):
    title = StringProperty('Group Info')

    def __init__(self, group_id, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.group_id = group_id
        self.client = self.app.client
        Clock.schedule_once(self.load_data, 0.1)

    def load_data(self, dt):
        if self.group_id not in self.client.groups:
            self.dismiss()
            return
        grp = self.client.groups[self.group_id]
        name = grp['name']
        g_type = grp.get('type', 0)
        is_ghost = str(g_type) == '1'
        self.title = f"{('⚡' if is_ghost else '📢')} {name}"
        container = self.ids.info_container
        container.clear_widgets()
        add_info_item_to_container(container, '群名称 (Name)', name)
        add_info_item_to_container(container, '群组 ID', self.group_id, copyable=True)
        if is_ghost:
            add_info_item_to_container(container, '群主 (Owner)', '无 (匿名群 - Anonymous)', copyable=False)
            owner_pk = None
        else:
            owner_pk = self.client.db.get_group_owner(self.group_id)
            if owner_pk:
                owner_name = self.client.db.get_contact_name(owner_pk) or 'Unknown'
                owner_npub = to_npub(owner_pk)
                add_info_item_to_container(container, '群主 (Owner)', f'{owner_name}\n{owner_npub}', copyable=True)
            else:
                add_info_item_to_container(container, '群主 (Owner)', '未知 (Unknown)', copyable=False)
        invite_link = self._generate_invite_link(self.group_id, grp['key_hex'], name, owner_pk, g_type)
        add_info_item_to_container(container, '邀请链接 (Invite Link)', invite_link, copyable=True)
        if invite_link and (not invite_link.startswith('Error')):
            qr_b64 = generate_qr_texture(invite_link)
            if qr_b64:
                qr_tex = get_kivy_image_from_base64(qr_b64)
                if qr_tex:
                    img = Image(texture=qr_tex, size_hint_y=None, height=dp(200), allow_stretch=True, keep_ratio=True)
                    container.add_widget(MDLabel(text='群邀请码 (Scan to Join)', font_style='Caption', theme_text_color='Hint', halign='center', adaptive_height=True))
                    container.add_widget(img)
        if not is_ghost:
            members = self.client.db.get_group_members(self.group_id)
            lbl = MDLabel(text=f'群成员 ({len(members)}人)', font_style='Subtitle2', theme_text_color='Secondary', font_name='GlobalFont', padding=[0, '10dp', 0, 0])
            container.add_widget(lbl)
            member_txt = ''
            for pk in members[:8]:
                m_name = self.client.db.get_contact_name(pk) or get_npub_abbr(pk)
                member_txt += f'• {m_name}\n'
            if len(members) > 8:
                member_txt += '...'
            lbl_list = MDLabel(text=member_txt, font_name='GlobalFont', theme_text_color='Hint', adaptive_height=True)
            container.add_widget(lbl_list)
        real_owner_pk = self.client.db.get_group_owner(self.group_id)
        self._setup_buttons(is_ghost, real_owner_pk, invite_link)

    def _generate_invite_link(self, gid, key, name, owner, gtype):
        try:
            final_owner = owner
            if str(gtype) == '1':
                final_owner = ''
            salt = 'DAGE_SECURE_V1'
            raw_sum = f'{gid}{key}{gtype}{salt}'
            checksum = sha256(raw_sum.encode()).hexdigest()[:6]
            safe_name = base64.urlsafe_b64encode(name.encode()).decode()
            raw_data = f"{gid}|{key}|{final_owner or ''}|{safe_name}|{gtype}|{checksum}"
            if str(gtype) == '1':
                obfuscate_key = sha256('dagechat'.encode()).digest()
                box = SecretBox(obfuscate_key)
                encrypted = box.encrypt(raw_data.encode('utf-8'))
                b64_payload = base64.urlsafe_b64encode(encrypted).decode('utf-8')
                return f'dage://invite/ghost/{b64_payload}'
            else:
                b64_payload = base64.urlsafe_b64encode(raw_data.encode('utf-8')).decode('utf-8')
                return f'dage://invite/normal/{b64_payload}'
        except Exception as e:
            return f'Error: {e}'

    def _setup_buttons(self, is_ghost, owner_pk, invite_link):
        btn_box = self.ids.button_container
        btn_box.clear_widgets()
        btn_invite = MDRaisedButton(text='邀请好友', md_bg_color=self.app.theme_cls.primary_color, font_name='GlobalFont')
        btn_invite.bind(on_release=lambda x: self.open_invite())
        btn_box.add_widget(btn_invite)
        btn_qr = MDFlatButton(text='二维码', theme_text_color='Custom', text_color=self.app.theme_cls.primary_color, font_name='GlobalFont')
        btn_qr.bind(on_release=lambda x: self.show_qr(invite_link))
        btn_box.add_widget(btn_qr)
        is_blocked = self.client.db.is_group_blocked(self.group_id)
        block_text = '恢复' if is_blocked else '屏蔽'
        block_col = 'green' if is_blocked else 'gray'
        btn_block = MDFlatButton(text=block_text, theme_text_color='Custom', text_color=block_col, font_name='GlobalFont')
        btn_block.bind(on_release=lambda x: self.toggle_block(not is_blocked))
        btn_box.add_widget(btn_block)
        if not is_ghost and owner_pk == self.client.pk:
            btn_ban = MDFlatButton(text='黑名单', theme_text_color='Custom', text_color='orange', font_name='GlobalFont')
            btn_ban.bind(on_release=lambda x: self.open_ban_list())
            btn_box.add_widget(btn_ban)
        btn_clear = MDFlatButton(text='清空', theme_text_color='Custom', text_color='red', font_name='GlobalFont')
        btn_clear.bind(on_release=lambda x: self.confirm_clear())
        btn_box.add_widget(btn_clear)
        btn_exit = MDFlatButton(text='退出', theme_text_color='Custom', text_color='red', font_name='GlobalFont')
        btn_exit.bind(on_release=lambda x: self.confirm_exit())
        btn_box.add_widget(btn_exit)

    def show_qr(self, link):
        QRDisplayDialog(link, title='群组邀请码').open()

    def open_invite(self):
        self.dismiss()
        friends = self.client.db.get_friends()
        MultiSelectDialog(friends, self._do_invite).open()

    def _do_invite(self, selected_pks):
        if not selected_pks:
            return
        count = 0
        grp = self.client.groups[self.group_id]
        owner = self.client.db.get_group_owner(self.group_id)
        gtype = grp.get('type', 0)
        link = self._generate_invite_link(self.group_id, grp['key_hex'], grp['name'], owner, gtype)
        text = f"邀请加入群聊【{grp['name']}】\n点击链接加入:\n{link}"
        for pk in selected_pks:
            enc = self.client.db.get_contact_enc_key(pk)
            if enc:
                self.client.send_dm(pk, text, enc)
                count += 1
        toast(f'已发送 {count} 份邀请')

    def toggle_block(self, block):
        self.client.db.block_group(self.group_id, block)
        toast('已屏蔽' if block else '已恢复')
        self.app.root.get_screen('main').refresh_chats()
        self.load_data(0)

    def confirm_clear(self):
        ConfirmationDialog('清空确认', '确定要清空本群所有聊天记录吗？', self._do_clear).open()

    def _do_clear(self):
        self.client.db.clear_chat_history(self.group_id)
        toast('记录已清空')
        if self.app.current_chat_id == self.group_id:
            chat_screen = self.app.root.get_screen('chat')
            chat_screen.ids.msg_list.clear_widgets()
            chat_screen.load_messages()

    def confirm_exit(self):
        ConfirmationDialog('退出确认', '确定要退出并删除该群组吗？', self._do_exit).open()

    def _do_exit(self):
        self.client.db.delete_group_completely(self.group_id)
        if self.group_id in self.client.groups:
            del self.client.groups[self.group_id]
        if self.app.current_chat_id == self.group_id:
            self.app.current_chat_id = None
            self.app.root.get_screen('main').manager.current = 'main'
        toast('已退出群组')
        self.dismiss()
        self.app.root.get_screen('main').refresh_chats()

    def open_ban_list(self):
        GroupBanListWindow(self.app, self.group_id).open()

class UserProfileDialog(ModalView):

    def __init__(self, pubkey, **kwargs):
        super().__init__(**kwargs)
        self.app = MDApp.get_running_app()
        self.pubkey = pubkey
        self.client = self.app.client
        Clock.schedule_once(self.load_data, 0.1)

    def load_data(self, dt):
        info = self.client.db.get_contact_info(self.pubkey)
        name = 'User'
        if info:
            name = info[1] or 'User'
        self.ids.label_name.text = name
        av = AvatarFactory.get_avatar(self.pubkey, name, 'dm', self.client)
        av.size_hint = (1, 1)
        self.ids.avatar_box.add_widget(av)
        container = self.ids.info_list
        container.clear_widgets()
        about = ''
        website = ''
        lud16 = ''
        if info:
            if len(info) > 7:
                about = info[7]
            if len(info) > 8:
                website = info[8]
            if len(info) > 9:
                lud16 = info[9]
        npub = to_npub(self.pubkey)
        add_info_item_to_container(container, '公钥 (Public Key)', npub, copyable=True)
        if npub:
            qr_b64 = generate_qr_texture(npub)
            if qr_b64:
                qr_tex = get_kivy_image_from_base64(qr_b64)
                if qr_tex:
                    qr_img = Image(texture=qr_tex, size_hint_y=None, height=dp(200), allow_stretch=True, keep_ratio=True)
                    container.add_widget(qr_img)
        add_info_item_to_container(container, '简介 (About)', about, copyable=True)
        add_info_item_to_container(container, '网站 (Website)', website, copyable=True)
        add_info_item_to_container(container, '闪电网络', lud16, copyable=True)
        btn_box = self.ids.action_area
        btn_box.clear_widgets()
        is_friend = self.client.db.is_friend(self.pubkey)
        is_blocked = self.client.db.is_blocked(self.pubkey)
        if not is_friend:
            btn = MDRaisedButton(text='加为好友', md_bg_color=self.app.theme_cls.primary_color, font_name='GlobalFont')
            btn.bind(on_release=self.add_friend)
            btn_box.add_widget(btn)
        else:
            btn = MDFlatButton(text='删除好友', theme_text_color='Custom', text_color='red', font_name='GlobalFont')
            btn.bind(on_release=lambda x: self.confirm_del_friend())
            btn_box.add_widget(btn)
        block_text = '解除屏蔽' if is_blocked else '屏蔽用户'
        block_col = 'green' if is_blocked else 'gray'
        btn_blk = MDFlatButton(text=block_text, theme_text_color='Custom', text_color=block_col, font_name='GlobalFont')
        btn_blk.bind(on_release=lambda x: self.toggle_block(not is_blocked))
        btn_box.add_widget(btn_blk)
        btn_clr = MDFlatButton(text='清空记录', theme_text_color='Custom', text_color='orange', font_name='GlobalFont')
        btn_clr.bind(on_release=lambda x: self.confirm_clear())
        btn_box.add_widget(btn_clr)
        btn_del = MDFlatButton(text='删除会话', theme_text_color='Custom', text_color='red', font_name='GlobalFont')
        btn_del.bind(on_release=lambda x: self.confirm_delete_session())
        btn_box.add_widget(btn_del)

    def add_friend(self, *args):
        self.client.db.save_contact(self.pubkey, self.ids.label_name.text, is_friend=1)
        self.client.fetch_user_profile(self.pubkey)
        toast('已添加好友')
        self.app.root.get_screen('main').refresh_contacts()
        self.load_data(0)

    def confirm_del_friend(self):
        ConfirmationDialog('删除确认', '确定要删除该好友吗？', self._do_del_friend).open()

    def _do_del_friend(self):
        self.client.db.save_contact(self.pubkey, None, is_friend=0)
        toast('已删除好友')
        self.app.root.get_screen('main').refresh_contacts()
        self.load_data(0)

    def toggle_block(self, block):
        self.client.db.block_contact(self.pubkey, block)
        toast('已屏蔽' if block else '已恢复')
        self.app.root.get_screen('main').refresh_chats()
        self.load_data(0)

    def confirm_clear(self):
        ConfirmationDialog('清空确认', '确定要清空与该用户的所有聊天记录吗？', self._do_clear).open()

    def _do_clear(self):
        self.client.db.clear_chat_history(self.pubkey)
        toast('记录已清空')
        if self.app.current_chat_id == self.pubkey:
            self.app.root.get_screen('chat').ids.msg_list.clear_widgets()
            self.app.root.get_screen('chat').load_messages()

    def confirm_delete_session(self):
        ConfirmationDialog('删除确认', '确定要删除该会话吗？', self._do_delete_session).open()

    def _do_delete_session(self):
        self.client.db.clear_chat_history(self.pubkey)
        self.client.db.set_session_hidden(self.pubkey, is_group=False, hidden=True)
        if self.app.current_chat_id == self.pubkey:
            self.app.current_chat_id = None
            self.app.root.get_screen('main').manager.current = 'main'
        self.dismiss()
        self.app.root.get_screen('main').refresh_chats()
        toast('会话已删除')

class SelectableContactItem(OneLineAvatarIconListItem):

    def __init__(self, pk, name, toggle_cb, **kwargs):
        super().__init__(**kwargs)
        self.pk = pk
        self.text = name
        self.toggle_cb = toggle_cb
        self.is_selected = False
        app = MDApp.get_running_app()
        av = AvatarFactory.get_avatar(pk, name, 'dm', app.client)
        c = MDBoxLayout(size_hint=(None, None), size=('40dp', '40dp'))
        c.add_widget(av)
        self.add_widget(c)

    def toggle_selection(self):
        self.is_selected = not self.is_selected
        icon = 'checkbox-marked-circle' if self.is_selected else 'checkbox-blank-circle-outline'
        self.ids.check_icon.icon = icon
        self.toggle_cb(self.pk, self.is_selected)

class MultiSelectDialog(ModalView):

    def __init__(self, contacts, callback, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.9, 0.8)
        self.auto_dismiss = True
        self.callback = callback
        self.selected_pks = set()
        layout = MDCard(orientation='vertical', padding='10dp', radius=[15])
        layout.add_widget(MDLabel(text='选择联系人', font_style='H6', size_hint_y=None, height='40dp', font_name='GlobalFont'))
        scroll = Builder.load_string('\nScrollView:\n    MDList:\n        id: contact_list\n')
        self.list_container = scroll.ids.contact_list
        layout.add_widget(scroll)
        btn = MDRaisedButton(text='确定', pos_hint={'right': 1}, font_name='GlobalFont')
        btn.bind(on_release=self.confirm)
        layout.add_widget(btn)
        self.add_widget(layout)
        for c in contacts:
            pk = c['pubkey']
            name = c['name'] or pk[:8]
            item = SelectableContactItem(pk, name, self.on_toggle)
            self.list_container.add_widget(item)

    def on_toggle(self, pk, is_selected):
        if is_selected:
            self.selected_pks.add(pk)
        else:
            self.selected_pks.discard(pk)

    def confirm(self, *args):
        self.callback(list(self.selected_pks))
        self.dismiss()

class TabItem(MDBoxLayout, MDTabsBase):
    pass

class SelectSessionDialog(ModalView):

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.app = MDApp.get_running_app()
        self.client = self.app.client
        tab_recent = TabItem(title='最近')
        scroll_r = Builder.load_string('ScrollView:\n    MDList:\n        id: list')
        self._fill_recent(scroll_r.ids.list)
        tab_recent.add_widget(scroll_r)
        self.ids.tabs.add_widget(tab_recent)
        tab_friends = TabItem(title='好友')
        scroll_f = Builder.load_string('ScrollView:\n    MDList:\n        id: list')
        self._fill_friends(scroll_f.ids.list)
        tab_friends.add_widget(scroll_f)
        self.ids.tabs.add_widget(tab_friends)
        tab_groups = TabItem(title='群组')
        scroll_g = Builder.load_string('ScrollView:\n    MDList:\n        id: list')
        self._fill_groups(scroll_g.ids.list)
        tab_groups.add_widget(scroll_g)
        self.ids.tabs.add_widget(tab_groups)

    def _create_item(self, text, secondary, sid, stype, name):
        item = TwoLineAvatarIconListItem(text=text, secondary_text=secondary)
        item.bind(on_release=lambda x: self.on_select(sid, stype, name))
        avatar = AvatarFactory.get_avatar(sid, name, 'group' if stype == 'group' else 'dm', self.client)
        container = LeftAvatarContainer(size_hint=(None, None), size=(40, 40))
        container.add_widget(avatar)
        item.add_widget(container)
        return item

    def _fill_recent(self, container):
        sessions = self.client.db.get_session_list()
        for s in sessions:
            stype = 'group' if s['type'] == 'group' else 'dm'
            item = self._create_item(s['name'], 'Session', s['id'], stype, s['name'])
            container.add_widget(item)

    def _fill_friends(self, container):
        friends = self.client.db.get_friends()
        for f in friends:
            name = f['name'] or f['pubkey'][:8]
            item = self._create_item(name, 'Friend', f['pubkey'], 'dm', name)
            container.add_widget(item)

    def _fill_groups(self, container):
        for gid, info in self.client.groups.items():
            item = self._create_item(info['name'], 'Group', gid, 'group', info['name'])
            container.add_widget(item)

    def on_select(self, sid, stype, name):
        self.callback(sid, stype, name)
        self.dismiss()

class ForwardConfirmDialog(ModalView):
    target_name = StringProperty('')
    msg_preview = StringProperty('')

    def __init__(self, target_name, msg_preview, on_confirm, **kwargs):
        self.target_name = target_name
        self.msg_preview = msg_preview
        self.on_confirm_cb = on_confirm
        super().__init__(**kwargs)

    def confirm(self):
        self.on_confirm_cb()
        self.dismiss()

class HistoryViewerDialog(ModalView):

    def __init__(self, history_data, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self.auto_dismiss = True
        self.background_color = MDApp.get_running_app().theme_cls.bg_dark
        self.history_data = history_data
        layout = MDBoxLayout(orientation='vertical')
        top_bar = MDBoxLayout(size_hint_y=None, height='50dp', padding='10dp', md_bg_color=(0.15, 0.15, 0.15, 1))
        title = self.history_data.get('title', '聊天记录')
        top_bar.add_widget(MDLabel(text=title, font_style='H6', theme_text_color='Custom', text_color=(1, 1, 1, 1), font_name='GlobalFont'))
        close_btn = MDIconButton(icon='close', theme_text_color='Custom', text_color=(1, 1, 1, 1))
        close_btn.bind(on_release=lambda x: self.dismiss())
        top_bar.add_widget(close_btn)
        layout.add_widget(top_bar)
        scroll = Builder.load_string('\nScrollView:\n    MDBoxLayout:\n        id: container\n        orientation: "vertical"\n        adaptive_height: True\n        padding: "15dp"\n        spacing: "20dp"\n')
        self.container = scroll.ids.container
        self._populate_list()
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _populate_list(self):
        items = self.history_data.get('items', [])
        for item in items:
            name = item.get('n', 'User')
            ts = item.get('t', 0)
            content = item.get('c', '')
            img_b64 = item.get('i')
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            row = MDBoxLayout(orientation='vertical', adaptive_height=True, spacing='5dp')
            header = MDLabel(text=f'{name}  {time_str}', font_style='Caption', theme_text_color='Hint', adaptive_height=True, font_name='GlobalFont')
            row.add_widget(header)
            if content and content.strip().startswith('{'):
                try:
                    d = json.loads(content)
                    if d.get('type') == 'history':
                        sub_title = d.get('title', 'Chat History')
                        card = MDCard(orientation='vertical', padding='10dp', radius=[4], md_bg_color=(0.2, 0.2, 0.2, 1), elevation=0, adaptive_height=True, on_release=lambda x, data=d: HistoryViewerDialog(data).open())
                        card.add_widget(MDLabel(text=f'📂 {sub_title}', theme_text_color='Custom', text_color=(0.9, 0.9, 0.9, 1), font_name='GlobalFont', adaptive_height=True))
                        card.add_widget(MDLabel(text='点击查看详情', font_style='Caption', theme_text_color='Hint', font_name='GlobalFont', adaptive_height=True))
                        row.add_widget(card)
                        content = ''
                except:
                    pass
            if img_b64:
                tex = get_kivy_image_from_base64(img_b64)
                if tex:
                    w, h = tex.size
                    max_w = dp(250)
                    max_h = dp(300)
                    scale = 1.0
                    if w > max_w:
                        scale = max_w / w
                    if h * scale > max_h:
                        scale = max_h / h
                    display_w = w * scale
                    display_h = h * scale
                    clk_img = ClickableImage(texture=tex, viewer_callback=lambda t: FullScreenImageViewer(texture=t).open(), size_hint=(None, None), size=(display_w, display_h), allow_stretch=True, keep_ratio=True)
                    row.add_widget(clk_img)
            if content:
                txt_lbl = MDLabel(text=content, theme_text_color='Primary', adaptive_height=True, font_name='GlobalFont')
                row.add_widget(txt_lbl)
            sep = MDBoxLayout(size_hint_y=None, height='1dp', md_bg_color=(0.3, 0.3, 0.3, 1))
            self.container.add_widget(row)
            self.container.add_widget(sep)

class SearchMessageDialog(ModalView):

    def __init__(self, chat_id, **kwargs):
        super().__init__(**kwargs)
        self.chat_id = chat_id
        self.app = MDApp.get_running_app()
        self.size_hint = (0.9, 0.8)
        self.auto_dismiss = True
        card = MDCard(orientation='vertical', padding='10dp', radius=[15], md_bg_color=self.app.theme_cls.bg_dark)
        search_box = MDBoxLayout(size_hint_y=None, height='50dp', spacing='10dp')
        self.tf_search = MDTextField(hint_text='输入关键词...', mode='round', font_name='GlobalFont')
        btn_search = MDIconButton(icon='magnify', on_release=lambda x: self.do_search())
        search_box.add_widget(self.tf_search)
        search_box.add_widget(btn_search)
        card.add_widget(search_box)
        scroll = Builder.load_string('\nScrollView:\n    MDList:\n        id: result_list\n')
        self.result_list = scroll.ids.result_list
        card.add_widget(scroll)
        btn_close = MDFlatButton(text='关闭', on_release=lambda x: self.dismiss(), font_name='GlobalFont')
        card.add_widget(btn_close)
        self.add_widget(card)

    def do_search(self):
        keyword = self.tf_search.text.strip()
        if not keyword:
            return
        self.result_list.clear_widgets()
        from backend.client_persistent import OFFICIAL_GROUP_CONFIG
        exclude = OFFICIAL_GROUP_CONFIG['id'] if self.chat_id is None else None
        results = self.app.client.db.search_messages(keyword, specific_target_id=self.chat_id, limit=50, exclude_gid=exclude)
        if not results:
            toast('无搜索结果')
            return
        for res in results:
            msg_id = res[0]
            content = res[3]
            ts = res[4]
            sender_name = res[5]
            display_text = content
            if content.startswith('{'):
                try:
                    display_text = json.loads(content).get('text', '[图片/卡片]')
                except:
                    pass
            if len(display_text) > 30:
                display_text = display_text[:30] + '...'
            time_str = datetime.fromtimestamp(ts).strftime('%m-%d %H:%M')
            item = TwoLineListItem(text=f'{sender_name}: {display_text}', secondary_text=time_str, font_style='Caption', on_release=lambda x, m=msg_id, g=res[1]: self.on_result_click(g, m))
            self.result_list.add_widget(item)

    def on_result_click(self, group_id, msg_id):
        self.dismiss()
        chat_screen = self.app.root.get_screen('chat')
        if self.app.current_chat_id != group_id:
            name = 'Chat'
            ctype = 'dm'
            if group_id in self.app.client.groups:
                name = self.app.client.groups[group_id]['name']
                ctype = 'group'
            else:
                name = self.app.client.db.get_contact_name(group_id) or 'User'
            self.app.root.get_screen('main').open_chat(group_id, name, ctype)
        Clock.schedule_once(lambda dt: chat_screen.jump_to_message(msg_id), 0.5)

class SimpleFilePicker(ModalView):

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback
        self.size_hint = (0.9, 0.8)
        self.auto_dismiss = True
        self.background_color = (0, 0, 0, 0.8)
        layout = MDCard(orientation='vertical', padding='15dp', spacing='10dp', radius=[15], md_bg_color=MDApp.get_running_app().theme_cls.bg_dark)
        layout.add_widget(MDLabel(text='选择备份文件 (APP私有目录)', font_style='H6', size_hint_y=None, height='40dp', font_name='GlobalFont'))
        scroll = Builder.load_string('\nScrollView:\n    MDList:\n        id: file_list\n')
        self.list_container = scroll.ids.file_list
        layout.add_widget(scroll)
        self._scan_files()
        btn_sys = MDRaisedButton(text='📂 打开系统文件选择器 (推荐)', size_hint_x=1, on_release=self._open_system_picker)
        layout.add_widget(btn_sys)
        btn = MDFlatButton(text='取消', pos_hint={'right': 1}, font_name='GlobalFont', on_release=self.dismiss)
        layout.add_widget(btn)
        self.add_widget(layout)

    def _open_system_picker(self, *args):
        self.dismiss()
        if platform == 'android':
            NativeFilePicker(self.callback).open()
        else:
            toast('PC端请直接使用弹窗')

    def _scan_files(self):
        import glob
        files = []
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            ext_file_dir = context.getExternalFilesDir(None).getAbsolutePath()
            target_dirs = [ext_file_dir, '/storage/emulated/0/Download']
            for d in target_dirs:
                if d and os.path.exists(d):
                    pattern = os.path.join(d, '*.dgbk')
                    files.extend(glob.glob(pattern))
        except:
            if platform != 'android':
                files = glob.glob(os.path.expanduser('~/Downloads/*.dgbk'))
        self.list_container.clear_widgets()
        if not files:
            self.list_container.add_widget(OneLineAvatarIconListItem(text='私有目录无文件，请使用系统选择器'))
            return
        for f_path in files:
            f_name = os.path.basename(f_path)
            item = TwoLineAvatarIconListItem(text=f_name, secondary_text=f_path, on_release=lambda x, p=f_path: self._select_file(p))
            icon = IconLeftWidget(icon='file-document-outline')
            item.add_widget(icon)
            self.list_container.add_widget(item)

    def _select_file(self, path):
        self.dismiss()
        if self.callback:
            self.callback([path])

class NativeFilePicker:

    def __init__(self, callback):
        self.callback = callback
        self._request_code = 4242

    def open(self):
        try:
            android_activity.bind(on_activity_result=self._on_activity_result)
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType('*/*')
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            currentActivity = cast('android.app.Activity', PythonActivity.mActivity)
            currentActivity.startActivityForResult(intent, self._request_code)
        except Exception as e:
            toast(f'System Picker Error: {e}')
            SimpleFilePicker(self.callback).open()

    def _on_activity_result(self, requestCode, resultCode, intent):
        if requestCode != self._request_code:
            return
        android_activity.unbind(on_activity_result=self._on_activity_result)
        if resultCode != -1:
            toast('取消选择')
            return
        try:
            uri = intent.getData()
            if not uri:
                return
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            content_resolver = context.getContentResolver()
            input_stream = content_resolver.openInputStream(uri)
            app_root = MDApp.get_running_app().user_data_dir
            temp_dir = os.path.join(app_root, 'restore_temp')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            temp_filename = f'restore_{int(datetime.now().timestamp())}.dgbk'
            temp_path = os.path.join(temp_dir, temp_filename)
            FileUtils = autoclass('android.os.FileUtils')
            buffer = bytearray(1024 * 1024)
            with open(temp_path, 'wb') as f:
                while True:
                    read_len = input_stream.read(buffer)
                    if read_len == -1:
                        break
                    f.write(buffer[:read_len])
            input_stream.close()
            Clock.schedule_once(lambda dt: self.callback([temp_path]), 0)
        except Exception as e:
            toast(f'Read File Error: {e}')
            import traceback
            traceback.print_exc()