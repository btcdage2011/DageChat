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
import time
from datetime import datetime
from kivy.utils import platform
from kivymd.toast import toast
from kivymd.app import MDApp
from kivy.uix.modalview import ModalView
from kivy.uix.image import Image
from kivy.uix.scatter import Scatter
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivymd.uix.button import MDIconButton

class ZoomableImage(Scatter):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_rotation = False
        self.do_scale = True
        self.do_translation = True
        self.auto_bring_to_front = False
        self.scale_min = 1.0
        self.scale_max = 4.0

    def on_touch_down(self, touch):
        if touch.is_double_tap:
            self.scale = 1.0
            self.pos = (0, 0)
            return True
        return super().on_touch_down(touch)

class FullScreenImageViewer(ModalView):

    def __init__(self, texture, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (1, 1)
        self.background_color = (0, 0, 0, 1)
        self.auto_dismiss = False
        self.texture = texture
        self.layout = FloatLayout()
        self.scatter = ZoomableImage(size_hint=(None, None))
        win_w, win_h = (Window.width, Window.height)
        img_w, img_h = texture.size
        ratio = min(win_w / img_w, win_h / img_h)
        display_w = img_w * ratio
        display_h = img_h * ratio
        self.scatter.size = (display_w, display_h)
        self.scatter.center = (win_w / 2, win_h / 2)
        self.img = Image(texture=texture, size=self.scatter.size, nocache=True)
        self.scatter.add_widget(self.img)
        self.layout.add_widget(self.scatter)
        close_btn = MDIconButton(icon='close', theme_text_color='Custom', text_color=(1, 1, 1, 1), icon_size='32sp', pos_hint={'right': 0.98, 'top': 0.98}, on_release=self.dismiss)
        self.layout.add_widget(close_btn)
        save_btn = MDIconButton(icon='download', theme_text_color='Custom', text_color=(1, 1, 1, 1), icon_size='32sp', pos_hint={'right': 0.98, 'bottom': 0.05}, on_release=self.save_image)
        self.layout.add_widget(save_btn)
        self.add_widget(self.layout)

    def save_image(self, *args):
        if not self.texture:
            return
        pixels = self.texture.pixels
        if not pixels:
            toast('图片数据为空')
            return
        from PIL import Image as PILImage
        from io import BytesIO
        try:
            size = self.texture.size
            pil_img = PILImage.frombytes('RGBA', size, pixels)
            filename = f"IMG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            if platform == 'android':
                save_dir = '/storage/emulated/0/Pictures/DageChat'
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)
                full_path = os.path.join(save_dir, filename)
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                pil_img.save(full_path, quality=95)
                toast(f'已保存至相册 (DageChat)')
                try:
                    from jnius import autoclass
                    MediaScannerConnection = autoclass('android.media.MediaScannerConnection')
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    activity = PythonActivity.mActivity
                    MediaScannerConnection.scanFile(activity, [full_path], None, None)
                except:
                    pass
            else:
                save_dir = os.path.expanduser('~/Downloads')
                full_path = os.path.join(save_dir, filename)
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                pil_img.save(full_path, quality=95)
                toast(f'已保存: {full_path}')
        except Exception as e:
            toast(f'保存失败: {e}')