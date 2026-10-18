from concurrent.futures import Future
import json
import threading
import time
import urllib.error

import pytest

from scripts import staging_read_load
from scripts.read_load_observer import Observer, RequestPool


class Response:
    status = 200
    def read(self, limit): return b'ok'
    def __enter__(self): return self
    def __exit__(self, *args): pass


@pytest.fixture
def scheduled(monkeypatch):
    now = [0.0]
    class Healthy:
        def __init__(self, check): self.check = check
        def start(self): return bool(self.check())
        def valid(self): return True
        def close(self): return True
        def evidence(self): return []
    class InlinePool:
        def __init__(self, **kwargs): assert kwargs == dict(max_workers=10)
        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future
        def shutdown(self): return True
    monkeypatch.setattr(staging_read_load, 'Observer', Healthy)
    monkeypatch.setattr(staging_read_load, 'RequestPool', InlinePool)
    monkeypatch.setattr(staging_read_load.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(staging_read_load.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now, Healthy


@pytest.mark.parametrize('failure', [TimeoutError('secret-token'),
    urllib.error.HTTPError('https://secret-host/', 503, 'secret-message', {}, None)])
def test_failed_read_diagnostics_are_bounded_and_private(scheduled, failure):
    rows = []
    def request_open(request, timeout):
        assert timeout == 2
        raise failure
    result = staging_read_load.run('http://secret-host', 'secret-token', lambda: True, read_only_health=True,
                                   duration=.2, progress=rows.append, request_open=request_open)
    assert result['requests'] == result['read_failures'] == 2
    assert not result['passed'] and result['elapsed_seconds'] >= .2
    for row in rows:
        assert row['failed'] and row['error_type'] == type(failure).__name__
        assert row['http_status'] == (503 if isinstance(failure, urllib.error.HTTPError) else None)
        assert row['finished_after_seconds'] >= row['started_after_seconds'] >= 0
        assert row['seconds'] == pytest.approx(row['finished_after_seconds'] - row['started_after_seconds'])
    assert 'secret' not in json.dumps(dict(result=result, rows=rows))


def test_full_schedule_and_original_thresholds(scheduled):
    rows = []
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        progress=rows.append, request_open=lambda *a, **k: Response())
    assert result['passed'] and result['requests'] == 1560
    assert result['elapsed_seconds'] == pytest.approx(300)
    assert sum(row['route'] == '/api/v1/me' for row in rows) == 60
    assert all(row['queue_delay_seconds'] == 0 for row in rows)
    assert result['pacing_valid'] and result['observation_valid']


def test_deadline_miss_stops_without_catchup(scheduled, monkeypatch):
    now, _ = scheduled
    def oversleep(seconds): now[0] += seconds + .4
    monkeypatch.setattr(staging_read_load.time, 'sleep', oversleep)
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        duration=1, request_open=lambda *a, **k: Response())
    assert not result['passed'] and not result['pacing_valid']
    assert result['requests'] == 2 and result['undispatched_requests'] == 4
    assert result['max_scheduling_lag_seconds'] > .1


@pytest.mark.parametrize('valid', [False, True])
def test_initial_check_and_stale_observation_stop_dispatch(scheduled, valid):
    now, healthy = scheduled
    healthy.start = lambda self: valid
    healthy.valid = lambda self: now[0] < .5
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        duration=1, request_open=lambda *a, **k: Response())
    assert not result['passed'] and not result['observation_valid']
    assert result['host_floor_violations'] == 1
    assert result['requests'] == (4 if valid else 0)


def test_queue_delay_is_separate_from_latency(scheduled, monkeypatch):
    now, _ = scheduled
    class DelayedPool:
        def __init__(self, **kwargs): pass
        def submit(self, function, *args):
            now[0] += .03
            future = Future(); future.set_result(function(*args)); return future
        def shutdown(self): return True
    monkeypatch.setattr(staging_read_load, 'RequestPool', DelayedPool)
    rows = []
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        duration=.2, progress=rows.append, request_open=lambda *a, **k: Response())
    assert result['passed']
    assert all(row['queue_delay_seconds'] > 0 and row['seconds'] == 0 for row in rows)


@pytest.mark.parametrize('check', [lambda: False, lambda: (_ for _ in ()).throw(ValueError('secret'))])
def test_failed_observer_is_unhealthy_and_sanitized(check):
    observer = Observer(check)
    assert not observer.start()
    assert not observer.valid() and observer.close()
    assert 'secret' not in json.dumps(observer.evidence())
    assert observer.evidence()[0]['healthy'] is False


def test_slow_observer_initial_timeout_and_bounded_close():
    release = threading.Event()
    observer = Observer(lambda: release.wait(1))
    observer.max_age = .01
    started = time.monotonic()
    try:
        assert not observer.start()
        assert not observer.close()
        assert time.monotonic() - started < .5
    finally:
        release.set(); observer.thread.join(1)


