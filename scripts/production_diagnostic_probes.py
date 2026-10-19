"""Bounded HTTP comparison and exact-source legacy scheduler instrumentation."""
from concurrent.futures import wait
import hashlib
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

from scripts.read_load_observer import Observer, RequestPool


def request_comparison(server, token, health, publish, *, request_open=None,
                       duration=60, count=120, read_only_health=False):
    """Alternating readiness/authentication, absolute deadlines, ten threads.

    Shorter schedules are allowed only for engineering tests; native admission
    must bind duration=60/count=120. publish must durably write each snapshot.
    """
    if read_only_health is not True:
        raise ValueError('Read-only asynchronous health callback review required')
    if duration <= 0 or count <= 0 or count % 2 or duration > 60 or count > 120:
        raise ValueError('Bounded paired comparison required')
    opener = request_open or urllib.request.urlopen
    observer = Observer(health)
    pool = RequestPool(max_workers=10)
    records, submitted, futures = {}, [], []
    lock = threading.Lock()
    publication_lock = threading.Lock()
    closed = threading.Event()
    publication_failed = threading.Event()
    started = time.monotonic()
    healthy = False
    pacing = True
    pending = set()
    def snapshot():
        with lock:
            rows = [dict(records.get(row['request_id'], dict(row, incomplete=True))) for row in submitted]
        return rows
    def emit():
        try:
            with publication_lock:
                publish(snapshot())
        except Exception:
            publication_failed.set()
    def read(row):
        begin = time.monotonic()
        completed = dict(row, started_after_seconds=begin-started,
            queue_delay_seconds=begin-started-row['dispatched_after_seconds'])
        request = urllib.request.Request(server.rstrip('/') + row['route'],
            headers={'Authorization': 'Bearer ' + token} if row['route'] == '/api/v1/me' else {})
        try:
            with opener(request, timeout=2) as response:
                response.read(1024*1024)
                completed.update(status=response.status, failed=response.status != 200)
                correlation = response.headers.get('X-Diagnostic-ID')
                import re
                if isinstance(correlation, str) and re.fullmatch('[a-f0-9]{32}', correlation):
                    completed['correlation_id'] = correlation
        except Exception as error:
            completed.update(failed=True, error_type=type(error).__name__[:80])
            if isinstance(error, urllib.error.HTTPError):
                completed['status'] = error.code
        completed.update(seconds=time.monotonic()-begin, finished_after_seconds=time.monotonic()-started)
        with lock:
            if closed.is_set():
                return
            records[row['request_id']] = completed
        emit()
    try:
        healthy = observer.start()
        started = time.monotonic()
        for index in range(count):
            target = started + index * duration / count
            while healthy and time.monotonic() < target:
                healthy = observer.valid() and not publication_failed.is_set()
                time.sleep(min(.02, max(0, target-time.monotonic())))
            healthy = healthy and observer.valid() and not publication_failed.is_set()
            if not healthy:
                break
            dispatched = time.monotonic()
            if dispatched-target > .1:
                pacing = False
                break
            row = dict(request_id=index, route='/api/v1/me' if index % 2 else '/health/ready',
                scheduled_after_seconds=target-started, intent_after_seconds=dispatched-started)
            with lock:
                submitted.append(row)
            emit()
            healthy = observer.valid() and not publication_failed.is_set()
            dispatched = time.monotonic()
            if not healthy:
                break
            if dispatched-target > .1:
                pacing = False
                break
            with lock:
                row['dispatched_after_seconds'] = dispatched-started
            futures.append(pool.submit(read, row))
        end = started + duration
        while healthy and pacing and time.monotonic() < end:
            healthy = observer.valid() and not publication_failed.is_set()
            time.sleep(min(.02, max(0, end-time.monotonic())))
        pending = set(futures)
        deadline = time.monotonic()+5
        while pending and time.monotonic() < deadline:
            healthy = healthy and observer.valid() and not publication_failed.is_set()
            _, pending = wait(pending, timeout=min(.02, max(0, deadline-time.monotonic())))
    finally:
        workers_stopped = pool.shutdown()
        observer_stopped = observer.close()
        with lock:
            closed.set()
        emit()
    return dict(complete=(healthy and pacing and workers_stopped and observer_stopped
            and len(records) == count and not publication_failed.is_set()),
        requests=snapshot(), observation_valid=healthy, pacing_valid=pacing,
        termination_complete=workers_stopped and observer_stopped and not pending,
        evidence_complete=not publication_failed.is_set(), expected_requests=count,
        undispatched_requests=count-len(futures), elapsed_seconds=time.monotonic()-started)


