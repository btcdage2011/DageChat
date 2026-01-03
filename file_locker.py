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
import sys
if sys.platform == 'win32':
    import msvcrt

    class FileLock:

        def __init__(self, file_path):
            self.file_path = file_path
            self.fd = None

        def acquire(self):
            try:
                self.fd = open(self.file_path, 'w')
                msvcrt.locking(self.fd.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except (IOError, PermissionError):
                if self.fd:
                    self.fd.close()
                    self.fd = None
                return False

        def release(self):
            if self.fd:
                try:
                    self.fd.seek(0)
                    msvcrt.locking(self.fd.fileno(), msvcrt.LK_UNLCK, 1)
                except:
                    pass
                try:
                    self.fd.close()
                except:
                    pass
                self.fd = None
else:
    import fcntl

    class FileLock:

        def __init__(self, file_path):
            self.file_path = file_path
            self.fd = None

        def acquire(self):
            try:
                self.fd = open(self.file_path, 'w')
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, BlockingIOError):
                if self.fd:
                    self.fd.close()
                    self.fd = None
                return False

        def release(self):
            if self.fd:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                except:
                    pass
                self.fd.close()
                self.fd = None
