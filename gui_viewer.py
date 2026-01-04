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

import customtkinter as ctk
from PIL import Image
import base64
from io import BytesIO
import tkinter as tk
from tkinter import messagebox

class ImageViewer(ctk.CTkToplevel):

    def __init__(self, parent_app, image_list, start_index=0):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.image_list = image_list
        self.current_index = start_index
        self.title(f'查看原图 ({start_index + 1}/{len(image_list)})')
        w, h = (900, 700)
        if parent_app and hasattr(parent_app, 'winfo_x'):
            try:
                parent_app.update_idletasks()
                x = parent_app.winfo_x() + (parent_app.winfo_width() - w) // 2
                y = parent_app.winfo_y() + (parent_app.winfo_height() - h) // 2
                x = max(0, x)
                y = max(0, y)
                self.geometry(f'{w}x{h}+{x}+{y}')
            except:
                self.geometry(f'{w}x{h}')
        else:
            self.geometry(f'{w}x{h}')
        self.attributes('-topmost', True)
        self.hide_timer = None
        self.main_frame = ctk.CTkFrame(self, fg_color='black')
        self.main_frame.pack(fill='both', expand=True)
        self.img_label = ctk.CTkLabel(self.main_frame, text='', text_color='white')
        self.img_label.pack(expand=True, fill='both')
        btn_color = '#2B2B2B'
        hover_color = '#505050'
        self.btn_prev = ctk.CTkButton(self.main_frame, text='<', width=60, height=100, fg_color=btn_color, hover_color=hover_color, font=('Arial', 24, 'bold'), corner_radius=8, command=self.prev_img)
        self.btn_next = ctk.CTkButton(self.main_frame, text='>', width=60, height=100, fg_color=btn_color, hover_color=hover_color, font=('Arial', 24, 'bold'), corner_radius=8, command=self.next_img)
        self.btn_save = ctk.CTkButton(self.main_frame, text='💾 保存图片', width=120, height=40, fg_color=btn_color, hover_color=hover_color, font=('Arial', 14, 'bold'), corner_radius=20, command=self.save_current)
        self.bind('<Motion>', self.on_mouse_activity)
        self.bind('<Key>', self.on_key)
        self.show_current_image()
        self.on_mouse_activity(None)

    def show_current_image(self):
        idx = self.current_index
        img_data = self.image_list[idx]
        self.title(f'查看原图 ({idx + 1}/{len(self.image_list)})')
        try:
            img_bytes = base64.b64decode(img_data['image_b64'])
            pil_img = Image.open(BytesIO(img_bytes))
            screen_w = self.winfo_screenwidth() * 0.9
            screen_h = self.winfo_screenheight() * 0.9
            img_w, img_h = pil_img.size
            ratio = min(screen_w / img_w, screen_h / img_h)
            if ratio < 1.0:
                new_size = (int(img_w * ratio), int(img_h * ratio))
                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.img_label.configure(image=ctk_img)
            self.img_label.image = ctk_img
            self.update_button_visibility()
        except Exception as e:
            self.img_label.configure(image=None, text=f'加载失败: {e}')

    def prev_img(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()

    def next_img(self):
        if self.current_index < len(self.image_list) - 1:
            self.current_index += 1
            self.show_current_image()

    def save_current(self):
        idx = self.current_index
        b64 = self.image_list[idx]['image_b64']
        self.parent_app.save_image_local(base64.b64decode(b64), parent=self)

    def hide_controls(self):
        self.btn_prev.place_forget()
        self.btn_next.place_forget()
        self.btn_save.place_forget()

    def update_button_visibility(self):
        if self.current_index > 0:
            self.btn_prev.place(relx=0.02, rely=0.5, anchor='w')
            self.btn_prev.lift()
        else:
            self.btn_prev.place_forget()
        if self.current_index < len(self.image_list) - 1:
            self.btn_next.place(relx=0.98, rely=0.5, anchor='e')
            self.btn_next.lift()
        else:
            self.btn_next.place_forget()
        self.btn_save.place(relx=0.5, rely=0.92, anchor='s')
        self.btn_save.lift()

    def on_mouse_activity(self, event):
        self.update_button_visibility()
        if self.hide_timer:
            self.after_cancel(self.hide_timer)
        self.hide_timer = self.after(2500, self.hide_controls)

    def on_key(self, event):
        self.on_mouse_activity(None)
        if event.keysym == 'Left':
            self.prev_img()
        elif event.keysym == 'Right':
            self.next_img()