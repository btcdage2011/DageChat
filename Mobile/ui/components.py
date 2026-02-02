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

import base64
import qrcode
import os
import json
from io import BytesIO
from datetime import datetime
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.list import ILeftBodyTouch
import re
import webbrowser
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.app import MDApp

class CopyableLabel(TextInput):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = (1, 1, 1, 1)
        self.readonly = True
        self.font_name = 'GlobalFont'
        self.font_size = '16sp'
        self.padding = [0, 0]
        self.cursor_color = (0, 0, 0, 0)
        self.selection_color = (0.5, 0.5, 1, 0.4)
        self.use_bubble = True
        self.use_handles = True
        self.allow_copy = True

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        else:
            if self.focus or self.selection_text:
                self._hard_deselect()
            return super().on_touch_down(touch)

    def copy(self, data=''):
        super().copy(data)
        Clock.schedule_once(lambda dt: self._hard_deselect(), 0.1)

    def _hard_deselect(self):
        self.cancel_selection()
        self.focus = False
        if hasattr(self, '_hide_cut_copy_paste'):
            self._hide_cut_copy_paste()
        if hasattr(self, '_hide_handles'):
            self._hide_handles()

def get_kivy_image_from_base64(b64_str):
    if not b64_str:
        return None
    try:
        if ',' in b64_str[:30]:
            b64_str = b64_str.split(',', 1)[1]
        data = base64.b64decode(b64_str)
        bio = BytesIO(data)
        im = CoreImage(bio, ext='png')
        return im.texture
    except:
        return None

def generate_qr_texture(data):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f'QR Gen Error: {e}')
        return None

class LeftAvatarContainer(ILeftBodyTouch, MDBoxLayout):
    adaptive_width = True

