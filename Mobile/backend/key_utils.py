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

import binascii
CHARSET = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'

def bech32_decode(bech):
    if any((ord(x) < 33 or ord(x) > 126 for x in bech)) or (bech.lower() != bech and bech.upper() != bech):
        return (None, None)
    bech = bech.lower()
    pos = bech.rfind('1')
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        return (None, None)
    if not all((x in CHARSET for x in bech[pos + 1:])):
        return (None, None)
    hrp = bech[:pos]
    data = [CHARSET.find(x) for x in bech[pos + 1:]]
    if not bech32_verify_checksum(hrp, data):
        return (None, None)
    return (hrp, data[:-6])

def bech32_verify_checksum(hrp, data):
    return bech32_polymod(bech32_hrp_expand(hrp) + data) == 1

def bech32_polymod(values):
    GEN = [996825010, 642813549, 513874426, 1027748829, 705979059]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 33554431) << 5 ^ v
        for i in range(5):
            chk ^= GEN[i] if b >> i & 1 else 0
    return chk

def bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

def convertbits(data, frombits, tobits, pad=True):
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << frombits + tobits - 1) - 1
    for value in data:
        if value < 0 or value >> frombits:
            return None
        acc = (acc << frombits | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append(acc >> bits & maxv)
    if pad:
        if bits:
            ret.append(acc << tobits - bits & maxv)
    elif bits >= frombits or acc << tobits - bits & maxv:
        return None
    return ret

def bech32_create_checksum(hrp, data):
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [polymod >> 5 * (5 - i) & 31 for i in range(6)]

def bech32_encode(hrp, data):
    combined = data + bech32_create_checksum(hrp, data)
    return hrp + '1' + ''.join([CHARSET[d] for d in combined])

def to_hex_pubkey(input_str):
    if not input_str:
        return None
    s = input_str.strip()
    if len(s) == 64:
        try:
            int(s, 16)
            return s.lower()
        except:
            pass
    if s.startswith('npub1'):
        hrp, data = bech32_decode(s)
        if hrp == 'npub' and data:
            decoded = convertbits(data, 5, 8, False)
            if decoded:
                return binascii.hexlify(bytearray(decoded)).decode('utf-8')
    return None

def to_hex_privkey(input_str):
    if not input_str:
        return None
    s = input_str.strip()
    if len(s) == 64:
        try:
            int(s, 16)
            return s.lower()
        except:
            pass
    if s.startswith('nsec1'):
        hrp, data = bech32_decode(s)
        if hrp == 'nsec' and data:
            decoded = convertbits(data, 5, 8, False)
            if decoded:
                return binascii.hexlify(bytearray(decoded)).decode('utf-8')
    return None

def to_npub(hex_str):
    if not hex_str or len(hex_str) != 64:
        return hex_str
    try:
        raw_bytes = binascii.unhexlify(hex_str)
        data5 = convertbits(raw_bytes, 8, 5, True)
        return bech32_encode('npub', data5)
    except:
        return hex_str

def to_nsec(hex_str):
    if not hex_str or len(hex_str) != 64:
        return hex_str
    try:
        raw_bytes = binascii.unhexlify(hex_str)
        data5 = convertbits(raw_bytes, 8, 5, True)
        return bech32_encode('nsec', data5)
    except:
        return hex_str

def get_npub_abbr(hex_str):
    full_npub = to_npub(hex_str)
    if not full_npub:
        return '???'
    if len(full_npub) > 16:
        return f'{full_npub[:10]}...{full_npub[-6:]}'
    return full_npub