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