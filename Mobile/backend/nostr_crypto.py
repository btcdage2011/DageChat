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
import time
import base64
import hashlib
import binascii
from hashlib import sha256
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
import nacl.bindings
try:
    import coincurve
    HAS_COINCURVE = True
except ImportError:
    HAS_COINCURVE = False

class BIP340:
    p = 115792089237316195423570985008687907853269984665640564039457584007908834671663
    n = 115792089237316195423570985008687907852837564279074904382605163141518161494337
    G = (55066263022277343669578718895168534326250603453777594175500187360389116729240, 32670510020758816978083085130507043184471273380659243275938904335757337482424)

    @staticmethod
    def point_add(P1, P2):
        if P1 is None:
            return P2
        if P2 is None:
            return P1
        x1, y1 = P1
        x2, y2 = P2
        if x1 == x2 and y1 != y2:
            return None
        if x1 == x2:
            lam = 3 * x1 * x1 * pow(2 * y1, BIP340.p - 2, BIP340.p) % BIP340.p
        else:
            lam = (y2 - y1) * pow(x2 - x1, BIP340.p - 2, BIP340.p) % BIP340.p
        x3 = (lam * lam - x1 - x2) % BIP340.p
        y3 = (lam * (x1 - x3) - y1) % BIP340.p
        return (x3, y3)

    @staticmethod
    def point_mul(P, n):
        R = None
        for i in range(256):
            if n >> i & 1:
                R = BIP340.point_add(R, P)
            P = BIP340.point_add(P, P)
        return R

    @staticmethod
    def bytes_from_int(x):
        return x.to_bytes(32, byteorder='big')

    @staticmethod
    def int_from_bytes(b):
        return int.from_bytes(b, byteorder='big')

    @staticmethod
    def lift_x(x):
        if x >= BIP340.p:
            return None
        y_sq = (pow(x, 3, BIP340.p) + 7) % BIP340.p
        y = pow(y_sq, (BIP340.p + 1) // 4, BIP340.p)
        if pow(y, 2, BIP340.p) != y_sq:
            return None
        return (x, y if y % 2 == 0 else BIP340.p - y)

    @staticmethod
    def hash_sha256(b):
        return hashlib.sha256(b).digest()

    @staticmethod
    def tagged_hash(tag, msg):
        tag_hash = BIP340.hash_sha256(tag.encode())
        return BIP340.hash_sha256(tag_hash + tag_hash + msg)

    @staticmethod
    def sign(priv_key_bytes, msg_bytes, aux_rand):
        d0 = BIP340.int_from_bytes(priv_key_bytes)
        if not 1 <= d0 <= BIP340.n - 1:
            return None
        P = BIP340.point_mul(BIP340.G, d0)
        if P[1] % 2 != 0:
            d0 = BIP340.n - d0
        t = (d0 ^ BIP340.int_from_bytes(BIP340.tagged_hash('BIP0340/aux', aux_rand))).to_bytes(32, 'big')
        rand = BIP340.tagged_hash('BIP0340/nonce', t + BIP340.bytes_from_int(P[0]) + msg_bytes)
        k = BIP340.int_from_bytes(rand) % BIP340.n
        if k == 0:
            return None
        R = BIP340.point_mul(BIP340.G, k)
        if R[1] % 2 != 0:
            k = BIP340.n - k
        e = BIP340.int_from_bytes(BIP340.tagged_hash('BIP0340/challenge', BIP340.bytes_from_int(R[0]) + BIP340.bytes_from_int(P[0]) + msg_bytes)) % BIP340.n
        sig = BIP340.bytes_from_int(R[0]) + BIP340.bytes_from_int((k + e * d0) % BIP340.n)
        return sig

    @staticmethod
    def verify(pub_key_bytes, msg_bytes, sig_bytes):
        if len(pub_key_bytes) != 32 or len(sig_bytes) != 64:
            return False
        P = BIP340.lift_x(BIP340.int_from_bytes(pub_key_bytes))
        if P is None:
            return False
        r = BIP340.int_from_bytes(sig_bytes[:32])
        s = BIP340.int_from_bytes(sig_bytes[32:])
        if r >= BIP340.p or s >= BIP340.n:
            return False
        e = BIP340.int_from_bytes(BIP340.tagged_hash('BIP0340/challenge', sig_bytes[:32] + pub_key_bytes + msg_bytes)) % BIP340.n
        R = BIP340.point_add(BIP340.point_mul(BIP340.G, s), BIP340.point_mul(P, BIP340.n - e))
        return R is not None and R[1] % 2 == 0 and (R[0] == r)

class NostrCrypto:

    @staticmethod
    def generate_private_key_hex():
        while True:
            key_bytes = os.urandom(32)
            d = int.from_bytes(key_bytes, 'big')
            if 1 <= d < BIP340.n:
                P = BIP340.point_mul(BIP340.G, d)
                if P[1] % 2 == 0:
                    return key_bytes.hex()

    @staticmethod
    def get_public_key_hex(priv_hex):
        try:
            if HAS_COINCURVE:
                priv = coincurve.PrivateKey(bytes.fromhex(priv_hex))
                return priv.public_key.format(compressed=True)[1:].hex()
            else:
                priv_bytes = bytes.fromhex(priv_hex)
                d0 = BIP340.int_from_bytes(priv_bytes)
                P = BIP340.point_mul(BIP340.G, d0)
                return BIP340.bytes_from_int(P[0]).hex()
        except:
            return None

    @staticmethod
    def sign_event_id(priv_hex, event_id_hex):
        try:
            if not priv_hex or not event_id_hex:
                return None
            priv_bytes = bytes.fromhex(priv_hex)
            msg_bytes = bytes.fromhex(event_id_hex)
            aux_bytes = os.urandom(32)
            if HAS_COINCURVE:
                try:
                    priv = coincurve.PrivateKey(priv_bytes)
                    if hasattr(priv, 'schnorr_sign'):
                        return priv.schnorr_sign(msg_bytes, aux_bytes).hex()
                except:
                    pass
            sig = BIP340.sign(priv_bytes, msg_bytes, aux_bytes)
            if sig:
                return sig.hex()
            return None
        except Exception as e:
            print(f'❌ [Crypto] Sign Error: {e}')
            return None

    @staticmethod
    def verify_signature(pub_hex, event_id_hex, sig_hex):
        try:
            if not pub_hex or not event_id_hex or (not sig_hex):
                return False
            pub_bytes = bytes.fromhex(pub_hex)
            sig_bytes = bytes.fromhex(sig_hex)
            msg_bytes = bytes.fromhex(event_id_hex)
            if HAS_COINCURVE:
                try:
                    if coincurve.verify_schnorr(sig_bytes, msg_bytes, pub_bytes):
                        return True
                except:
                    pass
                try:
                    if coincurve.verify_schnorr(sig_bytes, msg_bytes, b'\x02' + pub_bytes):
                        return True
                except:
                    pass
            if BIP340.verify(pub_bytes, msg_bytes, sig_bytes):
                return True
            return False
        except:
            return False

    @staticmethod
    def _get_conversation_key(priv_hex, pub_hex):
        try:
            priv_bytes = bytes.fromhex(priv_hex)
            shared_point_bytes = None
            if HAS_COINCURVE:
                priv = coincurve.PrivateKey(priv_bytes)
                clean_pub = pub_hex[-64:]
                pk_bytes = bytes.fromhex('02' + clean_pub)
                pub = coincurve.PublicKey(pk_bytes)
                shared_point_bytes = priv.ecdh(pub.format())
            else:
                clean_pub = pub_hex[-64:]
                x = int(clean_pub, 16)
                P = BIP340.lift_x(x)
                if P is None:
                    return None
                d = BIP340.int_from_bytes(priv_bytes)
                S = BIP340.point_mul(P, d)
                if S is None:
                    return None
                prefix = b'\x02' if S[1] % 2 == 0 else b'\x03'
                compressed_point = prefix + BIP340.bytes_from_int(S[0])
                shared_point_bytes = hashlib.sha256(compressed_point).digest()
            if not shared_point_bytes:
                return None
            hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b'nip44-v2', info=b'', backend=default_backend())
            return hkdf.derive(shared_point_bytes)
        except Exception as e:
            print(f'ECDH Error: {e}')
            return None

    @staticmethod
    def encrypt_nip44(priv_hex, pub_hex, plaintext):
        try:
            key = NostrCrypto._get_conversation_key(priv_hex, pub_hex)
            if not key:
                return None
            version = b'\x02'
            nonce = os.urandom(24)
            data = plaintext.encode('utf-8')
            ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(data, None, nonce, key)
            payload = version + nonce + ciphertext
            return base64.b64encode(payload).decode('utf-8')
        except Exception as e:
            print(f'Encrypt NIP44 error: {e}')
            return None

    @staticmethod
    def decrypt_nip44(priv_hex, pub_hex, payload_b64):
        try:
            key = NostrCrypto._get_conversation_key(priv_hex, pub_hex)
            if not key:
                return None
            raw = base64.b64decode(payload_b64)
            if len(raw) < 41:
                return None
            if raw[0] != 2:
                return None
            nonce = raw[1:25]
            ciphertext = raw[25:]
            plaintext_bytes = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, nonce, key)
            return plaintext_bytes.decode('utf-8')
        except:
            return None

    @staticmethod
    def make_gift_wrap(sender_priv, receiver_pub, data_json, kind=14, extra_tags=None):
        try:
            now = int(time.time())
            sender_pub = NostrCrypto.get_public_key_hex(sender_priv)
            rumor_tags = extra_tags if extra_tags else []
            rumor = {'id': '', 'pubkey': sender_pub, 'created_at': now, 'kind': kind, 'tags': rumor_tags, 'content': data_json}
            rumor_str = json.dumps([0, rumor['pubkey'], rumor['created_at'], rumor['kind'], rumor['tags'], rumor['content']], separators=(',', ':'), ensure_ascii=False)
            rumor_id = sha256(rumor_str.encode('utf-8')).hexdigest()
            rumor['id'] = rumor_id
            rumor_json = json.dumps(rumor, separators=(',', ':'), ensure_ascii=False)
            sealed_content = NostrCrypto.encrypt_nip44(sender_priv, receiver_pub, rumor_json)
            if not sealed_content:
                return (None, None)
            seal = {'pubkey': sender_pub, 'created_at': now, 'kind': 13, 'tags': [], 'content': sealed_content}
            seal_str = json.dumps([0, seal['pubkey'], seal['created_at'], seal['kind'], seal['tags'], seal['content']], separators=(',', ':'), ensure_ascii=False)
            seal['id'] = sha256(seal_str.encode('utf-8')).hexdigest()
            seal['sig'] = NostrCrypto.sign_event_id(sender_priv, seal['id'])
            if not seal['sig']:
                return (None, None)
            ephemeral_priv = NostrCrypto.generate_private_key_hex()
            ephemeral_pub = NostrCrypto.get_public_key_hex(ephemeral_priv)
            seal_json = json.dumps(seal, separators=(',', ':'), ensure_ascii=False)
            wrapped_content = NostrCrypto.encrypt_nip44(ephemeral_priv, receiver_pub, seal_json)
            if not wrapped_content:
                return (None, None)
            wrap_event = {'pubkey': ephemeral_pub, 'created_at': now, 'kind': 1059, 'tags': [['p', receiver_pub]], 'content': wrapped_content}
            wrap_str = json.dumps([0, wrap_event['pubkey'], wrap_event['created_at'], wrap_event['kind'], wrap_event['tags'], wrap_event['content']], separators=(',', ':'), ensure_ascii=False)
            wrap_event['id'] = sha256(wrap_str.encode('utf-8')).hexdigest()
            wrap_event['sig'] = NostrCrypto.sign_event_id(ephemeral_priv, wrap_event['id'])
            if not wrap_event['sig']:
                return (None, None)
            return (wrap_event, rumor_id)
        except Exception as e:
            print(f'❌ [Crypto] GiftWrap Error: {e}')
            return (None, None)

    @staticmethod
    def unwrap_gift(my_priv, wrap_event):
        try:
            if wrap_event['kind'] != 1059:
                return (None, None)
            ephemeral_pub = wrap_event['pubkey']
            seal_json_str = NostrCrypto.decrypt_nip44(my_priv, ephemeral_pub, wrap_event['content'])
            if not seal_json_str:
                return (None, None)
            seal_event = json.loads(seal_json_str)
            if not NostrCrypto.verify_signature(seal_event['pubkey'], seal_event['id'], seal_event.get('sig')):
                return (None, None)
            real_sender_pub = seal_event['pubkey']
            rumor_json_str = NostrCrypto.decrypt_nip44(my_priv, real_sender_pub, seal_event['content'])
            if not rumor_json_str:
                return (None, None)
            rumor = json.loads(rumor_json_str)
            return (real_sender_pub, rumor)
        except:
            return (None, None)

    @staticmethod
    def generate_group_key():
        return os.urandom(32).hex()

    @staticmethod
    def encrypt_group_msg(key_hex, plain_text):
        try:
            key = bytes.fromhex(key_hex)
            version = b'\x02'
            nonce = os.urandom(24)
            data = plain_text.encode('utf-8')
            ciphertext = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(data, None, nonce, key)
            return base64.b64encode(version + nonce + ciphertext).decode('utf-8')
        except:
            return None

    @staticmethod
    def decrypt_group_msg(key_hex, b64_content):
        try:
            key = bytes.fromhex(key_hex)
            raw = base64.b64decode(b64_content)
            if len(raw) < 41:
                return None
            if raw[0] != 2:
                return None
            nonce = raw[1:25]
            ciphertext = raw[25:]
            plaintext_bytes = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(ciphertext, None, nonce, key)
            return plaintext_bytes.decode('utf-8')
        except:
            return None

    @staticmethod
    def mine_pow_and_sign(priv_hex, kind, content, tags, difficulty):
        try:
            pub_key = NostrCrypto.get_public_key_hex(priv_hex)
            created_at = int(time.time())
            target = 1 << 256 - difficulty
            nonce = 0
            current_tags = [t for t in tags if t[0] != 'nonce']
            current_tags.append(['nonce', str(nonce), str(difficulty)])
            while True:
                if nonce % 100 == 0:
                    time.sleep(0)
                current_tags[-1][1] = str(nonce)
                event_data = [0, pub_key, created_at, kind, current_tags, content]
                json_str = json.dumps(event_data, separators=(',', ':'), ensure_ascii=False)
                event_id_bytes = hashlib.sha256(json_str.encode('utf-8')).digest()
                event_id_int = int.from_bytes(event_id_bytes, 'big')
                if event_id_int < target:
                    event_id_hex = event_id_bytes.hex()
                    sig = NostrCrypto.sign_event_id(priv_hex, event_id_hex)
                    return {'id': event_id_hex, 'pubkey': pub_key, 'created_at': created_at, 'kind': kind, 'tags': current_tags, 'content': content, 'sig': sig}
                nonce += 1
        except Exception as e:
            print(f'❌ [Crypto] Mining Error: {e}')
            return None

    @staticmethod
    def derive_backup_key(priv_hex, salt):
        try:
            ikm = bytes.fromhex(priv_hex)
            info = b'DageChat-Backup-Encryption-v1'
            hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info, backend=default_backend())
            return hkdf.derive(ikm)
        except Exception as e:
            print(f'❌ [Crypto] Key Derivation Error: {e}')
            return None

    @staticmethod
    def sign_backup_header(priv_hex, salt, nonce, pubkey_bytes):
        try:
            payload = salt + nonce + pubkey_bytes
            msg_hash = hashlib.sha256(payload).digest()
            msg_hex = msg_hash.hex()
            return NostrCrypto.sign_event_id(priv_hex, msg_hex)
        except Exception as e:
            print(f'❌ [Crypto] Backup Sign Error: {e}')
            return None

    @staticmethod
    def verify_backup_header(pub_hex, salt, nonce, sig_hex):
        try:
            pub_bytes = bytes.fromhex(pub_hex)
            payload = salt + nonce + pub_bytes
            msg_hash = hashlib.sha256(payload).digest()
            msg_hex = msg_hash.hex()
            return NostrCrypto.verify_signature(pub_hex, msg_hex, sig_hex)
        except:
            return False