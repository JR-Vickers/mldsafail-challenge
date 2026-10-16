from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from deploy import host_checks


def test_backup_freshness_and_leases_do_not_depend_on_queue(monkeypatch):
    monkeypatch.setattr(host_checks.shutil, 'disk_usage', lambda _: SimpleNamespace(free=6 * 1024**3))
    monkeypatch.setattr(host_checks.Path, 'read_text', lambda _: 'MemAvailable: 262144 kB\n')
    now = datetime.now(timezone.utc)
    assert host_checks.evaluate(True, {'coordinator': True}, [], now, [], now) == set()
    assert host_checks.evaluate(True, {'coordinator': True}, [now - timedelta(seconds=1)],
                                now - timedelta(hours=27), [], now) == {'lease', 'backup'}
    assert host_checks.evaluate(False, {'web': False}, [], None, ['failed'], now) == {
        'readiness', 'service', 'backup', 'scheduled_job'}


def test_future_backup_never_claims_freshness(monkeypatch):
    monkeypatch.setattr(host_checks.shutil, 'disk_usage', lambda _: SimpleNamespace(free=6 * 1024**3))
    monkeypatch.setattr(host_checks.Path, 'read_text', lambda _: 'MemAvailable: 262144 kB\n')
    now = datetime.now(timezone.utc)
    assert host_checks.evaluate(True, {'web': True}, [], now + timedelta(seconds=1), [], now) == {'backup'}


def test_service_scope_defers_backups_and_preserves_other_checks(monkeypatch):
    monkeypatch.setattr(host_checks.shutil, 'disk_usage', lambda _: SimpleNamespace(free=6 * 1024**3))
    monkeypatch.setattr(host_checks.Path, 'read_text', lambda _: 'MemAvailable: 262144 kB\n')
    now = datetime.now(timezone.utc)
    assert host_checks.evaluate(True, {'web': True}, [], None, [], now, scope='service') == set()
    assert host_checks.evaluate(True, {'web': True}, [], None, [], now) == {'backup'}
    assert host_checks.evaluate(True, {'web': True}, [now - timedelta(seconds=1)], None,
                                ['job'], now, scope='service') == {'lease', 'scheduled_job'}


def test_failed_resource_inspections_are_failures(monkeypatch):
    def fail(*args):
        raise OSError('inspection failed')
    monkeypatch.setattr(host_checks.shutil, 'disk_usage', fail)
    monkeypatch.setattr(host_checks.Path, 'read_text', fail)
    assert host_checks.evaluate(True, {'web': True}, [], None, [], scope='service') == {'disk', 'ram'}


def test_monitor_configuration_validation():
    import pytest
    config = dict(env_file='/private/env', compose='/release/compose.yaml',
                  readiness_url='http://127.0.0.1:8080/health/ready')
    assert host_checks.validate_config(config) == 'full'
    assert host_checks.validate_config({**config, 'scope': 'service'}) == 'service'
    for changes in ({'scope': 'unknown'}, {'scheduled_units': 'backup.service'},
                    {'service_scheduled_units': ['--help']}, {'env_file': 'relative'},
                    {'healthchecks': {'enabled': 'false'}}, {'alert_enabled': 'false'},
                    {'readiness_url': 'file:///private/file'},
                    {'readiness_url': 'http://127.0.0.1:invalid/ready'}):
        with pytest.raises(ValueError):
            host_checks.validate_config({**config, **changes})


def test_service_main_skips_backup_jobs_and_reports_scope(tmp_path, monkeypatch, capsys):
    import json
    import pytest
    config = tmp_path / 'monitor.json'
    config.write_text(json.dumps(dict(scope='service', env_file='/private/env',
        compose='/release/compose.yaml', readiness_url='http://127.0.0.1/health/ready',
        scheduled_units=['backup.service'], service_scheduled_units=['service-job.service'])))
    config.chmod(0o600)
    monkeypatch.setattr('sys.argv', ['monitor', '--config', str(config)])
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        if argv[0] == 'systemctl':
            return 'success'
        if 'inspect' in argv:
            return '{"Running":true}'
        if 'exec' in argv:
            return '[]'
        return 'container-id'
    monkeypatch.setattr('subprocess.check_output', command)
    class Ready:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Ready())
    monkeypatch.setattr(host_checks.shutil, 'disk_usage', lambda _: SimpleNamespace(free=6 * 1024**3))
    original = host_checks.Path.read_text
    monkeypatch.setattr(host_checks.Path, 'read_text', lambda path: 'MemAvailable: 262144 kB\n'
                        if str(path) == '/proc/meminfo' else original(path))
    def forbidden(*args):
        raise AssertionError('Service scope inspected backup state')
    monkeypatch.setattr('deploy.recovery.validate_verified_state', forbidden)
    delivered = []
    monkeypatch.setattr('deploy.healthchecks.notify', lambda config, check, healthy: delivered.append(healthy))
    with pytest.raises(SystemExit) as exit:
        host_checks.main()
    assert exit.value.code == 0 and delivered == [True]
    assert not any('backup.service' in argv for argv in calls)
    assert any('service-job.service' in argv for argv in calls)
    assert json.loads(capsys.readouterr().out) == dict(healthy=True, checks=[], scope='service', backup_status='deferred')


def test_malformed_config_never_sends_heartbeat(tmp_path, monkeypatch):
    import pytest
    config = tmp_path / 'monitor.json'
    config.write_text('{"scope":"unsupported"}')
    config.chmod(0o600)
    monkeypatch.setattr('sys.argv', ['monitor', '--config', str(config)])
    def forbidden(*args):
        raise AssertionError('Invalid config sent a heartbeat')
    monkeypatch.setattr('deploy.healthchecks.notify', forbidden)
    with pytest.raises(ValueError):
        host_checks.main()
