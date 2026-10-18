import itertools
import json
import urllib.error

import pytest

from scripts import staging_read_load


@pytest.mark.parametrize('failure', [
    TimeoutError('secret-token'),
    urllib.error.HTTPError('https://secret-host/', 503, 'secret-message', {}, None),
])
def test_failed_read_diagnostics_are_bounded_and_private(monkeypatch, failure):
    clock = itertools.count(0, .01)
    monkeypatch.setattr(staging_read_load.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(staging_read_load.time, 'sleep', lambda _: None)
    rows = []
    def request_open(request, timeout):
        assert timeout == 2
        raise failure
    result = staging_read_load.run('http://secret-host', 'secret-token', lambda: True,
                                   duration=.2, progress=rows.append, request_open=request_open)
    assert result['requests'] == result['read_failures'] == 2
    assert not result['passed'] and result['duration_seconds'] == .2
    assert result['elapsed_seconds'] > 0 and result['max_scheduling_lag_seconds'] >= 0
    for row in rows:
        assert row['failed'] and row['error_type'] == type(failure).__name__
        assert row['http_status'] == (503 if isinstance(failure, urllib.error.HTTPError) else None)
        assert row['finished_after_seconds'] >= row['started_after_seconds'] >= 0
        assert row['seconds'] == pytest.approx(row['finished_after_seconds'] - row['started_after_seconds'])
    assert 'secret' not in json.dumps(dict(result=result, rows=rows))


def test_blocking_health_check_is_visible_in_elapsed_and_pacing(monkeypatch):
    from concurrent.futures import Future
    class InlinePool:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future
    monkeypatch.setattr(staging_read_load, 'ThreadPoolExecutor', InlinePool)
    now = [0.0]
    monkeypatch.setattr(staging_read_load.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(staging_read_load.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    class Response:
        status = 200
        def read(self, limit): return b'ok'
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def health():
        now[0] += 2
        return True
    result = staging_read_load.run('http://localhost', 'token', health, duration=1,
                                   request_open=lambda *a, **k: Response())
    assert result['passed'] and result['requests'] == 6 and result['read_failures'] == 0
    assert result['duration_seconds'] == 1 and result['elapsed_seconds'] >= 2
    assert result['max_scheduling_lag_seconds'] >= 1
