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
import zlib
import time
import threading
import struct
import shutil
import nacl.utils
import nacl.bindings
from nostr_crypto import NostrCrypto
from lang_utils import tr

class BackupManager:
    MAGIC = b'DGBK'
    VERSION = b'\x01'

    def __init__(self, client):
        self.client = client
        self.cancel_event = threading.Event()

    def _derive_key(self, salt):
        return NostrCrypto.derive_backup_key(self.client.priv_k, salt)

    def run_backup(self, filepath, target_gid, progress_cb, include_messages=True):
        temp_file = filepath + '.tmp'
        try:
            self.cancel_event.clear()
            progress_cb(0, tr('BKP_STEP_PREPARE'))
            raw_data = self.client.db.get_backup_data(target_gid, include_messages=include_messages)
            count_msg = len(raw_data.get('messages', []))
            count_contact = len(raw_data.get('contacts', []))
            if self.cancel_event.is_set():
                raise InterruptedError
            progress_cb(20, tr('BKP_STEP_SERIALIZE'))
            json_bytes = json.dumps(raw_data).encode('utf-8')
            del raw_data
            if self.cancel_event.is_set():
                raise InterruptedError
            progress_cb(40, tr('BKP_STEP_COMPRESS'))
            compressed_data = zlib.compress(json_bytes, level=6)
            del json_bytes
            if self.cancel_event.is_set():
                raise InterruptedError
            progress_cb(60, tr('BKP_STEP_ENCRYPT'))
            salt = nacl.utils.random(16)
            nonce = nacl.utils.random(24)
            pub_bytes = bytes.fromhex(self.client.pk)
            sig_hex = NostrCrypto.sign_backup_header(self.client.priv_k, salt, nonce, pub_bytes)
            if not sig_hex:
                raise Exception('Sign failed')
            sig_bytes = bytes.fromhex(sig_hex)
            key = NostrCrypto.derive_backup_key(self.client.priv_k, salt)
            encrypted_data = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(compressed_data, None, nonce, key)
            del compressed_data
            if self.cancel_event.is_set():
                raise InterruptedError
            progress_cb(80, tr('BKP_STEP_WRITE'))
            with open(temp_file, 'wb') as f:
                f.write(self.MAGIC)
                f.write(self.VERSION)
                f.write(salt)
                f.write(nonce)
                f.write(pub_bytes)
                f.write(sig_bytes)
                f.write(encrypted_data)
            if os.path.exists(filepath):
                os.remove(filepath)
            os.rename(temp_file, filepath)
            progress_cb(100, 'Done!')
            success_msg = f"{tr('BKP_SUCCESS')}\n(Msg: {count_msg}, Contact: {count_contact})"
            return (True, success_msg)
        except InterruptedError:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return (False, tr('BKP_CANCEL'))
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            import traceback
            traceback.print_exc()
            return (False, f'Error: {e}')

    def run_restore(self, filepath, progress_cb):
        try:
            self.cancel_event.clear()
            progress_cb(0, tr('RST_STEP_READ'))
            if not os.path.exists(filepath):
                return (False, tr('ERR_FILE_NOT_FOUND'))
            with open(filepath, 'rb') as f:
                magic = f.read(4)
                if magic != self.MAGIC:
                    return (False, tr('ERR_INVALID_FORMAT'))
                ver = f.read(1)
                salt = f.read(16)
                nonce = f.read(24)
                pub_bytes = f.read(32)
                sig_bytes = f.read(64)
                file_pub_hex = pub_bytes.hex()
                sig_hex = sig_bytes.hex()
                if file_pub_hex != self.client.pk:
                    return (False, tr('ERR_IDENTITY_MISMATCH'))
                if not NostrCrypto.verify_backup_header(file_pub_hex, salt, nonce, sig_hex):
                    return (False, tr('ERR_SIG_FAILED'))
                progress_cb(20, tr('RST_STEP_DECRYPT'))
                key = NostrCrypto.derive_backup_key(self.client.priv_k, salt)
                encrypted_body = f.read()
                try:
                    compressed_data = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(encrypted_body, None, nonce, key)
                except:
                    return (False, tr('ERR_DECRYPT_FAILED'))
                del encrypted_body
                if self.cancel_event.is_set():
                    raise InterruptedError
                progress_cb(40, tr('RST_STEP_DECOMPRESS'))
                json_bytes = zlib.decompress(compressed_data)
                del compressed_data
                data_dict = json.loads(json_bytes)
                del json_bytes
                progress_cb(50, tr('RST_STEP_DB'))

                def _db_prog_cb(curr, total, txt):
                    if total > 0:
                        p = 50 + int(curr / total * 50)
                        progress_cb(p, f'{txt} ({curr}/{total})')
                success, result = self.client.db.restore_data_incremental(data_dict, progress_callback=_db_prog_cb, cancel_event=self.cancel_event)
                if success:
                    lines = [tr('RST_SUMMARY_HEAD')]
                    key_map = {'Messages': 'TYPE_MSG', 'Contacts': 'TYPE_CONTACT', 'Groups': 'TYPE_GROUP', 'Members': 'TYPE_MEMBER'}
                    for db_key, trans_key in key_map.items():
                        if db_key in result:
                            info = result[db_key]
                            total = info['total']
                            new = info['inserted']
                            skipped = total - new
                            if total > 0:
                                line = tr('RST_SUMMARY_ITEM').format(type=tr(trans_key), new=new, total=total, skip=skipped)
                                lines.append(line)
                    final_msg = '\n'.join(lines)
                    return (True, final_msg)
                else:
                    if 'Cancelled' in str(result):
                        return (False, tr('RST_CANCEL'))
                    return (False, str(result))
        except InterruptedError:
            return (False, tr('RST_CANCEL'))
        except Exception as e:
            import traceback
            traceback.print_exc()
            return (False, f'Error: {e}')

    def cancel(self):
        self.cancel_event.set()