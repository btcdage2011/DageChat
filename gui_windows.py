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

import configparser
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
import os
import glob
import sys
import base64
from PIL import Image
from io import BytesIO
import nacl.encoding
from key_utils import to_hex_privkey, to_hex_pubkey, to_npub, to_nsec
import time
import threading
import websocket
from datetime import datetime
import json
from lang_utils import tr, save_language_config, CURRENT_LANG
import ctypes
from PIL import Image, ImageEnhance, ImageTk, ImageGrab

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
                    try:
                        os.makedirs(custom_path, exist_ok=True)
                    except:
                        print(f'⚠️ [Setup] 无法创建自定义路径: {custom_path}')
                        return default_root
                if os.access(custom_path, os.W_OK):
                    print(f'📂 [Setup] 使用自定义数据路径: {custom_path}')
                    return custom_path
                else:
                    print(f'⚠️ [Setup] 自定义路径无写权限: {custom_path}')
        except Exception as e:
            print(f'❌ [Setup] 读取 setup.ini 失败: {e}')
    return default_root

class SafeToplevel(ctk.CTkToplevel):

    def __init__(self, *args, **kwargs):
        self._is_destroyed = False
        self._pending_tasks = []
        if args and hasattr(args[0], 'show_toast'):
            self.parent_app = args[0]
        else:
            self.parent_app = kwargs.get('parent_app', None)
        super().__init__(*args, **kwargs)
        self.bind('<Destroy>', self._on_destroy_event)
        self._focus_task = self.after(200, self._safe_focus)
        self._pending_tasks.append(self._focus_task)

    def center_window(self, w, h):
        if self.parent_app and hasattr(self.parent_app, 'winfo_x'):
            try:
                self.parent_app.update_idletasks()
                p_x = self.parent_app.winfo_x()
                p_y = self.parent_app.winfo_y()
                p_w = self.parent_app.winfo_width()
                p_h = self.parent_app.winfo_height()
                x = p_x + (p_w - w) // 2
                y = p_y + (p_h - h) // 2
                x = max(0, x)
                y = max(0, y)
                self.geometry(f'{w}x{h}+{x}+{y}')
                return
            except:
                pass
        self.geometry(f'{w}x{h}')

    def after(self, ms, func=None, *args):
        if self._is_destroyed:
            return 'ignore'
        if func:
            id = super().after(ms, func, *args)
            self._pending_tasks.append(id)
            return id
        return super().after(ms, func, *args)

    def _on_destroy_event(self, event):
        if event.widget == self:
            self._is_destroyed = True
            self._cancel_all_tasks()

    def _cancel_all_tasks(self):
        for t_id in self._pending_tasks:
            try:
                self.after_cancel(t_id)
            except:
                pass
        self._pending_tasks.clear()

    def destroy(self):
        self._is_destroyed = True
        self._cancel_all_tasks()
        try:
            self.grab_release()
        except:
            pass
        try:
            super().destroy()
        except:
            pass

    def _safe_focus(self):
        if self._is_destroyed:
            return
        try:
            if self.winfo_exists():
                self.grab_set()
                self.focus_force()
        except:
            pass

    def focus_set(self):
        if not self._is_destroyed:
            try:
                super().focus_set()
            except:
                pass

    def grab_set(self):
        if not self._is_destroyed:
            try:
                super().grab_set()
            except:
                pass

    def show_toast(self, message, duration=2000):
        if self.parent_app and hasattr(self.parent_app, 'show_toast'):
            self.parent_app.show_toast(message, duration, master=self)

class InputWindow(SafeToplevel):

    def __init__(self, parent_app, title, prompt):
        super().__init__(parent_app)
        self.title(title)
        self.value = None
        self.center_window(350, 180)
        self.attributes('-topmost', True)
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=prompt, font=('Microsoft YaHei UI', 12)).pack(pady=(20, 10))
        self.entry = ctk.CTkEntry(self, width=280)
        self.entry.pack(pady=5)
        self.entry.bind('<Return>', lambda e: self.on_ok())
        self.entry.focus_force()
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text=tr('BTN_CONFIRM'), width=100, command=self.on_ok).pack(side='left', padx=10)
        ctk.CTkButton(btn_frame, text=tr('BTN_CANCEL'), width=100, fg_color='#555', command=self.on_cancel).pack(side='left', padx=10)
        self.wait_window()

    def on_ok(self):
        self.value = self.entry.get()
        self.destroy()

    def on_cancel(self):
        self.value = None
        self.destroy()

    def get_input(self):
        return self.value

class PasswordInputDialog(SafeToplevel):

    def __init__(self, parent, title=None, prompt=None):
        super().__init__(parent)
        self.title(title if title else tr('DIALOG_PWD_TITLE'))
        self.center_window(350, 200)
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.parent = parent
        self.value = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(self, text=prompt, font=('Microsoft YaHei UI', 14)).pack(pady=(20, 10))
        self.entry = ctk.CTkEntry(self, width=250, show='*')
        self.entry.pack(pady=10)
        self.entry.bind('<Return>', lambda e: self.on_ok())
        self.entry.focus_force()
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(pady=20)
        ctk.CTkButton(btn_frame, text=tr('BTN_CONFIRM'), width=100, command=self.on_ok).pack(side='left', padx=10)
        ctk.CTkButton(btn_frame, text=tr('BTN_CANCEL'), width=100, fg_color='#555', command=self.on_cancel).pack(side='left', padx=10)
        self.wait_window()

    def on_ok(self):
        self.value = self.entry.get()
        self.destroy()

    def on_cancel(self):
        self.value = None
        self.destroy()

    def get_input(self):
        return self.value

class GroupBanListWindow(SafeToplevel):

    def __init__(self, parent_app, group_id):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.group_id = group_id
        self.title(tr('INFO_BTN_BAN_LIST'))
        self.center_window(500, 400)
        self.transient(parent_app)
        self.attributes('-topmost', True)
        ctk.CTkLabel(self, text=tr('BAN_WIN_TIP'), text_color='gray').pack(pady=10)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        self.load_bans()

    def load_bans(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        bans = self.parent_app.client.db.get_group_ban_list(self.group_id)
        if not bans:
            ctk.CTkLabel(self.scroll, text=tr('BAN_WIN_NONE'), text_color='gray').pack(pady=50)
            return
        for b in bans:
            pk, reason = (b[0], b[1])
            name = self.parent_app.client.db.get_contact_name(pk) or f'{pk[:6]}...'
            row = ctk.CTkFrame(self.scroll, fg_color='transparent')
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=f'🚫 {name}', width=150, anchor='w').pack(side='left', padx=5)
            ctk.CTkLabel(row, text=tr('BAN_REASON').format(r=reason), text_color='gray').pack(side='left', padx=5)
            ctk.CTkButton(row, text=tr('BAN_BTN_LIFT'), width=80, fg_color='green', command=lambda p=pk: self.unban(p)).pack(side='right', padx=5)

    def unban(self, target_pk):
        self.parent_app.client.db.remove_group_ban(self.group_id, target_pk)
        owner = self.parent_app.client.db.get_group_owner(self.group_id)
        if owner == self.parent_app.client.pk:
            if messagebox.askyesno(tr('DIALOG_WARN_TITLE'), tr('DIALOG_UNBLOCK_OWNER_MSG')):
                self.parent_app.client.unban_group_member(self.group_id, target_pk)
        self.load_bans()
        self.show_toast(tr('TOAST_UNBLOCK_USER'))

