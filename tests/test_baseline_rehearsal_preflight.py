import json
import hashlib
import fcntl
import os
from pathlib import Path

import pytest

from scripts.baseline_production_rehearsal import LABEL, cleanup, execute, validate


def config(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'compose.production.yaml').write_text('services: {}')
    benchmark = source / 'src/mldsafail/benchmark_v050'
    benchmark.mkdir(parents=True)
    for name in ('execution', 'generator', 'scoring', 'evidence'):
        (benchmark / (name + '.py')).write_text('# frozen-source-fixture\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'source_commit': 'a' * 40, 'source_files_sha256':
        {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in [source / 'compose.production.yaml', *benchmark.glob('*.py')]}}))
    release = tmp_path / 'release.json'
    rollback = tmp_path / 'rollback.json'
    release_data = {'source_commit': 'a' * 40, 'images':
        {role: {'id': 'sha256:' + 'a' * 64} for role in ('web', 'coordinator', 'worker')},
        'worker_lock_sha256': 'c' * 64, 'mlwe_trusted_fingerprint': 'd' * 64}
    release.write_text(json.dumps(release_data))
    rollback.write_text(json.dumps({**release_data, 'source_commit': 'b4d212da3109b7716eb41553986848e377fb5b3d'}))
    return dict(release_manifest=str(release), rollback_manifest=str(rollback), source_manifest=str(manifest), run_directory=str(tmp_path / 'new-owned-root'), staging_root=str(tmp_path / 'staging'),
                operator_source=str(source), docker_socket='/run/user/1000/docker.sock',
                images={role: 'sha256:' + 'a' * 64 for role in
                        ('web', 'coordinator', 'worker', 'postgres', 'caddy', 'rollback_web', 'rollback_coordinator')},
                fixture_repository='https://github.com/example/reviewed-fixtures', fixture_commit='b' * 40,
                fixture_solver_path='reference')


def test_disposable_rehearsal_rejects_staging_and_mutable_images(tmp_path):
    value = config(tmp_path)
    assert validate(value)[0].name == 'new-owned-root'
    for root in (value['staging_root'], str(tmp_path), value['staging_root'] + '/child'):
        with pytest.raises(ValueError, match='overlap'):
            validate({**value, 'run_directory': root})
    value['images']['web'] = 'mutable:tag'
    with pytest.raises(ValueError, match='Immutable'):
        validate(value)


def test_rehearsal_cleanup_never_removes_ownership_mismatch_and_retries_independently(tmp_path, monkeypatch):
    (tmp_path / 'journal.json').write_text(json.dumps({'run_id': 'owned', 'cleanup_complete': False}))
    calls = []
    def command(argv, **_):
        calls.append(argv)
        if argv[:3] == ['docker', 'ps', '-aq']:
            return b'container-id\n'
        if argv[:4] == ['docker', 'volume', 'ls', '-q']:
            return b'volume-id\n'
        if argv[:4] == ['docker', 'network', 'ls', '-q']:
            return b'network-id\n'
        if argv[:3] == ['docker', 'container', 'inspect']:
            return json.dumps([{'Config': {'Labels': {LABEL: 'other'}}}]).encode()
        if argv[:3] in (['docker', 'volume', 'inspect'], ['docker', 'network', 'inspect']):
            return json.dumps([{'Labels': {LABEL: 'owned'}}]).encode()
        return b''
    monkeypatch.setattr('scripts.baseline_production_rehearsal.command', command)
    assert cleanup(tmp_path, {}) is False
    assert ['docker', 'rm', '-f', 'container-id'] not in calls
    assert ['docker', 'volume', 'rm', 'volume-id'] in calls
    assert ['docker', 'network', 'rm', 'network-id'] in calls
    assert json.loads((tmp_path / 'journal.json').read_text())['cleanup_complete'] is False


