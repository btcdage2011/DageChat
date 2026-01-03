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