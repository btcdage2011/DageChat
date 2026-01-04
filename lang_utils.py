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
import locale
import json
import os
import sys
from lang_data import TRANS
DEFAULT_LANG = 'zh_CN'
CURRENT_LANG = DEFAULT_LANG

def load_language_config():
    global CURRENT_LANG
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, 'config.json')
    saved_lang = None
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                saved_lang = data.get('language')
        except:
            pass
    if saved_lang and saved_lang in TRANS:
        CURRENT_LANG = saved_lang
        print(f'🌐 [Lang] Loaded from config: {CURRENT_LANG}')
        return
    try:
        sys_lang_code, _ = locale.getdefaultlocale()
        if sys_lang_code:
            if 'zh' in sys_lang_code.lower():
                CURRENT_LANG = 'zh_CN'
            elif 'en' in sys_lang_code.lower():
                CURRENT_LANG = 'en_US'
            print(f'🌐 [Lang] Detected OS language: {sys_lang_code} -> {CURRENT_LANG}')
    except:
        print(f'🌐 [Lang] Detection failed, using default: {CURRENT_LANG}')

def save_language_config(lang_code):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, 'config.json')
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            pass
    data['language'] = lang_code
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f'❌ [Lang] Save failed: {e}')
        return False

def tr(key):
    lang_dict = TRANS.get(CURRENT_LANG, TRANS[DEFAULT_LANG])
    return lang_dict.get(key, key)
load_language_config()