def test_complete_observation_becomes_stale():
    observer = Observer(lambda: True)
    assert observer.start()
    with observer.lock:
        observer.completed = time.monotonic() - 6
    assert not observer.valid()
    assert observer.close()


def test_pending_reads_are_retained_and_termination_is_bounded(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(staging_read_load, 'DRAIN_SECONDS', .01)
    def blocked(*args, **kwargs):
        release.wait(2)
        return Response()
    started = time.monotonic()
    rows = []
    try:
        result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
            duration=.2, progress=rows.append, request_open=blocked)
        assert time.monotonic() - started < 1
        assert not result['passed'] and not result['termination_complete']
        assert result['incomplete_requests'] == 2
        assert all(row['incomplete'] for row in rows)
    finally:
        release.set()


def test_request_pool_shutdown_cancels_queued_requests():
    release = threading.Event()
    pool = RequestPool(max_workers=1)
    running = threading.Event()
    def blocked(): running.set(); release.wait(1)
    first = pool.submit(blocked)
    assert running.wait(1)
    queued = pool.submit(lambda: pytest.fail('Cancelled request executed'))
    try:
        assert not pool.shutdown()
        assert queued.cancelled()
    finally:
        release.set()
        pool.threads[0].join(1)
    assert first.done()


def test_second_paired_dispatch_cannot_hide_a_deadline_miss(scheduled, monkeypatch):
    now, _ = scheduled
    class SlowSubmit:
        def __init__(self, **kwargs): pass
        def submit(self, function, *args):
            future = Future(); future.set_result(function(*args))
            now[0] += .11
            return future
        def shutdown(self): return True
    monkeypatch.setattr(staging_read_load, 'RequestPool', SlowSubmit)
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        duration=.2, request_open=lambda *a, **k: Response())
    assert not result['pacing_valid'] and not result['passed']
    assert result['dispatched_requests'] == 1


def test_owner_quiescence_cancels_and_joins_before_cleanup(tmp_path):
    from scripts.read_load_observer import quiesce
    entered, release = threading.Event(), threading.Event()
    def check(): entered.set(); return release.wait(2)
    check.owner_root = str(tmp_path)
    check.cancel = release.set
    observer = Observer(check)
    observer.max_age = .01
    assert not observer.start() and entered.is_set()
    assert quiesce(tmp_path, timeout=1)
    assert not observer.thread.is_alive()
    assert observer.close()


def test_unquiesced_observer_fences_cleanup_before_clients(tmp_path, monkeypatch):
    from scripts import production_rehearsal as rehearsal
    from scripts.read_load_observer import quiesce
    entered, release = threading.Event(), threading.Event()
    def check(): entered.set(); return release.wait(2)
    check.owner_root = str(tmp_path)
    observer = Observer(check); observer.max_age = .01
    assert not observer.start() and entered.is_set()
    real_quiesce = quiesce
    monkeypatch.setattr('scripts.read_load_observer.quiesce', lambda root: real_quiesce(root, timeout=.01))
    monkeypatch.setattr(rehearsal.operator_daemon_lifecycle, 'settle', lambda *a, **k: pytest.fail('Snapshot raced observer'))
    try:
        assert not rehearsal.cleanup(tmp_path, {}, dict(run_id='owned'))
        report = json.loads((tmp_path / 'journal.json').read_text())
        assert report['cleanup_phase'] == 'observer_incomplete'
    finally:
        release.set(); assert real_quiesce(tmp_path, timeout=1)


def test_completed_request_progress_survives_unfinished_peer(monkeypatch):
    published = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(staging_read_load, 'DRAIN_SECONDS', .01)
    def reader(request, **kwargs):
        if request.has_header('Authorization'):
            assert published.wait(1), 'Completed read evidence waited for the whole phase'
            release.wait(1)
        return Response()
    rows = []
    def progress(row):
        rows.append(row)
        if not row.get('incomplete'):
            published.set()
    try:
        result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
            duration=.2, request_open=reader, progress=progress)
        assert published.is_set() and not result['passed']
        assert len(rows) == 2 and sum(bool(row.get('incomplete')) for row in rows) == 1
    finally:
        release.set()


def test_failed_evidence_publication_invalidates_phase_without_secrets(scheduled):
    def fail(row): raise ValueError('secret-evidence')
    result = staging_read_load.run('http://localhost', 'token', lambda: True, read_only_health=True,
        duration=.2, request_open=lambda *a, **k: Response(), progress=fail)
    assert result['requests'] == 2 and not result['passed']
    assert result['evidence_error_types'] == ['ValueError', 'ValueError']
    assert 'secret' not in json.dumps(result)


def test_unreviewed_legacy_health_cannot_start_background_observer(monkeypatch):
    monkeypatch.setattr(staging_read_load, 'Observer', lambda *a: pytest.fail('Started unreviewed observer'))
    with pytest.raises(ValueError, match='callback review required'):
        staging_read_load.run('http://localhost', 'token', lambda: pytest.fail('Legacy journal write'))
