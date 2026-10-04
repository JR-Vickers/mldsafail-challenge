import json
import hashlib
import fcntl
import os

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