def legacy_module(path, expected_sha256):
    """Load the frozen legacy source bytes; never reconstruct its scheduler."""
    path = Path(path)
    if path.is_symlink() or not path.is_absolute():
        raise ValueError('Actual frozen legacy source required')
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != expected_sha256:
        raise ValueError('Actual frozen legacy source required')
    # Compile checked bytes directly, avoiding an unbound stale pyc file.
    import types
    module = types.ModuleType('diagnostic_frozen_legacy')
    module.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def legacy_experiment(path, expected_sha256, server, token, health, publish, *, duration=60):
    """Instrument the actual legacy module's executor; run in an owned process.

    The outer native controller must enforce the 600-second process ceiling and
    cancel its owned clients before cleanup. Legacy executor draining is retained
    unchanged here, so this function alone does not grant native admission.
    """
    from concurrent.futures import ThreadPoolExecutor
    legacy = legacy_module(path, expected_sha256)
    started = time.monotonic()
    rows, checks = [], []
    lock = threading.Lock()
    publication_lock = threading.Lock()
    current = threading.local()
    publication_failed = threading.Event()
    def emit():
        with publication_lock:
            with lock:
                report = dict(source_sha256=expected_sha256, nominal_seconds=duration,
                    elapsed_seconds=time.monotonic()-started,
                    requests=[dict(row) for row in rows], observations=[dict(row) for row in checks])
            try:
                publish(report)
            except Exception:
                publication_failed.set()
    class Clock:
        first = True
        def monotonic(self):
            nonlocal started
            value = time.monotonic()
            if self.first:
                started = value
                self.first = False
            return value
        sleep = staticmethod(time.sleep)
    legacy.time = Clock()
    def opener(request, timeout):
        row = current.row
        row['http_started_after_seconds'] = time.monotonic()-started
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except Exception as error:
            row.update(http_finished_after_seconds=time.monotonic()-started,
                       error_type=type(error).__name__[:80])
            raise
        class Response:
            status = response.status
            def __enter__(self):
                response.__enter__()
                return self
            def read(self, *args):
                return response.read(*args)
            def __exit__(self, *args):
                try:
                    return response.__exit__(*args)
                finally:
                    row['http_finished_after_seconds'] = time.monotonic()-started
        return Response()
    class Executor(ThreadPoolExecutor):
        def submit(self, fn, *args, **kwargs):
            with lock:
                index = len(rows)
                # The exact source emits one extra auth request every 25 ticks.
                tick = index - (index + 25) // 26
                tick = max(0, tick)
                row = dict(request_id=index, route=args[0], scheduled_after_seconds=tick/5,
                    dispatched_after_seconds=time.monotonic()-started, incomplete=True)
                rows.append(row)
            emit()
            def invoke():
                begin = time.monotonic()
                with lock:
                    row.update(started_after_seconds=begin-started,
                               queue_delay_seconds=begin-started-row['dispatched_after_seconds'])
                current.row = row
                try:
                    return fn(*args, **kwargs)
                finally:
                    with lock:
                        row.update(finished_after_seconds=time.monotonic()-started, incomplete=False)
                    emit()
            return super().submit(invoke)
    legacy.ThreadPoolExecutor = Executor
    def observed():
        begin = time.monotonic()
        healthy = False
        try:
            healthy = bool(health())
            return healthy
        finally:
            with lock:
                checks.append(dict(started_after_seconds=begin-started, seconds=time.monotonic()-begin, healthy=healthy))
            emit()
    result = legacy.run(server, token, observed, duration=duration, request_open=opener)
    emit()
    return dict(result=result, instrumentation_complete=not publication_failed.is_set(),
                source_sha256=expected_sha256, elapsed_seconds=time.monotonic()-started)
