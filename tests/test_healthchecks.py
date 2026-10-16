from types import SimpleNamespace
import pytest
from deploy.healthchecks import ping, notify

ENDPOINT = 'https://hc-ping.com/12345678-1234-1234-1234-123456789abc'


class Response:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size): return b'OK'


def test_healthy_heartbeats_repeat_and_failure_recovers():
    calls = []
    opener = SimpleNamespace(open=lambda req, **kw: calls.append(req) or Response())
    for healthy in (True, True, False, True):
        assert ping(ENDPOINT, 'service', healthy, opener=opener)
    assert [r.full_url for r in calls] == [ENDPOINT, ENDPOINT, ENDPOINT+'/fail', ENDPOINT]
    assert {r.data for r in calls} == {b'service:healthy', b'service:failure'}


def test_retry_and_delivery_failure_redact_endpoint():
    calls, waits = [], []
    def fail(req, **kw):
        calls.append(req)
        raise RuntimeError(req.full_url)
    with pytest.raises(RuntimeError, match='^Healthchecks delivery failed$'):
        ping(ENDPOINT, 'recovery', True, opener=SimpleNamespace(open=fail), sleep=waits.append)
    assert len(calls) == 3 and waits == [1, 2]
    calls.clear()
    def recover(req, **kw):
        calls.append(req)
        if len(calls) == 1: raise OSError('transient')
        return Response()
    assert ping(ENDPOINT, 'recovery', True, opener=SimpleNamespace(open=recover), sleep=lambda _: None)


def test_ignored_success_response_is_failure():
    class Ignored(Response):
        def read(self, size): return b'OK (rate limited)'
    with pytest.raises(RuntimeError):
        ping(ENDPOINT, 'service', True, opener=SimpleNamespace(open=lambda *a, **k: Ignored()), sleep=lambda _: None)


@pytest.mark.parametrize('endpoint', ['http://hc-ping.com/id', ENDPOINT+'?secret=x',
                                     ENDPOINT.replace('hc-ping.com', 'other.test'), ENDPOINT+'/fail'])
def test_invalid_endpoint_does_not_send(endpoint):
    with pytest.raises(ValueError): ping(endpoint, 'service', True)


def test_disabled_configuration_never_reads_credentials():
    assert notify({}, 'service', True) is False


@pytest.mark.parametrize('result,expected', [
    ({'daily_recovery_verified': True}, [('recovery', True)]),
    ({'cleanup_complete': True}, []),
    ({'restore_verified': True}, []),
])
def test_recovery_success_requires_terminal_verified_marker(tmp_path, monkeypatch, result, expected):
    import deploy.daily_recovery as daily
    monkeypatch.setattr(daily.signal, 'signal', lambda *args: None)
    monkeypatch.setattr(daily.os, 'umask', lambda *args: None)
    config = tmp_path/'config.json'
    config.write_text('{}')
    config.chmod(0o600)
    monkeypatch.setattr('sys.argv', ['daily', '--config', str(config)])
    monkeypatch.setattr(daily, 'run', lambda *args: result)
    calls = []
    monkeypatch.setattr('deploy.healthchecks.notify', lambda config, check, healthy: calls.append((check, healthy)))
    daily.main()
    assert calls == expected


def test_failed_recovery_signals_failure_and_keeps_nonzero_exit(tmp_path, monkeypatch):
    import deploy.daily_recovery as daily
    monkeypatch.setattr(daily.signal, 'signal', lambda *args: None)
    monkeypatch.setattr(daily.os, 'umask', lambda *args: None)
    config = tmp_path/'config.json'
    config.write_text('{}'); config.chmod(0o600)
    monkeypatch.setattr('sys.argv', ['daily', '--config', str(config)])
    monkeypatch.setattr(daily, 'run', lambda *args: (_ for _ in ()).throw(RuntimeError('private failure')))
    calls = []
    monkeypatch.setattr('deploy.healthchecks.notify', lambda config, check, healthy: calls.append((check, healthy)))
    with pytest.raises(SystemExit) as error: daily.main()
    assert error.value.code == 1 and calls == [('recovery', False)]
