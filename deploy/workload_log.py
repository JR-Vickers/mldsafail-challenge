"""Bound command logs without imposing file-size limits on command resources."""
import os
import selectors
import subprocess
import threading
import time


class OutputLimit(RuntimeError):
    pass


class LogPipe:
    def __init__(self, stream, limit):
        self.stream = stream
        self.limit = limit
        self.read_fd, self.write_fd = os.pipe()
        os.set_blocking(self.read_fd,False)
        self.stop = threading.Event()
        self.overflow = threading.Event()
        self.errors = []
        self.thread = threading.Thread(target=self.drain,daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def spawned(self):
        if self.write_fd is not None:
            os.close(self.write_fd)
            self.write_fd = None

    def drain(self):
        size = 0
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.read_fd,selectors.EVENT_READ)
                while not self.stop.is_set():
                    if not selector.select(.025):continue
                    try:data = os.read(self.read_fd,65536)
                    except BlockingIOError:continue
                    if not data:return
                    remaining = max(0,self.limit-size)
                    if len(data)>remaining:self.overflow.set()
                    self.stream.write(data[:remaining])
                    size += min(len(data),remaining)
        except BaseException as error:
            self.errors.append(error)
            self.overflow.set()

    def wait(self, process, timeout):
        self.spawned()
        deadline = time.monotonic()+timeout
        while True:
            if self.overflow.is_set():raise OutputLimit('command_log_limit')
            remaining = deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(process.args,timeout)
            try:
                process.wait(timeout=min(.025,remaining))
                return process.returncode
            except subprocess.TimeoutExpired:
                if time.monotonic()>=deadline:raise

    def __exit__(self, *args):
        self.spawned()
        self.thread.join(timeout=.25)
        self.stop.set()
        self.thread.join(timeout=.1)
        os.close(self.read_fd)
        self.stream.flush()
        os.fsync(self.stream.fileno())
        if self.thread.is_alive():raise RuntimeError('command_log_reader_unresolved')
        if self.errors:raise RuntimeError('command_log_reader_failed') from self.errors[0]
        if self.overflow.is_set() and args[0] is None:raise OutputLimit('command_log_limit')
