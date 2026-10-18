"""One fail-closed read-only observer, independent of request scheduling."""
import threading
import time


_active = set()
_active_lock = threading.Lock()

def quiesce(root, timeout=35):
    """No lifecycle snapshot may race an observer creating owned clients."""
    with _active_lock:
        observers = [item for item in _active if item.owner_root == str(root)]
    for item in observers:
        item.cancel()
    deadline = time.monotonic() + timeout
    for item in observers:
        item.thread.join(timeout=max(0, deadline - time.monotonic()))
    with _active_lock:
        for item in observers:
            if not item.thread.is_alive():
                _active.discard(item)
    return not any(item.thread.is_alive() for item in observers)


class Observer:
    # Refresh within five seconds, leaving headroom for a nonzero check duration.
    interval = 2.5
    max_age = 5.0

    def __init__(self, check):
        self.check = check
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.completed = None
        self.failed = False
        self.rows = []
        self.thread = threading.Thread(target=self._observe, daemon=True)
        self.owner_root = getattr(check, 'owner_root', None)

    def _observe(self):
        while not self.stop.is_set():
            started = time.monotonic()
            error_type = None
            try:
                healthy = bool(self.check())
            except Exception as error:
                healthy = False
                error_type = type(error).__name__[:80]
            finished = time.monotonic()
            with self.lock:
                self.rows.append(dict(started=started, finished=finished,
                                      seconds=finished - started, healthy=healthy,
                                      error_type=error_type))
                self.failed |= not healthy
                if healthy:
                    self.completed = finished
            self.ready.set()
            if not healthy:
                return
            self.stop.wait(max(0, self.interval - (finished - started)))

    def start(self):
        if self.owner_root is not None:
            with _active_lock:
                _active.add(self)
        self.thread.start()
        return self.ready.wait(self.max_age) and self.valid()

    def valid(self):
        with self.lock:
            return (not self.failed and self.completed is not None
                    and time.monotonic() - self.completed <= self.max_age)

    def cancel(self):
        self.stop.set()
        cancel = getattr(self.check, 'cancel', None)
        if cancel is not None:
            cancel()

    def close(self):
        self.cancel()
        self.thread.join(timeout=.1)
        if not self.thread.is_alive():
            with _active_lock:
                _active.discard(self)
            return True
        return False

    def evidence(self):
        with self.lock:
            return [dict(row) for row in self.rows]


class RequestPool:
    """Bounded caller drain; survivors remain visible to outer operator cleanup.

    Socket timeouts bound normal reads. A pathological peer or injected reader
    can exceed them; daemon workers let the owned operator retain the partial
    receipt and terminate its domain rather than hang at interpreter shutdown.
    """
    def __init__(self, max_workers=10):
        import queue
        self.tasks = queue.Queue()
        self.stop = threading.Event()
        self.threads = [threading.Thread(target=self._work, daemon=True)
                        for _ in range(max_workers)]
        for thread in self.threads:
            thread.start()

    def _work(self):
        import queue
        while not self.stop.is_set():
            try:
                future, function, args = self.tasks.get(timeout=.02)
            except queue.Empty:
                continue
            if self.stop.is_set():
                future.cancel()
                return
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(function(*args))
                except BaseException as error:
                    future.set_exception(error)

    def submit(self, function, *args):
        from concurrent.futures import Future
        future = Future()
        self.tasks.put((future, function, args))
        return future

    def shutdown(self):
        import queue
        self.stop.set()
        while True:
            try:
                future, _, _ = self.tasks.get_nowait()
                future.cancel()
            except queue.Empty:
                break
        deadline = time.monotonic() + .2
        for thread in self.threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        return not any(thread.is_alive() for thread in self.threads)