class CircularAvatarImage(ButtonBehavior, Widget):

    def __init__(self, texture, tap_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.texture = texture
        self.tap_callback = tap_callback
        with self.canvas:
            Color(1, 1, 1, 1)
            self.rect = RoundedRectangle(texture=self.texture, pos=self.pos, size=self.size, radius=[dp(20)])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        self.rect.radius = [min(self.size[0], self.size[1]) / 2]

    def on_release(self):
        if self.tap_callback:
            self.tap_callback()

class TextAvatarCard(MDCard):

    def __init__(self, text, bg_color, tap_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(40), dp(40))
        self.radius = [dp(20)]
        self.md_bg_color = bg_color
        self.elevation = 0
        self.tap_callback = tap_callback
        label = MDLabel(text=text, halign='center', valign='center', theme_text_color='Custom', text_color=(1, 1, 1, 1), font_style='H6', bold=True, font_name='GlobalFont')
        self.add_widget(label)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.tap_callback:
                self.tap_callback()
                return True
        return super().on_touch_down(touch)

def create_avatar_card(text, bg_color):
    card = MDCard(size_hint=(None, None), size=(dp(40), dp(40)), radius=[dp(20)], md_bg_color=bg_color, elevation=0)
    label = MDLabel(text=text, halign='center', valign='center', theme_text_color='Custom', text_color=(1, 1, 1, 1), font_style='H6', bold=True, font_name='GlobalFont')
    card.add_widget(label)
    return card

class AvatarFactory:
    _texture_cache = {}

    @staticmethod
    def get_avatar(cid, name, ctype, client=None, callback=None):
        texture = None
        if cid in AvatarFactory._texture_cache:
            texture = AvatarFactory._texture_cache[cid]
        elif client:
            b64 = None
            try:
                info = client.db.get_contact_info(cid)
                if info and len(info) > 6 and info[6]:
                    b64 = info[6]
            except:
                pass
            if b64:
                texture = get_kivy_image_from_base64(b64)
                if texture:
                    AvatarFactory._texture_cache[cid] = texture
        if texture:
            return CircularAvatarImage(texture=texture, tap_callback=callback)
        if ctype == 'ghost':
            mask_path = 'assets/ghost_mask.png'
            if os.path.exists(mask_path):
                try:
                    if 'ghost_mask' not in AvatarFactory._texture_cache:
                        AvatarFactory._texture_cache['ghost_mask'] = CoreImage(mask_path).texture
                    return CircularAvatarImage(texture=AvatarFactory._texture_cache['ghost_mask'], tap_callback=callback)
                except:
                    pass
            return TextAvatarCard('⚡', (0.5, 0, 0.5, 1), tap_callback=callback)
        if ctype == 'group':
            return TextAvatarCard('📢', (0, 0.5, 0, 1), tap_callback=callback)
        letter = name[0].upper() if name else '?'
        return TextAvatarCard(letter, (0.2, 0.2, 0.8, 1), tap_callback=callback)

    @staticmethod
    def clear_cache(cid):
        if cid in AvatarFactory._texture_cache:
            del AvatarFactory._texture_cache[cid]

class ClickableImage(Image):

    def __init__(self, texture, viewer_callback, menu_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.texture = texture
        self.viewer_callback = viewer_callback
        self.menu_callback = menu_callback
        self._long_press_event = None
        self._is_long_press_triggered = False

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._is_long_press_triggered = False
            if self.menu_callback:
                self._long_press_event = Clock.schedule_once(lambda dt: self._trigger_long_press(touch), 0.5)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            if self._is_long_press_triggered:
                return True
            if self._long_press_event:
                self._long_press_event.cancel()
                self._long_press_event = None
            if self.viewer_callback:
                self.viewer_callback(self.texture)
            return True
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        if self._long_press_event and (abs(touch.dx) > 10 or abs(touch.dy) > 10):
            self._long_press_event.cancel()
            self._long_press_event = None
        return super().on_touch_move(touch)

    def _trigger_long_press(self, touch):
        self._is_long_press_triggered = True
        self._long_press_event = None
        if self.menu_callback:
            self.menu_callback(self)

class LongPressCard(MDCard):

    def __init__(self, long_press_callback, **kwargs):
        super().__init__(**kwargs)
        self.long_press_callback = long_press_callback
        self._long_press_event = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._long_press_event = Clock.schedule_once(lambda dt: self._on_long_press(touch), 0.35)
            return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        if self._long_press_event and (abs(touch.dx) > 10 or abs(touch.dy) > 10):
            self._long_press_event.cancel()
            self._long_press_event = None
        return super().on_touch_move(touch)

    def _on_long_press(self, touch):
        if self.long_press_callback:
            self.long_press_callback(self, touch)

class MessageBubble(MDBoxLayout):

    def __init__(self, text='', is_me=False, sender_name='', avatar_widget=None, image_texture=None, viewer_callback=None, menu_callback=None, reply_info=None, timestamp=0, avatar_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.adaptive_height = True
        self.spacing = dp(8)
        self.padding = [dp(10), dp(5)]
        self.checkbox = MDCheckbox(size_hint=(None, None), size=(0, 0), width=0, active=False, opacity=0, disabled=True)
        self.add_widget(self.checkbox)
        avatar_container = MDBoxLayout(size_hint=(None, None), size=(dp(40), dp(40)))
        avatar_container.pos_hint = {'top': 1}
        if avatar_widget:
            avatar_container.add_widget(avatar_widget)
        else:
            fallback = create_avatar_card('?', (0.5, 0.5, 0.5, 1))
            if avatar_callback:
                pass
            avatar_container.add_widget(fallback)
        bg_color = (0.12, 0.42, 0.65, 1) if is_me else (0.2, 0.2, 0.2, 1)
        content_card = LongPressCard(long_press_callback=menu_callback, radius=[dp(10)], md_bg_color=bg_color, elevation=0, size_hint=(None, None), padding=dp(8))
        content_card.width = dp(240)
        inner_box = MDBoxLayout(orientation='vertical', adaptive_height=True, spacing=dp(2))
        self.inner_box = inner_box
        time_str = ''
        if timestamp:
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        header_text = ''
        if not is_me and sender_name:
            header_text = f'{sender_name}  {time_str}'
        elif is_me:
            header_text = time_str
        if header_text:
            header_lbl = MDLabel(text=header_text, font_style='Caption', theme_text_color='Custom', text_color=(0.7, 0.7, 0.7, 1), adaptive_height=True, font_name='GlobalFont', font_size='10sp')
            inner_box.add_widget(header_lbl)
        if reply_info:
            quote_frame = MDBoxLayout(orientation='horizontal', md_bg_color=(0, 0, 0, 0.2), radius=[dp(4)], padding=dp(5), spacing=dp(5), adaptive_height=True, size_hint_x=1)
            reply_img_b64 = reply_info.get('image_b64')
            if reply_img_b64:
                q_tex = get_kivy_image_from_base64(reply_img_b64)
                if q_tex:
                    q_img = Image(texture=q_tex, size_hint=(None, None), size=(dp(40), dp(40)), allow_stretch=True, keep_ratio=True)
                    quote_frame.add_widget(q_img)
            q_text = reply_info.get('text', '')
            q_sender = reply_info.get('sender', 'User')
            if not q_text and reply_img_b64:
                q_text = '[图片]'
            elif len(q_text) > 40:
                q_text = q_text[:40] + '...'
            q_lbl = MDLabel(text=f'{q_sender}: {q_text}', font_style='Caption', theme_text_color='Custom', text_color=(0.8, 0.8, 0.8, 1), size_hint_y=None, size_hint_x=1, font_name='GlobalFont', shorten=True, shorten_from='right')
            q_lbl.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
            quote_frame.add_widget(q_lbl)
            inner_box.add_widget(quote_frame)
        is_history_card = False
        if text and text.strip().startswith('{'):
            try:
                data = json.loads(text)
                if data.get('type') == 'history':
                    is_history_card = True
                    self._render_history_card(inner_box, data)
            except:
                pass
        if not is_history_card:
            if image_texture:
                img_w, img_h = image_texture.size
                max_w_limit = dp(220)
                max_h_limit = dp(300)
                scale = 1.0
                if img_w > max_w_limit:
                    scale = max_w_limit / img_w
                if img_h * scale > max_h_limit:
                    scale = max_h_limit / img_h
                final_w = img_w * scale
                final_h = img_h * scale

                def _img_menu_adapter(caller):
                    if menu_callback:
                        menu_callback(caller, None)
                img_widget = ClickableImage(texture=image_texture, viewer_callback=viewer_callback, menu_callback=_img_menu_adapter, size_hint=(None, None), size=(final_w, final_h), allow_stretch=True, keep_ratio=True, nocache=True)
                inner_box.add_widget(img_widget)
            if text:
                msg_input = CopyableLabel(text=text, size_hint_y=None)

                def update_text_height(instance, width):
                    instance.height = instance.minimum_height
                msg_input.bind(width=update_text_height)
                Clock.schedule_once(lambda dt: update_text_height(msg_input, msg_input.width), 0.05)
                inner_box.add_widget(msg_input)
                try:
                    urls = re.findall('(https?://[^\\s]+)', text)
                    dage_links = re.findall('(dage://invite/[^\\s]+)', text)
                    if dage_links or urls:
                        app = MDApp.get_running_app()
                        if dage_links and app:
                            main_screen = app.root.get_screen('main')
                            for d_link in dage_links:
                                is_ghost = '/ghost/' in d_link
                                btn_text = '⚡ 加入共享群' if is_ghost else '🚀 加入群聊'
                                btn_color = (0.5, 0, 0.5, 1) if is_ghost else app.theme_cls.primary_color
                                btn = MDRaisedButton(text=btn_text, size_hint_x=1, height=dp(36), font_name='GlobalFont', md_bg_color=btn_color)
                                btn.bind(on_release=lambda x, l=d_link: main_screen.process_join_link(l))
                                inner_box.add_widget(btn)
                        if urls:
                            for url in urls:
                                display_url = url[:25] + '...' if len(url) > 25 else url
                                btn = MDFlatButton(text=f'🔗 {display_url}', size_hint_x=1, height=dp(30), theme_text_color='Custom', text_color=(0.4, 0.8, 1, 1), font_name='GlobalFont')
                                btn.bind(on_release=lambda x, u=url: webbrowser.open(u))
                                inner_box.add_widget(btn)
                except Exception as e:
                    print(f'Link parse error: {e}')
        content_card.add_widget(inner_box)

        def update_card_height(*args):
            content_card.height = inner_box.height + dp(20)
        inner_box.bind(height=update_card_height)
        if is_me:
            self.add_widget(MDBoxLayout())
            self.add_widget(content_card)
            self.add_widget(avatar_container)
        else:
            self.add_widget(avatar_container)
            self.add_widget(content_card)
            self.add_widget(MDBoxLayout())

    def set_recalled(self):
        if hasattr(self, 'inner_box'):
            self.inner_box.clear_widgets()
            lbl = MDLabel(text='🔒 消息已撤回', theme_text_color='Hint', font_style='Caption', halign='center', font_name='GlobalFont', size_hint_y=None, height=dp(20))
            self.inner_box.add_widget(lbl)

    def set_select_mode(self, active):
        if active:
            self.checkbox.opacity = 1
            self.checkbox.disabled = False
            self.checkbox.size = (dp(40), dp(40))
            self.checkbox.width = dp(40)
        else:
            self.checkbox.opacity = 0
            self.checkbox.disabled = True
            self.checkbox.size = (0, 0)
            self.checkbox.width = 0
            self.checkbox.active = False

    def _render_history_card(self, container, data):
        title = data.get('title', '聊天记录')
        items = data.get('items', [])
        card = MDCard(orientation='vertical', md_bg_color=(1, 1, 1, 1), radius=[dp(6)], padding=dp(10), spacing=dp(4), elevation=1, size_hint_y=None, on_release=lambda x: self._open_history_viewer(data))
        display_count = min(len(items), 4)
        content_h = display_count * dp(22)
        if len(items) > 4:
            content_h += dp(15)
        total_h = dp(30) + dp(2) + content_h + dp(20) + dp(20)
        card.height = total_h
        title_lbl = MDLabel(text=title, font_style='Subtitle1', theme_text_color='Custom', text_color=(0, 0, 0, 1), size_hint_y=None, height=dp(30), font_name='GlobalFont', bold=True)
        card.add_widget(title_lbl)
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(0.85, 0.85, 0.85, 1)
            RoundedRectangle(pos=sep.pos, size=sep.size)
        card.add_widget(sep)
        for item in items[:4]:
            n = item.get('n', 'User')
            c = item.get('c', '')
            if item.get('i') and (not c.startswith('[图片]')):
                c = f'[图片] {c}'
            if len(c) > 18:
                c = c[:18] + '...'
            row_lbl = MDLabel(text=f'{n}: {c}', font_style='Caption', theme_text_color='Custom', text_color=(0.4, 0.4, 0.4, 1), size_hint_y=None, height=dp(20), font_name='GlobalFont', shorten=True, shorten_from='right')
            card.add_widget(row_lbl)
        if len(items) > 4:
            ell = MDLabel(text='...', font_style='Caption', theme_text_color='Hint', size_hint_y=None, height=dp(15))
            card.add_widget(ell)
        bot = MDLabel(text='Chat History', font_style='Overline', theme_text_color='Hint', size_hint_y=None, height=dp(20))
        card.add_widget(bot)
        container.add_widget(card)

    def _open_history_viewer(self, data):
        from ui.dialogs import HistoryViewerDialog
        HistoryViewerDialog(data).open()