def test_rehearsal_lock_fences_concurrent_cleanup(tmp_path, monkeypatch):
    value = config(tmp_path)
    root = tmp_path / 'new-owned-root'
    lock = root.with_name('.' + root.name + '-run.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root.mkdir(mode=0o700)
        journal = root / 'journal.json'
        journal.write_text(json.dumps({'run_id': 'a' * 32, 'owner_uid': os.getuid(), 'docker_socket': '/run/user/' + str(os.getuid()) + '/docker.sock'}))
        journal.chmod(0o600)
        value['docker_socket'] = '/run/user/' + str(os.getuid()) + '/docker.sock'
        monkeypatch.setattr('scripts.baseline_production_rehearsal._execute_locked',
                            lambda *_: pytest.fail('concurrent cleanup reached execution'))
        with pytest.raises(BlockingIOError):
            execute(value, cleanup_only=True)
    finally:
        os.close(descriptor)


def test_cleanup_final_inventory_rejects_late_container_creation(tmp_path, monkeypatch):
    (tmp_path / 'journal.json').write_text(json.dumps({'run_id': 'owned', 'cleanup_complete': False}))
    scans = 0
    def command(argv, **_):
        nonlocal scans
        if argv[:3] == ['docker', 'ps', '-aq']:
            scans += 1
            return b'late-owned-container\n' if scans == 3 else b''
        return b''
    monkeypatch.setattr('scripts.baseline_production_rehearsal.command', command)
    assert cleanup(tmp_path, {}) is False
    report = json.loads((tmp_path / 'journal.json').read_text())
    assert report['cleanup_phase'] == 'incomplete'
    assert report['final_inventory']['container'] == ['late-owned-container']


def test_protected_roots_and_readiness_timeout_are_enforced(tmp_path, monkeypatch):
    import subprocess
    from scripts.baseline_production_rehearsal import wait_database
    value = config(tmp_path)
    with pytest.raises(ValueError, match='protected'):
        validate({**value, 'protected_roots': [str(tmp_path / 'new-owned-root')]})
    ticks = iter([0, 0, 0, 121, 121])
    monkeypatch.setattr('scripts.baseline_production_rehearsal.time.monotonic', lambda: next(ticks))
    monkeypatch.setattr('scripts.baseline_production_rehearsal.time.sleep', lambda _: None)
    def hang(argv, **kwargs):
        assert kwargs['timeout'] == 10
        raise subprocess.TimeoutExpired(argv, 10)
    monkeypatch.setattr('scripts.baseline_production_rehearsal.client_run', hang)
    evidence = []
    with pytest.raises(RuntimeError, match='readiness timeout'):
        wait_database(['docker', 'compose'], {}, evidence.append)
    assert evidence == [{'outcome': 'timeout', 'timeout_seconds_maximum': 10}]


def test_cleanup_does_not_require_source_or_release_manifests(tmp_path):
    from scripts.baseline_production_rehearsal import cleanup_authority
    root = tmp_path / 'owned'
    root.mkdir(mode=0o700)
    socket = '/run/user/' + str(os.getuid()) + '/docker.sock'
    journal = root / 'journal.json'
    journal.write_text(json.dumps({'run_id': 'a' * 32, 'owner_uid': os.getuid(), 'docker_socket': socket}))
    journal.chmod(0o600)
    assert cleanup_authority({'run_directory': str(root), 'docker_socket': socket}) == root
    with pytest.raises(ValueError, match='binding'):
        cleanup_authority({'run_directory': str(root), 'docker_socket': '/run/user/999999/docker.sock'})


def test_cleanup_continues_after_corrupt_clients_and_journal_publication_failure(tmp_path, monkeypatch):
    (tmp_path / 'journal.json').write_text(json.dumps({'run_id': 'owned', 'cleanup_complete': False}))
    (tmp_path / 'clients.json').write_text('{truncated')
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        assert kwargs['env']['MLDSAFAIL_OWNED_CLIENT_RECEIPT'].startswith('cleanup-clients-')
        return b''
    monkeypatch.setattr('scripts.baseline_production_rehearsal.command', command)
    def refuse(path, _):
        if path.name == 'journal.json':
            raise OSError('publication failed')
    monkeypatch.setattr('scripts.baseline_production_rehearsal.atomic_json', refuse)
    errors = []
    assert cleanup(tmp_path, {}, errors_out=errors) is False
    assert len(calls) == 7  # all four phases and all three final inventories
    assert any(error['step'] == 'receipt_load' for error in errors)
    assert sum(error.get('kind') == 'journal' for error in errors) == 5


def test_failed_preservation_publication_still_calls_cleanup_and_preserves_original(tmp_path, monkeypatch):
    from scripts.baseline_production_rehearsal import _execute_locked
    from deploy.recovery_journal import atomic_json as real_publish
    value = config(tmp_path)
    root = Path(value['run_directory'])
    calls = []
    def command(*_args, **_kwargs):
        raise ValueError('original preflight failure')
    monkeypatch.setattr('scripts.baseline_production_rehearsal.command', command)
    writes = 0
    def publish(path, data):
        nonlocal writes
        if path.name == 'journal.json':
            writes += 1
            if writes > 1:
                raise OSError('publication failure')
        real_publish(path, data)
    monkeypatch.setattr('scripts.baseline_production_rehearsal.atomic_json', publish)
    def repair(destination, _env, journal, errors):
        calls.append(destination)
        assert journal['preserve_failed_volumes'] is True
        return False
    monkeypatch.setattr('scripts.baseline_production_rehearsal.cleanup', repair)
    with pytest.raises(ValueError, match='original preflight failure'):
        _execute_locked(value)
    assert calls == [root]
    assert json.loads((root / 'report.json').read_text())['complete'] is False


def test_empty_inventory_cannot_clear_unacknowledged_daemon_mutation(tmp_path, monkeypatch):
    (tmp_path / 'journal.json').write_text(json.dumps({'run_id': 'owned', 'cleanup_complete': False}))
    (tmp_path / 'daemon-mutations.json').write_text(json.dumps([{'id': 'create', 'acknowledged': False}]))
    monkeypatch.setattr('scripts.baseline_production_rehearsal.command', lambda *_args, **_kwargs: b'')
    assert cleanup(tmp_path, {}) is False
    receipt = json.loads((tmp_path / 'journal.json').read_text())
    assert receipt['final_inventory'] == {'container': [], 'volume': [], 'network': []}
    assert receipt['cleanup_errors'][0]['kind'] == 'daemon_mutation_uncertainty'