class ProfileWindow(SafeToplevel):

    def __init__(self, parent_app, pubkey, is_self=False):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.pubkey = pubkey
        self.is_self = is_self
        self.decrypted_key = None
        title = tr('PROFILE_TITLE_SELF') if is_self else tr('PROFILE_TITLE_USER')
        self.title(title)
        self.center_window(550, 780)
        self.attributes('-topmost', True)
        if not is_self:
            self.parent_app.client.fetch_user_profile(pubkey)
        db = self.parent_app.client.db
        info = db.get_contact_info(pubkey)
        db = self.parent_app.client.db
        info = db.get_contact_info(pubkey)
        self.original_data = {'name': info[1] if info else '', 'pic': info[6] if info and len(info) > 6 else '', 'about': info[7] if info and len(info) > 7 else '', 'web': info[8] if info and len(info) > 8 else '', 'ln': info[9] if info and len(info) > 9 else '', 'enc': info[2] if info else '', 'relays': info[10] if info and len(info) > 10 else ''}
        self.current_pic_b64 = self.original_data['pic']
        self.entry_widgets = {}
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=10)
        self.avatar_frame = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self.avatar_frame.pack(pady=10)
        self.avatar_label = ctk.CTkLabel(self.avatar_frame, text='[Avatar]', width=100, height=100, fg_color='#333', corner_radius=10)
        self.avatar_label.pack()
        if self.current_pic_b64:
            self.render_avatar(self.current_pic_b64)
        if is_self:
            hint = ctk.CTkLabel(self.avatar_frame, text=tr('PROFILE_HINT_AVATAR'), font=('Microsoft YaHei UI', 10), text_color='gray')
            hint.pack(pady=2)
            self.avatar_label.bind('<Button-1>', self.upload_avatar)
            self.avatar_label.configure(cursor='hand2')
        fields = [(tr('PROFILE_LBL_NICK'), 'name', True, False), (tr('PROFILE_LBL_PK'), 'pk_static', False, False), (tr('PROFILE_LBL_ABOUT'), 'about', True, True), (tr('PROFILE_LBL_WEB'), 'web', True, False), (tr('PROFILE_LBL_LN'), 'ln', True, False), (tr('PROFILE_LBL_RELAY'), 'relays', True, True)]
        self.original_data['pk_static'] = to_npub(pubkey)
        for lbl, key, editable, is_multiline in fields:
            val = self.original_data.get(key, '')
            state = 'normal' if is_self and editable else 'readonly'
            bg_color = '#343638' if is_self and editable else '#2b2b2b'
            if not is_self and key == 'relays':
                bg_color = '#2b2b2b'
                state = 'readonly'
            label_color = '#A0A0A0'
            if key == 'pk_static':
                label_color = '#1F6AA5'
            ctk.CTkLabel(self.scroll, text=lbl, font=('Microsoft YaHei UI', 12, 'bold'), text_color=label_color).pack(anchor='w', pady=(10, 2))
            if is_multiline:
                widget = ctk.CTkTextbox(self.scroll, height=60, fg_color=bg_color)
                widget.insert('0.0', val)
                if state == 'readonly':
                    widget.configure(state='disabled')
            else:
                widget = ctk.CTkEntry(self.scroll, fg_color=bg_color)
                widget.insert(0, val)
                widget.configure(state=state)
            widget.pack(fill='x')
            self.entry_widgets[key] = widget
            if not is_self and key == 'relays' and val:
                ctk.CTkButton(self.scroll, text=tr('PROFILE_BTN_SYNC_RELAY'), width=120, height=24, fg_color='#1F6AA5', command=self.sync_others_relays).pack(anchor='e', pady=(5, 0))
            elif not (is_self and editable) and val and (key != 'relays'):
                ctk.CTkButton(self.scroll, text=tr('BTN_COPY'), width=50, height=20, fg_color='#444', command=lambda v=val: self.copy_text(v)).pack(anchor='e', pady=(2, 0))
        if is_self:
            ctk.CTkLabel(self.scroll, text=tr('PROFILE_WARN_KEY'), font=('Microsoft YaHei UI', 12, 'bold'), text_color='#D32F2F').pack(anchor='w', pady=(15, 2))
            secure_frame = ctk.CTkFrame(self.scroll, fg_color='#2b2b2b', corner_radius=6)
            secure_frame.pack(fill='x', pady=2)
            self.priv_key_display = ctk.CTkEntry(secure_frame, font=('Consolas', 12), justify='center')
            self.priv_key_display.insert(0, '******')
            self.priv_key_display.configure(state='readonly')
            self.priv_key_display.pack(fill='x', padx=10, pady=10)
            btn_frame = ctk.CTkFrame(secure_frame, fg_color='transparent')
            btn_frame.pack(fill='x', padx=5, pady=(0, 10))
            self.btn_unlock = ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_UNLOCK'), fg_color='#D32F2F', command=self.unlock_private_key)
            self.btn_unlock.pack(fill='x', pady=2)
            self.secure_action_btns = []
            self.btn_view = ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_VIEW'), fg_color='gray', state='disabled')
            self.btn_view.pack(fill='x', pady=2)
            self.btn_view.bind('<ButtonPress-1>', self.on_view_press)
            self.btn_view.bind('<ButtonRelease-1>', self.on_view_release)
            self.secure_action_btns.append(self.btn_view)
            copy_frame = ctk.CTkFrame(btn_frame, fg_color='transparent')
            copy_frame.pack(fill='x', pady=2)
            btn_copy_all = ctk.CTkButton(copy_frame, text=tr('PROFILE_BTN_COPY_ALL'), width=80, fg_color='gray', state='disabled', command=lambda: self.copy_private_key_part('all'))
            btn_copy_all.pack(side='left', padx=2, expand=True)
            self.secure_action_btns.append(btn_copy_all)
            btn_copy_head = ctk.CTkButton(copy_frame, text=tr('PROFILE_BTN_COPY_HEAD'), width=80, fg_color='gray', state='disabled', command=lambda: self.copy_private_key_part('head'))
            btn_copy_head.pack(side='left', padx=2, expand=True)
            self.secure_action_btns.append(btn_copy_head)
            btn_copy_tail = ctk.CTkButton(copy_frame, text=tr('PROFILE_BTN_COPY_TAIL'), width=80, fg_color='gray', state='disabled', command=lambda: self.copy_private_key_part('tail'))
            btn_copy_tail.pack(side='left', padx=2, expand=True)
            self.secure_action_btns.append(btn_copy_tail)
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(side='bottom', fill='x', pady=20, padx=20)
        if is_self:
            ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_SAVE'), height=40, fg_color='green', command=self.save_profile).pack(fill='x')
            my_name = self.original_data.get('name') or 'Me'
            ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_EXPORT_SELF'), fg_color='#555', command=lambda: ExportSelectionDialog(self.parent_app, target_id=self.pubkey, target_name=my_name)).pack(fill='x', pady=10)
        else:
            is_friend = info[4] == 1 if info and len(info) > 4 else False
            is_blocked = info[5] == 1 if info and len(info) > 5 else False
            if not is_friend:
                ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_ADD_FRIEND'), fg_color='#1F6AA5', command=self.add_friend).pack(fill='x', pady=5)
            else:
                ctk.CTkButton(btn_frame, text=tr('PROFILE_BTN_DEL_FRIEND'), fg_color='#D32F2F', command=self.del_friend).pack(fill='x', pady=5)
            name_display = self.original_data.get('name') or 'User'
            ctk.CTkButton(btn_frame, text=tr('MENU_EXPORT_CHAT'), fg_color='#555', command=lambda: ExportSelectionDialog(self.parent_app, target_id=self.pubkey, target_name=name_display)).pack(fill='x', pady=5)
            if not is_blocked:
                ctk.CTkButton(btn_frame, text=tr('MENU_BLOCK_USER'), fg_color='#555', command=self.block_user).pack(fill='x', pady=5)
            else:
                ctk.CTkButton(btn_frame, text=tr('MENU_UNBLOCK_USER'), fg_color='green', command=self.unblock_user).pack(fill='x', pady=5)
        ctk.CTkButton(btn_frame, text=tr('INFO_BTN_CLOSE'), fg_color='gray', command=self.destroy).pack(fill='x', pady=(10, 0))

    def unlock_private_key(self):
        dialog = PasswordInputDialog(self, title=tr('DIALOG_SECURE_AUTH'), prompt=tr('DIALOG_SECURE_PROMPT'))
        pwd = dialog.get_input()
        if not pwd:
            return
        if self.parent_app.client.verify_password(pwd):
            try:
                sk_hex = self.parent_app.client.priv_k
                nsec_key = to_nsec(sk_hex)
                self.decrypted_key = nsec_key
                self.btn_unlock.configure(text=tr('PROFILE_BTN_UNLOCKED'), state='disabled', fg_color='#2b2b2b', text_color='green')
                for btn in self.secure_action_btns:
                    btn.configure(state='normal')
                    if btn == self.secure_action_btns[0]:
                        btn.configure(fg_color='#1F6AA5')
                    else:
                        btn.configure(fg_color='#333')
            except Exception as e:
                messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('DIALOG_READ_ERR').format(e=e), parent=self)
        else:
            messagebox.showerror(tr('DIALOG_AUTH_FAIL'), tr('DIALOG_AUTH_ERR_PWD'), parent=self)

    def on_view_press(self, event):
        if not self.decrypted_key:
            return
        self.priv_key_display.configure(state='normal')
        self.priv_key_display.delete(0, 'end')
        self.priv_key_display.insert(0, self.decrypted_key)
        self.priv_key_display.configure(state='readonly')

    def on_view_release(self, event):
        self.priv_key_display.configure(state='normal')
        self.priv_key_display.delete(0, 'end')
        self.priv_key_display.insert(0, '******')
        self.priv_key_display.configure(state='readonly')

    def copy_private_key_part(self, mode):
        if not self.decrypted_key:
            return
        text, msg = ('', '')
        if mode == 'all':
            text = self.decrypted_key
            msg = tr('TOAST_KEY_ALL_COPIED')
        elif mode == 'head':
            text = self.decrypted_key[:32]
            msg = tr('TOAST_KEY_HEAD_COPIED')
        elif mode == 'tail':
            text = self.decrypted_key[32:]
            msg = tr('TOAST_KEY_TAIL_COPIED')
        self.copy_text(text, custom_msg=msg)

    def reload_ui(self):
        info = self.parent_app.client.db.get_contact_info(self.pubkey)
        if not info:
            return
        self.original_data = {'name': info[1] if info else '', 'pic': info[6] if info and len(info) > 6 else '', 'about': info[7] if info and len(info) > 7 else '', 'web': info[8] if info and len(info) > 8 else '', 'ln': info[9] if info and len(info) > 9 else '', 'enc': info[2] if info else '', 'relays': info[10] if info and len(info) > 10 else ''}
        if self.original_data['pic']:
            self.render_avatar(self.original_data['pic'])
        for key, widget in self.entry_widgets.items():
            if key == 'pk_static' or key == 'enc':
                continue
            val = self.original_data.get(key, '')
            if isinstance(widget, ctk.CTkTextbox):
                widget.configure(state='normal')
                widget.delete('0.0', 'end')
                widget.insert('0.0', val)
                if not self.is_self:
                    widget.configure(state='disabled')
            elif isinstance(widget, ctk.CTkEntry):
                widget.configure(state='normal')
                widget.delete(0, 'end')
                widget.insert(0, val)
                if not self.is_self:
                    widget.configure(state='readonly')

    def render_avatar(self, b64_str):
        if not b64_str:
            return
        try:
            data = base64.b64decode(b64_str)
            img = Image.open(BytesIO(data))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 100))
            self.avatar_label.configure(image=ctk_img, text='')
            self.avatar_label.image = ctk_img
        except:
            pass

    def upload_avatar(self, event=None):
        if not self.is_self:
            return
        try:
            path = ctk.filedialog.askopenfilename(parent=self, filetypes=[('Images', '*.jpg;*.png;*.jpeg')])
            if not path:
                return
            img = Image.open(path)
            img.thumbnail((200, 200))
            buffer = BytesIO()
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(buffer, format='JPEG', quality=80)
            b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.current_pic_b64 = b64_str
            self.render_avatar(b64_str)
        except Exception as e:
            messagebox.showerror('错误', f'图片处理失败: {e}', parent=self)

    def save_profile(self):
        new_name = self.entry_widgets['name'].get().strip()
        new_about = self.entry_widgets['about'].get('0.0', 'end').strip()
        new_web = self.entry_widgets['web'].get().strip()
        new_ln = self.entry_widgets['ln'].get().strip()
        new_relays = self.entry_widgets['relays'].get('0.0', 'end').strip()
        if not new_name:
            self.parent_app.show_toast(tr('TOAST_NICK_EMPTY'))
            return
        profile = {'name': new_name, 'picture': self.current_pic_b64, 'about': new_about, 'website': new_web, 'ln': new_ln, 'relays': new_relays}
        try:
            self.parent_app.client.set_profile(profile)
            self.parent_app.refresh_ui()
            self.parent_app.show_toast(tr('TOAST_SAVED'))
            self.destroy()
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), str(e), parent=self)

    def copy_text(self, text, custom_msg='已复制'):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.show_toast(f'📋 {custom_msg}')

    def add_friend(self):
        self.parent_app.client.db.save_contact(self.pubkey, None, is_friend=1)
        self.parent_app.client.fetch_user_profile(self.pubkey)
        self.parent_app.refresh_ui()
        self.parent_app.show_toast('✅ 已添加好友')
        self.destroy()
        self.parent_app.show_user_profile(self.pubkey)

    def del_friend(self):
        if messagebox.askyesno('确认', '确定删除好友？', parent=self):
            self.parent_app.client.db.save_contact(self.pubkey, None, is_friend=0)
            self.parent_app.refresh_ui()
            self.parent_app.show_toast('🗑️ 好友已删除')
            self.destroy()
            self.parent_app.show_user_profile(self.pubkey)

    def block_user(self):
        if messagebox.askyesno('确认', '屏蔽后将不再接收对方私聊。', parent=self):
            self.parent_app.client.db.block_contact(self.pubkey, True)
            self.parent_app.refresh_ui()
            self.parent_app.show_toast('🚫 已屏蔽用户')
            if self.parent_app.current_chat_id == self.pubkey:
                self.parent_app.update_input_state()
            self.destroy()
            self.parent_app.show_user_profile(self.pubkey)

    def unblock_user(self):
        self.parent_app.client.db.block_contact(self.pubkey, False)
        self.parent_app.refresh_ui()
        self.parent_app.show_toast('✅ 已解除屏蔽')
        if self.parent_app.current_chat_id == self.pubkey:
            self.parent_app.update_input_state()
        self.destroy()
        self.parent_app.show_user_profile(self.pubkey)

    def sync_others_relays(self):
        raw_text = self.entry_widgets['relays'].get('0.0', 'end').strip()
        if not raw_text:
            messagebox.showinfo('提示', '对方 Relay 列表为空', parent=self)
            return
        import re
        candidates = [x.strip() for x in re.split('[;,\\n]', raw_text) if x.strip()]
        candidates = [url for url in candidates if url.startswith('ws://') or url.startswith('wss://')]
        if not candidates:
            messagebox.showwarning('提示', '未找到有效Relay地址', parent=self)
            return
        with self.parent_app.client.lock:
            local_relays = set(self.parent_app.client.relays.keys())
        new_relays = [r for r in candidates if r not in local_relays]
        if not new_relays:
            messagebox.showinfo('提示', '无需同步', parent=self)
            return
        if not messagebox.askyesno('确认同步', f'发现 {len(new_relays)} 个新 Relay，是否测试并添加？'):
            return
        threading.Thread(target=self._test_and_add_relays, args=(new_relays,), daemon=True).start()

    def _test_and_add_relays(self, relay_list):
        added_count = 0
        try:
            import websocket
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_path, 'relays.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            saved_urls = config_data['client']['relay_url']
            if isinstance(saved_urls, str):
                saved_urls = [saved_urls]
            for url in relay_list:
                try:
                    ws = websocket.create_connection(url, timeout=3)
                    ws.close()
                    self.parent_app.client.add_relay_dynamic(url)
                    if url not in saved_urls:
                        saved_urls.append(url)
                        added_count += 1
                except:
                    continue
            if added_count > 0:
                config_data['client']['relay_url'] = saved_urls
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=4)
        except:
            pass
        self.after(0, lambda: messagebox.showinfo('同步完成', f'成功添加 {added_count} 个Relay。', parent=self))

