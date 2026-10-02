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
