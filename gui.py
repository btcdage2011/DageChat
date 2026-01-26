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
import threading
import time
import sys
import os
import queue
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageGrab
import base64
from io import BytesIO
import webbrowser
import re
import urllib.request
import json
from datetime import datetime
from client_persistent import OFFICIAL_GROUP_CONFIG
from lang_utils import tr, save_language_config, CURRENT_LANG
import pystray
from pystray import MenuItem as TrayItem, Menu as TrayMenus
if False:
    import gui_windows
    import client_gui
    import client_persistent
    import db
    import nostr_crypto
    import key_utils
    import file_locker
    import lang_utils
    import lang_data
    import gui_viewer
    import nacl
    import coincurve
APP_VERSION = 'v0.5.9'
APP_BUILD_NAME = f'DageChat Beta {APP_VERSION}'
APP_AUMID = f'DageTech.DageChat.Client.{APP_VERSION}'

def _get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')
FileLock = None
GuiChatUser = None
to_hex_pubkey = None
get_npub_abbr = None
to_npub = None
LoginWindow = None
ProfileWindow = None
RelayConfigWindow = None
InfoWindow = None
SelectContactDialog = None
GroupBanListWindow = None
LocalBlockListWindow = None
ExportSelectionDialog = None
ImageViewer = None
nacl = None