class RelayConfigWindow(SafeToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title('Relay 连接管理')
        self.center_window(700, 500)
        self.attributes('-topmost', True)
        self.relay_rows = {}
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(base_path, 'relays.json')
        top_frame = ctk.CTkFrame(self, fg_color='transparent')
        top_frame.pack(fill='x', padx=10, pady=10)
        self.url_entry = ctk.CTkEntry(top_frame, placeholder_text='输入 Relay 地址 (ws://...)', width=350)
        self.url_entry.pack(side='left', padx=5)
        ctk.CTkButton(top_frame, text='+ 添加并连接', width=100, command=self.add_relay).pack(side='left', padx=5)
        header_frame = ctk.CTkFrame(self, height=30, fg_color='#333')
        header_frame.pack(fill='x', padx=10, pady=(10, 0))
        ctk.CTkLabel(header_frame, text='地址', width=280, anchor='w').pack(side='left', padx=10)
        ctk.CTkLabel(header_frame, text='状态', width=80, anchor='center').pack(side='left', padx=5)
        ctk.CTkLabel(header_frame, text='操作', width=80, anchor='center').pack(side='right', padx=10)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        ctk.CTkLabel(self, text='提示: 修改后配置会自动保存。', text_color='gray', font=('Microsoft YaHei UI', 11)).pack(pady=5)
        self.refresh_list()
        self.start_auto_refresh()

    def start_auto_refresh(self):
        if self.winfo_exists():
            self.refresh_list()
            self.after(1000, self.start_auto_refresh)

    def refresh_list(self):
        status_data = self.parent.client.get_connection_status()
        details = status_data.get('details', [])
        new_data_map = {}
        for item in details:
            url = item['url']
            latency = -1
            with self.parent.client.lock:
                if url in self.parent.client.relays:
                    latency = self.parent.client.relays[url].latency
            status_code = item['status']
            status_color = 'gray'
            status_text = '未知'
            if status_code == 0:
                status_color = '#D32F2F'
                status_text = '断开'
            elif status_code == 1:
                status_color = '#FFA000'
                status_text = '连接中'
            elif status_code == 2:
                status_color = '#388E3C'
                status_text = '在线'
            lat_text = f'{latency}ms' if latency >= 0 else '--'
            lat_color = 'gray'
            if latency > 0:
                if latency < 100:
                    lat_color = 'green'
                elif latency < 300:
                    lat_color = 'orange'
                else:
                    lat_color = 'red'
            new_data_map[url] = {'s_text': status_text, 's_col': status_color, 'l_text': lat_text, 'l_col': lat_color}
        to_delete = []
        for url in self.relay_rows:
            if url not in new_data_map:
                self.relay_rows[url]['frame'].destroy()
                to_delete.append(url)
        for url in to_delete:
            del self.relay_rows[url]
        for url, props in new_data_map.items():
            if url in self.relay_rows:
                widgets = self.relay_rows[url]
                if widgets['status_lbl'].cget('text') != props['s_text']:
                    widgets['status_lbl'].configure(text=props['s_text'], text_color=props['s_col'])
                    widgets['status_lbl'].configure(text_color=props['s_col'])
                if widgets['lat_lbl'].cget('text') != props['l_text']:
                    widgets['lat_lbl'].configure(text=props['l_text'], text_color=props['l_col'])
                    widgets['lat_lbl'].configure(text_color=props['l_col'])
            else:
                row = ctk.CTkFrame(self.scroll, fg_color='transparent', height=40)
                row.pack(fill='x', pady=2)
                ctk.CTkLabel(row, text=url, width=220, anchor='w', font=('Microsoft YaHei UI', 12)).pack(side='left', padx=5)
                s_lbl = ctk.CTkLabel(row, text=props['s_text'], text_color=props['s_col'], width=50)
                s_lbl.pack(side='left', padx=5)
                l_lbl = ctk.CTkLabel(row, text=props['l_text'], text_color=props['l_col'], width=60, anchor='e')
                l_lbl.pack(side='left', padx=5)
                ctk.CTkButton(row, text='删除', width=50, fg_color='#444', hover_color='#D32F2F', height=24, command=lambda u=url: self.delete_relay(u)).pack(side='right', padx=5)
                ctk.CTkButton(row, text='复制', width=50, fg_color='#444', height=24, command=lambda u=url: self.copy_url(u)).pack(side='right', padx=5)
                self.relay_rows[url] = {'frame': row, 'status_lbl': s_lbl, 'lat_lbl': l_lbl}

    def copy_url(self, url):
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()
        app = getattr(self, 'parent', None) or getattr(self, 'parent_app', None)
        self.show_toast('📋 地址已复制')

    def add_relay(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if not (url.startswith('ws://') or url.startswith('wss://')):
            messagebox.showerror('格式错误', '地址必须以 ws:// 或 wss:// 开头', parent=self)
            return
        try:
            data = {}
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    data = {'client': {'relay_url': []}}
            if 'client' not in data:
                data['client'] = {}
            if 'relay_url' not in data['client']:
                data['client']['relay_url'] = []
            urls = data['client']['relay_url']
            if isinstance(urls, str):
                urls = [urls]
            if url not in urls:
                urls.append(url)
                data['client']['relay_url'] = urls
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                self.parent.client.add_relay_dynamic(url)
                self.url_entry.delete(0, 'end')
                self.refresh_list()
                if hasattr(self.parent, 'show_toast'):
                    self.parent.show_toast(f'✅ 已添加: {url}')
            elif hasattr(self.parent, 'show_toast'):
                self.parent.show_toast('⚠️ 该 Relay 已存在')
        except Exception as e:
            messagebox.showerror('错误', f'保存配置失败: {e}', parent=self)

    def delete_relay(self, target_url):
        if not messagebox.askyesno('删除确认', f'确定删除节点？\n{target_url}', parent=self):
            return
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                urls = data.get('client', {}).get('relay_url', [])
                if isinstance(urls, str):
                    urls = [urls]
                if target_url in urls:
                    urls.remove(target_url)
                    data['client']['relay_url'] = urls
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
            with self.parent.client.lock:
                if target_url in self.parent.client.relays:
                    self.parent.client.relays[target_url].stop()
                    del self.parent.client.relays[target_url]
            self.parent.client.relay_manager._notify_status_change()
            if target_url in self.relay_rows:
                self.relay_rows[target_url]['frame'].destroy()
                del self.relay_rows[target_url]
            self.refresh_list()
            if hasattr(self.parent, 'show_toast'):
                self.parent.show_toast('🗑️ 已删除 Relay')
        except Exception as e:
            messagebox.showerror('错误', f'删除失败: {e}', parent=self)

class LoginWindow(SafeToplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title(tr('LOGIN_WIN_TITLE'))
        self.center_window(450, 480)
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.data_root = _resolve_data_root()
        ctk.CTkLabel(self, text=tr('LOGIN_MAIN_TITLE'), font=('Microsoft YaHei UI', 20, 'bold')).pack(pady=15)
        self.tab_view = ctk.CTkTabview(self, height=320)
        self.tab_view.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        self.tab_login = self.tab_view.add(tr('LOGIN_TAB_LOGIN'))
        self.users_combo = ctk.CTkComboBox(self.tab_login, values=self.scan_local_users(), width=250, state='readonly')
        self.users_combo.pack(pady=(30, 10))
        self.pwd_entry_login = ctk.CTkEntry(self.tab_login, placeholder_text=tr('LOGIN_PH_PWD'), show='*', width=250)
        self.pwd_entry_login.pack(pady=10)
        self.pwd_entry_login.bind('<Return>', lambda e: self.login_existing())
        ctk.CTkButton(self.tab_login, text=tr('LOGIN_BTN_UNLOCK'), command=self.login_existing).pack(pady=20)
        self.tab_create = self.tab_view.add(tr('LOGIN_TAB_CREATE'))
        self.new_nick = ctk.CTkEntry(self.tab_create, placeholder_text=tr('CREATE_PH_NICK'), width=250)
        self.new_nick.pack(pady=(20, 10))
        self.new_pwd = ctk.CTkEntry(self.tab_create, placeholder_text=tr('CREATE_PH_PWD'), show='*', width=250)
        self.new_pwd.pack(pady=5)
        self.new_pwd_2 = ctk.CTkEntry(self.tab_create, placeholder_text=tr('CREATE_PH_PWD2'), show='*', width=250)
        self.new_pwd_2.pack(pady=5)
        ctk.CTkButton(self.tab_create, text=tr('CREATE_BTN_GO'), command=self.create_new).pack(pady=20)
        self.tab_import = self.tab_view.add(tr('LOGIN_TAB_IMPORT'))
        self.imp_folder = ctk.CTkEntry(self.tab_import, placeholder_text=tr('IMPORT_PH_FOLDER'), width=250)
        self.imp_folder.pack(pady=(10, 5))
        self.imp_key = ctk.CTkEntry(self.tab_import, placeholder_text=tr('IMPORT_PH_KEY'), width=250)
        self.imp_key.pack(pady=5)
        self.imp_nick = ctk.CTkEntry(self.tab_import, placeholder_text=tr('IMPORT_PH_NICK'), width=250)
        self.imp_nick.pack(pady=5)
        self.imp_pwd = ctk.CTkEntry(self.tab_import, placeholder_text=tr('IMPORT_PH_PWD'), show='*', width=250)
        self.imp_pwd.pack(pady=5)
        self.imp_pwd_2 = ctk.CTkEntry(self.tab_import, placeholder_text=tr('IMPORT_PH_PWD2'), show='*', width=250)
        self.imp_pwd_2.pack(pady=5)
        ctk.CTkButton(self.tab_import, text=tr('IMPORT_BTN_GO'), command=self.import_login).pack(pady=15)
        warning_lbl = ctk.CTkLabel(self, text='* 仅供技术研究，严禁用于非法用途', text_color='gray', font=('Microsoft YaHei UI', 10))
        warning_lbl.pack(side='bottom', pady=5)

    def scan_local_users(self):
        users = []
        search_pattern = os.path.join(self.data_root, 'user_*')
        for d in glob.glob(search_pattern):
            if os.path.isdir(d) and os.path.exists(os.path.join(d, 'user.db')):
                folder_name = os.path.basename(d)
                if folder_name.startswith('user_'):
                    users.append(folder_name[5:])
        return users if users else [tr('LOGIN_NO_ACCOUNT')]

    def login_existing(self):
        nick = self.users_combo.get()
        pwd = self.pwd_entry_login.get()
        if nick == '(暂无账号)' or nick == tr('LOGIN_NO_ACCOUNT') or (not nick):
            return
        if not pwd:
            messagebox.showwarning(tr('DIALOG_INFO_TITLE'), tr('LOGIN_MSG_ENTER_PWD'), parent=self)
            return
        db_path = os.path.join(self.data_root, f'user_{nick}', 'user.db')
        self.parent.start_backend_secure(db_path, mode='LOGIN', password=pwd, nickname=nick)

    def create_new(self):
        nick = self.new_nick.get().strip()
        p1 = self.new_pwd.get()
        p2 = self.new_pwd_2.get()
        if not nick:
            return messagebox.showwarning(tr('DIALOG_INFO_TITLE'), tr('LOGIN_MSG_ENTER_NICK'), parent=self)
        if not p1:
            return messagebox.showwarning(tr('DIALOG_INFO_TITLE'), tr('LOGIN_MSG_ENTER_PWD'), parent=self)
        if len(p1) < 8:
            return messagebox.showwarning(tr('DIALOG_WARN_TITLE'), tr('LOGIN_MSG_PWD_LEN'), parent=self)
        if p1 != p2:
            return messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_PWD_MISMATCH'), parent=self)
        folder_path = os.path.join(self.data_root, f'user_{nick}')
        if os.path.exists(folder_path):
            return messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_USER_EXISTS'), parent=self)
        try:
            os.makedirs(folder_path)
            db_path = os.path.join(folder_path, 'user.db')
            self.parent.start_backend_secure(db_path, mode='CREATE', password=p1, nickname=nick)
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_DIR_ERR').format(e=e), parent=self)

    def import_login(self):
        folder_name = self.imp_folder.get().strip()
        raw_key = self.imp_key.get().strip()
        nick = self.imp_nick.get().strip()
        pwd = self.imp_pwd.get()
        pwd2 = self.imp_pwd_2.get()
        hex_key = to_hex_privkey(raw_key)
        if not folder_name or not hex_key or (not pwd):
            return messagebox.showwarning(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_INFO_INCOMPLETE'), parent=self)
        if len(pwd) < 8:
            return messagebox.showwarning(tr('DIALOG_WARN_TITLE'), tr('LOGIN_MSG_PWD_LEN'), parent=self)
        if pwd != pwd2:
            return messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_PWD_MISMATCH'), parent=self)
        folder_path = os.path.join(self.data_root, f'user_{folder_name}')
        try:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            db_path = os.path.join(folder_path, 'user.db')
            self.parent.start_backend_secure(db_path, mode='IMPORT', password=pwd, nickname=nick, priv_key=hex_key)
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('LOGIN_MSG_IMPORT_ERR').format(e=e), parent=self)

    def on_close(self):
        self.parent.destroy()
        sys.exit(0)

class InfoWindow(SafeToplevel):

    def __init__(self, title, info_dict, buttons=None, member_list=None, parent_app=None):
        super().__init__(parent_app)
        self.title(title)
        self.parent_app = parent_app
        self.entry_widgets = {}
        window_height = 800 if member_list is not None else 550
        self.center_window(550, window_height)
        self.attributes('-topmost', True)
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.main_scroll.pack(fill='both', expand=True, padx=5, pady=(5, 0))
        self.bottom_frame = ctk.CTkFrame(self, fg_color='transparent', height=50)
        self.bottom_frame.pack(fill='x', side='bottom', pady=10)
        self.info_frame = ctk.CTkFrame(self.main_scroll, fg_color='transparent')
        self.info_frame.pack(fill='x', padx=10, pady=10)
        keys_with_copy = [tr('INFO_KEY_CODE_GHOST'), tr('INFO_KEY_CODE_NORMAL'), tr('INFO_KEY_ID')]
        for label, value in info_dict.items():
            ctk.CTkLabel(self.info_frame, text=label, font=('Microsoft YaHei UI', 12, 'bold'), anchor='w').pack(fill='x', pady=(5, 0))
            entry = ctk.CTkEntry(self.info_frame)
            entry.insert(0, str(value))
            entry.configure(state='readonly')
            entry.pack(fill='x', pady=(2, 0))
            self.entry_widgets[label] = entry
            if label in keys_with_copy:
                ctk.CTkButton(self.info_frame, text=tr('BTN_COPY'), width=40, height=24, fg_color='#444', command=lambda v=value, e=entry: self.copy_from_entry(e)).pack(anchor='e', pady=(2, 0))
        if member_list:
            ctk.CTkLabel(self.main_scroll, text=tr('INFO_LBL_MEMBERS').format(n=len(member_list)), font=('Microsoft YaHei UI', 14, 'bold'), anchor='w').pack(fill='x', padx=15, pady=(15, 5))
            self.member_scroll = ctk.CTkScrollableFrame(self.main_scroll, height=180, fg_color='#2b2b2b')
            self.member_scroll.pack(fill='x', padx=10, pady=5)
            for m_info in member_list:
                row = ctk.CTkFrame(self.member_scroll, fg_color='transparent')
                row.pack(fill='x', pady=2)
                lbl = ctk.CTkLabel(row, text=f"👤 {m_info['name']}", anchor='w', text_color='silver', cursor='hand2')
                lbl.pack(side='left', padx=5)
                lbl.bind('<Button-1>', lambda e, pk=m_info['pk']: self.open_profile(pk))
                if m_info.get('kick_cb'):
                    ctk.CTkButton(row, text=tr('INFO_BTN_KICK'), width=50, height=20, fg_color='#D32F2F', command=m_info['kick_cb']).pack(side='right', padx=5)
        if buttons is None:
            buttons = []
        if self.parent_app and hasattr(self.parent_app, 'current_chat_id') and self.parent_app.current_chat_id:
            cid = self.parent_app.current_chat_id
            buttons.append((tr('MENU_EXPORT_CHAT'), lambda: ExportSelectionDialog(self.parent_app, target_id=cid, target_name='Current_Chat'), '#1F6AA5'))
        if buttons:
            btn_frame = ctk.CTkFrame(self.main_scroll, fg_color='transparent')
            btn_frame.pack(fill='x', pady=10, padx=20)
            for btn_text, btn_cmd, btn_color in buttons:
                ctk.CTkButton(btn_frame, text=btn_text, command=btn_cmd, fg_color=btn_color).pack(fill='x', pady=5)
        ctk.CTkButton(self.bottom_frame, text=tr('INFO_BTN_CLOSE'), fg_color='gray', command=self.destroy).pack(side='top')

    def copy_from_entry(self, entry_widget):
        val = entry_widget.get()
        self.clipboard_clear()
        self.clipboard_append(val)
        self.update()
        self.show_toast('📋 内容已复制')

    def open_profile(self, pubkey):
        if self.parent_app:
            self.parent_app.show_user_profile(pubkey)

class LocalBlockListWindow(SafeToplevel):

    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.title(tr('INFO_BTN_BAN_LIST'))
        self.center_window(500, 400)
        self.attributes('-topmost', True)
        ctk.CTkLabel(self, text=tr('BLOCK_WIN_TIP'), text_color='gray').pack(pady=10)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        self.load_list()

    def load_list(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        blocked = self.parent_app.client.db.get_blocked_contacts()
        if not blocked:
            ctk.CTkLabel(self.scroll, text='没有被屏蔽的用户').pack(pady=20)
            return
        for u in blocked:
            pk, name = (u['pubkey'], u['name'] or '未知')
            row = ctk.CTkFrame(self.scroll, fg_color='transparent')
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=f'🚫 {name} ({pk[:6]}...)', anchor='w').pack(side='left', padx=10)
            ctk.CTkButton(row, text='解除', width=60, fg_color='green', command=lambda p=pk: self.unblock_user(p)).pack(side='right', padx=10)

    def unblock_user(self, pk):
        self.parent_app.client.db.block_contact(pk, False)
        self.load_block_list()
        self.parent_app.refresh_ui()

class SelectContactDialog(SafeToplevel):

    def __init__(self, contacts, on_select_callback, parent_app=None):
        if parent_app is None and hasattr(contacts, 'winfo_x'):
            pass
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.title('选择好友')
        self.center_window(400, 500)
        self.attributes('-topmost', True)
        self.callback = on_select_callback
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        ctk.CTkLabel(self, text='请选择联系人:', font=('Microsoft YaHei UI', 14, 'bold')).pack(pady=10)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        final_contacts = contacts if isinstance(contacts, list) else []
        if not final_contacts:
            ctk.CTkLabel(self.scroll, text='暂无联系人', text_color='gray').pack(pady=20)
        for c in final_contacts:
            name = c['name'] or f"用户 {c['pubkey'][:6]}"
            btn = ctk.CTkButton(self.scroll, text=f'👤 {name}', anchor='w', fg_color='transparent', border_width=1, text_color='silver', command=lambda pk=c['pubkey']: self.select_contact(pk))
            btn.pack(fill='x', pady=2)
        ctk.CTkButton(self, text='手动输入公钥', fg_color='gray', command=self.manual_input).pack(pady=10)

    def select_contact(self, pubkey):
        self.callback(pubkey)
        self.destroy()

    def manual_input(self):
        self.withdraw()
        try:
            self.grab_release()
        except:
            pass
        if self.callback:
            self.callback(None, manual=True)
        self.destroy()

    def on_close(self):
        self.callback(None)
        self.destroy()

class SelectSessionDialog(SafeToplevel):

    def __init__(self, parent_app, on_select_callback):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.callback = on_select_callback
        self.title(tr('TITLE_SELECT_SESSION'))
        w, h = (400, 550)
        self.center_window(w, h)
        self.attributes('-topmost', True)
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab_recent = self.tab_view.add('最近')
        self.scroll_r = ctk.CTkScrollableFrame(self.tab_recent, fg_color='transparent')
        self.scroll_r.pack(fill='both', expand=True)
        try:
            recents = self.parent_app.client.db.get_session_list()
            if not recents:
                ctk.CTkLabel(self.scroll_r, text='暂无最近会话', text_color='gray').pack(pady=20)
            for s in recents:
                sid = s['id']
                s_name = s['name']
                s_type = s['type']
                icon = '👤'
                color = 'silver'
                if s_type == 'group':
                    grp = self.parent_app.client.groups.get(sid)
                    if grp and str(grp.get('type')) == '1':
                        icon = '⚡'
                        color = '#FF79C6'
                    else:
                        icon = '📢'
                        color = '#69F0AE'
                btn = ctk.CTkButton(self.scroll_r, text=f'{icon} {s_name}', anchor='w', fg_color='transparent', border_width=1, text_color=color, command=lambda pid=sid, pt=s_type, pn=s_name: self._on_select(pid, pt, pn))
                btn.pack(fill='x', pady=2)
        except Exception as e:
            print(f'Recent load error: {e}')
        self.tab_friends = self.tab_view.add(tr('TAB_FRIENDS'))
        self.scroll_f = ctk.CTkScrollableFrame(self.tab_friends, fg_color='transparent')
        self.scroll_f.pack(fill='both', expand=True)
        friends = self.parent_app.client.db.get_friends()
        if not friends:
            ctk.CTkLabel(self.scroll_f, text=tr('LBL_NO_FRIENDS'), text_color='gray').pack(pady=20)
        for f in friends:
            name = f['name'] or f"User {f['pubkey'][:6]}"
            btn = ctk.CTkButton(self.scroll_f, text=f'👤 {name}', anchor='w', fg_color='transparent', border_width=1, text_color='silver', command=lambda pid=f['pubkey'], n=name: self._on_select(pid, 'dm', n))
            btn.pack(fill='x', pady=2)
        self.tab_groups = self.tab_view.add(tr('TAB_GROUPS'))
        self.scroll_g = ctk.CTkScrollableFrame(self.tab_groups, fg_color='transparent')
        self.scroll_g.pack(fill='both', expand=True)
        groups = self.parent_app.client.groups
        if not groups:
            ctk.CTkLabel(self.scroll_g, text=tr('LBL_NO_GROUPS'), text_color='gray').pack(pady=20)
        for gid, info in groups.items():
            gname = info['name']
            gtype = info.get('type', 0)
            icon = '⚡' if str(gtype) == '1' else '📢'
            color = '#FF79C6' if str(gtype) == '1' else '#69F0AE'
            btn = ctk.CTkButton(self.scroll_g, text=f'{icon} {gname}', anchor='w', fg_color='transparent', border_width=1, text_color=color, command=lambda pid=gid, n=gname: self._on_select(pid, 'group', n))
            btn.pack(fill='x', pady=2)

    def _on_select(self, target_id, target_type, name):
        self.withdraw()
        try:
            self.grab_release()
        except:
            pass
        self.callback(target_id, target_type, name)
        self.after(200, lambda: self._safe_destroy())

    def _safe_destroy(self):
        try:
            super().destroy()
        except:
            pass

class ExportSelectionDialog(SafeToplevel):

    def __init__(self, parent_app, target_id=None, target_name='All'):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.target_id = target_id
        display_name = target_name
        type_label = '🌏 全局备份 (不含测试频道)'
        info_color = '#1F6AA5'
        if target_id:
            from client_persistent import OFFICIAL_GROUP_CONFIG
            from key_utils import get_npub_abbr
            if target_id in parent_app.client.groups:
                grp = parent_app.client.groups[target_id]
                display_name = grp['name']
                g_type = str(grp.get('type', '0'))
                if target_id == OFFICIAL_GROUP_CONFIG['id']:
                    type_label = '📡 测试频道'
                    info_color = '#FFD700'
                elif g_type == '1':
                    type_label = '⚡ 共享群'
                    info_color = '#FF79C6'
                else:
                    type_label = '📢 普通群'
                    info_color = '#69F0AE'
            elif target_id == parent_app.client.pk:
                n = parent_app.client.db.get_contact_name(target_id)
                display_name = n if n else '我'
                type_label = '📝 个人笔记'
                info_color = '#FFCC00'
            else:
                n = parent_app.client.db.get_contact_name(target_id)
                base_name = n if n else '未知用户'
                abbr = get_npub_abbr(target_id)
                display_name = f'{base_name} ({abbr})'
                type_label = '👤 私聊会话'
                info_color = '#DCE4EE'
        self.target_name = display_name
        title_text = '全局导出'
        if target_id:
            title_text = f'导出: {display_name}'
        self.title(title_text)
        self.center_window(450, 600)
        self.attributes('-topmost', True)
        info_frame = ctk.CTkFrame(self, fg_color='#333', corner_radius=6)
        info_frame.pack(fill='x', padx=20, pady=15)
        ctk.CTkLabel(info_frame, text=type_label, font=('Microsoft YaHei UI', 12, 'bold'), text_color=info_color).pack(pady=(10, 2))
        if target_id:
            ctk.CTkLabel(info_frame, text=display_name, font=('Microsoft YaHei UI', 12), text_color='white').pack(pady=(0, 10))
        ctk.CTkLabel(self, text='文件格式:', anchor='w', font=('Microsoft YaHei UI', 12, 'bold')).pack(fill='x', padx=25, pady=(10, 5))
        f_frame = ctk.CTkFrame(self, fg_color='transparent')
        f_frame.pack(fill='x', padx=25)
        self.format_var = ctk.StringVar(value='html')
        ctk.CTkRadioButton(f_frame, text='HTML (推荐, 含图片)', variable=self.format_var, value='html').pack(anchor='w', pady=2)
        ctk.CTkRadioButton(f_frame, text='TXT (仅文字)', variable=self.format_var, value='txt').pack(anchor='w', pady=2)
        ctk.CTkLabel(self, text='时间范围 (可选, 留空为全部):', anchor='w', font=('Microsoft YaHei UI', 12, 'bold')).pack(fill='x', padx=25, pady=(20, 5))
        date_frame = ctk.CTkFrame(self, fg_color='transparent')
        date_frame.pack(fill='x', padx=20)
        ctk.CTkLabel(date_frame, text='从:').grid(row=0, column=0, padx=5, pady=5)
        self.entry_start = ctk.CTkEntry(date_frame, placeholder_text='YYYY-MM-DD', width=120)
        self.entry_start.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(date_frame, text='至:').grid(row=0, column=2, padx=5, pady=5)
        self.entry_end = ctk.CTkEntry(date_frame, placeholder_text='YYYY-MM-DD', width=120)
        self.entry_end.grid(row=0, column=3, padx=5, pady=5)
        quick_frame = ctk.CTkFrame(self, fg_color='transparent')
        quick_frame.pack(fill='x', padx=20, pady=5)
        quick_frame.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        ctk.CTkButton(quick_frame, text='全部', width=50, height=24, fg_color='#555', command=lambda: self.set_quick_date(0)).grid(row=0, column=0, padx=2)
        ctk.CTkButton(quick_frame, text=tr('BTN_TODAY'), width=50, height=24, fg_color='#555', command=lambda: self.set_quick_date(-1)).grid(row=0, column=1, padx=2)
        ctk.CTkButton(quick_frame, text='近7天', width=50, height=24, fg_color='#555', command=lambda: self.set_quick_date(7)).grid(row=0, column=2, padx=2)
        ctk.CTkButton(quick_frame, text='近30天', width=50, height=24, fg_color='#555', command=lambda: self.set_quick_date(30)).grid(row=0, column=3, padx=2)
        ctk.CTkButton(quick_frame, text='今年', width=50, height=24, fg_color='#555', command=lambda: self.set_quick_date(365)).grid(row=0, column=4, padx=2)
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(side='bottom', fill='x', pady=20, padx=40)
        ctk.CTkButton(btn_frame, text='开始导出', fg_color='green', command=self.start_export).pack(fill='x', pady=5)
        ctk.CTkButton(btn_frame, text='取消', fg_color='gray', command=self.destroy).pack(fill='x', pady=5)

    def set_quick_date(self, days):
        self.entry_start.delete(0, 'end')
        self.entry_end.delete(0, 'end')
        now = datetime.now()
        today_str = now.strftime('%Y-%m-%d')
        if days == 0:
            return
        if days == -1:
            self.entry_start.insert(0, today_str)
            self.entry_end.insert(0, today_str)
            return
        self.entry_end.insert(0, today_str)
        if days == 365:
            self.entry_start.insert(0, f'{now.year}-01-01')
        else:
            from datetime import timedelta
            delta = timedelta(days=days)
            start_date = now - delta
            self.entry_start.insert(0, start_date.strftime('%Y-%m-%d'))

    def parse_date(self, date_str, is_end=False):
        if not date_str.strip():
            return 0
        try:
            dt = datetime.strptime(date_str.strip(), '%Y-%m-%d')
            if is_end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return int(dt.timestamp())
        except ValueError:
            return -1

    def start_export(self):
        fmt = self.format_var.get()
        s_str = self.entry_start.get()
        e_str = self.entry_end.get()
        s_ts = self.parse_date(s_str, is_end=False)
        e_ts = self.parse_date(e_str, is_end=True)
        if s_ts == -1 or e_ts == -1:
            return self.show_toast('❌ 日期格式错误 (应为 YYYY-MM-DD)')
        if s_ts > 0 and e_ts > 0 and (s_ts > e_ts):
            return self.show_toast('❌ 起始日期不能晚于结束日期')
        safe_name = ''.join([c for c in self.target_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_name:
            safe_name = 'Export'
        time_tag = ''
        if s_str:
            time_tag = f'_{s_str}'
        default_name = f'ChatHistory_{safe_name}{time_tag}_{int(time.time())}'
        ext = '.html' if fmt == 'html' else '.txt'
        file_path = ctk.filedialog.asksaveasfilename(parent=self, defaultextension=ext, initialfile=default_name + ext, title='保存导出文件')
        if file_path:
            self.destroy()
            threading.Thread(target=self.parent_app.run_export_task, args=(self.target_id, file_path, fmt, s_ts, e_ts)).start()

class SearchWindow(SafeToplevel):

    def __init__(self, parent_app, target_id=None):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.target_id = target_id
        title_text = tr('SEARCH_TITLE_GLOBAL')
        if target_id:
            name = tr('SEARCH_TITLE_CURRENT')
            if target_id in parent_app.client.groups:
                name = parent_app.client.groups[target_id]['name']
            else:
                n = parent_app.client.db.get_contact_name(target_id)
                if n:
                    name = n
            title_text = f"{tr('SEARCH_TITLE_PREFIX')}{name}"
        self.title(title_text)
        self.center_window(600, 500)
        self.attributes('-topmost', True)
        top_frame = ctk.CTkFrame(self, fg_color='transparent')
        top_frame.pack(fill='x', padx=10, pady=10)
        self.entry = ctk.CTkEntry(top_frame, placeholder_text=tr('SEARCH_PH'), width=400)
        self.entry.pack(side='left', padx=5)
        self.entry.bind('<Return>', lambda e: self.do_search())
        ctk.CTkButton(top_frame, text=tr('SEARCH_BTN'), width=100, command=self.do_search).pack(side='left', padx=5)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        self.status_lbl = ctk.CTkLabel(self, text=tr('SEARCH_LBL_TIP'), text_color='gray', font=('Microsoft YaHei UI', 11))
        self.status_lbl.pack(pady=5)

    def do_search(self):
        keyword = self.entry.get().strip()
        if not keyword:
            return
        for w in self.scroll.winfo_children():
            w.destroy()
        from client_persistent import OFFICIAL_GROUP_CONFIG
        exclude = None
        if self.target_id is None:
            exclude = OFFICIAL_GROUP_CONFIG['id']
        results = self.parent_app.client.db.search_messages(keyword, specific_target_id=self.target_id, limit=50, exclude_gid=exclude)
        if not results:
            self.status_lbl.configure(text=tr('SEARCH_LBL_NO_RESULT'))
            return
        self.status_lbl.configure(text=tr('SEARCH_LBL_FOUND').format(n=len(results)))
        for res in results:
            msg_id, gid, sender_pk, content, ts, sname = res
            display_text = content
            if content.startswith('{'):
                try:
                    js = json.loads(content)
                    display_text = js.get('text', tr('SEARCH_RES_IMG'))
                except:
                    pass
            if len(display_text) > 60:
                display_text = display_text[:60] + '...'
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
            sender_name = tr('SEARCH_SENDER_ME')
            if sender_pk != self.parent_app.client.pk:
                sender_name = self.parent_app.client.db.get_contact_name(sender_pk) or tr('SEARCH_SENDER_USER')
            row = ctk.CTkFrame(self.scroll, fg_color='#2b2b2b', corner_radius=6)
            row.pack(fill='x', pady=2)
            header = ctk.CTkFrame(row, fg_color='transparent')
            header.pack(fill='x', padx=5, pady=(5, 0))
            ctk.CTkLabel(header, text=f'📂 {sname}', font=('Microsoft YaHei UI', 11, 'bold'), text_color='#1F6AA5').pack(side='left')
            ctk.CTkLabel(header, text=time_str, font=('Microsoft YaHei UI', 10), text_color='gray').pack(side='right')
            body = ctk.CTkFrame(row, fg_color='transparent')
            body.pack(fill='x', padx=5, pady=(0, 5))
            ctk.CTkLabel(body, text=f'{sender_name}: {display_text}', anchor='w', text_color='silver', font=('Microsoft YaHei UI', 12)).pack(fill='x')
            self._bind_events_recursive(row, lambda e, g=gid, m=msg_id: self.jump_to_chat(g, m), lambda e, f=row: f.configure(fg_color='#3a3a3a'), lambda e, f=row: f.configure(fg_color='#2b2b2b'))

    def _bind_events_recursive(self, widget, jump_func, enter_func, leave_func):
        widget.bind('<Double-Button-1>', jump_func)
        widget.bind('<Enter>', enter_func)
        widget.bind('<Leave>', leave_func)
        for child in widget.winfo_children():
            self._bind_events_recursive(child, jump_func, enter_func, leave_func)

    def jump_to_chat(self, group_id, msg_id):
        self.parent_app.jump_to_message_context(group_id, msg_id)

class SettingsWindow(SafeToplevel):

    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.title(tr('SETTING_WIN_TITLE'))
        self.center_window(700, 550)
        self.attributes('-topmost', True)
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab_net = self.tab_view.add(tr('SETTING_TAB_NET'))
        self.tab_priv = self.tab_view.add(tr('SETTING_TAB_PRIV'))
        self.tab_data = self.tab_view.add(tr('SETTING_TAB_DATA'))
        self.tab_lang = self.tab_view.add(tr('SETTING_TAB_LANG'))
        self.tab_about = self.tab_view.add(tr('SETTING_TAB_ABOUT'))
        self._init_network_tab()
        self._init_privacy_tab()
        self._init_data_tab()
        self._init_about_tab()
        self._init_lang_tab()

    def _init_lang_tab(self):
        frame = self.tab_lang
        ctk.CTkLabel(frame, text=tr('SETTING_LBL_LANG'), font=('Microsoft YaHei UI', 12)).pack(pady=20)
        self.lang_map = {'简体中文': 'zh_CN', 'English': 'en_US'}
        self.rev_lang_map = {v: k for k, v in self.lang_map.items()}
        current_display = self.rev_lang_map.get(CURRENT_LANG, '简体中文')
        self.lang_combo = ctk.CTkComboBox(frame, values=list(self.lang_map.keys()), state='readonly', width=200)
        self.lang_combo.set(current_display)
        self.lang_combo.pack(pady=10)
        ctk.CTkButton(frame, text=tr('SETTING_BTN_SAVE_LANG'), command=self.save_lang).pack(pady=20)

    def save_lang(self):
        selection = self.lang_combo.get()
        code = self.lang_map.get(selection)
        if code:
            if save_language_config(code):
                messagebox.showinfo('DageChat', tr('SETTING_MSG_RESTART'), parent=self)
            else:
                messagebox.showerror('Error', 'Failed to save config.', parent=self)

    def _init_network_tab(self):
        frame = self.tab_net
        top_bar = ctk.CTkFrame(frame, fg_color='transparent')
        top_bar.pack(fill='x', pady=5)
        self.url_entry = ctk.CTkEntry(top_bar, placeholder_text='输入 Relay 地址 (ws://...)', width=350)
        self.url_entry.pack(side='left', padx=5)
        ctk.CTkButton(top_bar, text='+ 添加并连接', width=100, command=self.add_relay).pack(side='left', padx=5)
        header = ctk.CTkFrame(frame, height=30, fg_color='#333')
        header.pack(fill='x', pady=(10, 0))
        ctk.CTkLabel(header, text='地址', width=250, anchor='w').pack(side='left', padx=10)
        ctk.CTkLabel(header, text='状态', width=80).pack(side='left', padx=5)
        ctk.CTkLabel(header, text='延迟', width=80).pack(side='left', padx=5)
        self.relay_scroll = ctk.CTkScrollableFrame(frame)
        self.relay_scroll.pack(fill='both', expand=True, pady=5)
        self.relay_rows = {}
        self.refresh_relay_list()
        self.start_relay_refresh_loop()

    def start_relay_refresh_loop(self):
        if self.winfo_exists():
            self.refresh_relay_list()
            self.after(1000, self.start_relay_refresh_loop)

    def refresh_relay_list(self):
        status_data = self.parent_app.client.get_connection_status()
        details = status_data.get('details', [])
        new_data_map = {}
        for item in details:
            url = item['url']
            status_code = item['status']
            latency = -1
            with self.parent_app.client.lock:
                if url in self.parent_app.client.relays:
                    latency = self.parent_app.client.relays[url].latency
            if status_code == 0:
                s_text, s_col = ('断开', '#D32F2F')
            elif status_code == 1:
                s_text, s_col = ('连接中', '#FFA000')
            else:
                s_text, s_col = ('在线', '#388E3C')
            l_text = f'{latency}ms' if latency >= 0 else '--'
            l_col = 'gray'
            if latency > 0:
                if latency < 100:
                    l_col = 'green'
                elif latency < 300:
                    l_col = 'orange'
                else:
                    l_col = '#D32F2F'
            new_data_map[url] = {'s_text': s_text, 's_col': s_col, 'l_text': l_text, 'l_col': l_col}
        to_delete = []
        for url in self.relay_rows:
            if url not in new_data_map:
                self.relay_rows[url]['frame'].destroy()
                to_delete.append(url)
        for url in to_delete:
            del self.relay_rows[url]
        for url, props in new_data_map.items():
            if url in self.relay_rows:
                widgets = self.relay_rows[url]
                if widgets['status_lbl'].cget('text') != props['s_text']:
                    widgets['status_lbl'].configure(text=props['s_text'], text_color=props['s_col'])
                if widgets['lat_lbl'].cget('text') != props['l_text']:
                    widgets['lat_lbl'].configure(text=props['l_text'], text_color=props['l_col'])
            else:
                row = ctk.CTkFrame(self.relay_scroll, fg_color='transparent', height=35)
                row.pack(fill='x', pady=2)
                ctk.CTkLabel(row, text=url, width=250, anchor='w', font=('Microsoft YaHei UI', 12)).pack(side='left', padx=10)
                s_lbl = ctk.CTkLabel(row, text=props['s_text'], text_color=props['s_col'], width=80, font=('Microsoft YaHei UI', 12))
                s_lbl.pack(side='left', padx=5)
                l_lbl = ctk.CTkLabel(row, text=props['l_text'], text_color=props['l_col'], width=80, font=('Microsoft YaHei UI', 12))
                l_lbl.pack(side='left', padx=5)
                ctk.CTkButton(row, text='删除', width=50, height=24, fg_color='#444', hover_color='#D32F2F', font=('Microsoft YaHei UI', 12), command=lambda u=url: self.delete_relay(u)).pack(side='right', padx=10)
                ctk.CTkButton(row, text='复制', width=50, height=24, fg_color='#444', font=('Microsoft YaHei UI', 12), command=lambda u=url: self.copy_url(u)).pack(side='right', padx=5)
                self.relay_rows[url] = {'frame': row, 'status_lbl': s_lbl, 'lat_lbl': l_lbl}

    def copy_url(self, url):
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()
        self.show_toast('📋 地址已复制')

    def add_relay(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        if not (url.startswith('ws://') or url.startswith('wss://')):
            self.parent_app.show_toast('❌ 格式错误: 需以 ws:// 或 wss:// 开头')
            return
        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_path, 'relays.json')
            data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    data = {'client': {'relay_url': []}}
            if 'client' not in data:
                data['client'] = {}
            if 'relay_url' not in data['client']:
                data['client']['relay_url'] = []
            urls = data['client']['relay_url']
            if isinstance(urls, str):
                urls = [urls]
            if url not in urls:
                urls.append(url)
                data['client']['relay_url'] = urls
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                self.parent_app.client.add_relay_dynamic(url)
                self.url_entry.delete(0, 'end')
                self.refresh_relay_list()
                self.show_toast(f'✅ 已添加: {url}')
            else:
                self.show_toast('⚠️ 该 Relay 已存在')
        except Exception as e:
            self.parent_app.show_toast(f'❌ 保存失败: {e}')

    def delete_relay(self, url):
        if not messagebox.askyesno('删除确认', f'确定删除节点？\n{url}', parent=self):
            return
        try:
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_path, 'relays.json')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                urls = data.get('client', {}).get('relay_url', [])
                if isinstance(urls, str):
                    urls = [urls]
                if url in urls:
                    urls.remove(url)
                    data['client']['relay_url'] = urls
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
            with self.parent_app.client.lock:
                if url in self.parent_app.client.relays:
                    self.parent_app.client.relays[url].stop()
                    del self.parent_app.client.relays[url]
            self.parent_app.client.relay_manager._notify_status_change()
            self.refresh_relay_list()
            self.show_toast('🗑️ Relay 已删除')
        except Exception as e:
            self.show_toast(f'❌ 删除出错: {e}')

    def _init_privacy_tab(self):
        frame = self.tab_priv
        sec_frame = ctk.CTkFrame(frame, fg_color='transparent')
        sec_frame.pack(fill='x', padx=20, pady=(20, 10))
        ctk.CTkLabel(sec_frame, text=tr('SETTING_LBL_TIMEOUT'), font=('Microsoft YaHei UI', 12)).pack(anchor='w', pady=5)
        input_row = ctk.CTkFrame(sec_frame, fg_color='transparent')
        input_row.pack(fill='x')
        self.timeout_entry = ctk.CTkEntry(input_row, width=100)
        self.timeout_entry.pack(side='left', padx=(0, 10))
        current_min = 30
        if self.parent_app.client:
            try:
                val = self.parent_app.client.db.get_setting('auto_lock_minutes')
                if val is not None:
                    current_min = int(val)
            except:
                pass
        self.timeout_entry.insert(0, str(current_min))
        ctk.CTkButton(input_row, text=tr('SETTING_BTN_SAVE_TIMEOUT'), width=120, fg_color='#1F6AA5', command=self.save_timeout).pack(side='left')
        ctk.CTkFrame(frame, height=2, fg_color='#444').pack(fill='x', padx=10, pady=10)
        ctk.CTkLabel(frame, text='本地屏蔽名单 (仅自己不可见)', text_color='gray').pack(pady=5)
        self.block_scroll = ctk.CTkScrollableFrame(frame)
        self.block_scroll.pack(fill='both', expand=True, padx=5, pady=5)
        ctk.CTkButton(frame, text='刷新列表', command=self.load_block_list).pack(pady=5)
        self.load_block_list()

    def save_timeout(self):
        try:
            val_str = self.timeout_entry.get().strip()
            val = int(val_str)
            if val < 0:
                raise ValueError
            self.parent_app.client.db.set_setting('auto_lock_minutes', str(val))
            self.parent_app._LOCK_TIMEOUT = val * 60
            self.show_toast(tr('TOAST_TIMEOUT_SAVED').format(n=val))
        except:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), '请输入有效的正整数 (0或更大)', parent=self)

    def load_block_list(self):
        for w in self.block_scroll.winfo_children():
            w.destroy()
        blocked = self.parent_app.client.db.get_blocked_contacts()
        if not blocked:
            ctk.CTkLabel(self.block_scroll, text='没有被屏蔽的用户').pack(pady=20)
            return
        for u in blocked:
            pk, name = (u['pubkey'], u['name'] or '未知')
            row = ctk.CTkFrame(self.block_scroll, fg_color='transparent')
            row.pack(fill='x', pady=2)
            ctk.CTkLabel(row, text=f'🚫 {name} ({pk[:6]}...)', anchor='w').pack(side='left', padx=10)
            ctk.CTkButton(row, text='解除', width=60, fg_color='green', command=lambda p=pk: self.unblock_user(p)).pack(side='right', padx=10)

    def unblock_user(self, pk):
        self.parent_app.client.db.block_contact(pk, False)
        self.load_block_list()
        self.parent_app.refresh_ui()

    def _init_data_tab(self):
        frame = self.tab_data
        ctk.CTkLabel(frame, text='数据检索与备份', font=('Microsoft YaHei UI', 14, 'bold')).pack(pady=20)
        ctk.CTkButton(frame, text='🔍 全局消息搜索', height=40, width=200, command=lambda: SearchWindow(self.parent_app, target_id=None)).pack(pady=10)
        ctk.CTkButton(frame, text='📤 导出所有聊天记录', height=40, width=200, fg_color='#1F6AA5', command=lambda: ExportSelectionDialog(self.parent_app, target_id=None, target_name='All_Backup')).pack(pady=10)
        ctk.CTkLabel(frame, text='提示: 导出操作可能较慢，请耐心等待。', text_color='gray').pack(pady=10)

    def _init_about_tab(self):
        frame = self.tab_about

        def _rejoin_official():
            self.parent_app.client.db.set_setting('exited_official_lobby', '0')
            self.parent_app.client._ensure_official_group()
            self.parent_app.refresh_ui()
            self.parent_app.show_toast(tr('TOAST_REJOIN_OFFICIAL'), master=self)
        ctk.CTkButton(frame, text=tr('SETTING_BTN_REJOIN'), height=30, fg_color='#333', command=_rejoin_official).pack(pady=10)
        ctk.CTkLabel(frame, text=tr('SETTING_ABOUT_TITLE'), font=('Microsoft YaHei UI', 24, 'bold')).pack(pady=(20, 5))
        version_text = getattr(self.parent_app, 'app_version', 'v0.0.0')
        ctk.CTkLabel(frame, text=version_text, font=('Microsoft YaHei UI', 12), text_color='gray').pack(pady=(0, 20))
        text_box = ctk.CTkTextbox(frame, width=550, height=350, fg_color='#2b2b2b', font=('Consolas', 12))
        text_box.pack(pady=10, padx=20)
        text_box.insert('0.0', tr('SETTING_ABOUT_DESC'))

        def _smart_readonly(event):
            if event.state & 4 and event.keysym.lower() in ['c', 'a']:
                return None
            if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior', 'Next']:
                return None
            return 'break'
        text_box.bind('<Key>', _smart_readonly)

class ForwardConfirmDialog(SafeToplevel):

    def __init__(self, parent, target_name, msg_preview, on_confirm, image_obj=None):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.title(tr('TITLE_FORWARD'))
        h = 450 if image_obj else 250
        self.center_window(350, h)
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header_frame = ctk.CTkFrame(self, fg_color='transparent')
        header_frame.pack(pady=(15, 5), fill='x')
        ctk.CTkLabel(header_frame, text=tr('FWD_LBL_SEND_TO'), font=('Microsoft YaHei UI', 12), text_color='gray').pack()
        ctk.CTkLabel(header_frame, text=target_name, font=('Microsoft YaHei UI', 16, 'bold')).pack()
        preview_frame = ctk.CTkFrame(self, fg_color='#333', corner_radius=6)
        preview_frame.pack(pady=10, padx=20, fill='both', expand=True)
        if image_obj:
            try:
                img_lbl = ctk.CTkLabel(preview_frame, text='', image=image_obj)
                img_lbl.pack(pady=10, expand=True)
                img_lbl.image = image_obj
            except Exception as e:
                ctk.CTkLabel(preview_frame, text=tr('FWD_IMG_ERR').format(e=e), text_color='gray').pack(pady=20)
        if msg_preview and msg_preview != '[Image]':
            display_text = msg_preview[:100] + '...' if len(msg_preview) > 100 else msg_preview
            ctk.CTkLabel(preview_frame, text=display_text, font=('Microsoft YaHei UI', 12), text_color='#ddd', wraplength=280).pack(pady=10, padx=10)
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(side='bottom', pady=20, fill='x')
        inner = ctk.CTkFrame(btn_frame, fg_color='transparent')
        inner.pack()
        ctk.CTkButton(inner, text=tr('BTN_CANCEL'), fg_color='transparent', border_width=1, text_color='silver', width=80, command=self.destroy).pack(side='left', padx=10)
        ctk.CTkButton(inner, text=tr('BTN_SEND_FORWARD'), fg_color='#1F6AA5', width=80, command=self._do_confirm).pack(side='left', padx=10)

    def _do_confirm(self):
        self.withdraw()
        try:
            self.grab_release()
        except:
            pass
        self.on_confirm()
        self.after(200, lambda: self._safe_destroy())

    def _safe_destroy(self):
        try:
            super().destroy()
        except:
            pass

class MultiSelectContactDialog(SafeToplevel):

    def __init__(self, parent_app, contacts, on_confirm_callback):
        super().__init__(parent_app)
        self.title(tr('TITLE_SELECT_MEMBER'))
        self.center_window(400, 500)
        self.attributes('-topmost', True)
        self.callback = on_confirm_callback
        self.parent_app = parent_app
        self.check_vars = {}
        ctk.CTkLabel(self, text=tr('MULTI_TIP').format(n=len(contacts)), font=('Microsoft YaHei UI', 12, 'bold')).pack(pady=10)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        if not contacts:
            ctk.CTkLabel(self.scroll, text=tr('MULTI_NONE'), text_color='gray').pack(pady=20)
        else:
            sorted_contacts = sorted(contacts, key=lambda x: x['name'] or '')
            for c in sorted_contacts:
                pk = c['pubkey']
                name = c['name'] or f'User {pk[:6]}...'
                var = ctk.BooleanVar(value=False)
                self.check_vars[pk] = var
                row = ctk.CTkFrame(self.scroll, fg_color='transparent')
                row.pack(fill='x', pady=2)
                cb = ctk.CTkCheckBox(row, text=f'👤 {name}', variable=var, checkbox_width=20, checkbox_height=20, font=('Microsoft YaHei UI', 12))
                cb.pack(side='left', padx=5)
        btn_frame = ctk.CTkFrame(self, fg_color='transparent')
        btn_frame.pack(side='bottom', fill='x', pady=15, padx=20)
        ctk.CTkButton(btn_frame, text=tr('BTN_CONFIRM'), fg_color='#1F6AA5', command=self.on_ok).pack(side='right', padx=5, fill='x', expand=True)
        ctk.CTkButton(btn_frame, text=tr('BTN_CANCEL'), fg_color='#555', command=self.destroy).pack(side='left', padx=5, fill='x', expand=True)

    def on_ok(self):
        selected_pks = []
        for pk, var in self.check_vars.items():
            if var.get():
                selected_pks.append(pk)
        self.callback(selected_pks)
        self.destroy()

class SelectGroupMemberDialog(SafeToplevel):

    def __init__(self, parent_app, members_data, on_select_callback):
        super().__init__(parent_app)
        self.title(tr('TITLE_SELECT_MENTION'))
        self.center_window(350, 450)
        self.attributes('-topmost', True)
        self.callback = on_select_callback
        self.search_entry = ctk.CTkEntry(self, placeholder_text=tr('PH_SEARCH_MEMBER'))
        self.search_entry.pack(fill='x', padx=10, pady=10)
        self.search_entry.bind('<KeyRelease>', self.filter_list)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=10, pady=5)
        self.members_data = members_data
        self.buttons = []
        self.render_list(self.members_data)
        self.bind('<Escape>', lambda e: self.destroy())

    def _safe_focus(self):
        if self._is_destroyed:
            return
        try:
            if self.winfo_exists():
                self.focus_force()
                self.search_entry.focus_set()
        except:
            pass

    def render_list(self, data):
        for btn in self.buttons:
            btn.destroy()
        self.buttons.clear()
        if not data:
            ctk.CTkLabel(self.scroll, text=tr('LBL_NO_MATCH'), text_color='gray').pack(pady=20)
            return
        for m in data:
            name = m['name']
            pk = m['pk']
            btn = ctk.CTkButton(self.scroll, text=f'👤 {name}', anchor='w', fg_color='transparent', border_width=1, text_color='silver', command=lambda p=pk, n=name: self._on_click(p, n))
            btn.pack(fill='x', pady=2)
            self.buttons.append(btn)

    def _on_click(self, pk, name):
        self.callback(pk, name)
        self.destroy()

    def filter_list(self, event):
        keyword = self.search_entry.get().lower().strip()
        if not keyword:
            self.render_list(self.members_data)
            return
        filtered = [m for m in self.members_data if keyword in m['name'].lower()]
        self.render_list(filtered)

class EmojiWindow(SafeToplevel):

    def __init__(self, parent_app, on_select):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.on_select = on_select
        self.width = 400
        self.height = 320
        self.title(tr('TITLE_EMOJI'))
        self.geometry(f'{self.width}x{self.height}')
        self.resizable(False, False)
        self.withdraw()
        self.protocol('WM_DELETE_WINDOW', self.hide_window)
        self.bind('<Unmap>', self._check_minimize)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=5, pady=5)
        self.loading_lbl = ctk.CTkLabel(self.scroll, text='Loading...', text_color='gray')
        self.loading_lbl.pack(pady=20)
        self.grid_row = 0
        self.grid_col = 0
        self.is_loaded = False
        self._start_loading()

    def _check_minimize(self, event):
        if event.widget == self:
            try:
                if self.state() == 'iconic':
                    self.withdraw()
            except:
                pass

    def _safe_focus(self):
        pass

    def _start_loading(self):
        if hasattr(sys, '_MEIPASS'):
            base_img_dir = os.path.join(sys._MEIPASS, 'img')
        else:
            base_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'img')
        manifest_path = os.path.join(base_img_dir, 'emojis_manifest.json')
        emojis_dir = os.path.join(base_img_dir, 'emojis')
        threading.Thread(target=self._bg_read_files, args=(manifest_path, emojis_dir), daemon=True).start()

    def _bg_read_files(self, manifest_path, emojis_dir):
        files_to_load = []
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        fname = item.get('file')
                        if fname:
                            p = os.path.join(emojis_dir, fname)
                            if os.path.exists(p):
                                files_to_load.append(p)
            except:
                pass
        if not files_to_load and os.path.exists(emojis_dir):
            for ext in ['*.webp', '*.png', '*.jpg', '*.gif']:
                files_to_load.extend(glob.glob(os.path.join(emojis_dir, ext)))
        if files_to_load:
            self.after(0, lambda: self.loading_lbl.destroy())
            for f_path in files_to_load:
                try:
                    pil_img = Image.open(f_path)
                    pil_img.load()
                    pil_img.thumbnail((64, 64))
                    self.after(10, lambda p=f_path, i=pil_img: self._add_ui_item(p, i))
                    time.sleep(0.02)
                except:
                    pass
        else:
            self.after(0, lambda: self.loading_lbl.configure(text='No Emojis'))
        self.is_loaded = True

    def _add_ui_item(self, f_path, pil_img):
        if self._is_destroyed:
            return
        try:
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            btn = ctk.CTkButton(self.scroll, text='', image=ctk_img, width=70, height=70, fg_color='transparent', hover_color='#444', command=lambda p=f_path: self._on_click(p))
            btn.grid(row=self.grid_row, column=self.grid_col, padx=5, pady=5)
            self.grid_col += 1
            if self.grid_col >= 4:
                self.grid_col = 0
                self.grid_row += 1
        except:
            pass

    def _on_click(self, path):
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            self.on_select(raw)
            self.hide_window()
        except:
            pass

    def hide_window(self):
        self.withdraw()

    def show_at(self, target_widget):
        try:
            target_widget.update_idletasks()
            root_x = target_widget.winfo_rootx()
            root_y = target_widget.winfo_rooty()
            target_width = target_widget.winfo_width()
            pos_x = root_x
            pos_y = root_y - self.height - 5
            if pos_y < 0:
                pos_y = 0
            if pos_x < 0:
                pos_x = 0
            self.geometry(f'{self.width}x{self.height}+{pos_x}+{pos_y}')
            self.deiconify()
            self.attributes('-topmost', True)
            self.focus_force()
        except Exception as e:
            print(f'Emoji show error: {e}')
            self.geometry(f'{self.width}x{self.height}')
            self.deiconify()

