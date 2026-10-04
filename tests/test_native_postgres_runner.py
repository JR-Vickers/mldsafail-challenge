import fcntl
import json
import os
from types import SimpleNamespace

import pytest

from scripts import native_postgres_acceptance as runner


def receipt():
    return dict(schema_version=1, run_id='a' * 32, name='launch-postgres-' + 'a' * 32,
                database_image='sha256:' + 'b' * 64, clients=[], cleanup_complete=False)


def test_cleanup_retry_preserves_failed_receipt_and_checks_exact_ownership(tmp_path, monkeypatch):
    value = receipt()
    present = [True]
    failing = [True]
    identifier = 'c' * 64
    def command(argv, output, record, **kwargs):
        if argv[:2] == ['docker', 'ps']:
            return identifier if present[0] else ''
        if argv[:2] == ['docker', 'inspect']:
            return json.dumps([dict(Id=identifier, Name='/' + value['name'],
                                   Image=value['database_image'], Config={'Labels': {runner.LABEL: value['run_id']}})])
        if failing[0]:
            raise RuntimeError('synthetic removal failure')
        present[0] = False
        return ''
    monkeypatch.setattr(runner, 'command', command)
    monkeypatch.setattr(runner.time, 'sleep', lambda _: None)
    assert not runner.cleanup(tmp_path, value)
    failed = json.loads((tmp_path / 'ownership.json').read_text())
    assert failed['phase'] == 'cleanup_incomplete' and failed['cleanup_errors']
    failing[0] = False
    assert runner.cleanup(tmp_path, value)
    assert runner.cleanup(tmp_path, value)
    assert value['cleanup_complete']
    attempts = [json.loads((tmp_path / name).read_text()) for name in value['cleanup_attempts']]
    assert len(attempts) == 3 and any(not attempt['cleanup_complete'] for attempt in attempts)


def test_cleanup_never_removes_mismatched_resource(tmp_path, monkeypatch):
    value = receipt()
    calls = []
    def command(argv, *args, **kwargs):
        calls.append(argv)
        if argv[:2] == ['docker', 'ps']:
            return 'c' * 64
        return json.dumps([dict(Id='c' * 64, Name='/another-database', Image=value['database_image'],
                               Config={'Labels': {runner.LABEL: value['run_id']}})])
    monkeypatch.setattr(runner, 'command', command)
    assert not runner.cleanup(tmp_path, value)
    assert not any(argv[:3] == ['docker', 'rm', '-f'] for argv in calls)


def test_command_delegates_durable_client_receipt(tmp_path, monkeypatch):
    value = receipt()
    def interrupted(argv, entries, save, directory, **kwargs):
        entries.append({'id': 'owned', 'finished': False})
        save()
        raise InterruptedError('injected interruption')
    from deploy import owned_client
    monkeypatch.setattr(owned_client, 'run', interrupted)
    with pytest.raises(InterruptedError):
        runner.command(['docker', 'run'], tmp_path, value)
    assert json.loads((tmp_path / 'ownership.json').read_text())['clients'] == [{'id': 'owned', 'finished': False}]


def test_execute_and_cleanup_share_exclusive_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    output = tmp_path / 'run'
    descriptor = os.open(tmp_path / '.run.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            runner.run(None, output, cleanup_only=True)
    finally:
        os.close(descriptor)


def test_output_symlink_and_public_parent_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='non-symlink'):
        runner.run(None, link / 'run', True)
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError, match='Private evidence parent'):
        runner.run(None, tmp_path / 'run', True)