class Tooltip:

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.cancel_id = None
        self.widget.bind('<Enter>', self.on_enter)
        self.widget.bind('<Leave>', self.on_leave)
        self.widget.bind('<ButtonPress>', self.on_leave)

    def update_text(self, text):
        self.text = text

    def on_enter(self, event=None):
        self.cancel_id = self.widget.after(600, self.show_tip)

    def on_leave(self, event=None):
        if self.cancel_id:
            self.widget.after_cancel(self.cancel_id)
            self.cancel_id = None
        self.hide_tip()

    def show_tip(self):
        if self.tooltip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            self.tooltip_window = tk.Toplevel(self.widget)
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_geometry(f'+{x}+{y}')
            self.tooltip_window.attributes('-topmost', True)
            label = tk.Label(self.tooltip_window, text=self.text, justify='left', background='#2b2b2b', fg='#ffffff', relief='solid', borderwidth=1, font=('Microsoft YaHei UI', 10))
            label.pack(ipadx=5, ipady=2)
        except:
            pass

    def hide_tip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class ChatApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.app_version = APP_VERSION
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_AUMID)
            except Exception as e:
                print(f'Set AUMID failed: {e}')
        self.is_window_focused = True
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.bind('<Alt-a>', self.start_screenshot)
        self.bind('<Alt-A>', self.start_screenshot)
        self.protocol('WM_DELETE_WINDOW', self.on_x_click)
        try:
            if sys.platform == 'win32':
                icon_path = _get_resource_path(os.path.join('img', 'dagechat.ico'))
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            else:
                png_path = _get_resource_path(os.path.join('img', 'dagechat.png'))
                if os.path.exists(png_path):
                    icon_img = tk.PhotoImage(file=png_path)
                    self.iconphoto(True, icon_img)
        except Exception as e:
            print(f'Set icon error: {e}')
        self.pending_mentions = {}
        self.pending_image_bytes = None
        self.is_multi_select_mode = False
        self.selected_ids = set()
        self.title(tr('APP_TITLE'))
        sw, sh = (self.winfo_screenwidth(), self.winfo_screenheight())
        w, h = (500, 300)
        x, y = ((sw - w) // 2, (sh - h) // 2)
        self.geometry(f'{w}x{h}+{x}+{y}')
        self.last_official_msg_time = 0
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(fg_color='#1a1a1a')
        self.splash_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.splash_frame.pack(fill='both', expand=True, padx=20, pady=20)
        ctk.CTkLabel(self.splash_frame, text=tr('APP_TITLE'), font=('Microsoft YaHei UI', 40, 'bold'), text_color='#1F6AA5').pack(pady=(50, 10))
        ctk.CTkLabel(self.splash_frame, text=tr('APP_SUBTITLE_SPLASH'), font=('Microsoft YaHei UI', 14), text_color='gray').pack(pady=(0, 40))
        self.progress_bar = ctk.CTkProgressBar(self.splash_frame, width=400, height=12, progress_color='#1F6AA5')
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(self.splash_frame, text=tr('SPLASH_LOADING_DB'), font=('Microsoft YaHei UI', 12), text_color='#888')
        self.status_label.pack(pady=5)
        self.client = None
        self.current_chat_id = None
        self.current_chat_type = None
        self.reply_target_id = None
        self.invite_window = None
        self.load_task_id = None
        self.login_window = None
        self.active_profile_window = None
        self.instance_lock = None
        self.rendered_msg_ids = set()
        self.gui_queue = queue.Queue()
        self.last_refresh_ts = 0
        self.avatar_cache = {}
        self._ghost_mask_cache = None
        self._ghost_mask_pil = None
        self._image_ref_pool = []
        self._sent_greetings = set()
        self.session_widgets = {}
        self.contact_widgets = {}
        self.msg_widgets = {}
        self.chat_frames_cache = {}
        self.active_chat_frame = None
        self.msg_scroll = None
        self.chat_title = None
        self.fingerprint_label = None
        self.ui_is_ready = False
        self.tray_icon = None
        self.last_notify_times = {}
        self.current_image_viewer = None
        self.emoji_window = None
        self._emoji_lock = False
        self._last_hide_timestamp = 0
        self._LOCK_TIMEOUT = 30 * 60
        self.bind('<Unmap>', self._on_window_unmap)
        self.bind('<Map>', self._on_window_map)
        self.bind_all('<Button-1>', self._on_global_click)
        self.after(50, self._start_loading_thread)

    def start_multi_select_from_menu(self, initial_msg_id):
        self._toggle_multi_select_mode(True)
        if initial_msg_id:
            self.selected_ids.add(initial_msg_id)
        self.refresh_message_bubbles_selection(True)
        self.update_multi_op_bar()

    def _toggle_multi_select_mode(self, start_mode=False):
        self.is_multi_select_mode = start_mode
        if self.is_multi_select_mode:
            self.selected_ids.clear()
            self.show_multi_select_ui()
            self.focus_set()
            self.bind('<Escape>', lambda e: self._toggle_multi_select_mode(False))
        else:
            self.selected_ids.clear()
            self.hide_multi_select_ui()
            self.unbind('<Escape>')
            if self.msg_entry.winfo_exists():
                self.msg_entry.focus_set()

    def show_multi_select_ui(self):
        if not self.active_chat_container.winfo_ismapped():
            self.active_chat_container.pack(fill='both', expand=True)
        if self.input_container.winfo_ismapped():
            self.input_container.pack_forget()
        if hasattr(self, 'multi_op_bar') and self.multi_op_bar:
            try:
                self.multi_op_bar.destroy()
            except:
                pass
            self.multi_op_bar = None
        self.multi_op_bar = ctk.CTkFrame(self.active_chat_container, height=50, fg_color='#2b2b2b')
        self.multi_op_bar.pack(fill='x', side='bottom', padx=10, pady=10)
        info_frame = ctk.CTkFrame(self.multi_op_bar, fg_color='transparent')
        info_frame.pack(side='left', padx=10)
        txt = tr('LBL_SELECTED_COUNT').format(n=len(self.selected_ids))
        self.multi_count_lbl = ctk.CTkLabel(info_frame, text=txt, text_color='#69F0AE', font=('Microsoft YaHei UI', 12, 'bold'))
        self.multi_count_lbl.pack(side='left', padx=(0, 15))
        self.multi_size_lbl = ctk.CTkLabel(info_frame, text='容量: 0KB / 800KB', text_color='gray', font=('Microsoft YaHei UI', 11))
        self.multi_size_lbl.pack(side='left')
        ctk.CTkButton(self.multi_op_bar, text=tr('BTN_CANCEL_MULTI'), width=60, fg_color='gray', command=lambda: self._toggle_multi_select_mode(False)).pack(side='right', padx=5)
        ctk.CTkButton(self.multi_op_bar, text=tr('BTN_MERGE_FORWARD'), width=90, fg_color='#1F6AA5', command=self.prepare_combined_forward).pack(side='right', padx=5)
        ctk.CTkButton(self.multi_op_bar, text=tr('BTN_STEP_FORWARD'), width=90, fg_color='#1F6AA5', command=self.prepare_step_forward).pack(side='right', padx=5)
        ctk.CTkButton(self.multi_op_bar, text=tr('BTN_BATCH_DELETE'), width=60, fg_color='#D32F2F', command=self.handle_batch_delete).pack(side='right', padx=10)
        self.refresh_message_bubbles_selection(True)
        self.update_multi_op_bar()

    def _get_selected_messages_sorted(self):
        msgs = []
        if not self.selected_ids:
            return msgs
        for mid in self.selected_ids:
            m = self.client.db.get_message(mid)
            if m:
                msgs.append(m)
            else:
                print(f'⚠️ [GUI] Message ID {mid} not found in DB! (Possible ID mismatch)')
        msgs.sort(key=lambda x: x[4])
        return msgs

    def prepare_combined_forward(self):
        try:
            if not self.selected_ids:
                self.show_toast(tr('TOAST_SELECT_ONE'))
                return
            msgs = self._get_selected_messages_sorted()
            if not msgs:
                self.show_toast('Error: Selected messages not found in local DB.')
                return
            total_size = 0
            for m in msgs:
                content = m[3]
                if content:
                    total_size += len(content.encode('utf-8'))
                    if '"image":' in content:
                        total_size += 51200
            if total_size > 800 * 1024:
                messagebox.showwarning(tr('WARN_SIZE_LIMIT'), tr('WARN_SIZE_MSG').format(s=total_size // 1024), parent=self)
                return
            from gui_windows import SelectSessionDialog
            SelectSessionDialog(self, self._perform_combined_forward)
        except Exception as e:
            print(f'Merge Forward Error: {e}')
            import traceback
            traceback.print_exc()
            messagebox.showerror('Error', f'Failed: {e}', parent=self)

    def _perform_combined_forward(self, target_id, target_type, target_name):
        msgs = self._get_selected_messages_sorted()
        if not msgs:
            return
        src_title = self.chat_title.cget('text') or '聊天记录'
        for p in ['📢 ', '👤 ', '📝 ', '📡 ', '⚡ ']:
            src_title = src_title.replace(p, '')
        final_title = f'{src_title} 的聊天记录'

        def _confirmed_action():
            history_payload = {'type': 'history', 'title': final_title, 'items': []}

            def _bg_task():
                try:
                    for m in msgs:
                        raw_content = m[3]
                        sender_pk = m[2]
                        ts = m[4]
                        is_me = m[5] == 1
                        sender_name = 'Unknown'
                        if is_me:
                            my_name = self.client.db.get_contact_name(self.client.pk)
                            if not my_name:
                                acc = self.client.db.load_account()
                                if acc and acc[2]:
                                    my_name = acc[2]
                            if not my_name:
                                my_name = '我'
                            sender_name = my_name
                        else:
                            sender_name = self.client.db.get_contact_name(sender_pk)
                            if not sender_name:
                                sender_name = f'User {get_npub_abbr(sender_pk)}'
                        final_text = raw_content
                        final_img = None
                        if raw_content and raw_content.strip().startswith('{'):
                            try:
                                d = json.loads(raw_content)
                                if d.get('type') == 'history':
                                    final_text = raw_content
                                else:
                                    final_text = d.get('text', '')
                                    if d.get('image'):
                                        if hasattr(self, '_compress_image_for_history'):
                                            compressed_b64 = self._compress_image_for_history(d.get('image'))
                                        else:
                                            compressed_b64 = d.get('image')
                                        if compressed_b64:
                                            final_img = compressed_b64
                                        else:
                                            final_text += tr('EXP_IMG_IGNORE')
                            except:
                                final_text = raw_content
                        item = {'n': sender_name, 't': ts, 'c': final_text}
                        if final_img:
                            item['i'] = final_img
                        history_payload['items'].append(item)
                    final_json = json.dumps(history_payload, ensure_ascii=False)
                    if len(final_json.encode('utf-8')) > 800 * 1024:
                        self.show_toast(tr('TOAST_PKG_TOO_LARGE'))
                        return
                    real_eid = None
                    if target_type == 'group':
                        grp_info = self.client.groups.get(target_id)
                        if grp_info and str(grp_info.get('type')) == '1':
                            self.client.send_ghost_msg(target_id, final_json)
                        else:
                            real_eid = self.client.send_group_msg(target_id, final_json)
                    elif target_type == 'dm':
                        enc = self.client.db.get_contact_enc_key(target_id)
                        if enc:
                            real_eid = self.client.send_dm(target_id, final_json, enc)
                    now_ts = int(time.time())
                    if real_eid:
                        self.client.db.save_message(real_eid, target_id, self.client.pk, final_json, now_ts, True)
                        if self.current_chat_id == target_id:
                            self.after(0, lambda: self.add_message_bubble(real_eid, final_json, True, tr('MSG_SENDER_ME'), now_ts, scroll_to_bottom=True))
                            self.after(100, lambda: self.scroll_to_bottom())
                    self.show_toast(tr('TOAST_MERGE_FWD_DONE'))
                except Exception as e:
                    print(f'Combined forward error: {e}')
                    import traceback
                    traceback.print_exc()
                    self.show_toast(f'Error: {e}')
            threading.Thread(target=_bg_task, daemon=True).start()
            self._toggle_multi_select_mode(False)
        from gui_windows import ForwardConfirmDialog
        msg_preview = tr('FWD_MERGE_PREVIEW').format(title=final_title)
        ForwardConfirmDialog(self, target_name, msg_preview, _confirmed_action)

    def _perform_step_forward(self, target_id, target_type, target_name):
        msgs = self._get_selected_messages_sorted()
        total = len(msgs)
        if total == 0:
            return

        def _confirmed_action():

            def _bg_task():
                success_count = 0
                for i, m in enumerate(msgs):
                    content = m[3]
                    text = content
                    image_b64 = None
                    is_raw_json = False
                    if content.strip().startswith('{'):
                        try:
                            data = json.loads(content)
                            if data.get('type') == 'history':
                                text = content
                                is_raw_json = True
                            else:
                                text = data.get('text', '')
                                image_b64 = data.get('image')
                        except:
                            pass
                    try:
                        if target_type == 'group':
                            if is_raw_json:
                                self.client.send_group_msg(target_id, text)
                            else:
                                self.client.send_group_msg(target_id, text, image_base64=image_b64)
                        elif target_type == 'dm':
                            enc = self.client.db.get_contact_enc_key(target_id)
                            if enc:
                                if is_raw_json:
                                    self.client.send_dm(target_id, text, enc)
                                else:
                                    self.client.send_dm(target_id, text, enc, image_base64=image_b64)
                        success_count += 1
                        time.sleep(0.2)
                    except Exception as e:
                        print(f'Step forward error: {e}')
                self.show_toast(tr('TOAST_STEP_FWD_DONE').format(n=success_count, total=total))
            threading.Thread(target=_bg_task, daemon=True).start()
            self._toggle_multi_select_mode(False)
        from gui_windows import ForwardConfirmDialog
        msg_preview = tr('FWD_STEP_PREVIEW').format(n=total)
        ForwardConfirmDialog(self, target_name, msg_preview, _confirmed_action)

    def add_message_bubble(self, msg_id, content, is_me, sender_name, time_ts, reply_to_id=None, sender_pk=None, scroll_to_bottom=True, insert_at_top=False, top_anchor=None):
        target_frame = self.msg_scroll
        if not target_frame:
            return
        if not hasattr(target_frame, 'rendered_ids'):
            target_frame.rendered_ids = set()
        if not hasattr(target_frame, 'max_loaded_ts'):
            target_frame.max_loaded_ts = 0
        if msg_id in target_frame.rendered_ids:
            return
        target_frame.rendered_ids.add(msg_id)
        if time_ts > target_frame.max_loaded_ts:
            target_frame.max_loaded_ts = time_ts
        if not content.startswith('{') and (content.startswith('🛡️') or content.startswith('📢')):
            self.add_system_message(content)
            return
        is_ghost_grp = False
        if self.current_chat_type == 'group':
            grp = self.client.groups.get(self.current_chat_id)
            if grp and str(grp.get('type')) == '1':
                is_ghost_grp = True
        display_name = sender_name
        if is_ghost_grp and (not display_name.endswith('🎭')):
            display_name = f'{display_name} 🎭'
        avatar_obj = None
        if is_ghost_grp:
            avatar_obj = self._get_ghost_avatar()
        else:
            target_pk = sender_pk
            if is_me and (not target_pk):
                target_pk = self.client.pk
            if target_pk:
                avatar_obj = self._get_avatar_from_cache(target_pk)
        bubble_frame = ctk.CTkFrame(target_frame, fg_color='transparent')
        if insert_at_top and top_anchor:
            try:
                bubble_frame.pack(before=top_anchor, fill='x', pady=(5, 5))
            except:
                bubble_frame.pack(fill='x', pady=(5, 5))
        else:
            bubble_frame.pack(fill='x', pady=(5, 5))
        align = 'e' if is_me else 'w'
        bubble_color = '#95EC69' if is_me else '#D1C4E9' if is_ghost_grp else '#FFFFFF'
        if is_ghost_grp and avatar_obj is None:
            avatar_lbl = ctk.CTkLabel(bubble_frame, text='V', width=36, height=36, fg_color='#333', text_color='red', font=('Microsoft YaHei UI', 16, 'bold'), corner_radius=4)
        elif avatar_obj is not None:
            avatar_lbl = ctk.CTkLabel(bubble_frame, text='', image=avatar_obj)
            avatar_lbl.image = avatar_obj
        else:
            avatar_lbl = ctk.CTkLabel(bubble_frame, text='👤', width=36, height=36, fg_color='#ccc', corner_radius=4)
        if is_me:
            avatar_lbl.pack(side='right', anchor='n', padx=(0, 5))
        else:
            avatar_lbl.pack(side='left', anchor='n', padx=(5, 0))
        if sender_pk:
            avatar_lbl.bind('<Button-3>', lambda e=None, pk=sender_pk, nm=sender_name: self.show_avatar_menu(e, pk, is_me, name=nm))
        dt = datetime.fromtimestamp(time_ts).strftime('%Y-%m-%d %H:%M:%S')
        info_text = f'{display_name} {dt}' if not is_me else f'{dt} {display_name}'
        ctk.CTkLabel(bubble_frame, text=info_text, font=('Microsoft YaHei UI', 11), text_color='gray').pack(anchor=align, padx=10)
        container = ctk.CTkFrame(bubble_frame, fg_color=bubble_color, corner_radius=6)
        container.pack(anchor=align, padx=10)
        self.msg_widgets[msg_id] = container
        is_history_card = False
        parsed_data = None
        if content.strip().startswith('{'):
            try:
                temp_data = json.loads(content)
                if temp_data.get('type') == 'history':
                    is_history_card = True
                    parsed_data = temp_data
                elif 'text' in temp_data:
                    inner_text = temp_data['text']
                    if inner_text and isinstance(inner_text, str) and inner_text.strip().startswith('{'):
                        try:
                            inner_json = json.loads(inner_text)
                            if inner_json.get('type') == 'history':
                                is_history_card = True
                                parsed_data = inner_json
                        except:
                            pass
                    if not is_history_card:
                        parsed_data = temp_data
            except:
                pass
        if is_history_card and parsed_data:
            self._render_history_card(container, parsed_data, msg_id, is_me, sender_pk)
            if scroll_to_bottom:
                self.after(50, lambda: self.scroll_to_bottom())
            return bubble_frame
        if reply_to_id:
            quote_bg = '#609e45' if is_me else '#E0E0E0'
            quote_text_color = '#e8f5e9' if is_me else '#555555'
            quote_frame = ctk.CTkFrame(container, fg_color=quote_bg, corner_radius=4)
            quote_frame.pack(fill='x', padx=5, pady=5)
            quote_frame.bind('<Button-3>', lambda e, rid=reply_to_id: self.show_quote_context_menu(e, rid))
            orig_msg = self.client.db.get_message(reply_to_id)
            q_text = '🔒 Orig Msg Locked'
            q_image_obj = None
            if orig_msg:
                o_pk = orig_msg[2]
                o_name = 'User'
                if orig_msg[5]:
                    o_name = 'Me'
                else:
                    o_name = self.client.db.get_contact_name(o_pk) or 'User'
                raw_c = orig_msg[3]
                disp_c = raw_c
                if raw_c.strip().startswith('{'):
                    try:
                        js = json.loads(raw_c)
                        if js.get('type') == 'history':
                            disp_c = f"[聊天记录] {js.get('title', 'History')}"
                        else:
                            disp_c = js.get('text', '')
                            if js.get('image'):
                                try:
                                    img_bytes = base64.b64decode(js['image'])
                                    pil_img = Image.open(BytesIO(img_bytes))
                                    max_w = 256
                                    max_h = 150
                                    img_w, img_h = pil_img.size
                                    ratio = min(max_w / img_w, max_h / img_h)
                                    if ratio < 1.0:
                                        new_w = int(img_w * ratio)
                                        new_h = int(img_h * ratio)
                                    else:
                                        new_w, new_h = (img_w, img_h)
                                    q_image_obj = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
                                    if not disp_c:
                                        disp_c = ''
                                except Exception as e:
                                    if not disp_c:
                                        disp_c = '[Image]'
                    except:
                        pass
                if len(disp_c) > 50:
                    disp_c = disp_c[:50] + '...'
                q_text = f'{o_name}: {disp_c}'
            if q_image_obj:
                q_img_label = ctk.CTkLabel(quote_frame, text='', image=q_image_obj)
                q_img_label.image = q_image_obj
                q_img_label.pack(side='left', padx=5, pady=2)
                q_img_label.bind('<Button-3>', lambda e, rid=reply_to_id: self.show_quote_context_menu(e, rid))
            q_label = ctk.CTkLabel(quote_frame, text=q_text, text_color=quote_text_color, font=('Microsoft YaHei UI', 11, 'italic'), wraplength=250)
            q_label.pack(side='left', padx=5)
            q_label.bind('<Button-3>', lambda e, rid=reply_to_id: self.show_quote_context_menu(e, rid))
        text_display = content
        img_bytes_data = None
        if parsed_data:
            text_display = parsed_data.get('text', '')
            if parsed_data.get('image'):
                try:
                    img_bytes_data = base64.b64decode(parsed_data['image'])
                except:
                    pass
        elif content.strip().startswith('{'):
            try:
                data = json.loads(content)
                text_display = data.get('text', '')
                if data.get('image'):
                    img_bytes_data = base64.b64decode(data['image'])
            except:
                pass
        if img_bytes_data:
            self._render_image_in_container(container, img_bytes_data, msg_id, is_me, sender_pk, content, should_scroll=scroll_to_bottom)
        if text_display:
            lines = text_display.count('\n') + len(text_display) // 20 + 1
            height = min(lines * 24 + 15, 500)
            msg_box = ctk.CTkTextbox(container, width=300, height=height, fg_color='transparent', text_color='black', font=('Microsoft YaHei UI', 14), activate_scrollbars=height > 400)
            msg_box.pack(padx=10, pady=5)
            msg_box.insert('0.0', text_display)
            msg_box.configure(state='disabled')
            msg_box.bind('<Button-3>', lambda e=None: self.show_context_menu(e, msg_id, content, is_me, sender_pk))
            urls = re.findall('(https?://\\S+)', text_display)
            if urls:
                self._process_media_urls(container, urls)
                for url in urls:
                    btn = ctk.CTkButton(container, text=f'🔗 Open: {url[:20]}...', height=24, fg_color='#444', font=('Microsoft YaHei UI', 11), command=lambda u=url: webbrowser.open(u))
                    btn.pack(pady=2, padx=5, fill='x')
            dage_links = re.findall('(dage://invite/\\S+)', text_display)
            for d_link in dage_links:
                btn_text = '🚀 加入群聊'
                btn_col = '#1F6AA5'
                if '/ghost/' in d_link:
                    btn_text = '⚡ 加入共享群'
                    btn_col = '#7B1FA2'
                btn = ctk.CTkButton(container, text=btn_text, height=28, fg_color=btn_col, font=('Microsoft YaHei UI', 12, 'bold'), command=lambda l=d_link: self.handle_dage_link(l))
                btn.pack(pady=5, padx=5, fill='x')
        if scroll_to_bottom:
            self.after(50, lambda: self.scroll_to_bottom())
        return bubble_frame

    def _compress_image_for_history(self, original_b64):
        try:
            img_bytes = base64.b64decode(original_b64)
            img = Image.open(BytesIO(img_bytes))
            max_side = 300
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=40)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f'Compress error: {e}')
            return None

    def prepare_step_forward(self):
        if not self.selected_ids:
            self.show_toast('请至少选择一条消息')
            return
        from gui_windows import SelectSessionDialog
        SelectSessionDialog(self, self._perform_step_forward)

    def hide_multi_select_ui(self):
        if hasattr(self, 'multi_op_bar') and self.multi_op_bar:
            self.multi_op_bar.destroy()
            self.multi_op_bar = None
        self.input_container.pack(fill='x', side='bottom')
        self.refresh_message_bubbles_selection(False)

    def refresh_message_bubbles_selection(self, show_checkbox):
        self.msg_scroll.update_idletasks()
        for msg_id, container in self.msg_widgets.items():
            if not container or not container.winfo_exists():
                continue
            bubble_frame = container.master
            if not bubble_frame:
                continue
            checkbox = None
            for child in bubble_frame.winfo_children():
                if isinstance(child, ctk.CTkCheckBox):
                    checkbox = child
                    break
            if show_checkbox and (not checkbox):
                checkbox = ctk.CTkCheckBox(bubble_frame, text='', width=24, height=24, checkbox_width=20, checkbox_height=20)
                checkbox.configure(command=lambda m=msg_id, cb=checkbox: self._toggle_selection(cb, m))
                children = bubble_frame.winfo_children()
                target = None
                for c in children:
                    if c != checkbox:
                        target = c
                        break
                if target:
                    checkbox.pack(side='left', padx=(10, 5), before=target)
                else:
                    checkbox.pack(side='left', padx=(10, 5))
            if checkbox:
                if show_checkbox:
                    if not checkbox.winfo_ismapped():
                        checkbox.pack_forget()
                        children = bubble_frame.winfo_children()
                        target = None
                        for c in children:
                            if c != checkbox and c.winfo_ismapped():
                                target = c
                                break
                        if target:
                            checkbox.pack(side='left', padx=(10, 5), before=target)
                        else:
                            checkbox.pack(side='left', padx=(10, 5))
                    if msg_id in self.selected_ids:
                        checkbox.select()
                    else:
                        checkbox.deselect()
                else:
                    checkbox.pack_forget()

    def _toggle_selection(self, checkbox_widget, msg_id):
        if checkbox_widget.get() == 1:
            self.selected_ids.add(msg_id)
        else:
            self.selected_ids.discard(msg_id)
        self.update_multi_op_bar()

    def update_multi_op_bar(self):
        if not hasattr(self, 'multi_op_bar') or not self.multi_op_bar:
            return
        count = len(self.selected_ids)
        txt = tr('LBL_SELECTED_COUNT').format(n=count)
        self.multi_count_lbl.configure(text=txt)
        total_size_bytes = 0
        for mid in self.selected_ids:
            msg = self.client.db.get_message(mid)
            if msg:
                content = msg[3]
                total_size_bytes += len(content.encode('utf-8'))
                if '"image":' in content:
                    total_size_bytes += 51200
                total_size_bytes += 200
        total_kb = total_size_bytes / 1024
        limit_kb = 800
        self.multi_size_lbl.configure(text=f'容量: {total_kb:.1f}KB / {limit_kb}KB')
        if total_kb > limit_kb:
            self.multi_size_lbl.configure(text_color='#D32F2F')
        elif total_kb > limit_kb * 0.8:
            self.multi_size_lbl.configure(text_color='#FFA000')
        else:
            self.multi_size_lbl.configure(text_color='gray')

    def _on_global_click(self, event):
        if self._emoji_lock:
            return
        if self.emoji_window and self.emoji_window.winfo_ismapped():
            clicked_widget = event.widget
            try:
                toplevel = clicked_widget.winfo_toplevel()
                if toplevel != self.emoji_window:
                    if clicked_widget != self.btn_emoji:
                        self.emoji_window.hide_window()
            except:
                pass

    def open_emoji_panel(self):
        if not self.current_chat_id:
            self.show_toast(tr('TOAST_SELECT_CHAT'))
            return
        if self.emoji_window and self.emoji_window.winfo_ismapped():
            self.emoji_window.hide_window()
            return
        self._emoji_lock = True
        self.after(200, lambda: setattr(self, '_emoji_lock', False))
        if not self.emoji_window or not self.emoji_window.winfo_exists():
            self._preload_emoji_window()

        def _send_emoji_immediately(img_bytes):
            if not img_bytes:
                return
            try:
                b64_str = base64.b64encode(img_bytes).decode('utf-8')
                self.send_message(image_data=b64_str)
                if self.emoji_window:
                    self.emoji_window.hide_window()
            except Exception as e:
                print(f'Send emoji error: {e}')
        self.emoji_window.on_select = _send_emoji_immediately
        try:
            self.emoji_window.show_at(self.tool_bar)
        except Exception as e:
            print(f'Open emoji error: {e}')
            self.emoji_window.deiconify()

    def start_screenshot(self, event=None):
        if not self.current_chat_id:
            if self.winfo_viewable():
                self.show_toast(tr('TOAST_SELECT_CHAT'))
            return
        from gui_windows import ScreenshotOverlay
        was_visible = self.winfo_viewable()
        if was_visible:
            self.withdraw()
            self.update()
            time.sleep(0.2)

        def _on_captured(img_bytes):
            if was_visible and (not self.winfo_viewable()):
                self.deiconify()
                self.lift()
            if img_bytes:
                self.stage_image(img_bytes)
        try:
            overlay = ScreenshotOverlay(self, _on_captured)
            if not overlay.winfo_exists():
                if was_visible:
                    self.deiconify()
                return

            def _on_overlay_close(e):
                if e.widget == overlay:
                    if was_visible and (not self.winfo_viewable()):
                        self.deiconify()
            overlay.bind('<Destroy>', _on_overlay_close, add='+')
        except Exception as e:
            print(f'Screenshot error: {e}')
            if was_visible:
                self.deiconify()

    def _on_focus_in(self, event):
        self.is_window_focused = True

    def _on_focus_out(self, event):
        self.is_window_focused = False

    def _start_loading_thread(self):
        t = threading.Thread(target=self._load_heavy_modules, daemon=True)
        t.start()

    def _load_heavy_modules(self):
        global FileLock, GuiChatUser, to_hex_pubkey, get_npub_abbr, to_npub
        global LoginWindow, ProfileWindow, RelayConfigWindow, InfoWindow
        global SelectContactDialog, GroupBanListWindow, LocalBlockListWindow, ExportSelectionDialog
        global ImageViewer, nacl
        try:
            self._update_splash(0.1, tr('SPLASH_LOADING_CRYPTO'))
            import nacl.signing
            import nacl.encoding
            self._update_splash(0.3, tr('SPLASH_LOADING_UTILS'))
            from file_locker import FileLock as FL
            FileLock = FL
            from key_utils import to_hex_pubkey as thp, get_npub_abbr as gna, to_npub as tn
            to_hex_pubkey, get_npub_abbr, to_npub = (thp, gna, tn)
            self._update_splash(0.5, tr('SPLASH_LOADING_DB'))
            from client_gui import GuiChatUser as GCU
            GuiChatUser = GCU
            self._update_splash(0.7, tr('SPLASH_LOADING_UI'))
            from gui_windows import LoginWindow as LW, ProfileWindow as PW, RelayConfigWindow as RCW, InfoWindow as IW, SelectContactDialog as SCD, GroupBanListWindow as GBLW, LocalBlockListWindow as LBLW, ExportSelectionDialog as ESD
            LoginWindow, ProfileWindow, RelayConfigWindow, InfoWindow = (LW, PW, RCW, IW)
            SelectContactDialog, GroupBanListWindow, LocalBlockListWindow, ExportSelectionDialog = (SCD, GBLW, LBLW, ESD)
            from gui_viewer import ImageViewer as IV
            ImageViewer = IV
            self._update_splash(0.8, tr('SPLASH_LOADING_RES'))
            self._try_load_ghost_mask()
            self._update_splash(1.0, tr('SPLASH_READY'))
            time.sleep(0.3)
            self.after(0, self._finish_splash_and_show_login)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror(tr('DIALOG_ERROR_TITLE'), f"{tr('DIALOG_START_FAIL')}: {e}"))
            self.after(0, self.destroy)

    def _update_splash(self, progress, text):
        self.after(0, lambda: self.progress_bar.set(progress))
        self.after(0, lambda: self.status_label.configure(text=text))

    def _finish_splash_and_show_login(self):
        self.splash_frame.destroy()
        self.overrideredirect(False)
        self.attributes('-topmost', False)
        self.withdraw()
        self.geometry('1000x650')
        self.title(APP_BUILD_NAME)
        self._show_login()

    def _get_tray_image(self):
        try:
            icon_path = _get_resource_path(os.path.join('img', 'dagechat.ico'))
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                return img.convert('RGBA')
            else:
                print(f'⚠️ [Tray] Icon file not found at: {icon_path}')
        except Exception as e:
            print(f'❌ [Tray] Load icon failed: {e}')
        print('ℹ️ [Tray] Using fallback icon (Blue Block)')
        img = Image.new('RGBA', (64, 64), color=(31, 106, 165, 255))
        return img

    def _get_tray_image(self):
        icon_path = _get_resource_path(os.path.join('img', 'dagechat.ico'))
        if os.path.exists(icon_path):
            try:
                return Image.open(icon_path)
            except:
                pass
        img = Image.new('RGB', (64, 64), color=(31, 106, 165))
        return img

    def _on_window_unmap(self, event):
        if event.widget == self:
            if getattr(self, '_is_lock_active', False):
                return
            self._last_hide_timestamp = time.time()

    def _on_window_map(self, event):
        if event.widget == self and self.ui_is_ready:
            self._check_security_lock()

    def _check_security_lock(self):
        if self._LOCK_TIMEOUT <= 0:
            return
        if self._last_hide_timestamp == 0:
            return
        if getattr(self, '_is_lock_active', False):
            return
        time_diff = time.time() - self._last_hide_timestamp
        if time_diff > self._LOCK_TIMEOUT:
            self._is_lock_active = True
            try:
                self.withdraw()
                self.update()
                from gui_windows import PasswordInputDialog
                mins = self._LOCK_TIMEOUT // 60
                dialog = PasswordInputDialog(self, title='安全锁定', prompt=f'已锁定 (超时{mins}分钟)，请输入密码恢复:')
                pwd = dialog.get_input()
                if pwd and self.client.verify_password(pwd):
                    self._last_hide_timestamp = 0
                    self.deiconify()
                    self.lift()
                    self.focus_force()
                    self.show_toast('✅ 解锁成功')
                else:
                    self.withdraw()
                    self.update()
                    if pwd:
                        self.after(200, lambda: self.show_toast('❌ 密码错误，保持锁定'))
            finally:
                self._is_lock_active = False
        else:
            self._last_hide_timestamp = 0

    def restore_window(self, icon=None, item=None):

        def _do_restore():
            now = time.time()
            should_lock = False
            if self._LOCK_TIMEOUT > 0 and self._last_hide_timestamp > 0:
                if now - self._last_hide_timestamp > self._LOCK_TIMEOUT:
                    should_lock = True
            if should_lock:
                self._check_security_lock()
            else:
                self._last_hide_timestamp = 0
                self.deiconify()
                self.lift()
                self.focus_force()
                self.is_window_focused = True
        self.after(0, _do_restore)

    def confirm_quit_from_tray(self, icon=None, item=None):
        self.after(0, self.on_closing_confirmed)

    def on_x_click(self):
        self._last_hide_timestamp = time.time()
        self.withdraw()

    def on_closing_confirmed(self):
        self.deiconify()
        self.lift()
        if messagebox.askyesno('退出确认', '确定要退出 DageChat 吗？'):
            self.quit_app()

    def quit_app(self):
        if self.instance_lock:
            self.instance_lock.release()
        if self.tray_icon:
            self.tray_icon.stop()
        self.destroy()
        sys.exit(0)

    def _flash_session_item(self, session_id):
        if session_id not in self.session_widgets:
            return
        widget = self.session_widgets[session_id]
        base_color = 'transparent'
        flash_color = '#3A3A3A'

        def _do_flash(count):
            if not widget.winfo_exists():
                return
            if count <= 0:
                widget.configure(fg_color=base_color)
                return
            current_fg = widget.cget('fg_color')
            next_color = flash_color if current_fg == base_color else base_color
            widget.configure(fg_color=next_color)
            self.after(500, lambda: _do_flash(count - 1))
        _do_flash(5 * 2)

    def show_system_notification(self, msg_data):
        if not self.tray_icon:
            return
        if msg_data.get('is_me', False):
            return
        sender_pk = msg_data.get('real_sender') or msg_data.get('sender_pk')
        if self.client and sender_pk == self.client.pk:
            return
        gid = msg_data.get('group_id')
        is_at_me = msg_data.get('is_at_me', False)
        from client_persistent import OFFICIAL_GROUP_CONFIG
        if gid == OFFICIAL_GROUP_CONFIG['id'] and (not is_at_me):
            return
        msg_ts = msg_data.get('time', 0)
        now_ts = int(time.time())
        if now_ts - msg_ts > 120:
            return
        source_id = gid if gid else sender_pk
        if not is_at_me:
            last_time = self.last_notify_times.get(source_id, 0)
            if now_ts - last_time < 5.0:
                return
        self.last_notify_times[source_id] = now_ts
        title = tr('NOTIFY_TITLE_APP')
        msg_text = tr('NOTIFY_CONTENT_DEFAULT')
        prefix = tr('NOTIFY_PREFIX_MENTION') if is_at_me else ''
        if gid:
            grp = self.client.groups.get(gid)
            if grp:
                if str(grp.get('type')) == '1':
                    title = tr('NOTIFY_TITLE_SECURITY')
                    msg_text = f"{prefix}{tr('NOTIFY_CONTENT_ANON')}"
                else:
                    title = tr('NOTIFY_TITLE_GROUP')
                    msg_text = f"{prefix}{tr('NOTIFY_CONTENT_GROUP').format(group=grp['name'])}"
        else:
            nickname = msg_data.get('nickname', 'User')
            title = tr('NOTIFY_TITLE_NEW')
            msg_text = f"{prefix}{tr('NOTIFY_CONTENT_DM').format(name=nickname)}"
        cfg = self.client.ui_settings
        allow_bubble = cfg.get('notify_bubble', True)
        allow_sound = cfg.get('notify_sound', False)
        if allow_bubble:
            try:
                self.tray_icon.notify(msg_text, title)
            except Exception as e:
                print(f'Notification error: {e}')
        elif allow_sound:
            try:
                import winsound
                winsound.MessageBeep()
            except:
                pass

    def _filter_contact_list(self, event=None):
        keyword = self.contact_search_entry.get().strip().lower()
        self.refresh_ui(contact_keyword=keyword)

    def _filter_chat_list(self, event=None):
        keyword = self.chat_search_entry.get().strip().lower()
        self.refresh_ui(chat_keyword=keyword)

    def _lazy_build_ui(self):
        if self.ui_is_ready:
            return
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky='nsew')
        self.sidebar.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.sidebar, text=tr('APP_TITLE'), font=('Microsoft YaHei UI', 20, 'bold')).grid(row=0, column=0, pady=20, sticky='ew')
        self.tab_view = ctk.CTkTabview(self.sidebar, width=220)
        self.tab_view.grid(row=1, column=0, padx=10, sticky='nsew')
        self.tab_chats = self.tab_view.add(tr('TAB_CHATS'))
        self.tab_contacts = self.tab_view.add(tr('TAB_CONTACTS'))
        self.chat_search_entry = ctk.CTkEntry(self.tab_chats, placeholder_text=tr('SEARCH_PH'), height=30)
        self.chat_search_entry.pack(fill='x', padx=5, pady=(5, 5))
        self.chat_search_entry.bind('<KeyRelease>', self._filter_chat_list)
        self.scroll_chats = ctk.CTkScrollableFrame(self.tab_chats, fg_color='transparent')
        self.scroll_chats.pack(fill='both', expand=True)
        self.contact_search_entry = ctk.CTkEntry(self.tab_contacts, placeholder_text=tr('PH_SEARCH_MEMBER'), height=30)
        self.contact_search_entry.pack(fill='x', padx=5, pady=(5, 5))
        self.contact_search_entry.bind('<KeyRelease>', self._filter_contact_list)
        self.scroll_contacts = ctk.CTkScrollableFrame(self.tab_contacts, fg_color='transparent')
        self.scroll_contacts.pack(fill='both', expand=True)
        self.profile_frame = ctk.CTkFrame(self.sidebar, height=80, corner_radius=0, fg_color='#2b2b2b', cursor='hand2')
        self.profile_frame.grid(row=2, column=0, sticky='ew')
        self.profile_frame.bind('<Button-1>', lambda e: self.show_my_profile())
        self.my_avatar_label = ctk.CTkLabel(self.profile_frame, text='', width=40, height=40)
        self.my_avatar_label.pack(side='left', padx=(10, 5), pady=10)
        self.my_avatar_label.bind('<Button-1>', lambda e: self.show_my_profile())
        self.my_name_label = ctk.CTkLabel(self.profile_frame, text='', font=('Microsoft YaHei UI', 14, 'bold'))
        self.my_name_label.pack(side='left', padx=5)
        self.my_name_label.bind('<Button-1>', lambda e: self.show_my_profile())
        self.toolbar = ctk.CTkFrame(self.sidebar, fg_color='transparent')
        self.toolbar.grid(row=3, column=0, sticky='ew', pady=5)
        self.status_indicator = ctk.CTkCanvas(self.toolbar, width=14, height=14, bg='#2b2b2b', highlightthickness=0)
        self.status_indicator.pack(side='left', padx=(10, 5))
        self.status_indicator.create_oval(2, 2, 12, 12, fill='gray', tags='status_light')
        ctk.CTkButton(self.toolbar, text=tr('BTN_NEW_GROUP'), width=60, command=self.create_group_dialog).pack(side='left', padx=5)
        ctk.CTkButton(self.toolbar, text=tr('BTN_NEW_CONTACT'), width=60, command=self.add_contact_dialog).pack(side='left', padx=5)
        ctk.CTkButton(self.toolbar, text='⚙️', width=30, fg_color='#555', command=self.open_settings_window).pack(side='right', padx=10)
        self.chat_area = ctk.CTkFrame(self, corner_radius=0, fg_color='transparent')
        self.chat_area.grid(row=0, column=1, sticky='nsew')
        self.welcome_frame = ctk.CTkFrame(self.chat_area, fg_color='transparent')
        self.welcome_frame.place(relx=0.5, rely=0.5, anchor='center')
        ctk.CTkLabel(self.welcome_frame, text=tr('WELCOME_TITLE'), font=('Microsoft YaHei UI', 40, 'bold'), text_color='#333').pack(pady=10)
        ctk.CTkLabel(self.welcome_frame, text=tr('WELCOME_SUB'), font=('Microsoft YaHei UI', 14), text_color='gray').pack()
        ctk.CTkLabel(self.welcome_frame, text=tr('WELCOME_TIP'), font=('Microsoft YaHei UI', 12), text_color='#555').pack(pady=(40, 0))
        self.active_chat_container = ctk.CTkFrame(self.chat_area, fg_color='transparent', corner_radius=0)
        self.top_bar = ctk.CTkFrame(self.active_chat_container, height=50, corner_radius=0, fg_color='#232323')
        self.top_bar.pack(fill='x', side='top')
        self.title_frame = ctk.CTkFrame(self.top_bar, fg_color='transparent', cursor='hand2')
        self.title_frame.pack(side='left', padx=20, pady=5)
        self.title_frame.bind('<Button-1>', lambda e: self.show_chat_info())
        self.chat_title = ctk.CTkLabel(self.title_frame, text='', font=('Microsoft YaHei UI', 16, 'bold'), anchor='w')
        self.chat_title.pack(anchor='w')
        self.chat_title.bind('<Button-1>', lambda e: self.show_chat_info())
        self.fingerprint_label = ctk.CTkLabel(self.title_frame, text='', font=('Consolas', 10), text_color='gray', anchor='w')
        self.fingerprint_label.pack(anchor='w')
        self.fingerprint_label.bind('<Button-1>', lambda e: self.show_chat_info())
        self.btn_more = ctk.CTkButton(self.top_bar, text='...', width=40, font=('Microsoft YaHei UI', 20, 'bold'), fg_color='transparent', hover_color='#444', text_color='#ddd', command=self.show_chat_more_menu)
        self.btn_more.pack(side='right', padx=15, pady=10)
        self.chat_frame_container = ctk.CTkFrame(self.active_chat_container, fg_color='transparent')
        self.chat_frame_container.pack(fill='both', expand=True, padx=5, pady=5)
        self.input_container = ctk.CTkFrame(self.active_chat_container, corner_radius=0, fg_color='#2b2b2b')
        self.input_container.pack(fill='x', side='bottom')
        self.reply_bar = ctk.CTkFrame(self.input_container, height=30, fg_color='#3a3a3a')
        self.reply_thumb_label = ctk.CTkLabel(self.reply_bar, text='', image=None)
        self.reply_thumb_label.pack(side='left', padx=(10, 5), pady=2)
        self.reply_label = ctk.CTkLabel(self.reply_bar, text='', text_color='silver', font=('Microsoft YaHei UI', 12))
        self.reply_label.pack(side='left', padx=5)
        ctk.CTkButton(self.reply_bar, text='X', width=30, height=20, fg_color='transparent', command=self.cancel_reply).pack(side='right', padx=5)
        self.tool_bar = ctk.CTkFrame(self.input_container, height=30, fg_color='#2b2b2b', corner_radius=0)
        self.tool_bar.pack(fill='x', padx=10, pady=(5, 0))
        self.btn_emoji = ctk.CTkButton(self.tool_bar, text=tr('TOOL_BTN_EMOJI'), width=60, height=24, fg_color='transparent', hover_color='#444', text_color='#ccc', command=self.open_emoji_panel)
        self.btn_emoji.pack(side='left', padx=2)
        self.btn_file = ctk.CTkButton(self.tool_bar, text=tr('TOOL_BTN_FILE'), width=80, height=24, fg_color='transparent', hover_color='#444', text_color='#ccc', command=self.select_image)
        self.btn_file.pack(side='left', padx=2)
        self.btn_screenshot = ctk.CTkButton(self.tool_bar, text=tr('TOOL_BTN_SCREENSHOT'), width=100, height=24, fg_color='transparent', hover_color='#444', text_color='#ccc', command=self.start_screenshot)
        self.btn_screenshot.pack(side='left', padx=2)
        self.preview_bar = ctk.CTkFrame(self.input_container, fg_color='#333', corner_radius=5)
        self.preview_image_lbl = ctk.CTkLabel(self.preview_bar, text='', image=None)
        self.preview_image_lbl.pack(side='left', padx=10, pady=5)
        self.preview_info_lbl = ctk.CTkLabel(self.preview_bar, text='待发送图片', text_color='gray', font=('Microsoft YaHei UI', 11))
        self.preview_info_lbl.pack(side='left', padx=5)
        ctk.CTkButton(self.preview_bar, text='🗑️', width=30, height=30, fg_color='transparent', hover_color='#555', command=self.clear_pending_image).pack(side='right', padx=10)
        self.input_area = ctk.CTkFrame(self.input_container, height=120, corner_radius=0, fg_color='#2b2b2b')
        self.input_area.pack(fill='x', padx=10, pady=10)
        self.msg_entry = ctk.CTkTextbox(self.input_area, height=80, fg_color='#343638', text_color='#fff', font=('Microsoft YaHei UI', 14))
        self.msg_entry.pack(side='left', fill='x', expand=True, padx=(10, 10), pady=8)
        self.msg_entry.bind('<Return>', self._on_enter_key)
        self.msg_entry.bind('<Control-Return>', self._on_ctrl_enter_key)
        self.msg_entry.bind('<KeyRelease>', self._on_input_key_release)
        self.msg_entry.bind('<Button-1>', self._on_input_click)
        self.bind_all('<Control-v>', self.on_paste)
        btn_text = f"{tr('BTN_SEND')} (Enter)"
        self.send_btn = ctk.CTkButton(self.input_area, text=btn_text, width=80, height=40, command=self.send_message)
        self.send_btn.pack(side='right', padx=(0, 10), pady=15)
        self.ui_is_ready = True
        self._show_welcome_state()

    def stage_image(self, img_bytes):
        if not img_bytes:
            return
        self.pending_image_bytes = img_bytes
        try:
            pil_img = Image.open(BytesIO(img_bytes))
            pil_img.thumbnail((200, 80))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.preview_image_lbl.configure(image=ctk_img)
            self.preview_image_lbl.image = ctk_img
            size_kb = len(img_bytes) / 1024
            self.preview_info_lbl.configure(text=f'图片 ({size_kb:.1f} KB)')
            self.preview_bar.pack(after=self.tool_bar, fill='x', padx=10, pady=(2, 2))
            self.msg_entry.focus_set()
        except Exception as e:
            self.show_toast(f'图片预览失败: {e}')
            self.clear_pending_image()

    def clear_pending_image(self):
        self.pending_image_bytes = None
        self.preview_image_lbl.configure(image=None)
        self.preview_bar.pack_forget()

    def _on_input_click(self, event):
        if hasattr(self, 'current_mention_dialog') and self.current_mention_dialog:
            try:
                if self.current_mention_dialog.winfo_exists():
                    self.current_mention_dialog.destroy()
            except:
                pass
            self.current_mention_dialog = None
        if self.emoji_window and self.emoji_window.winfo_exists():
            if self.emoji_window.winfo_viewable():
                self.emoji_window.hide_window()

    def add_contact_dialog(self):
        from gui_windows import InputWindow
        dialog = InputWindow(self, title=tr('BTN_NEW_CONTACT'), prompt='Pubkey (Hex / npub1):')
        raw_pk = dialog.get_input()
        if not raw_pk:
            return
        clean_pk = to_hex_pubkey(raw_pk)
        if clean_pk and len(clean_pk) == 64:
            if clean_pk == self.client.pk:
                messagebox.showerror(tr('DIALOG_ERROR_TITLE'), 'Cannot add yourself!', parent=self)
                return
            current_name = self.client.db.get_contact_name(clean_pk)
            display_name = current_name if current_name else 'Syncing...'
            self.client.db.save_contact(clean_pk, display_name, enc_key=clean_pk, is_friend=1)
            self.client.fetch_user_profile(clean_pk)
            self.refresh_ui()
            self.tab_view.set(tr('TAB_CONTACTS'))
            self.switch_chat(clean_pk, display_name, 'dm')
            self.after(500, lambda: self.send_auto_greeting(clean_pk))
            self.show_toast(tr('TOAST_FRIEND_ADDED'))
        else:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), 'Invalid Pubkey', parent=self)

    def handle_batch_delete(self):
        if not self.selected_ids:
            self.show_toast(tr('TOAST_SELECT_ONE'))
            return
        ids_list = list(self.selected_ids)
        count = len(ids_list)
        if messagebox.askyesno(tr('DIALOG_BATCH_DEL_TITLE'), tr('DIALOG_BATCH_DEL_MSG').format(n=count), icon='warning'):
            deleted_count = self.client.db.delete_messages_batch(ids_list)
            for msg_id in ids_list:
                if msg_id in self.msg_widgets:
                    container = self.msg_widgets[msg_id]
                    if container and container.master:
                        try:
                            container.master.destroy()
                        except:
                            pass
                    del self.msg_widgets[msg_id]
                    if hasattr(self.msg_scroll, 'rendered_ids'):
                        self.msg_scroll.rendered_ids.discard(msg_id)
            self._toggle_multi_select_mode(False)
            self.show_toast(tr('TOAST_BATCH_DEL_OK').format(n=deleted_count))

    def prepare_batch_forward(self):
        if not self.selected_ids:
            self.show_toast('请至少选择一条消息')
            return
        batch_data = []
        valid_selection = True
        for msg_id in self.selected_ids:
            msg = self.client.db.get_message(msg_id)
            if msg:
                batch_data.append({'id': msg[0], 'group_id': msg[1], 'sender_pk': msg[2], 'content': msg[3], 'created_at': msg[4], 'is_me': msg[5], 'reply_to_id': msg[6] if len(msg) > 6 else None})
            else:
                valid_selection = False
                break
        if not valid_selection:
            self.show_toast('部分消息已丢失，请重试')
            self._toggle_multi_select_mode(False)
            return
        from gui_windows import SelectSessionDialog

        def _on_forward_select(target_id, target_type, target_name):
            self.forward_messages(target_id, target_type, target_name, batch_data)
        SelectSessionDialog(self, _on_forward_select)

    def forward_messages(self, target_id, target_type, target_name, messages_data):
        for msg in messages_data:
            text = msg.get('content', '')
            reply_to_id = msg.get('reply_to_id')
            image_b64 = None
            if text.strip().startswith('{'):
                try:
                    data = json.loads(text)
                    text = data.get('text', '')
                    image_b64 = data.get('image')
                except:
                    pass
            if target_type == 'group':
                self.client.send_group_msg(target_id, text, reply_to_id=reply_to_id, image_base64=image_b64)
            elif target_type == 'dm':
                enc_key = self.client.db.get_contact_enc_key(target_id)
                if enc_key:
                    self.client.send_dm(target_id, text, enc_key, reply_to_id=reply_to_id, image_base64=image_b64)
            time.sleep(0.1)
        self.show_toast(f'已转发 {len(messages_data)} 条消息')
        self._toggle_multi_select_mode(False)

    def _on_enter_key(self, event):
        self.send_message()
        return 'break'

    def _on_ctrl_enter_key(self, event):
        self.msg_entry.insert('insert', '\n')
        return 'break'

    def _on_input_key_release(self, event):
        if self.current_chat_type != 'group':
            return
        grp = self.client.groups.get(self.current_chat_id)
        if grp and str(grp.get('type')) == '1':
            return
        if event.char == '@':
            self._open_mention_selector()

    def _open_mention_selector(self):
        gid = self.current_chat_id
        if not gid:
            return
        self._on_input_click(None)
        m_pks = self.client.db.get_group_members(gid)
        members_data = []
        owner = self.client.db.get_group_owner(gid)
        if owner == self.client.pk:
            members_data.append({'name': tr('LBL_EVERYONE'), 'pk': 'ALL'})
        for pk in m_pks:
            if pk == self.client.pk:
                continue
            name = self.client.db.get_contact_name(pk) or f'User {get_npub_abbr(pk)}'
            members_data.append({'name': name, 'pk': pk})
        if not members_data:
            return
        from gui_windows import SelectGroupMemberDialog

        def _on_select(pk, name):
            self.msg_entry.insert('insert', f'{name} ')
            self.pending_mentions[name] = pk
            self.msg_entry.focus_set()
            self.current_mention_dialog = None
        self.current_mention_dialog = SelectGroupMemberDialog(self, members_data, _on_select)

    def _show_welcome_state(self):
        self.active_chat_container.pack_forget()
        self.welcome_frame.place(relx=0.5, rely=0.5, anchor='center')

    def _show_active_chat_state(self):
        self.welcome_frame.place_forget()
        self.active_chat_container.pack(fill='both', expand=True)

    def open_search_window(self):
        from gui_windows import SearchWindow
        SearchWindow(self)

    def jump_to_message_context(self, chat_id, target_msg_id):
        chat_name = tr('MSG_SENDER_UNKNOWN')
        chat_type = 'dm'
        if chat_id in self.client.groups:
            chat_name = self.client.groups[chat_id]['name']
            chat_type = 'group'
        else:
            info = self.client.db.get_contact_info(chat_id)
            if info:
                chat_name = info[1]
            else:
                n = self.client.db.get_contact_name(chat_id)
                if n:
                    chat_name = n
        self.switch_chat(chat_id, chat_name, chat_type)
        if self.load_task_id:
            self.after_cancel(self.load_task_id)
            self.load_task_id = None
        target_frame = self.msg_scroll
        if not target_frame:
            return
        for w in target_frame.winfo_children():
            w.destroy()
        if hasattr(target_frame, 'rendered_ids'):
            target_frame.rendered_ids.clear()
        else:
            target_frame.rendered_ids = set()
        self.msg_widgets.clear()
        msgs, has_more_old, has_more_new = self.client.db.get_context_around_message(chat_id, target_msg_id, window=15)
        if not msgs:
            ctk.CTkLabel(target_frame, text=tr('CTX_NO_CONTEXT'), text_color='gray').pack(pady=20)
            return
        self.min_loaded_ts = msgs[0][4]
        if hasattr(target_frame, 'max_loaded_ts'):
            target_frame.max_loaded_ts = msgs[-1][4]
        if has_more_old:
            self.btn_load_more = ctk.CTkButton(target_frame, text=tr('CTX_LOAD_MORE_UP'), fg_color='transparent', text_color='#1F6AA5', height=24, command=self.load_more_history)
            self.btn_load_more.pack(pady=10)
        is_ghost_grp = False
        grp = self.client.groups.get(self.current_chat_id)
        if grp and str(grp.get('type')) == '1':
            is_ghost_grp = True
        target_widget = None
        for m in msgs:
            try:
                mid = m[0]
                msg_content = m[3]
                sender_pk = m[2]
                created_at = m[4]
                is_me_val = m[5] == 1
                reply_id = m[6] if len(m) > 6 else None
                sender_name = tr('MSG_SENDER_UNKNOWN')
                if is_ghost_grp:
                    try:
                        if msg_content.startswith('{'):
                            sender_name = json.loads(msg_content).get('alias', tr('MSG_SENDER_ANON'))
                    except:
                        pass
                else:
                    sender_name = self.client._format_sender_info(sender_pk)
                self.add_message_bubble(mid, msg_content, is_me_val, sender_name, created_at, reply_id, sender_pk, scroll_to_bottom=False)
                if mid == target_msg_id:
                    target_widget = self.msg_widgets.get(mid)
            except Exception as e:
                continue
        if target_widget:
            self._highlight_widget(target_widget)
            self.after(200, lambda: self._scroll_to_widget(target_widget))
        if has_more_new:
            ctk.CTkLabel(target_frame, text=tr('CTX_HAS_MORE_DOWN'), text_color='gray', font=('Microsoft YaHei UI', 10)).pack(pady=5)
            ctk.CTkButton(target_frame, text=tr('CTX_BACK_TO_NEW'), fg_color='transparent', text_color='#1F6AA5', command=self.reload_current_chat).pack(pady=10)
        else:
            self.after(200, self.scroll_to_bottom)

    def _highlight_widget(self, widget):
        if not widget:
            return
        original_fg = widget.cget('fg_color')
        flash_color = '#3A3A3A'

        def _flash(count):
            if count <= 0:
                try:
                    widget.configure(fg_color=original_fg)
                except:
                    pass
                return
            color = flash_color if count % 2 == 1 else original_fg
            try:
                widget.configure(fg_color=color)
            except:
                pass
            self.after(300, lambda: _flash(count - 1))
        _flash(6)

    def _scroll_to_widget(self, widget, retry=0):
        try:
            if not widget or not self.msg_scroll:
                return
            self.msg_scroll.update_idletasks()
            target_row = widget.master
            target_y = target_row.winfo_y()
            target_h = target_row.winfo_height()
            canvas = self.msg_scroll._parent_canvas
            view_height = canvas.winfo_height()
            bbox = canvas.bbox('all')
            total_scroll_height = bbox[3] if bbox else 0
            if total_scroll_height <= view_height:
                return
            desired_y = target_y - view_height / 2 + target_h / 2
            max_scroll = total_scroll_height - view_height
            desired_y = max(0, min(desired_y, max_scroll))
            fraction = desired_y / total_scroll_height
            canvas.yview_moveto(fraction)
            if retry < 3:
                self.after(200, lambda: self._scroll_to_widget(widget, retry + 1))
        except Exception as e:
            print(f'Scroll Error: {e}')

    def _try_load_ghost_mask(self):
        image_path = _get_resource_path(os.path.join('img', 'ghost_mask.png'))
        if os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                self._ghost_mask_pil = img
                self._ghost_mask_cache = ctk.CTkImage(light_image=img, dark_image=img, size=(36, 36))
            except Exception as e:
                print(f'❌ 加载MASK图片失败: {e}')
        else:
            print(f"ℹ️ [提示] 未找到 {image_path}，共享密钥群将使用默认图标 'V'。")

    def _show_login(self):
        self.login_window = LoginWindow(self)
        self._preload_emoji_window()

    def on_paste(self, event):
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                self.stage_image(buffer.getvalue())
                return 'break'
            if isinstance(img, list):
                if img and isinstance(img[0], str) and os.path.isfile(img[0]):
                    try:
                        with open(img[0], 'rb') as f:
                            raw = f.read()
                        Image.open(BytesIO(raw)).verify()
                        self.stage_image(raw)
                        return 'break'
                    except:
                        pass
        except Exception as e:
            print(f'Paste error: {e}')

    def confirm_send_image(self, pil_img):
        preview_win = ctk.CTkToplevel(self)
        preview_win.title('发送图片')
        preview_win.geometry('400x500')
        preview_win.attributes('-topmost', True)
        w, h = pil_img.size
        ratio = min(380 / w, 380 / h)
        new_size = (int(w * ratio), int(h * ratio))
        preview_ctk = ctk.CTkImage(pil_img, size=new_size)
        lbl = ctk.CTkLabel(preview_win, text='', image=preview_ctk)
        lbl.pack(pady=20)

        def _send():
            buffer = BytesIO()
            if pil_img.mode != 'RGB':
                pil_img.convert('RGB').save(buffer, format='JPEG')
            else:
                pil_img.save(buffer, format='JPEG')
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            self.send_message(image_data=b64)
            preview_win.destroy()
        ctk.CTkButton(preview_win, text='发送', fg_color='green', command=_send).pack(pady=10)
        ctk.CTkButton(preview_win, text='取消', fg_color='gray', command=preview_win.destroy).pack(pady=5)

    def update_relay_status_icon(self, status_data):

        def _update():
            try:
                if not self.winfo_exists():
                    return
                total = status_data['total']
                connected = status_data['connected']
                color = 'gray'
                if total > 0:
                    if connected == 0:
                        color = '#D32F2F'
                    elif connected < total:
                        color = '#FFA000'
                    else:
                        color = '#388E3C'
                self.status_indicator.itemconfigure('status_light', fill=color)
            except:
                pass
        self.after(0, _update)

    def _get_avatar_from_cache(self, pubkey, size=(36, 36)):
        if not pubkey:
            return None
        if pubkey in self.avatar_cache:
            return self.avatar_cache[pubkey]
        info = self.client.db.get_contact_info(pubkey)
        if info and len(info) > 6:
            b64 = info[6]
            if b64 and len(b64) > 10:
                try:
                    img_data = base64.b64decode(b64)
                    pil_img = Image.open(BytesIO(img_data))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                    self.avatar_cache[pubkey] = ctk_img
                    return ctk_img
                except:
                    pass
        if hasattr(self, '_ghost_mask_pil') and self._ghost_mask_pil:
            return ctk.CTkImage(light_image=self._ghost_mask_pil, dark_image=self._ghost_mask_pil, size=size)
        return None

    def _calc_invite_checksum(self, gid, key, gtype):
        from hashlib import sha256
        salt = 'DAGE_SECURE_V1'
        raw = f'{gid}{key}{gtype}{salt}'
        return sha256(raw.encode()).hexdigest()[:6]

    def start_backend_secure(self, db_file, mode, password, nickname=None, priv_key=None):
        try:
            lock_path = db_file + '.lock'
            if self.instance_lock:
                self.instance_lock.release()
            new_lock = FileLock(lock_path)
            if not new_lock.acquire():
                messagebox.showerror(tr('DIALOG_START_FAIL'), tr('DIALOG_START_FAIL_MSG'))
                return
            self.instance_lock = new_lock
            self.rendered_msg_ids.clear()
            if self.msg_scroll:
                for w in self.msg_scroll.winfo_children():
                    w.destroy()
            self.client = GuiChatUser(db_file, on_message_callback=self.on_backend_message, nickname=nickname)
            self.client.on_relay_status_callback = self.update_relay_status_icon
            try:
                saved_min = self.client.db.get_setting('auto_lock_minutes')
                if saved_min is not None:
                    self._LOCK_TIMEOUT = int(saved_min) * 60
                else:
                    self._LOCK_TIMEOUT = 30 * 60
            except Exception as e:
                print(f'Load setting error: {e}')
                self._LOCK_TIMEOUT = 30 * 60
            self._is_lock_active = False
            success, msg = (False, '')
            if mode == 'LOGIN':
                success, msg = self.client.unlock_account(password)
            elif mode == 'CREATE':
                success, msg = self.client.create_new_account(nickname, password)
            elif mode == 'IMPORT':
                success, msg = self.client.import_account(priv_key, nickname, password)
            if not success:
                if self.login_window and self.login_window.winfo_exists():
                    self.show_toast(f'❌ {msg}', duration=2500, master=self.login_window)
                else:
                    messagebox.showerror('验证失败', msg)
                return
            target_geometry = None
            if self.login_window and self.login_window.winfo_exists():
                try:
                    lx = self.login_window.winfo_x()
                    ly = self.login_window.winfo_y()
                    lw = self.login_window.winfo_width()
                    lh = self.login_window.winfo_height()
                    center_x = lx + lw // 2
                    center_y = ly + lh // 2
                    main_w, main_h = (1000, 650)
                    new_x = max(0, center_x - main_w // 2)
                    new_y = max(0, center_y - main_h // 2)
                    target_geometry = f'{main_w}x{main_h}+{new_x}+{new_y}'
                except:
                    pass
                self.login_window.destroy()
                self.login_window = None
            self._lazy_build_ui()
            print('🔍 [Debug] 正在启动系统托盘...')
            self.setup_tray_icon()
            if target_geometry:
                self.geometry(target_geometry)
            self.deiconify()
            self.lift()
            self.focus_force()
            self._process_gui_queue()
            t = threading.Thread(target=self.client.connect)
            t.daemon = True
            t.start()
            self.gui_queue.put(('refresh', None))
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror('系统错误', f'启动失败: {str(e)}')
            if self.instance_lock:
                self.instance_lock.release()
                self.instance_lock = None
            if self.state() == 'withdrawn':
                sys.exit(1)

    def _preload_emoji_window(self):
        if self.emoji_window:
            return
        from gui_windows import EmojiWindow

        def _on_emoji_select(img_bytes):
            if img_bytes:
                self.stage_image(img_bytes)
        try:
            self.emoji_window = EmojiWindow(self, _on_emoji_select)
        except Exception as e:
            print(f'❌ [Emoji] Preload failed: {e}')

    def setup_tray_icon(self):

        def _tray_thread():
            try:
                image = self._get_tray_image()
                tooltip = 'DageChat'
                if self.client:
                    nick = self.client.db.get_contact_name(self.client.pk) or 'User'
                    npub_short = get_npub_abbr(self.client.pk)
                    tooltip = f'DageChat - {nick} ({npub_short})'
                menu = pystray.Menu(pystray.MenuItem('显示主界面', self.restore_window, default=True), pystray.MenuItem('退出', self.confirm_quit_from_tray))
                self.tray_icon = pystray.Icon('dagechat', image, tooltip, menu)
                self.tray_icon.run()
            except Exception as e:
                print(f'❌ [Tray] Thread crashed: {e}')
                import traceback
                traceback.print_exc()
        t = threading.Thread(target=_tray_thread, daemon=True)
        t.start()

    def _process_gui_queue(self):
        try:
            needs_refresh = False
            for _ in range(50):
                try:
                    msg_type, data = self.gui_queue.get_nowait()
                except queue.Empty:
                    break
                if msg_type == 'refresh':
                    needs_refresh = True
                elif msg_type == 'new_msg':
                    self.handle_new_message(data)
                    if self.current_chat_type == 'dm' and data.get('sender_pk') == self.current_chat_id:
                        self._update_chat_title_if_needed(data['sender_pk'])
                elif msg_type == 'sys_msg':
                    gid = data.get('group_id')
                    if self.current_chat_id == gid:
                        self.add_system_message(data['text'])
                elif msg_type == 'recall':
                    self._realtime_recall(data)
            now = time.time()
            if needs_refresh:
                if now - self.last_refresh_ts > 0.5:
                    self.refresh_ui()
                    self.last_refresh_ts = now
                    if self.active_profile_window and self.active_profile_window.winfo_exists():
                        self.active_profile_window.reload_ui()
                else:
                    self.gui_queue.put(('refresh', None))
        except Exception as e:
            print(f'Queue error: {e}')
        finally:
            self.after(100, self._process_gui_queue)

    def on_closing(self):
        if messagebox.askyesno('退出确认', '确定要退出 DageChat 吗？'):
            if self.instance_lock:
                self.instance_lock.release()
            if self.client:
                pass
            self.destroy()
            sys.exit(0)

    def open_image_viewer(self, current_msg_id):
        if not self.current_chat_id:
            return
        if self.current_image_viewer and self.current_image_viewer.winfo_exists():
            try:
                self.current_image_viewer.destroy()
            except:
                pass
            self.current_image_viewer = None
        try:
            all_imgs = self.client.db.get_gallery_images(self.current_chat_id)
            if not all_imgs:
                return
            start_index = 0
            for i, item in enumerate(all_imgs):
                if item['id'] == current_msg_id:
                    start_index = i
                    break
            ImageViewer(self, all_imgs, start_index)
        except Exception as e:
            messagebox.showerror('错误', f'无法打开图片: {e}')

    def create_ghost_group(self, name):
        new_sk = nacl.signing.SigningKey.generate()
        new_pk = new_sk.verify_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
        sk_hex = new_sk.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')
        gid = new_pk
        self.client.db.save_group(gid, name, sk_hex, owner_pubkey=None, group_type=1)
        self.client.groups[gid] = {'name': name, 'key_hex': sk_hex, 'type': 1}
        req_msg = json.dumps(['REQ', gid])
        with self.client.lock:
            for url, worker in self.client.relays.items():
                if worker.is_connected():
                    worker.send(req_msg)
        self.refresh_ui()
        self.switch_chat(gid, name, 'group')
        self.show_toast(f'⚡ 共享密钥群创建成功\nID: {gid[:8]}...')

    def on_backend_message(self, msg_type, data):
        if msg_type in ['group', 'dm']:
            self.gui_queue.put(('new_msg', data))
            self.gui_queue.put(('refresh', None))
        elif msg_type == 'system_center':
            self.gui_queue.put(('sys_msg', data))
        elif msg_type == 'contact_update':
            target_pk = data.get('pubkey')
            if target_pk and target_pk in self.avatar_cache:
                del self.avatar_cache[target_pk]
            self.gui_queue.put(('refresh', None))
            if target_pk and target_pk != self.client.pk:
                if self.client.db.is_friend(target_pk):
                    has_key = data.get('k') or self.client.db.get_contact_enc_key(target_pk)
                    if has_key and (not self.client.db.has_chat_history(target_pk)):
                        self.after(500, lambda: self.send_auto_greeting(target_pk))
        elif msg_type == 'system':
            self.gui_queue.put(('refresh', None))
        elif msg_type == 'delete':
            self.gui_queue.put(('recall', data.get('ids', [])))

    def add_system_message(self, text):
        frame = ctk.CTkFrame(self.msg_scroll, fg_color='transparent')
        frame.pack(fill='x', pady=5)
        lbl = ctk.CTkLabel(frame, text=text, text_color='gray', font=('Microsoft YaHei UI', 11))
        lbl.pack(anchor='center')
        self.after(50, self.scroll_to_bottom)

    def _realtime_recall(self, target_ids):
        for tid in target_ids:
            if tid in self.msg_widgets:
                try:
                    container = self.msg_widgets[tid]
                    for child in container.winfo_children():
                        child.destroy()
                    ctk.CTkLabel(container, text='🔒 该消息已被撤回', text_color='gray', font=('Microsoft YaHei UI', 12, 'italic'), padx=10, pady=5).pack()
                except Exception as e:
                    print(f'Recall UI error: {e}')

    def _get_display_name(self, pubkey, name=None):
        if not pubkey:
            return '未知'
        short_pk = get_npub_abbr(pubkey)
        base_name = name
        if not base_name:
            base_name = self.client.db.get_contact_name(pubkey) or '未知用户'
        if ' (' in base_name:
            base_name = base_name.split(' (')[0]
        if pubkey == self.client.pk:
            return f'{base_name} (我)'
        return f'{base_name} ({short_pk})'

    def _update_chat_title_if_needed(self, pubkey):
        if self.current_chat_id != pubkey:
            return
        name = self.client.db.get_contact_name(pubkey)
        display_name = self._get_display_name(pubkey, name)
        fp_text, is_danger = self.client.get_safety_fingerprint(pubkey, 'dm')
        self.fingerprint_label.configure(text=fp_text)
        self.chat_title.configure(text=display_name)

    def refresh_ui(self, contact_keyword=None, chat_keyword=None):
        if not self.client:
            return
        now = time.time()
        if now - getattr(self, '_last_ui_refresh', 0) < 0.2:
            return
        self._last_ui_refresh = now
        if contact_keyword is None and hasattr(self, 'contact_search_entry'):
            try:
                contact_keyword = self.contact_search_entry.get().strip().lower()
            except:
                pass
        if chat_keyword is None and hasattr(self, 'chat_search_entry'):
            try:
                chat_keyword = self.chat_search_entry.get().strip().lower()
            except:
                pass
        my_nick_display = self._get_display_name(self.client.pk)
        self.my_name_label.configure(text=my_nick_display)
        my_avatar = self._get_avatar_from_cache(self.client.pk, size=(40, 40))
        if my_avatar:
            self.my_avatar_label.configure(image=my_avatar, text='')
            self.my_avatar_label.image = my_avatar
        else:
            self.my_avatar_label.configure(image=None, text='👤')
        sessions = self.client.db.get_session_list()
        all_friend_pks = {f['pubkey'] for f in self.client.db.get_friends()}
        from client_persistent import OFFICIAL_GROUP_CONFIG
        official_gid = OFFICIAL_GROUP_CONFIG['id']
        chat_list_data = []
        for sess in sessions:
            sid = sess['id']
            real_type = sess['type']
            if sid in all_friend_pks:
                real_type = 'dm'
            elif sid in self.client.groups:
                real_type = 'group'
            elif sid == self.current_chat_id:
                sess['unread'] = 0
            is_blocked = False
            display_text = ''
            item_text_color = '#DCE4EE'
            if real_type == 'group':
                is_blocked = self.client.db.is_group_blocked(sid)
                if sid == official_gid:
                    display_text = f"{tr('TYPE_OFFICIAL')} {sess['name']}"
                    item_text_color = '#FFD700'
                else:
                    grp_mem = self.client.groups.get(sid)
                    if grp_mem and str(grp_mem.get('type')) == '1':
                        display_text = f"{tr('TYPE_GHOST')} {sess['name']}"
                        item_text_color = '#FF79C6'
                    else:
                        display_text = f"{tr('TYPE_NORMAL')} {sess['name']}"
                        item_text_color = '#69F0AE'
            else:
                is_blocked = self.client.db.is_blocked(sid)
                d_name = self._get_display_name(sid, sess['name'])
                prefix = tr('TYPE_DM')
                if sid == self.client.pk:
                    prefix = tr('TYPE_NOTE')
                    item_text_color = '#FFCC00'
                display_text = f'{prefix} {d_name}'
            if is_blocked:
                display_text = f"{tr('STATUS_BLOCKED')} {display_text}"
                item_text_color = 'gray'
            chat_list_data.append({'id': sid, 'name': sess['name'], 'display': display_text, 'color': item_text_color, 'unread': sess['unread'], 'type': real_type, 'raw_sess': sess})
        if chat_keyword:
            chat_list_data = [c for c in chat_list_data if chat_keyword in c['name'].lower() or chat_keyword in c['display'].lower() or chat_keyword in c['id'].lower()]
        for widget in self.session_widgets.values():
            widget.pack_forget()
        visible_chat_ids = set()
        for item in chat_list_data:
            sid = item['id']
            visible_chat_ids.add(sid)
            fg_color = 'gray25' if sid == self.current_chat_id else 'transparent'
            unread_str = f"[{item['unread']}] " if item['unread'] > 0 else ''
            full_tooltip = f"{unread_str}{item['display']}"
            final_disp = item['display']
            if len(final_disp) > 22:
                final_disp = final_disp[:22] + '...'
            final_text_for_list = f'{unread_str}{final_disp}'
            if sid in self.session_widgets:
                btn = self.session_widgets[sid]
                btn.configure(text=final_text_for_list, fg_color=fg_color, text_color=item['color'])
                if hasattr(btn, '_tooltip'):
                    btn._tooltip.update_text(full_tooltip)
                else:
                    btn._tooltip = Tooltip(btn, full_tooltip)
                btn.pack(fill='x', pady=2)
            else:
                btn = ctk.CTkButton(self.scroll_chats, text=final_text_for_list, anchor='w', fg_color=fg_color, hover_color='gray30', text_color=item['color'], font=('Microsoft YaHei UI', 13), command=lambda s=item['raw_sess'], rt=item['type']: self.switch_chat(s['id'], s['name'], rt))
                btn.pack(fill='x', pady=2)
                btn.bind('<Button-3>', lambda e, s=item['raw_sess'], rt=item['type'], b=btn: self.on_right_click_item(e, s['id'], s['name'], rt, b))
                btn._tooltip = Tooltip(btn, full_tooltip)
                self.session_widgets[sid] = btn
        real_chat_ids = {s['id'] for s in sessions}
        to_remove_chats = []
        for sid, widget in self.session_widgets.items():
            if sid not in real_chat_ids:
                widget.destroy()
                to_remove_chats.append(sid)
        for sid in to_remove_chats:
            del self.session_widgets[sid]
        friends = self.client.db.get_friends()
        groups = self.client.db.get_all_groups()
        contact_list = []
        for g in groups:
            gid = g[0]
            g_name = g[1]
            is_blk = g[5] == 1 if len(g) > 5 else False
            g_type = g[8] if len(g) > 8 else 0
            c_color = '#DCE4EE'
            if gid == official_gid:
                disp = f"{tr('TYPE_OFFICIAL')} {g_name}"
                c_color = '#FFD700'
            elif g_type == 1:
                disp = f"{tr('TYPE_GHOST')} {g_name}"
                c_color = '#FF79C6'
            else:
                disp = f"{tr('TYPE_NORMAL')} {g_name}"
                c_color = '#69F0AE'
            if is_blk:
                disp = f"{tr('STATUS_BLOCKED')} {disp}"
                c_color = 'gray'
            contact_list.append({'id': gid, 'name': g_name, 'display': disp, 'blocked': is_blk, 'color': c_color})
        for c in friends:
            pk = c['pubkey']
            is_blk = self.client.db.is_blocked(pk)
            final_display = self._get_display_name(pk, c['name'])
            if pk == self.client.pk:
                prefix = tr('TYPE_NOTE')
                c_color = '#FFCC00'
            else:
                prefix = tr('TYPE_DM')
                c_color = '#DCE4EE'
            disp = f'{prefix} {final_display}'
            if is_blk:
                disp = f"{tr('STATUS_BLOCKED')} {disp}"
                c_color = 'gray'
            contact_list.append({'id': pk, 'name': c['name'] or '', 'display': disp, 'blocked': is_blk, 'color': c_color})
        if contact_keyword:
            contact_list = [c for c in contact_list if contact_keyword in c['name'].lower() or contact_keyword in c['id'].lower() or contact_keyword in c['display'].lower()]
        contact_list.sort(key=lambda x: x['name'])
        for widget in self.contact_widgets.values():
            widget.pack_forget()
        for item in contact_list:
            cid = item['id']
            c_fg_color = 'gray25' if cid == self.current_chat_id else 'transparent'
            full_tooltip_text = item['display']
            final_disp = item['display']
            if len(final_disp) > 22:
                final_disp = final_disp[:22] + '...'
            if cid in self.contact_widgets:
                btn = self.contact_widgets[cid]
                btn.configure(text=final_disp, text_color=item['color'], fg_color=c_fg_color)
                if hasattr(btn, '_tooltip'):
                    btn._tooltip.update_text(full_tooltip_text)
                else:
                    btn._tooltip = Tooltip(btn, full_tooltip_text)
                btn.pack(fill='x', pady=2)
            else:
                btn = ctk.CTkButton(self.scroll_contacts, text=final_disp, anchor='w', fg_color=c_fg_color, text_color=item['color'], hover_color='#404040', font=('Microsoft YaHei UI', 13), command=lambda i=item: self._on_contact_click(i))
                btn.pack(fill='x', pady=2)
                btn.bind('<Double-Button-1>', lambda e, i=item: self._on_contact_double_click(e, i))
                btn.bind('<Button-3>', lambda e, i=item, b=btn: self.on_right_click_item(e, i['id'], i['name'], 'contact', b))
                btn._tooltip = Tooltip(btn, full_tooltip_text)
                self.contact_widgets[cid] = btn
        real_contact_ids = set()
        for g in groups:
            real_contact_ids.add(g[0])
        for c in friends:
            real_contact_ids.add(c['pubkey'])
        to_remove_c = []
        for cid, widget in self.contact_widgets.items():
            if cid not in real_contact_ids:
                widget.destroy()
                to_remove_c.append(cid)
        for cid in to_remove_c:
            del self.contact_widgets[cid]

    def show_session_context_menu(self, event, sid, name, stype):
        menu = tk.Menu(self, tearoff=0)
        is_group = stype == 'group'
        if not is_group:
            if self.client.db.is_friend(sid):
                menu.add_command(label=tr('MENU_DEL_FRIEND').format(name=name), command=lambda: self.confirm_delete_friend(sid, name))
            else:
                menu.add_command(label=tr('MENU_ADD_FRIEND').format(name=name), command=lambda: self.add_friend_from_menu(sid))
            menu.add_separator()
        menu.add_command(label=tr('MENU_HIDE_CHAT').format(name=name), command=lambda: self.hide_session(sid, is_group))
        menu.add_command(label=tr('MENU_CLEAR_CHAT').format(name=name), command=lambda: self.clear_chat_history(sid, name))
        menu.add_separator()
        if is_group:
            menu.add_command(label=tr('MENU_EXIT_GROUP'), command=lambda: self.exit_group(sid, name))
        else:
            menu.add_command(label=tr('MENU_DEL_SESSION'), command=lambda: self.delete_chat_session(sid, stype, name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_contact_context_menu(self, event, pk, name):
        menu = tk.Menu(self, tearoff=0)
        if pk in self.client.groups:
            menu.add_command(label=tr('MENU_GROUP_INFO'), command=lambda: self.show_chat_info(target_id=pk))
            menu.add_separator()
            menu.add_command(label=tr('MENU_ENTER_GROUP'), command=lambda: self.switch_to_chat_from_contact(pk, name))
            is_blocked = self.client.db.is_group_blocked(pk)
            if is_blocked:
                menu.add_command(label=tr('MENU_UNBLOCK_GROUP'), command=lambda: self.toggle_block_group(False, pk))
            else:
                menu.add_command(label=tr('MENU_BLOCK_GROUP'), command=lambda: self.toggle_block_group(True, pk))
            menu.add_separator()
            menu.add_command(label=tr('MENU_EXIT_GROUP'), command=lambda: self.exit_group(pk, name))
        else:
            menu.add_command(label=tr('MENU_START_CHAT').format(name=name), command=lambda: self.switch_to_chat_from_contact(pk, name))
            menu.add_separator()
            menu.add_command(label=tr('MENU_VIEW_PROFILE'), command=lambda: self.show_user_profile(pk))
            is_blocked = self.client.db.is_blocked(pk)
            if is_blocked:
                menu.add_command(label=tr('MENU_UNBLOCK_USER'), command=lambda: self.unblock_user(pk))
            else:
                menu.add_command(label=tr('MENU_BLOCK_USER'), command=lambda: self.block_user(pk))
            menu.add_separator()
            menu.add_command(label=tr('MENU_DEL_FRIEND').format(name=name), command=lambda: self.confirm_delete_friend(pk, name))
        try:
            if event:
                x, y = (event.x_root, event.y_root)
            else:
                x, y = self.winfo_pointerxy()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def exit_group(self, gid, name):
        from client_persistent import OFFICIAL_GROUP_CONFIG
        if not messagebox.askyesno(tr('DIALOG_EXIT_GROUP_TITLE'), tr('DIALOG_EXIT_GROUP_MSG').format(name=name)):
            return
        try:
            if gid == OFFICIAL_GROUP_CONFIG['id']:
                self.client.db.set_setting('exited_official_lobby', '1')
            if gid in self.client.groups:
                del self.client.groups[gid]
            self.client.db.delete_group_completely(gid)
            if self.current_chat_id == gid:
                self.current_chat_id = None
                self.current_chat_type = None
                self.chat_title.configure(text='')
                self.fingerprint_label.configure(text='')
                self.cancel_reply()
                self._show_welcome_state()
            threading.Thread(target=self.client.sync_backup_to_cloud, daemon=True).start()
            self.refresh_ui()
            self.show_toast(tr('TOAST_EXIT_GROUP').format(name=name))
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), str(e))

    def add_friend_from_menu(self, pubkey):
        current_name = self.client.db.get_contact_name(pubkey)
        self.client.db.save_contact(pubkey, current_name, is_friend=1)
        self.client.fetch_user_profile(pubkey)
        self.refresh_ui()
        self.show_toast(tr('TOAST_FRIEND_ADDED'))

    def confirm_delete_friend(self, pk, name):
        if messagebox.askyesno(tr('DIALOG_DEL_FRIEND_TITLE'), tr('DIALOG_DEL_FRIEND_MSG').format(name=name)):
            self.client.db.save_contact(pk, None, is_friend=0)
            self.refresh_ui()
            self.show_toast(tr('TOAST_FRIEND_DELETED').format(name=name))

    def hide_session(self, sid, is_group):
        self.client.mark_session_read(sid, is_group)
        self.client.db.set_session_hidden(sid, is_group, hidden=True)
        if self.current_chat_id == sid:
            self.current_chat_id = None
            self.current_chat_type = None
            self.chat_title.configure(text='')
            self.fingerprint_label.configure(text='')
            self.cancel_reply()
            self._show_welcome_state()
        self.refresh_ui()

    def delete_chat_session(self, sid, stype, name_for_prompt='Chat'):
        if messagebox.askyesno(tr('DIALOG_DEL_CHAT_TITLE'), tr('DIALOG_DEL_CHAT_MSG').format(name=name_for_prompt)):
            is_group = stype == 'group'
            self.client.db.clear_chat_history(sid)
            self.client.db.set_session_hidden(sid, is_group, hidden=True)
            self.client.mark_session_read(sid, is_group)
            if self.current_chat_id == sid:
                self.current_chat_id = None
                self.current_chat_type = None
                self.chat_title.configure(text='')
                self.fingerprint_label.configure(text='')
                self.cancel_reply()
                self._show_welcome_state()
            self.refresh_ui()
            self.show_toast(tr('TOAST_CHAT_DELETED'))

    def show_chat_more_menu(self):
        if not self.current_chat_id:
            return
        menu = tk.Menu(self, tearoff=0)
        info_label = tr('MENU_VIEW_PROFILE')
        if self.current_chat_type == 'group':
            grp = self.client.groups.get(self.current_chat_id)
            if grp and str(grp.get('type')) == '1':
                info_label = tr('MENU_GHOST_INFO')
            else:
                info_label = tr('MENU_GROUP_INFO')
        menu.add_command(label=info_label, command=self.show_chat_info)
        menu.add_separator()
        menu.add_command(label=tr('MENU_SEARCH_CHAT'), command=self.search_current_chat)
        menu.add_command(label=tr('MENU_EXPORT_CHAT'), command=self.export_current_chat)
        menu.add_command(label='📦 备份此会话 (.dgbk)', command=self.backup_current_chat)
        menu.add_separator()
        menu.add_command(label=tr('MENU_CLEAR_LOCAL'), command=lambda: self.clear_chat_history(self.current_chat_id))
        try:
            x = self.btn_more.winfo_rootx()
            y = self.btn_more.winfo_rooty() + self.btn_more.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def backup_current_chat(self):
        if not self.current_chat_id:
            return
        from datetime import datetime
        name = self.chat_title.cget('text').split(' ')[-1]
        safe_name = ''.join([c for c in name if c.isalnum()])
        default_name = f"ChatBackup_{safe_name}_{datetime.now().strftime('%Y%m%d')}.dgbk"
        path = ctk.filedialog.asksaveasfilename(parent=self, defaultextension='.dgbk', initialfile=default_name, title='Backup Session')
        if not path:
            return
        from backup_manager import BackupManager
        from gui_windows import TaskProgressWindow
        manager = BackupManager(self.client)
        TaskProgressWindow(self, tr('BKP_TITLE'), BackupManager.run_backup, manager, path, self.current_chat_id, toast_master=self)

    def clear_chat_history(self, sid, name_for_prompt='Chat'):
        if messagebox.askyesno(tr('DIALOG_CLEAR_TITLE'), tr('DIALOG_CLEAR_MSG').format(name=name_for_prompt)):
            self.client.db.clear_chat_history(sid)
            if self.current_chat_id == sid:
                self.reload_current_chat()
            self.refresh_ui()
            self.show_toast(tr('TOAST_CHAT_CLEARED'))

    def _on_contact_click(self, item):
        target_id = item['id']
        name = item['name']
        ctype = 'dm'
        if target_id in self.client.groups:
            ctype = 'group'
            name = self.client.groups[target_id]['name']
        self.switch_chat(target_id, name, ctype)

    def _on_contact_double_click(self, event, item):
        self.switch_to_chat_from_contact(item['id'], item['name'])

    def switch_to_chat_from_contact(self, target_id, name):
        ctype = 'dm'
        if target_id in self.client.groups:
            ctype = 'group'
            name = self.client.groups[target_id]['name']
        self.tab_view.set('消息')
        self.switch_chat(target_id, name, ctype)

    def update_input_state(self):
        if not self.current_chat_id:
            return
        chat_id = self.current_chat_id
        chat_type = self.current_chat_type
        state = 'normal'
        placeholder = ''
        if chat_type == 'group':
            if self.client.db.is_group_blocked(chat_id):
                state = 'disabled'
                placeholder = tr('STATUS_BLOCKED') if chat_id in self.client.groups else tr('STATUS_KICKED')
            elif chat_id not in self.client.groups:
                state = 'disabled'
                placeholder = tr('STATUS_NOT_IN_GROUP')
        elif chat_type == 'dm':
            if self.client.db.is_blocked(chat_id):
                state = 'disabled'
                placeholder = tr('STATUS_BLOCKED')
        self.msg_entry.configure(state='normal')
        current_text = self.msg_entry.get('0.0', 'end').strip()
        if state == 'disabled':
            self.msg_entry.delete('0.0', 'end')
            if placeholder:
                self.msg_entry.insert('0.0', placeholder)
            self.msg_entry.configure(state='disabled', fg_color='#2b2b2b')
            self.send_btn.configure(state='disabled')
            if hasattr(self, 'btn_emoji'):
                self.btn_emoji.configure(state='disabled')
            if hasattr(self, 'btn_screenshot'):
                self.btn_screenshot.configure(state='disabled')
        else:
            if current_text in [tr('STATUS_BLOCKED'), tr('STATUS_KICKED'), tr('STATUS_NOT_IN_GROUP')]:
                self.msg_entry.delete('0.0', 'end')
            self.msg_entry.configure(state='normal', fg_color='#343638')
            self.send_btn.configure(state='normal')
            if hasattr(self, 'btn_emoji'):
                self.btn_emoji.configure(state='normal')
            if hasattr(self, 'btn_screenshot'):
                self.btn_screenshot.configure(state='normal')
            self.msg_entry.focus_set()

    def switch_chat(self, chat_id, chat_name, chat_type):
        if not chat_id:
            return
        if self.is_multi_select_mode:
            self._toggle_multi_select_mode(False)
        self._show_active_chat_state()
        is_group = chat_type == 'group'
        self.client.mark_session_read(chat_id, is_group)
        self.after(200, self.refresh_ui)
        if self.load_task_id:
            self.after_cancel(self.load_task_id)
            self.load_task_id = None
        self.current_chat_id = chat_id
        self.current_chat_type = chat_type
        display_title = chat_name
        if chat_type == 'group':
            grp = self.client.groups.get(chat_id)
            if grp:
                if str(grp.get('type')) == '1':
                    display_title = f"{tr('TYPE_GHOST')} {display_title}"
                else:
                    display_title = f"{tr('TYPE_NORMAL')} {display_title}"
        elif chat_type == 'dm':
            display_title = self._get_display_name(chat_id, chat_name)
            contact_enc_key = self.client.db.get_contact_enc_key(chat_id)
            if not contact_enc_key:
                display_title += f" {tr('MSG_SYNCING')}"
                self.client.fetch_user_profile(chat_id)
        self.chat_title.configure(text=display_title)
        fp_text, is_danger = self.client.get_safety_fingerprint(chat_id, chat_type)
        self.fingerprint_label.configure(text=fp_text, text_color='#D32F2F' if is_danger else 'gray')
        self.msg_entry.configure(state='normal')
        self.msg_entry.delete('0.0', 'end')
        self.update_input_state()
        self.cancel_reply()
        if self.active_chat_frame:
            self.active_chat_frame.pack_forget()
            self.active_chat_frame = None
        if chat_id in self.chat_frames_cache:
            target_frame = self.chat_frames_cache[chat_id]
            target_frame.pack(fill='both', expand=True)
            self.active_chat_frame = target_frame
            self.msg_scroll = target_frame
            if not hasattr(target_frame, 'widget_cache'):
                target_frame.widget_cache = {}
            self.msg_widgets = target_frame.widget_cache
            last_ts = getattr(target_frame, 'max_loaded_ts', 0)

            def _fill_gap():
                new_msgs = self.client.db.get_messages_after_timestamp(chat_id, last_ts)
                if new_msgs:
                    for m in new_msgs:
                        msg_content = m[3]
                        sender_pk = m[2]
                        is_me_val = m[5] == 1
                        reply_id = m[6] if len(m) > 6 else None
                        sender_name = tr('MSG_SENDER_UNKNOWN')
                        if self.current_chat_type == 'group':
                            grp = self.client.groups.get(chat_id)
                            if grp and str(grp.get('type')) == '1':
                                try:
                                    sender_name = json.loads(msg_content).get('alias', tr('MSG_SENDER_ANON'))
                                except:
                                    pass
                            else:
                                sender_name = self.client._format_sender_info(sender_pk)
                        else:
                            sender_name = self.client._format_sender_info(sender_pk)
                        self.add_message_bubble(m[0], msg_content, is_me_val, sender_name, m[4], reply_id, sender_pk=sender_pk, scroll_to_bottom=True)
            self.after(10, _fill_gap)
        else:
            if len(self.chat_frames_cache) >= 5:
                old_k = next(iter(self.chat_frames_cache))
                old_f = self.chat_frames_cache.pop(old_k)
                old_f.destroy()
            new_frame = ctk.CTkScrollableFrame(self.chat_frame_container, fg_color='transparent')
            new_frame.pack(fill='both', expand=True)
            new_frame.rendered_ids = set()
            new_frame.max_loaded_ts = 0
            new_frame.widget_cache = {}
            self.msg_widgets = new_frame.widget_cache
            self.chat_frames_cache[chat_id] = new_frame
            self.active_chat_frame = new_frame
            self.msg_scroll = new_frame
            self.load_task_id = self.after(10, self.reload_current_chat)

    def _perform_heavy_loading(self):
        self.rendered_msg_ids.clear()
        for w in self.msg_scroll.winfo_children():
            w.destroy()
        try:
            self.msg_scroll._parent_canvas.yview_moveto(0.0)
        except:
            pass
        self.reload_current_chat()

    def reload_current_chat(self):
        if not self.current_chat_id:
            return
        self.load_task_id = None
        for w in self.msg_scroll.winfo_children():
            w.destroy()
        if hasattr(self.msg_scroll, 'rendered_ids'):
            self.msg_scroll.rendered_ids.clear()
        else:
            self.msg_scroll.rendered_ids = set()
        self.msg_widgets.clear()
        limit = 20
        msgs = self.client.db.get_history(self.current_chat_id, limit=limit)
        if msgs:
            self.min_loaded_ts = msgs[0][4]
        else:
            self.min_loaded_ts = 0
        if len(msgs) >= limit:
            self.btn_load_more = ctk.CTkButton(self.msg_scroll, text=tr('CTX_LOAD_MORE_UP'), fg_color='transparent', text_color='#1F6AA5', height=24, command=self.load_more_history)
            self.btn_load_more.pack(pady=10)
        else:
            self.btn_load_more = None
            ctk.CTkLabel(self.msg_scroll, text=tr('CTX_NO_MORE_MSG'), text_color='gray', font=('Microsoft YaHei UI', 10)).pack(pady=10)
        is_ghost_grp = False
        grp = self.client.groups.get(self.current_chat_id)
        if grp and (grp.get('type') == 1 or str(grp.get('type')) == '1'):
            is_ghost_grp = True

        def render_batch(index):
            if index >= len(msgs) or (self.current_chat_id != msgs[0][1] and self.current_chat_id != msgs[0][2]):
                return
            batch = msgs[index:index + 10]
            for m in batch:
                msg_content = m[3]
                sender_pk = m[2]
                is_me_val = m[5] == 1
                sender_name = tr('MSG_SENDER_UNKNOWN')
                if is_ghost_grp:
                    try:
                        if msg_content.startswith('{'):
                            d = json.loads(msg_content)
                            if d.get('alias'):
                                sender_name = d.get('alias')
                    except:
                        pass
                else:
                    sender_name = self.client._format_sender_info(sender_pk)
                reply_id = m[6] if len(m) > 6 else None
                self.add_message_bubble(m[0], msg_content, is_me_val, sender_name, m[4], reply_id, sender_pk=sender_pk, scroll_to_bottom=False)
            if index + 10 < len(msgs):
                self.after(10, lambda: render_batch(index + 10))
            else:
                self.after(50, self.scroll_to_bottom)
        render_batch(0)

    def load_more_history(self):
        if not self.current_chat_id:
            return
        if hasattr(self, 'btn_load_more') and self.btn_load_more and self.btn_load_more.winfo_exists():
            self.btn_load_more.destroy()
            self.btn_load_more = None
        limit = 20
        old_msgs = self.client.db.get_history(self.current_chat_id, limit=limit, before_ts=self.min_loaded_ts)
        children = self.msg_scroll.winfo_children()
        top_anchor = children[0] if children else None
        if not old_msgs:
            lbl = ctk.CTkLabel(self.msg_scroll, text=tr('CTX_ALL_SHOWN'), text_color='gray', font=('Microsoft YaHei UI', 10))
            if top_anchor:
                lbl.pack(before=top_anchor, pady=10)
            else:
                lbl.pack(pady=10)
            return
        self.min_loaded_ts = old_msgs[0][4]
        is_ghost_grp = False
        grp = self.client.groups.get(self.current_chat_id)
        if grp and (grp.get('type') == 1 or str(grp.get('type')) == '1'):
            is_ghost_grp = True
        current_anchor = top_anchor
        for m in reversed(old_msgs):
            msg_id = m[0]
            sender_pk = m[2]
            msg_content = m[3]
            created_at = m[4]
            is_me_val = m[5] == 1
            reply_id = m[6] if len(m) > 6 else None
            sender_name = tr('MSG_SENDER_UNKNOWN')
            if is_ghost_grp:
                try:
                    if msg_content.startswith('{'):
                        d = json.loads(msg_content)
                        if d.get('alias'):
                            sender_name = d.get('alias')
                except:
                    pass
            else:
                sender_name = self.client._format_sender_info(sender_pk)
            new_widget = self.add_message_bubble(msg_id, msg_content, is_me_val, sender_name, created_at, reply_id, sender_pk, scroll_to_bottom=False, insert_at_top=True, top_anchor=current_anchor)
            if new_widget:
                current_anchor = new_widget
        if len(old_msgs) >= limit:
            self.btn_load_more = ctk.CTkButton(self.msg_scroll, text=tr('CTX_LOAD_MORE_UP'), fg_color='transparent', text_color='#1F6AA5', height=24, command=self.load_more_history)
            if current_anchor:
                self.btn_load_more.pack(before=current_anchor, pady=10)
            else:
                self.btn_load_more.pack(pady=10)
        else:
            lbl = ctk.CTkLabel(self.msg_scroll, text=tr('CTX_ALL_SHOWN'), text_color='gray', font=('Microsoft YaHei UI', 10))
            if current_anchor:
                lbl.pack(before=current_anchor, pady=10)
            else:
                lbl.pack(pady=10)

    def handle_new_message(self, data):
        incoming_group_id = data.get('group_id')
        real_sender = data.get('real_sender', data.get('sender_pk'))
        is_me = False
        if 'is_me' in data:
            is_me = data['is_me']
        elif self.client and real_sender == self.client.pk:
            is_me = True
        is_at_me = False
        if not is_me:
            at_list = data.get('at', [])
            if at_list and (self.client.pk in at_list or 'ALL' in at_list):
                is_at_me = True
            if not is_at_me:
                my_name = self.client.db.get_contact_name(self.client.pk)
                text_content = data.get('text', '')
                if my_name and f'@{my_name}' in text_content:
                    is_at_me = True
            data['is_at_me'] = is_at_me
        is_current_chat = False
        if self.current_chat_type == 'group':
            if incoming_group_id == self.current_chat_id:
                is_current_chat = True
        elif self.current_chat_type == 'dm':
            if not incoming_group_id:
                msg_session_id = data.get('sender_pk')
                if msg_session_id == self.current_chat_id:
                    is_current_chat = True
        if is_current_chat:
            self.add_message_bubble(data['id'], data['text'], is_me, data.get('nickname', 'Unknown'), data.get('time'), data.get('reply_to_id'), sender_pk=real_sender, scroll_to_bottom=True)
            is_grp = self.current_chat_type == 'group'
            self.client.mark_session_read(self.current_chat_id, is_grp)
            if not is_me:
                if not self.is_window_focused:
                    self.show_system_notification(data)
        elif not is_me:
            target_sid = incoming_group_id if incoming_group_id else data.get('sender_pk')
            self._flash_session_item(target_sid)
            self.show_system_notification(data)

    def _get_ghost_avatar(self):
        return self._ghost_mask_cache

    def show_toast(self, message, duration=2000, master=None):
        try:
            target = master if master else self
            if not target.winfo_exists():
                return
            toast = ctk.CTkFrame(target, fg_color='#333', corner_radius=20)
            toast.place(relx=0.5, rely=0.85, anchor='center')
            ctk.CTkLabel(toast, text=message, font=('Microsoft YaHei UI', 13), text_color='white', padx=20, pady=8).pack()
            target.after(duration, toast.destroy)
            toast.lift()
        except:
            pass

    def _render_bubble_content_placeholder(self, *args):
        pass

    def open_history_viewer(self, history_data, master_window=None):
        title = history_data.get('title', tr('HISTORY_VIEW_TITLE'))
        items = history_data.get('items', [])
        target_master = master_window if master_window else self
        top = ctk.CTkToplevel(target_master)
        top.title(title)
        w, h = (550, 650)
        try:
            target_master.update_idletasks()
            base_x = target_master.winfo_x()
            base_y = target_master.winfo_y()
            base_w = target_master.winfo_width()
            base_h = target_master.winfo_height()
            x = base_x + (base_w - w) // 2
            y = base_y + (base_h - h) // 2
            x = max(0, x)
            y = max(0, y)
            top.geometry(f'{w}x{h}+{x}+{y}')
        except:
            top.geometry(f'{w}x{h}')
        top.attributes('-topmost', True)
        top.transient(target_master)
        top.grab_set()
        top.focus_force()
        scroll = ctk.CTkScrollableFrame(top, fg_color='transparent')
        scroll.pack(fill='both', expand=True, padx=10, pady=10)
        if not items:
            ctk.CTkLabel(scroll, text='No Content').pack(pady=20)
            return
        for item in items:
            name = item.get('n', 'Unknown')
            ts = item.get('t', 0)
            text = item.get('c', '')
            img_b64 = item.get('i')
            bubble_frame = ctk.CTkFrame(scroll, fg_color='transparent')
            bubble_frame.pack(fill='x', pady=8)
            dt_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            info_text = f'{name}  {dt_str}'
            ctk.CTkLabel(bubble_frame, text=info_text, text_color='gray', font=('Microsoft YaHei UI', 11)).pack(anchor='w', padx=5)
            container = ctk.CTkFrame(bubble_frame, fg_color='#343638', corner_radius=6)
            container.pack(anchor='w', padx=5)
            if img_b64:
                try:
                    data = base64.b64decode(img_b64)
                    pil_img = Image.open(BytesIO(data))
                    max_w = 350
                    if pil_img.width > max_w:
                        ratio = max_w / pil_img.width
                        new_h = int(pil_img.height * ratio)
                        pil_img = pil_img.resize((max_w, new_h))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                    img_lbl = ctk.CTkLabel(container, image=ctk_img, text='')
                    img_lbl.pack(pady=5, padx=5)
                    fake_gallery_item = {'id': str(ts), 'image_b64': img_b64}
                    img_lbl.bind('<Double-Button-1>', lambda e, item=fake_gallery_item: ImageViewer(self, [item], 0))
                except Exception as e:
                    print(f'History img error: {e}')
            if text:
                is_nested_card = False
                if text.strip().startswith('{'):
                    try:
                        nested_data = json.loads(text)
                        if nested_data.get('type') == 'history':
                            is_nested_card = True
                            card_frame = ctk.CTkFrame(container, fg_color='#E0E0E0')
                            card_frame.pack(pady=5, padx=5, fill='x')
                            self._render_history_card(card_frame, nested_data, None, False, None)
                    except:
                        pass
                if not is_nested_card:
                    msg_lbl = ctk.CTkLabel(container, text=text, font=('Microsoft YaHei UI', 14), text_color='white', wraplength=400, justify='left')
                    msg_lbl.pack(pady=5, padx=10)

    def _render_history_card(self, container, data, msg_id, is_me, sender_pk):
        container._is_history_container = True
        title = data.get('title', tr('HISTORY_CARD_TITLE'))
        items = data.get('items', [])
        width = 280
        if hasattr(container.master, '_is_history_container'):
            width = 260
        container.configure(width=width)
        title_color = 'black' if not is_me else '#222'
        title_lbl = ctk.CTkLabel(container, text=title, font=('Microsoft YaHei UI', 13, 'bold'), text_color=title_color)
        title_lbl.pack(fill='x', padx=10, pady=(10, 5))
        line = ctk.CTkFrame(container, height=1, fg_color='#ccc')
        line.pack(fill='x', padx=10, pady=2)
        summary_frame = ctk.CTkFrame(container, fg_color='transparent')
        summary_frame.pack(fill='x', padx=10, pady=5)
        display_items = items[:4]
        for i, item in enumerate(display_items):
            name = item.get('n', 'User')
            content = item.get('c', '')
            ts = item.get('t', 0)
            dt_str = datetime.fromtimestamp(ts).strftime('%m-%d %H:%M')
            is_nested = False
            nested_data = None
            if content.strip().startswith('{'):
                try:
                    js = json.loads(content)
                    if js.get('type') == 'history':
                        is_nested = True
                        nested_data = js
                    elif js.get('text'):
                        content = js.get('text')
                        if js.get('image'):
                            content = '[图片] ' + content
                except:
                    pass
            row_frame = ctk.CTkFrame(summary_frame, fg_color='transparent')
            row_frame.pack(fill='x', pady=4)
            header_text = f'{name} {dt_str}'
            ctk.CTkLabel(row_frame, text=header_text, font=('Microsoft YaHei UI', 10), text_color='#666', anchor='w').pack(fill='x')
            if is_nested and nested_data:
                nested_container = ctk.CTkFrame(row_frame, fg_color='#e8e8e8', corner_radius=4)
                nested_container.pack(fill='x', padx=(5, 0), pady=2)
                self._render_history_card(nested_container, nested_data, None, False, None)
            else:
                if item.get('i'):
                    content = '[图片] ' + content
                if len(content) > 20:
                    content = content[:20] + '...'
                ctk.CTkLabel(row_frame, text=content, font=('Microsoft YaHei UI', 12), text_color='#333', anchor='w').pack(fill='x')
        if len(items) > 4:
            ctk.CTkLabel(summary_frame, text='...', font=('Microsoft YaHei UI', 10), text_color='#888').pack(anchor='w')
        line2 = ctk.CTkFrame(container, height=1, fg_color='#ccc')
        line2.pack(fill='x', padx=10, pady=2)
        hint_lbl = ctk.CTkLabel(container, text=tr('HISTORY_CLICK_HINT'), font=('Microsoft YaHei UI', 10), text_color='#666')
        hint_lbl.pack(anchor='w', padx=10, pady=(2, 8))

        def _bind_smart(widget):
            if widget != container and getattr(widget, '_is_history_container', False):
                return
            widget.bind('<Button-1>', lambda e: self.open_history_viewer(data, master_window=widget.winfo_toplevel()))
            for child in widget.winfo_children():
                _bind_smart(child)
        _bind_smart(container)
        if msg_id:
            json_str = json.dumps(data)
            container.bind('<Button-3>', lambda e: self.show_context_menu(e, msg_id, json_str, is_me, sender_pk))

    def show_quote_context_menu(self, event, reply_to_id):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='🔍 定位原消息', command=lambda: self.jump_to_message_context(self.current_chat_id, reply_to_id))
        try:
            if event:
                x, y = (event.x_root, event.y_root)
            else:
                x, y = self.winfo_pointerxy()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _render_image_in_container(self, container, img_bytes, msg_id, is_me, sender_pk, text_context, should_scroll=False):
        try:
            data = bytes(img_bytes)
            clean_buffer = BytesIO()
            with BytesIO(data) as original_stream:
                with Image.open(original_stream) as original:
                    original.load()
                    canvas = Image.new('RGB', original.size, (255, 255, 255))
                    if original.mode in ('RGBA', 'LA'):
                        canvas.paste(original, mask=original.split()[-1])
                    else:
                        canvas.paste(original)
                    canvas.save(clean_buffer, format='PNG')
            clean_buffer.seek(0)
            final_img = Image.open(clean_buffer)
            final_img.load()
            max_w = 250
            original_w, original_h = final_img.size
            if original_w > max_w:
                ratio = max_w / original_w
                new_w = max_w
                new_h = int(original_h * ratio)
            else:
                new_w = original_w
                new_h = original_h
            ctk_img = ctk.CTkImage(light_image=final_img, dark_image=final_img, size=(new_w, new_h))
            img_label = ctk.CTkLabel(container, image=ctk_img, text='', cursor='hand2')
            img_label.pack(pady=5, padx=5)
            img_label._persistent_ref = ctk_img
            if hasattr(self, '_image_ref_pool'):
                self._image_ref_pool.append(ctk_img)
                if len(self._image_ref_pool) > 50:
                    self._image_ref_pool.pop(0)
            img_label.bind('<Double-Button-1>', lambda e=None, mid=msg_id: self.open_image_viewer(mid))
            img_label.bind('<Button-3>', lambda e=None: self.show_context_menu(e, msg_id, text_context, is_me, sender_pk, image_bytes=data))
            if should_scroll:
                container.update_idletasks()
                self.after(50, self.scroll_to_bottom)
                self.after(300, self.scroll_to_bottom)
        except Exception as e:
            print(f'Render image error: {e}')
            ctk.CTkLabel(container, text='[❌ 图片渲染错误]', text_color='gray', font=('Microsoft YaHei UI', 10)).pack(pady=5)

    def _process_media_urls(self, container, urls):
        for url in urls:
            lower_url = url.lower()
            if any((lower_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])):
                self._async_load_url_image(container, url)
            elif any((lower_url.endswith(ext) for ext in ['.mp4', '.mov'])):
                btn = ctk.CTkButton(container, text=tr('MEDIA_PLAY_VIDEO'), fg_color='#333', height=30, command=lambda u=url: webbrowser.open(u))
                btn.pack(pady=5, padx=5)

    def _async_load_url_image(self, container, url):
        loading_lbl = ctk.CTkLabel(container, text=tr('MSG_LOAD_IMG'), text_color='gray', font=('Microsoft YaHei UI', 10))
        loading_lbl.pack(pady=2)

        def _load():
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = response.read()
                try:
                    pil_img = Image.open(BytesIO(data))

                    def _update_ui():
                        if not loading_lbl.winfo_exists():
                            return
                        loading_lbl.destroy()
                        max_w = 200
                        ratio = max_w / pil_img.width
                        new_h = int(pil_img.height * ratio)
                        ctk_img = ctk.CTkImage(pil_img, size=(max_w, new_h))
                        lbl = ctk.CTkLabel(container, image=ctk_img, text='', cursor='hand2')
                        lbl.pack(pady=5)
                        lbl.image = ctk_img
                        lbl.bind('<Button-1>', command=lambda u=url: webbrowser.open(url))
                    self.after(0, _update_ui)
                except:
                    self.after(0, lambda: loading_lbl.configure(text=tr('MSG_IMG_FMT_ERR')))
            except Exception as e:
                self.after(0, lambda: loading_lbl.configure(text=tr('MSG_LOAD_FAIL')))
        threading.Thread(target=_load, daemon=True).start()

    def show_avatar_menu(self, event, target_pk, is_me, name=None):
        if is_me:
            return
        menu = tk.Menu(self, tearoff=0)
        is_ghost = False
        if self.current_chat_type == 'group':
            grp = self.client.groups.get(self.current_chat_id)
            if grp and str(grp.get('type')) == '1':
                is_ghost = True
        if self.current_chat_type == 'group':
            menu.add_command(label=tr('MENU_MENTION'), command=lambda: self._add_mention_from_menu(target_pk, name))
            menu.add_separator()
        if not is_ghost:
            is_already_in_dm = self.current_chat_type == 'dm' and self.current_chat_id == target_pk
            if not is_already_in_dm:
                menu.add_command(label=tr('MENU_CHAT_WITH'), command=lambda: self.switch_to_chat_from_contact(target_pk, name))
            menu.add_command(label=tr('MENU_VIEW_PROFILE'), command=lambda: self.show_user_profile(target_pk))
            menu.add_separator()
            is_blocked = self.client.db.is_blocked(target_pk)
            if is_blocked:
                menu.add_command(label=tr('MENU_UNBLOCK_USER'), command=lambda: self.unblock_user(target_pk))
            else:
                menu.add_command(label=tr('MENU_BLOCK_USER'), command=lambda: self.block_user(target_pk))
        if self.current_chat_type == 'group' and (not is_ghost):
            grp = self.client.groups.get(self.current_chat_id)
            if grp:
                owner = self.client.db.get_group_owner(self.current_chat_id)
                if owner == self.client.pk:
                    menu.add_command(label=tr('MENU_OWNER_BAN'), command=lambda: self.client.ban_group_member(self.current_chat_id, target_pk))
        try:
            if event:
                x, y = (event.x_root, event.y_root)
            else:
                x, y = self.winfo_pointerxy()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _add_mention_from_menu(self, target_pk, target_name=None):
        if not self.current_chat_id:
            return
        grp = self.client.groups.get(self.current_chat_id)
        is_ghost = grp and str(grp.get('type')) == '1'
        final_name = 'User'
        if target_name:
            final_name = target_name
        elif not is_ghost:
            final_name = self.client.db.get_contact_name(target_pk) or f'User{get_npub_abbr(target_pk)}'
        else:
            final_name = 'Anon'
        current_text = self.msg_entry.get('0.0', 'end').strip()
        if current_text:
            self.msg_entry.insert('end', f' @{final_name} ')
        else:
            self.msg_entry.insert('0.0', f'@{final_name} ')
        if not is_ghost:
            self.pending_mentions[final_name] = target_pk
        self.msg_entry.focus_set()

    def show_context_menu(self, event, msg_id, raw_content, is_me, sender_pk=None, image_bytes=None):
        menu = tk.Menu(self, tearoff=0)
        text_preview = raw_content
        is_image = False
        is_history = False
        if raw_content.strip().startswith('{'):
            try:
                data = json.loads(raw_content)
                if data.get('type') == 'history':
                    is_history = True
                    title = data.get('title', '')
                    text_preview = f"{tr('HISTORY_CARD_TITLE')} {title}"
                else:
                    text_preview = data.get('text', '')
                    if data.get('image'):
                        is_image = True
                        if not text_preview:
                            text_preview = '[Image]'
            except:
                pass
        if msg_id:
            menu.add_command(label=tr('MENU_MULTI_SELECT'), command=lambda: self.start_multi_select_from_menu(msg_id))
            menu.add_separator()
        if msg_id and text_preview and (not is_history) and ('密钥已过期' not in text_preview):
            menu.add_command(label=tr('MENU_REPLY'), command=lambda: self.start_reply(msg_id, text_preview))
        menu.add_command(label=tr('MENU_FORWARD'), command=lambda: self.open_forward_dialog(raw_content))
        if text_preview and (not is_history):
            menu.add_command(label=tr('MENU_COPY_TEXT'), command=lambda: self.copy_to_clipboard(text_preview))
        if is_image:
            menu.add_command(label=tr('MENU_SAVE_IMG'), command=lambda: self.save_image_from_json(raw_content))
        menu.add_separator()
        if msg_id:
            menu.add_command(label=tr('MENU_DELETE_LOCAL'), command=lambda: self.delete_local_message(msg_id))
            if is_me:
                menu.add_command(label=tr('MENU_RECALL'), command=lambda: self.perform_recall(msg_id))
        try:
            if event:
                x, y = (event.x_root, event.y_root)
            else:
                x, y = self.winfo_pointerxy()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_forward_dialog(self, content_to_forward):
        from gui_windows import SelectSessionDialog

        def _on_selected(target_id, target_type, target_name):
            self._perform_forward(target_id, target_type, target_name, content_to_forward)
        SelectSessionDialog(self, _on_selected)

    def _perform_forward(self, target_id, target_type, target_name, content_json_str):
        clean_text = ''
        clean_img_b64 = None
        msg_preview = tr('FWD_MSG_PREVIEW')
        is_special_payload = False
        if content_json_str and content_json_str.strip().startswith('{'):
            try:
                data = json.loads(content_json_str)
                if data.get('type') == 'history':
                    is_special_payload = True
                    clean_text = content_json_str
                    title = data.get('title', tr('HISTORY_CARD_TITLE'))
                    msg_preview = f'[聊天记录] {title}'
                else:
                    clean_text = data.get('text', '')
                    clean_img_b64 = data.get('image')
            except:
                clean_text = content_json_str
        else:
            clean_text = content_json_str
        preview_ctk_image = None
        if clean_img_b64:
            msg_preview = tr('FWD_IMG_PREVIEW')
            if len(clean_img_b64) < 100:
                clean_img_b64 = None
                msg_preview = tr('FWD_IMG_DAMAGED')
            else:
                try:
                    img_data = base64.b64decode(clean_img_b64)
                    stream = BytesIO(img_data)
                    pil_img = Image.open(stream)
                    pil_img.load()
                    bg = Image.new('RGB', pil_img.size, (255, 255, 255))
                    if pil_img.mode in ('RGBA', 'LA'):
                        bg.paste(pil_img, mask=pil_img.split()[-1])
                    else:
                        bg.paste(pil_img)
                    bg.thumbnail((200, 150))
                    preview_ctk_image = ctk.CTkImage(light_image=bg, dark_image=bg, size=bg.size)
                except Exception as e:
                    print(f'Preview gen error: {e}')
                    msg_preview = tr('FWD_IMG_ERR').format(e=e)
        elif not is_special_payload:
            if len(clean_text) > 50:
                msg_preview = clean_text[:50] + '...'
            else:
                msg_preview = clean_text

        def _confirmed_action():
            ts = int(time.time())
            if is_special_payload:
                final_content = clean_text
            elif clean_img_b64:
                final_content = json.dumps({'text': clean_text, 'image': clean_img_b64})
            else:
                final_content = clean_text

            def _bg_forward():
                try:
                    real_eid = None
                    is_ghost_target = False
                    if target_type == 'group':
                        grp_info = self.client.groups.get(target_id)
                        if grp_info and str(grp_info.get('type')) == '1':
                            is_ghost_target = True
                            real_eid = self.client.send_ghost_msg(target_id, final_content, reply_to_id=None)
                        elif is_special_payload:
                            real_eid = self.client.send_group_msg(target_id, final_content)
                        else:
                            real_eid = self.client.send_group_msg(target_id, clean_text, image_base64=clean_img_b64)
                    elif target_type == 'dm':
                        enc = self.client.db.get_contact_enc_key(target_id)
                        if not enc:
                            self.after(0, lambda: messagebox.showerror(tr('DIALOG_ERROR_TITLE'), 'Missing Key'))
                            return
                        if is_special_payload:
                            real_eid = self.client.send_dm(target_id, final_content, enc)
                        else:
                            real_eid = self.client.send_dm(target_id, clean_text, enc, image_base64=clean_img_b64)
                    if real_eid:
                        if not is_ghost_target:
                            self.client.db.save_message(real_eid, target_id, self.client.pk, final_content, ts, True)
                            time.sleep(0.05)
                        self.after(0, lambda: self.show_toast(tr('TOAST_FORWARD_SUCCESS')))
                        self.after(200, self.refresh_ui)
                        if self.current_chat_id == target_id and (not is_ghost_target):
                            self.after(300, lambda: self.add_message_bubble(real_eid, final_content, True, tr('MSG_SENDER_ME'), ts, scroll_to_bottom=True))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror(tr('DIALOG_ERROR_TITLE'), str(e)))
            threading.Thread(target=_bg_forward, daemon=True).start()
        from gui_windows import ForwardConfirmDialog
        ForwardConfirmDialog(self, target_name, msg_preview, _confirmed_action, image_obj=preview_ctk_image)

    def save_image_from_json(self, json_str):
        try:
            data = json.loads(json_str)
            b64 = data.get('image')
            if b64:
                self.save_image_local(base64.b64decode(b64))
        except:
            pass

    def block_user(self, pk):
        if messagebox.askyesno(tr('DIALOG_BLOCK_USER_TITLE'), tr('DIALOG_BLOCK_USER_MSG')):
            self.client.db.block_contact(pk, True)
            self.refresh_ui()
            self.show_toast(tr('TOAST_BLOCK_USER'))

    def unblock_user(self, pk):
        self.client.db.block_contact(pk, False)
        self.refresh_ui()
        self.show_toast(tr('TOAST_UNBLOCK_USER'))

    def start_reply(self, msg_id, text_preview):
        self.reply_target_id = msg_id
        msg = self.client.db.get_message(msg_id)
        thumb_img = None
        if msg:
            content = msg[3]
            if content.strip().startswith('{') and '"image":' in content:
                try:
                    data = json.loads(content)
                    image_b64 = data.get('image')
                    if image_b64:
                        img_bytes = base64.b64decode(image_b64)
                        pil_img = Image.open(BytesIO(img_bytes))
                        max_w = 256
                        max_h = 150
                        img_w, img_h = pil_img.size
                        ratio = min(max_w / img_w, max_h / img_h)
                        if ratio < 1.0:
                            new_w = int(img_w * ratio)
                            new_h = int(img_h * ratio)
                        else:
                            new_w, new_h = (img_w, img_h)
                        thumb_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
                except Exception as e:
                    print(f'Reply image preview error: {e}')
        final_text = text_preview
        if thumb_img:
            if final_text in ['[Image]', '[图片]', tr('SEARCH_RES_IMG')]:
                final_text = ''
        short_text = final_text[:20] + '...' if len(final_text) > 20 else final_text
        label_text = f'回复: {short_text}' if short_text else '回复:'
        self.reply_label.configure(text=label_text)
        if thumb_img:
            self.reply_thumb_label.configure(image=thumb_img, width=thumb_img._size[0])
            self.reply_thumb_label.image = thumb_img
            self.reply_thumb_label.pack(side='left', padx=(10, 5), pady=2)
        else:
            self.reply_thumb_label.pack_forget()
            self.reply_thumb_label.configure(image=None)
            self.reply_thumb_label.image = None
        self.reply_bar.pack(fill='x', side='top', before=self.input_area)
        self.msg_entry.focus()

    def cancel_reply(self):
        self.reply_target_id = None
        self.reply_bar.pack_forget()
        self.reply_thumb_label.configure(image=None)
        self.reply_thumb_label.image = None

    def delete_local_message(self, msg_id):
        if messagebox.askyesno(tr('DIALOG_DEL_LOCAL_TITLE'), tr('DIALOG_DEL_LOCAL_MSG')):
            self.client.db.delete_message(msg_id)
            self.reload_current_chat()

    def perform_recall(self, msg_id):
        msg = self.client.db.get_message(msg_id)
        if not msg:
            return
        created_at = msg[4]
        now = time.time()
        if now - created_at > 86400:
            self.show_toast(tr('TOAST_RECALL_TIMEOUT'))
            return
        if messagebox.askyesno(tr('MENU_RECALL'), tr('DIALOG_RECALL_MSG')):
            self.client.recall_message(msg_id)
            self._realtime_recall([msg_id])

    def scroll_to_bottom(self):
        if hasattr(self, '_scroll_timer') and self._scroll_timer:
            self.after_cancel(self._scroll_timer)

        def _do_scroll():
            self._scroll_timer = None
            try:
                if self.msg_scroll and self.msg_scroll.winfo_exists():
                    self.msg_scroll._parent_canvas.yview_moveto(1.0)
            except:
                pass
        self._scroll_timer = self.after(100, _do_scroll)

    def select_image(self):
        if not self.current_chat_id:
            return
        file_path = ctk.filedialog.askopenfilename(filetypes=[('Images', '*.png;*.jpg;*.jpeg;*.gif')])
        if not file_path:
            return
        try:
            img = Image.open(file_path)
            max_side = 1280
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            buffer = BytesIO()
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(buffer, format='JPEG', quality=75)
            img_bytes = buffer.getvalue()
            limit_bytes = 700 * 1024
            if len(img_bytes) > limit_bytes:
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=50)
                img_bytes = buffer.getvalue()
                if len(img_bytes) > limit_bytes:
                    messagebox.showerror(tr('IMG_TOO_LARGE_TITLE'), tr('IMG_TOO_LARGE_MSG').format(s=len(img_bytes) // 1024))
                    return
            self.stage_image(img_bytes)
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), tr('IMG_PROC_ERR').format(e=e))

    def send_message(self, event=None, image_data=None):
        from client_persistent import OFFICIAL_GROUP_CONFIG
        if not self.client or not self.current_chat_id:
            return
        if self.current_chat_id == OFFICIAL_GROUP_CONFIG['id']:
            now = time.time()
            if now - self.last_official_msg_time < 5.0:
                self.show_toast(tr('INPUT_CD_TOAST'))
                return 'break'
            self.last_official_msg_time = now
        text = self.msg_entry.get('0.0', 'end').strip()
        final_image_b64 = image_data
        if not final_image_b64 and self.pending_image_bytes:
            final_image_b64 = base64.b64encode(self.pending_image_bytes).decode('utf-8')
        if not text and (not final_image_b64):
            return
        final_mention_pks = []
        if self.current_chat_type == 'group':
            for name, pk in list(self.pending_mentions.items()):
                if f'@{name}' in text:
                    if pk == 'ALL':
                        if 'ALL' not in final_mention_pks:
                            final_mention_pks.append('ALL')
                    elif pk not in final_mention_pks:
                        final_mention_pks.append(pk)
            self.pending_mentions.clear()
        self.msg_entry.delete('0.0', 'end')
        self.clear_pending_image()
        self.send_btn.configure(state='disabled', text=tr('BTN_SENDING'))
        if hasattr(self, 'btn_emoji'):
            self.btn_emoji.configure(state='disabled')
        if hasattr(self, 'btn_screenshot'):
            self.btn_screenshot.configure(state='disabled')
        rid = self.reply_target_id
        self.cancel_reply()
        chat_id = self.current_chat_id
        chat_type = self.current_chat_type

        def _restore():
            if not self.winfo_exists():
                return
            btn_text = f"{tr('BTN_SEND')} (Enter)"
            self.send_btn.configure(state='normal', text=btn_text)
            if hasattr(self, 'btn_emoji'):
                self.btn_emoji.configure(state='normal')
            if hasattr(self, 'btn_screenshot'):
                self.btn_screenshot.configure(state='normal')
            self.msg_entry.focus_set()

        def _bg_send():
            try:
                if chat_type == 'group':
                    grp = self.client.groups.get(chat_id)
                    if grp and (grp.get('type') == 1 or str(grp.get('type')) == '1'):
                        self.client.send_ghost_msg(chat_id, text, image_base64=final_image_b64, reply_to_id=rid)
                        return
                ts = int(time.time())
                db_content = text
                if final_image_b64:
                    db_content = json.dumps({'text': text, 'image': final_image_b64})
                real_event_id = None
                if chat_type == 'group':
                    real_event_id = self.client.send_group_msg(chat_id, text, reply_to_id=rid, image_base64=final_image_b64, mention_pks=final_mention_pks)
                    if real_event_id:
                        self.client.db.save_message(real_event_id, chat_id, self.client.pk, db_content, ts, True, reply_to_id=rid)
                elif chat_type == 'dm':
                    target_pk = chat_id
                    enc = self.client.db.get_contact_enc_key(target_pk)
                    if not enc:
                        self.after(0, lambda: self.show_toast(tr('TOAST_SYNCING')))
                        return
                    real_event_id = self.client.send_dm(target_pk, text, enc, reply_to_id=rid, image_base64=final_image_b64)
                if real_event_id:
                    self.after(0, lambda: self.add_message_bubble(real_event_id, db_content, True, tr('MSG_SENDER_ME'), ts, reply_to_id=rid, scroll_to_bottom=True))
                    self.after(0, self.refresh_ui)
                    self.after(100, lambda: self.scroll_to_bottom())
            except Exception as e:
                print(f'Async send error: {e}')
                self.after(0, lambda: self.show_toast(f'发送失败: {e}'))
            finally:
                self.after(0, _restore)
        threading.Thread(target=_bg_send, daemon=True).start()
        return 'break'

    def show_my_profile(self):
        if not self.client:
            return
        self.show_user_profile(self.client.pk)

    def show_user_profile(self, pubkey):
        if self.active_profile_window and self.active_profile_window.winfo_exists():
            self.active_profile_window.destroy()
        is_self = pubkey == self.client.pk
        self.active_profile_window = ProfileWindow(self, pubkey, is_self=is_self)

    def run_export_task(self, target_id, file_path, fmt, start_ts=0, end_ts=0):
        try:
            from client_persistent import OFFICIAL_GROUP_CONFIG
            from key_utils import get_npub_abbr, to_npub
            import base64
            exclude_gid = None
            if target_id is None:
                exclude_gid = OFFICIAL_GROUP_CONFIG['id']
            msgs = self.client.db.get_messages_grouped_for_export(target_id, start_ts=start_ts, end_ts=end_ts, exclude_gid=exclude_gid)
            if not msgs:
                self.after(0, lambda: self.show_toast(tr('TOAST_EXPORT_NODATA')))
                return

            def _render_items_recursive(items, level=0):
                html_out = ''
                txt_out = ''
                indent_str = '    ' * (level + 1)
                for item in items:
                    h_name = item.get('n', 'User')
                    h_ts = datetime.fromtimestamp(item.get('t', 0)).strftime('%Y-%m-%d %H:%M:%S')
                    raw_content = item.get('c', '')
                    img_b64 = item.get('i')
                    nested_html = ''
                    nested_txt = ''
                    display_text = raw_content
                    if raw_content and isinstance(raw_content, str) and raw_content.strip().startswith('{'):
                        try:
                            d = json.loads(raw_content)
                            if d.get('type') == 'history':
                                sub_title = d.get('title', 'Chat History')
                                sub_items = d.get('items', [])
                                sub_res = _render_items_recursive(sub_items, level + 1)
                                if fmt == 'html':
                                    nested_html = f"\n                                    <div class='history-card' style='margin-top:5px; border-left:3px solid #1F6AA5; background:#f0f0f0; padding:5px;'>\n                                        <div class='history-title' style='font-size:12px; font-weight:bold; color:#555; border-bottom:1px solid #ddd; margin-bottom:5px;'>{sub_title}</div>\n                                        {sub_res['html']}\n                                    </div>\n                                    "
                                    display_text = ''
                                else:
                                    nested_txt = f"\n{indent_str}>>> [{sub_title}]\n{sub_res['txt']}"
                                    display_text = ''
                            else:
                                txt_val = d.get('text', '')
                                display_text = txt_val
                                if d.get('image'):
                                    img_b64 = d.get('image')
                        except:
                            pass
                    if fmt == 'html':
                        safe_text = str(display_text).replace('<', '&lt;').replace('>', '&gt;')
                        text_html = f'<span>{safe_text}</span>' if safe_text else ''
                        img_tag = ''
                        if img_b64:
                            img_tag = f"<br><img src='data:image/jpeg;base64,{img_b64}' style='max-width:200px;max-height:200px; border-radius:4px; margin-top:4px; box-shadow:0 1px 3px rgba(0,0,0,0.2);'>"
                        if text_html or img_tag or nested_html:
                            html_out += f"\n                            <div class='history-item' style='padding:4px 0; border-bottom:1px dotted #ccc;'>\n                                <b style='color:#333;'>{h_name}</b> <span style='color:#888;font-size:11px'>({h_ts})</span>:\n                                {text_html}\n                                {img_tag}\n                                {nested_html}\n                            </div>\n                            "
                    else:
                        img_mark = ' [图片]' if img_b64 else ''
                        content_line = f'{display_text}{img_mark}'
                        if content_line or nested_txt:
                            txt_out += f'{indent_str}> {h_name} ({h_ts}): {content_line}{nested_txt}\n'
                return {'html': html_out, 'txt': txt_out}
            current_session_id = None
            with open(file_path, 'w', encoding='utf-8') as f:
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if fmt == 'html':
                    f.write(f"\n                    <html><head><meta charset='utf-8'><style>\n                    body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f5f5f5; padding: 20px; color:#333; }}\n                    .session-header {{ background: #e0e0e0; padding: 10px; margin-top: 30px; border-radius: 5px; font-weight: bold; color: #444; border-left: 5px solid #666; }}\n                    .msg {{ margin-bottom: 15px; padding: 10px; border-radius: 8px; max-width: 90%; clear: both; position: relative; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }}\n                    .msg.me {{ background: #95ec69; float: right; }}\n                    .meta {{ font-size: 12px; color: #888; margin-bottom: 5px; border-bottom: 1px solid #eee; padding-bottom: 2px; }}\n                    .content {{ font-size: 14px; white-space: pre-wrap; line-height: 1.5; }}\n                    .history-card {{ background: #fff; border: 1px solid #ccc; border-radius: 5px; padding: 10px; margin-top: 5px; }}\n                    .history-title {{ font-weight: bold; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 5px; color: #1F6AA5; }}\n                    img {{ max-width: 400px; display: block; margin-top: 5px; }}\n                    .clear {{ clear: both; }}\n                    </style></head><body>\n                    <h2>{tr('EXP_HTML_TITLE')}</h2><p>{now_str}</p>\n                    ")
                else:
                    f.write(f"{tr('EXP_TXT_HEADER')}\nTime: {now_str}\n====================\n")
                for m in msgs:
                    gid, gname, ts, sname, content, is_me, spk, stype_raw = m
                    if gid != current_session_id:
                        current_session_id = gid
                        header = f'Session: {gname} ({gid})'
                        if fmt == 'html':
                            f.write(f"<div class='clear'></div><div class='session-header'>{header}</div>")
                        else:
                            f.write(f'\n\n{header}\n--------------------\n')
                    text_part = content
                    img_html = ''
                    history_block = ''
                    if content.strip().startswith('{'):
                        try:
                            d = json.loads(content)
                            if isinstance(d, str):
                                try:
                                    d = json.loads(d)
                                except:
                                    pass
                            if isinstance(d, dict):
                                if d.get('type') == 'history':
                                    res = _render_items_recursive(d.get('items', []))
                                    title = d.get('title', 'History')
                                    if fmt == 'html':
                                        text_part = ''
                                        history_block = f"\n                                        <div class='history-card'>\n                                            <div class='history-title'>{title}</div>\n                                            {res['html']}\n                                        </div>\n                                        "
                                    else:
                                        text_part = f'[{title}]'
                                        history_block = res['txt']
                                else:
                                    raw_text = d.get('text', '')
                                    is_hidden_history = False
                                    if raw_text and isinstance(raw_text, str) and raw_text.strip().startswith('{'):
                                        try:
                                            inner = json.loads(raw_text)
                                            if inner.get('type') == 'history':
                                                is_hidden_history = True
                                                res = _render_items_recursive(inner.get('items', []))
                                                title = inner.get('title', 'History')
                                                if fmt == 'html':
                                                    text_part = ''
                                                    history_block = f"\n                                                    <div class='history-card'>\n                                                        <div class='history-title'>{title}</div>\n                                                        {res['html']}\n                                                    </div>\n                                                    "
                                                else:
                                                    text_part = f'[{title}]'
                                                    history_block = res['txt']
                                        except:
                                            pass
                                    if not is_hidden_history:
                                        text_part = raw_text
                                        if d.get('image'):
                                            b64 = d.get('image')
                                            if fmt == 'html':
                                                img_html = f"<br><img src='data:image/jpeg;base64,{b64}'>"
                                            else:
                                                text_part += ' [图片]'
                        except:
                            pass
                    time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                    sender = f"{tr('EXP_SENDER_ME')}" if is_me else sname
                    if fmt == 'html':
                        cls = 'me' if is_me else 'other'
                        safe_txt = str(text_part).replace('<', '&lt;').replace('>', '&gt;')
                        f.write(f"\n                        <div class='msg {cls}'>\n                            <div class='meta'>{sender} - {time_str}</div>\n                            <div class='content'>{safe_txt}{img_html}{history_block}</div>\n                        </div>\n                        ")
                    else:
                        f.write(f'[{time_str}] {sender}: {text_part}\n{history_block}')
                if fmt == 'html':
                    f.write("<div class='clear'></div></body></html>")
            self.after(0, lambda: self.show_toast(tr('TOAST_EXPORT_SUCCESS').format(path=os.path.basename(file_path))))
        except Exception as e:
            print(f'Export error: {e}')
            import traceback
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror('Error', str(e)))

    def show_chat_info(self, target_id=None):
        cid = target_id if target_id else self.current_chat_id
        if not cid:
            return
        if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
            self.current_info_window.destroy()
        if cid in self.client.groups:
            group_info = self.client.groups[cid]
            g_type = group_info.get('type', 0)
            from client_persistent import OFFICIAL_GROUP_CONFIG
            is_official = cid == OFFICIAL_GROUP_CONFIG['id']
            info = {}
            if is_official:
                info = {tr('INFO_KEY_NAME'): group_info['name'], tr('INFO_KEY_ID'): '-', tr('INFO_KEY_TYPE'): tr('INFO_VAL_OFFICIAL'), tr('INFO_KEY_DESC'): tr('INFO_VAL_OFFICIAL_DESC')}
            elif g_type == 1:
                link, _ = self._generate_invite_link_content(cid)
                display_code = link if link else 'Error'
                info = {tr('INFO_KEY_NAME'): group_info['name'], tr('INFO_KEY_ID'): 'Ghost Group (Hidden)', tr('INFO_KEY_TYPE'): tr('INFO_VAL_GHOST'), tr('INFO_KEY_CODE_GHOST'): display_code}
            else:
                link, _ = self._generate_invite_link_content(cid)
                display_code = link if link else 'Error'
                owner = self.client.db.get_group_owner(cid)
                owner_disp = self.client._format_sender_info(owner) if owner else 'Unknown'
                info = {tr('INFO_KEY_NAME'): group_info['name'], tr('INFO_KEY_ID'): cid, tr('INFO_KEY_OWNER'): owner_disp, tr('INFO_KEY_CODE_NORMAL'): display_code}
            buttons = []
            if is_official:
                is_blocked = self.client.db.is_group_blocked(cid)
                if is_blocked:
                    buttons.append((tr('INFO_BTN_UNBLOCK_OFFICIAL'), lambda: self.toggle_block_group(False, cid), 'green'))
                else:
                    buttons.append((tr('INFO_BTN_BLOCK_OFFICIAL'), lambda: self.toggle_block_group(True, cid), '#333'))
            elif g_type == 1:
                buttons.append((tr('INFO_BTN_GHOST_INVITE'), lambda: self.open_ghost_invite_dialog(cid), '#D32F2F'))
                buttons.append((tr('INFO_BTN_RENAME'), lambda: self.rename_group_local(cid), '#555'))
                buttons.append((tr('INFO_BTN_EXIT_GHOST'), lambda: self.exit_group(cid, group_info['name']), '#333'))
            else:
                buttons.append((tr('INFO_BTN_NORMAL_INVITE'), lambda: self.open_invite_dialog(cid), '#1F6AA5'))
                buttons.append((tr('INFO_BTN_RENAME'), lambda: self.rename_group_local(cid), '#555'))
                buttons.append((tr('INFO_BTN_BAN_LIST'), lambda: self.open_group_ban_manager(cid), '#555'))
                is_blocked = self.client.db.is_group_blocked(cid)
                if is_blocked:
                    buttons.append((tr('INFO_BTN_UNBLOCK_NORMAL'), lambda: self.toggle_block_group(False, cid), 'green'))
                else:
                    buttons.append((tr('INFO_BTN_BLOCK_NORMAL'), lambda: self.toggle_block_group(True, cid), '#333'))
                buttons.append((tr('INFO_BTN_EXIT_NORMAL'), lambda: self.exit_group(cid, group_info['name']), '#D32F2F'))
            member_list = None
            if g_type == 0:
                member_list = []
                m_pks = self.client.db.get_group_members(cid)
                owner = self.client.db.get_group_owner(cid)
                is_owner = owner == self.client.pk
                display_m_pks = m_pks[:100] if len(m_pks) > 100 else m_pks
                for pk in display_m_pks:
                    if pk == self.client.pk:
                        continue
                    m_data = {'name': self.client._format_sender_info(pk), 'pk': pk}
                    if is_owner and (not is_official):
                        m_data['kick_cb'] = lambda p=pk: self.owner_ban_action(p, group_id=cid)
                    member_list.append(m_data)
            title_prefix = tr('INFO_TITLE_OFFICIAL') if is_official else tr('INFO_TITLE_GHOST') if g_type == 1 else tr('INFO_TITLE_NORMAL')
            self.current_info_window = InfoWindow(title_prefix, info, buttons, member_list, parent_app=self)
        else:
            self.show_user_profile(cid)

    def open_ghost_invite_dialog(self, group_id):
        target_parent = self
        if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
            target_parent = self.current_info_window
        if messagebox.askyesno(tr('DIALOG_GHOST_WARN_TITLE'), tr('DIALOG_GHOST_WARN_MSG'), icon='warning', parent=target_parent):
            self.open_invite_dialog(group_id)

    def open_group_ban_manager(self, group_id=None):
        target_gid = group_id if group_id else self.current_chat_id
        if target_gid:
            GroupBanListWindow(self, target_gid)

    def owner_ban_action(self, target_pk, group_id=None):
        target_gid = group_id if group_id else self.current_chat_id
        if not target_gid:
            return
        if messagebox.askyesno(tr('DIALOG_WARN_TITLE'), 'Ban member?'):
            self.client.ban_group_member(target_gid, target_pk)
            self.show_toast(tr('TOAST_BAN_CMD_SENT'))
            if hasattr(self, 'current_info_window') and self.current_info_window.winfo_exists():
                self.current_info_window.destroy()
                self.show_chat_info(target_gid)

    def open_relay_config(self):
        RelayConfigWindow(self)

    def rename_group_local(self, group_id=None):
        target_gid = group_id if group_id else self.current_chat_id
        if not target_gid:
            return
        from gui_windows import InputWindow
        dialog = InputWindow(self, title=tr('INFO_BTN_RENAME'), prompt='New Name:')
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            final_name = new_name.strip()
            self.client.db.update_group_name_local(target_gid, final_name)
            if target_gid in self.client.groups:
                self.client.groups[target_gid]['name'] = final_name
            self.refresh_ui()
            if self.current_chat_id == target_gid:
                display_title = final_name
                grp = self.client.groups.get(target_gid)
                if grp:
                    if str(grp.get('type')) == '1':
                        display_title = f"{tr('TYPE_GHOST')} {display_title}"
                    else:
                        display_title = f"{tr('TYPE_NORMAL')} {display_title}"
                self.chat_title.configure(text=display_title)
            if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
                self.show_chat_info(target_gid)
            self.show_toast(tr('TOAST_RENAME_SUCCESS'))

    def toggle_block_group(self, block, group_id=None):
        target_gid = group_id if group_id else self.current_chat_id
        if not target_gid:
            return
        self.client.db.block_group(target_gid, block)
        self.refresh_ui()
        msg = tr('TOAST_BLOCK_GROUP') if block else tr('TOAST_UNBLOCK_GROUP')
        self.show_toast(msg)
        if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
            self.show_chat_info(target_gid)
        if self.current_chat_id == target_gid:
            self.update_input_state()

    def open_invite_dialog(self, group_id=None):
        target_gid = group_id if group_id else self.current_chat_id
        if not target_gid:
            return
        invite_link, invite_text = self._generate_invite_link_content(target_gid)
        if not invite_text:
            self.show_toast('生成邀请码失败')
            return
        all_friends = self.client.db.get_friends()
        candidates = [f for f in all_friends if f['pubkey'] != self.client.pk]
        if not candidates:
            self.show_toast('暂无好友可邀请')
            return
        from gui_windows import MultiSelectContactDialog
        target_parent = self
        if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
            target_parent = self.current_info_window

        def _on_invite_confirm(selected_pks):
            if not selected_pks:
                return
            import time
            from hashlib import sha256
            count = 0
            for pk in selected_pks:
                enc_key = self.client.db.get_contact_enc_key(pk)
                if enc_key:
                    self.client.send_dm(pk, invite_text, enc_key)
                    ts = int(time.time())
                    msg_id = sha256(f'{ts}{pk}'.encode()).hexdigest()
                    self.client.db.save_message(msg_id, pk, self.client.pk, invite_text, ts, True)
                    count += 1
                    time.sleep(0.1)
            self.show_toast(f'✅ 已发送 {count} 份邀请链接')
            if hasattr(self, 'current_info_window') and self.current_info_window and self.current_info_window.winfo_exists():
                self.current_info_window.destroy()
                self.current_info_window = None
        MultiSelectContactDialog(target_parent, candidates, _on_invite_confirm)

    def handle_dage_link(self, link):
        import base64
        from hashlib import sha256
        from nacl.secret import SecretBox
        if not link.startswith('dage://invite/'):
            self.show_toast('❌ 无效的链接格式')
            return
        try:
            parts = link.replace('dage://invite/', '').split('/')
            if len(parts) < 2:
                return
            invite_type = parts[0]
            payload = parts[1]
            raw_str = ''
            if invite_type == 'ghost':
                ciphertext = base64.urlsafe_b64decode(payload)
                obfuscate_key = sha256('dagechat'.encode()).digest()
                box = SecretBox(obfuscate_key)
                raw_str = box.decrypt(ciphertext).decode('utf-8')
            elif invite_type == 'normal':
                raw_str = base64.urlsafe_b64decode(payload).decode('utf-8')
            else:
                self.show_toast('❌ 未知的群组类型')
                return
            data_parts = raw_str.split('|')
            if len(data_parts) < 6:
                self.show_toast('❌ 链接数据损坏')
                return
            gid, key, owner, safe_name, g_type, checksum = data_parts[:6]
            try:
                group_name = base64.urlsafe_b64decode(safe_name).decode()
            except:
                group_name = 'Unknown Group'
            if self._calc_invite_checksum(gid, key, int(g_type)) != checksum:
                self.show_toast('❌ 链接校验失败 (可能被篡改)')
                return
            if gid in self.client.groups:
                self.show_toast(f'您已经在群组【{group_name}】中了')
                self.switch_chat(gid, group_name, 'group')
                return
            if not messagebox.askyesno('加入群聊', f'确定加入群组？\n\n名称: {group_name}\nID: {gid[:8]}...'):
                return
            self.client.db.save_group(gid, group_name, key, owner_pubkey=owner, group_type=int(g_type))
            if str(g_type) == '1':
                self.client.groups[gid] = {'name': group_name, 'key_hex': key, 'type': 1}
                filter_obj = {'kinds': [1059], '#p': [gid], 'limit': 50}
            else:
                self.client.groups[gid] = {'name': group_name, 'key_hex': key, 'type': 0}
                filter_obj = {'kinds': [42, 30078], '#g': [gid], 'limit': 50}
            sub_id = f'sub_join_{gid[:8]}'
            req_msg = json.dumps(['REQ', sub_id, filter_obj])

            def _bg_task():
                self.client.relay_manager.broadcast_send(req_msg)
                self.client.sync_backup_to_cloud()
                time.sleep(0.5)
                if str(g_type) == '0':
                    self.client.send_group_msg(gid, tr('GREETING_GROUP'))
                self.after(0, lambda: self.refresh_ui())
                self.after(0, lambda: self.switch_chat(gid, group_name, 'group'))
                self.after(0, lambda: self.show_toast(f'✅ 成功加入: {group_name}'))
            threading.Thread(target=_bg_task, daemon=True).start()
        except Exception as e:
            print(f'Link parse error: {e}')
            self.show_toast(f'❌ 链接解析错误: {e}')

    def process_invite(self, pubkey, manual=False):
        target_gid = getattr(self, '_invite_target_gid', self.current_chat_id)
        if manual:
            from gui_windows import InputWindow
            dialog = InputWindow(self, title=tr('BTN_MANUAL_INPUT'), prompt='Pubkey (Hex / npub1):')
            raw_inp = dialog.get_input()
            if not raw_inp:
                self.invite_window = None
                return
            pubkey = to_hex_pubkey(raw_inp)
        if not pubkey or len(pubkey) != 64:
            if manual:
                self.show_toast('❌ Invalid Pubkey')
            self.invite_window = None
            return
        enc = self.client.db.get_contact_enc_key(pubkey)
        if enc:
            if messagebox.askyesno(tr('DIALOG_CONFIRM_TITLE'), f'Invite {pubkey[:6]}...?'):
                self.client.invite_user(target_gid, enc)
                self.show_toast(tr('TOAST_INVITE_SENT_SINGLE').format(name=pubkey[:6]))
        else:
            self.client.fetch_user_profile(pubkey)
            self.show_toast(tr('TOAST_SYNCING'))
        self.invite_window = None

    def _generate_invite_link_content(self, gid):
        if gid not in self.client.groups:
            return (None, None)
        grp_info = self.client.groups[gid]
        g_name = grp_info['name']
        g_key = grp_info['key_hex']
        g_type = grp_info.get('type', 0)
        owner = self.client.db.get_group_owner(gid)
        import base64
        from hashlib import sha256
        from nacl.secret import SecretBox
        checksum = self._calc_invite_checksum(gid, g_key, g_type)
        safe_name = base64.urlsafe_b64encode(g_name.encode()).decode()
        raw_data = f"{gid}|{g_key}|{owner or ''}|{safe_name}|{g_type}|{checksum}"
        invite_link = ''
        try:
            if str(g_type) == '1':
                obfuscate_key = sha256('dagechat'.encode()).digest()
                box = SecretBox(obfuscate_key)
                encrypted = box.encrypt(raw_data.encode('utf-8'))
                b64_payload = base64.urlsafe_b64encode(encrypted).decode('utf-8')
                invite_link = f'dage://invite/ghost/{b64_payload}'
            else:
                b64_payload = base64.urlsafe_b64encode(raw_data.encode('utf-8')).decode('utf-8')
                invite_link = f'dage://invite/normal/{b64_payload}'
        except Exception as e:
            print(f'Gen link error: {e}')
            return (None, None)
        invite_text = f'邀请加入群聊【{g_name}】\n点击下方链接或复制加入：\n{invite_link}'
        return (invite_link, invite_text)

    def create_group_dialog(self):
        from gui_windows import MultiSelectContactDialog
        dialog = ctk.CTkToplevel(self)
        dialog.title(tr('TITLE_GROUP_MANAGE'))
        w, h = (450, 450)
        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() - w) // 2
            y = self.winfo_y() + (self.winfo_height() - h) // 2
            x = max(0, x)
            y = max(0, y)
            dialog.geometry(f'{w}x{h}+{x}+{y}')
        except:
            dialog.geometry(f'{w}x{h}')
        dialog.attributes('-topmost', True)
        self._temp_selected_members = []

        def _update_selected_members(selected_pks):
            self._temp_selected_members = selected_pks
            count = len(selected_pks)
            text_show = f'Selected {count}' if count > 0 else 'None'
            color_show = '#69F0AE' if count > 0 else 'gray'
            lbl_selected_count.configure(text=text_show, text_color=color_show)

        def _open_member_selector():
            friends = self.client.db.get_friends()
            friends = [f for f in friends if f['pubkey'] != self.client.pk]
            MultiSelectContactDialog(dialog, friends, _update_selected_members)
        tab_view = ctk.CTkTabview(dialog)
        tab_view.pack(fill='both', expand=True, padx=10, pady=10)
        tab_create = tab_view.add(tr('TAB_CREATE_GROUP'))
        ctk.CTkLabel(tab_create, text=tr('LBL_GROUP_NAME'), font=('Microsoft YaHei UI', 12)).pack(pady=(15, 5))
        entry_name = ctk.CTkEntry(tab_create, width=300)
        entry_name.pack(pady=5)
        is_ghost_var = ctk.BooleanVar(value=False)
        cb_ghost = ctk.CTkCheckBox(tab_create, text=tr('CB_GHOST_GROUP'), variable=is_ghost_var)
        cb_ghost.pack(pady=15)
        member_frame = ctk.CTkFrame(tab_create, fg_color='transparent')
        member_frame.pack(pady=5)
        ctk.CTkButton(member_frame, text=tr('BTN_ADD_INIT_MEMBER'), width=120, fg_color='#444', command=_open_member_selector).pack(side='left', padx=10)
        lbl_selected_count = ctk.CTkLabel(member_frame, text='None', text_color='gray', font=('Microsoft YaHei UI', 11))
        lbl_selected_count.pack(side='left', padx=5)

        def _do_create():
            name = entry_name.get().strip()
            if not name:
                return messagebox.showwarning(tr('DIALOG_WARN_TITLE'), 'Empty Name', parent=dialog)
            is_ghost = is_ghost_var.get()
            selected_pks = self._temp_selected_members
            if is_ghost and selected_pks:
                warn_msg = f'⚠️ 安全警告：共享密钥群\n\n您即将向 {len(selected_pks)} 位好友发送包含【群私钥】的邀请链接。\n私钥一旦发出无法撤回。请确保这些好友绝对值得信赖。\n\n确定要发送吗？'
                if not messagebox.askyesno('风险确认', warn_msg, parent=dialog, icon='warning'):
                    return
            dialog.destroy()
            self.show_toast(f'⏳ 正在创建【{name}】...', duration=2000)

            def _bg_task():
                try:
                    gid = self.client.create_group(name, is_ghost=is_ghost)
                    time.sleep(0.5)
                    self.gui_queue.put(('refresh', None))
                    time.sleep(0.5)
                    if not is_ghost:
                        self.client.send_group_msg(gid, tr('GREETING_GROUP_CREATE'))
                        time.sleep(0.2)
                    invite_count = 0
                    if selected_pks:
                        link, invite_txt = self._generate_invite_link_content(gid)
                        if invite_txt:
                            for pk in selected_pks:
                                enc_key = self.client.db.get_contact_enc_key(pk)
                                if enc_key:
                                    self.client.send_dm(pk, invite_txt, enc_key)
                                    ts = int(time.time())
                                    from hashlib import sha256
                                    msg_id = sha256(f'{ts}{pk}{gid}'.encode()).hexdigest()
                                    self.client.db.save_message(msg_id, pk, self.client.pk, invite_txt, ts, True)
                                    invite_count += 1
                                else:
                                    self.client.fetch_user_profile(pk)
                                time.sleep(0.1)

                    def _finish():
                        if is_ghost:
                            self.show_toast(tr('TOAST_CREATE_GHOST').format(id=gid[:8]))
                        else:
                            msg = tr('TOAST_CREATE_NORMAL').format(name=name)
                            if invite_count > 0:
                                msg += f'\n(已发送 {invite_count} 份邀请)'
                            self.show_toast(msg)
                        self.switch_chat(gid, name, 'group')
                    self.after(0, _finish)
                except Exception as e:
                    print(f'Create group error: {e}')
                    self.after(0, lambda: messagebox.showerror(tr('DIALOG_ERROR_TITLE'), f'Failed: {e}'))
            threading.Thread(target=_bg_task, daemon=True).start()
        ctk.CTkButton(tab_create, text=tr('BTN_CREATE_NOW'), command=_do_create, fg_color='green').pack(side='bottom', pady=20)
        tab_join = tab_view.add(tr('TAB_JOIN_GROUP'))
        ctk.CTkLabel(tab_join, text=tr('LBL_PASTE_CODE'), font=('Microsoft YaHei UI', 12)).pack(pady=(20, 5))
        entry_code = ctk.CTkEntry(tab_join, width=300)
        entry_code.pack(pady=5)

        def _do_join():
            inp = entry_code.get().strip()
            if not inp:
                return
            if inp.startswith('dage://invite/'):
                dialog.destroy()
                self.handle_dage_link(inp)
                return
            dialog.destroy()
            raw_invite_str = inp
            if inp.startswith('dage://ghost/'):
                try:
                    import base64
                    from hashlib import sha256
                    from nacl.secret import SecretBox
                    b64_content = inp.split('dage://ghost/')[1]
                    ciphertext = base64.urlsafe_b64decode(b64_content)
                    obfuscate_key = sha256('dagechat'.encode()).digest()
                    box = SecretBox(obfuscate_key)
                    decrypted = box.decrypt(ciphertext)
                    raw_invite_str = decrypted.decode('utf-8')
                except Exception as e:
                    messagebox.showerror(tr('DIALOG_ERROR_TITLE'), f'Code Error: {e}', parent=self)
                    return
            if '|' not in raw_invite_str:
                messagebox.showerror(tr('DIALOG_ERROR_TITLE'), 'Invalid Format', parent=self)
                return
            try:
                parts = [p.strip() for p in raw_invite_str.split('|')]
                if len(parts) < 6:
                    return messagebox.showerror('Error', 'Invalid Code', parent=self)
                gid, key, owner = (parts[0], parts[1], parts[2] if parts[2] else None)
                group_name = f'Group{gid[:6]}'
                if parts[3]:
                    try:
                        import base64
                        group_name = base64.urlsafe_b64decode(parts[3]).decode()
                    except:
                        group_name = parts[3]
                g_type = 0
                try:
                    g_type = int(parts[4])
                except:
                    pass
                if self._calc_invite_checksum(gid, key, g_type) != parts[5]:
                    return messagebox.showerror(tr('DIALOG_WARN_TITLE'), 'Checksum Failed', parent=self)
                self.client.db.save_group(gid, group_name, key, owner_pubkey=owner, group_type=g_type)
                if g_type == 1:
                    self.client.groups[gid] = {'name': group_name, 'key_hex': key, 'type': 1}
                else:
                    self.client.groups[gid] = {'name': group_name, 'key_hex': key, 'type': 0}
                sub_id = f'sub_join_{gid[:8]}'
                filter_obj = {}
                if g_type == 1:
                    filter_obj = {'kinds': [1059], '#p': [gid], 'limit': 50}
                else:
                    filter_obj = {'kinds': [42, 30078], '#g': [gid], 'limit': 50}
                req_msg = json.dumps(['REQ', sub_id, filter_obj])
                if owner:
                    self.client.db.add_group_member(gid, owner, role='owner')
                    self.client.db.add_group_member(gid, self.client.pk)

                def _bg_join_task():
                    self.client.relay_manager.broadcast_send(req_msg)
                    self.client.sync_backup_to_cloud()
                    time.sleep(0.5)
                    if g_type == 0:
                        self.client.send_group_msg(gid, tr('GREETING_GROUP'))
                    self.after(0, lambda: self.refresh_ui())
                    self.after(0, lambda: self.switch_chat(gid, group_name, 'group'))
                    self.after(0, lambda: self.show_toast(tr('TOAST_JOIN_SUCCESS').format(name=group_name)))
                threading.Thread(target=_bg_join_task, daemon=True).start()
            except Exception as e:
                messagebox.showerror(tr('DIALOG_ERROR_TITLE'), f'Join Error: {e}', parent=self)
        ctk.CTkButton(tab_join, text=tr('BTN_JOIN_NOW'), command=_do_join, fg_color='#1F6AA5').pack(pady=20)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.show_toast(tr('TOAST_CLIPBOARD'))

    def save_image_local(self, img_bytes, parent=None):
        try:
            target_parent = parent if parent else self
            file_path = ctk.filedialog.asksaveasfilename(parent=target_parent, defaultextension='.jpg', filetypes=[('JPEG Image', '*.jpg'), ('PNG Image', '*.png'), ('All Files', '*.*')], title='Save Image')
            if not file_path:
                return
            with open(file_path, 'wb') as f:
                f.write(img_bytes)
            self.show_toast(tr('TOAST_SAVED'))
        except Exception as e:
            messagebox.showerror(tr('DIALOG_ERROR_TITLE'), f'Error: {e}', parent=target_parent)

    def send_auto_greeting(self, target_pk):
        if target_pk in self._sent_greetings:
            return
        if self.client.db.has_chat_history(target_pk):
            return
        enc = self.client.db.get_contact_enc_key(target_pk)
        if not enc:
            return
        self._sent_greetings.add(target_pk)
        greeting_text = tr('GREETING_TEXT')
        try:
            real_event_id = self.client.send_dm(target_pk, greeting_text, enc)
            if real_event_id:
                ts = int(time.time())
                self.client.db.save_message(real_event_id, target_pk, self.client.pk, greeting_text, ts, True)
                if self.current_chat_id == target_pk:
                    self.add_message_bubble(real_event_id, greeting_text, True, 'Me', ts, scroll_to_bottom=True)
        except:
            pass

    def on_right_click_item(self, event, target_id, target_name, item_type, widget):
        original_color = widget.cget('fg_color')
        hover_color = widget.cget('hover_color')
        try:
            widget.configure(fg_color='#444444')
        except:
            pass
        if item_type == 'contact':
            self.show_contact_context_menu(event, target_id, target_name)
        else:
            self.show_session_context_menu(event, target_id, target_name, item_type)
        self.after(2000, lambda: self._restore_widget_color(widget, original_color))

    def _restore_widget_color(self, widget, color):
        try:
            widget.configure(fg_color=color)
        except:
            pass

    def open_settings_window(self):
        from gui_windows import SettingsWindow
        SettingsWindow(self)

    def search_current_chat(self):
        if not self.current_chat_id:
            return
        from gui_windows import SearchWindow
        SearchWindow(self, target_id=self.current_chat_id)

    def export_current_chat(self):
        if not self.current_chat_id:
            return
        ExportSelectionDialog(self, target_id=self.current_chat_id, target_name='Current')
if __name__ == '__main__':
    app = ChatApp()
    app.mainloop()