class ScreenshotOverlay(tk.Toplevel):

    def __init__(self, parent_app, on_capture):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.on_capture = on_capture
        self.overrideredirect(True)
        self.withdraw()
        self._init_dpi_awareness()
        self.update()
        time.sleep(0.2)
        try:
            self.original_image = ImageGrab.grab(all_screens=True)
            enhancer = ImageEnhance.Brightness(self.original_image)
            self.dark_image = enhancer.enhance(0.5)
            self.tk_img_original = ImageTk.PhotoImage(self.original_image)
            self.tk_img_dark = ImageTk.PhotoImage(self.dark_image)
            user32 = ctypes.windll.user32
            v_left = user32.GetSystemMetrics(76)
            v_top = user32.GetSystemMetrics(77)
            v_width = user32.GetSystemMetrics(78)
            v_height = user32.GetSystemMetrics(79)
            if v_width == 0:
                v_width = self.original_image.width
                v_height = self.original_image.height
                v_left = 0
                v_top = 0
            self.screen_width = v_width
            self.screen_height = v_height
            self.start_x_offset = v_left
            self.start_y_offset = v_top
        except Exception as e:
            print(f'Screenshot init failed: {e}')
            self.destroy()
            return
        geo_str = f'{self.screen_width}x{self.screen_height}+{self.start_x_offset}+{self.start_y_offset}'
        self.geometry(geo_str)
        self.deiconify()
        self.attributes('-topmost', True)
        self.lift()
        self.focus_force()
        self.canvas = tk.Canvas(self, width=self.screen_width, height=self.screen_height, cursor='cross', highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill='both', expand=True)
        self.bg_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_img_dark)
        self.start_x = None
        self.start_y = None
        self.selection_rect_id = None
        self.bright_img_id = None
        self.selection = None
        self.is_dragging = False
        self.info_text_id = self.canvas.create_text(self.screen_width // 2, 100, text=tr('TIP_SCREENSHOT'), fill='white', font=('Microsoft YaHei UI', 14, 'bold'))
        self.canvas.bind('<ButtonPress-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.canvas.bind('<Button-3>', self.on_right_click)
        self.bind('<Escape>', self.on_right_click)
        self.canvas.bind('<Double-Button-1>', self.confirm)

    def _init_dpi_awareness(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

    def on_mouse_down(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.is_dragging = False

    def on_mouse_drag(self, event):
        if self.start_x is None:
            return
        if not self.is_dragging:
            self._clear_selection()
            self.is_dragging = True
        cur_x, cur_y = (event.x, event.y)
        x1 = min(self.start_x, cur_x)
        y1 = min(self.start_y, cur_y)
        x2 = max(self.start_x, cur_x)
        y2 = max(self.start_y, cur_y)
        if self.selection_rect_id:
            self.canvas.coords(self.selection_rect_id, x1, y1, x2, y2)
        else:
            self.selection_rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline='#00FF00', width=2)
        w = x2 - x1
        h = y2 - y1
        self.canvas.itemconfigure(self.info_text_id, text=f'{w} x {h}')
        text_y = y1 - 30 if y1 > 50 else y1 + 30
        self.canvas.coords(self.info_text_id, x1 + w // 2, text_y)

    def on_mouse_up(self, event):
        if self.start_x is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.selection = (x1, y1, x2, y2)
            self._draw_bright_selection(x1, y1, x2, y2)
            self.canvas.itemconfigure(self.info_text_id, text='双击保存，右键取消')
        elif not self.selection:
            self._clear_selection()
            self.canvas.itemconfigure(self.info_text_id, text=tr('TIP_SCREENSHOT'))
            self.canvas.coords(self.info_text_id, self.screen_width // 2, 100)
        self.start_x = None
        self.is_dragging = False

    def _draw_bright_selection(self, x1, y1, x2, y2):
        if self.bright_img_id:
            self.canvas.delete(self.bright_img_id)
        try:
            region = self.original_image.crop((x1, y1, x2, y2))
            self.tk_region = ImageTk.PhotoImage(region)
            self.bright_img_id = self.canvas.create_image(x1, y1, anchor='nw', image=self.tk_region)
            self.canvas.tag_lower(self.bright_img_id, self.selection_rect_id)
        except:
            pass

    def _clear_selection(self):
        self.selection = None
        if self.selection_rect_id:
            self.canvas.delete(self.selection_rect_id)
            self.selection_rect_id = None
        if self.bright_img_id:
            self.canvas.delete(self.bright_img_id)
            self.bright_img_id = None

    def confirm(self, event=None):
        if not self.selection:
            return
        try:
            cropped = self.original_image.crop(self.selection)
            buffer = BytesIO()
            cropped.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            self.destroy()
            self.on_capture(img_bytes)
        except Exception as e:
            print(f'Crop failed: {e}')
            self.destroy()

    def on_right_click(self, event=None):
        if self.selection:
            self._clear_selection()
            self.canvas.itemconfigure(self.info_text_id, text=tr('TIP_SCREENSHOT'))
            self.canvas.coords(self.info_text_id, self.screen_width // 2, 100)
        else:
            self.destroy()
            self.on_capture(None)