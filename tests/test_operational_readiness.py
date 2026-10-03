import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
from deploy.daily_recovery import prune, remove_owned
from deploy.recovery_journal import Journal, atomic_json
from deploy.validate_production import validate
from scripts.retain_release import retain, verify


def test_production_paths(tmp_path):
    assert validate(str(tmp_path / 'production'), str(tmp_path / 'staging')) == tmp_path / 'production'
    for path in ('relative', str(tmp_path), str(tmp_path / 'staging/child')):
        with pytest.raises(ValueError):
            validate(path, str(tmp_path / 'staging'))
    (tmp_path / 'link').symlink_to(tmp_path / 'production')
    with pytest.raises(ValueError):
        validate(str(tmp_path / 'link'))


def inventory(tmp_path):
    roles = {role: role for role in ('manifest', 'images', 'wheel', 'checksums', 'rollback')}
    artifacts = {}
    for role in roles:
        source = tmp_path / role
        content = json.dumps({'source_commit':'a'*40}).encode() if role == 'manifest' else role.encode()
        source.write_bytes(content)
        artifacts[role] = dict(path=str(source), sha256=hashlib.sha256(content).hexdigest())
    return dict(source_commit='a' * 40, roles=roles, artifacts=artifacts)


def test_release_retention(tmp_path):
    data = inventory(tmp_path)
    root = tmp_path / 'releases'
    destination = retain(data, root)
    assert destination.name == 'a' * 40
    assert root.stat().st_mode & 0o077 == 0
    assert destination.stat().st_mode & 0o777 == 0o500
    assert (destination / 'images').stat().st_mode & 0o777 == 0o400
    assert retain(data, root) == destination
    conflicting = dict(data, roles={**data['roles'], 'wheel': 'images'})
    with pytest.raises(ValueError, match='Conflicting'):
        retain(conflicting, root)
    (tmp_path / 'wheel').write_text('bad')
    assert retain(data, root) == destination
    (tmp_path / 'wheel').unlink()
    assert retain(data, root) == destination
    assert verify(root, data['source_commit']) == destination
    (destination / 'wheel').chmod(0o600)
    with pytest.raises(ValueError, match='permissions'):
        verify(root, data['source_commit'])
    (destination / 'wheel').write_text('corrupted')
    (destination / 'wheel').chmod(0o400)
    with pytest.raises(ValueError, match='checksum'):
        retain(data, root)


def test_release_interrupted_publication(tmp_path, monkeypatch):
    data = inventory(tmp_path)
    root = tmp_path / 'releases'
    def fail(*_):
        raise InterruptedError()
    monkeypatch.setattr('scripts.retain_release.atomic_json', fail)
    with pytest.raises(InterruptedError):
        retain(data, root)
    assert not (root / ('a' * 40)).exists()
    assert not list(root.glob('.retaining-*'))


def test_retention_preserves_failures_and_repository(tmp_path, monkeypatch):
    (tmp_path / 'journals').mkdir()
    monkeypatch.setattr('deploy.daily_recovery.validate_set', lambda _: {})
    for index in range(7):
        run = f'{index:032x}'
        record = dict(repository='repo' if index != 6 else 'other',
                      set_directory='set-' + run, restore_directory='restore-' + run,
                      cleanup_complete=index != 4, restore_verified=index != 5,
                      verified_at=f'2026-10-0{index+1}')
        for key in ('set_directory', 'restore_directory'):
            (tmp_path / record[key]).mkdir()
        atomic_json(tmp_path / 'journals' / ('run-' + run + '.json'), record)
    prune(tmp_path, 'repo', 2)
    assert not (tmp_path / ('set-' + f'{0:032x}')).exists()
    assert not (tmp_path / ('set-' + f'{1:032x}')).exists()
    for index in range(2, 7):
        assert (tmp_path / ('set-' + f'{index:032x}')).exists()
    prune(tmp_path, 'repo', 2)
    with pytest.raises(ValueError):
        remove_owned(tmp_path, '../release')
    link = tmp_path / ('restore-' + 'f' * 32)
    link.symlink_to(tmp_path / 'journals', target_is_directory=True)
    with pytest.raises(ValueError):
        remove_owned(tmp_path, link.name)


DRIVER = r'''
import json, sys, time
from pathlib import Path
from types import SimpleNamespace
import deploy.daily_recovery as daily
import deploy.recovery_journal as journal
config = json.loads(Path(sys.argv[sys.argv.index('--config')+1]).read_text())
root = Path(config['recovery_root'])
marker = root.parent / 'boundary'
def output(argv, **kwargs):
    if 'inspect' in argv:
        if '--format' in argv: return '{"Running":true}'
        return json.dumps([{'Name':'/recovery-test','Image':'sha256:'+'a'*64,'Config':{'Labels':{'org.mldsafail.recovery':'recovery-test'}}}])
    return 'identifier'
def command(argv, **kwargs):
    if 'rm' in argv:
        (root.parent / 'removed').write_text('yes')
    return SimpleNamespace(stdout='identifier', returncode=0)
journal.subprocess.check_output = output
journal.subprocess.run = command
def boundary(stage):
    if config['stage'] == stage:
        marker.write_text(stage)
        time.sleep(30)
def assembly(config, destination, operation):
    destination.mkdir()
    operation.services(['docker','compose'], {'web': True, 'coordinator':True})
    operation.container('recovery-test', 'sha256:'+'a'*64)
    boundary('assembly')
def execute(config, *args):
    boundary('upload')
    Path(config['backup_state']).write_text(json.dumps({'repository':'repo','snapshot':'snapshot'}))
def verify(config, destination, operation):
    boundary('verification')
    return {'repository':'repo','snapshot':'snapshot','restore_verified':True,'cleanup_complete':True}
daily.assemble=assembly
daily.execute=execute
daily.verify=verify
daily.prune=lambda *args: None
daily.main()
'''


def process(tmp_path, stage):
    config = tmp_path / 'config.json'
    config.write_text(json.dumps(dict(recovery_root=str(tmp_path / 'root'), stage=stage,
                                     assembly={}, backup=dict(repository='repo', backup_state=str(tmp_path / 'state')))))
    config.chmod(0o600)
    argv = [sys.executable, '-c', DRIVER, '--config', str(config)]
    child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 5
    while not (tmp_path / 'boundary').exists():
        assert child.poll() is None, child.communicate()
        assert time.monotonic() < deadline
        time.sleep(0.01)
    return child, argv


@pytest.mark.parametrize('stage', ['assembly', 'upload', 'verification'])
@pytest.mark.parametrize('sig', [signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGKILL])
def test_subprocess_interrupt_and_cleanup(tmp_path, stage, sig):
    child, argv = process(tmp_path, stage)
    child.send_signal(sig)
    child.communicate(timeout=5)
    assert child.returncode != 0
    path = tmp_path / 'root/journals/operation.json'
    if sig == signal.SIGKILL:
        assert not json.loads(path.read_text())['cleanup_complete']
    else:
        assert json.loads(path.read_text())['cleanup_complete']
    for _ in range(2):
        result = subprocess.run(argv + ['--cleanup'], capture_output=True, timeout=5)
        assert result.returncode == 0, result.stderr
    assert json.loads(path.read_text())['cleanup_complete']
    assert (tmp_path / 'removed').exists()
    assert not (tmp_path / 'state').exists() or not json.loads((tmp_path / 'state').read_text()).get('restore_verified')


def test_concurrent_and_restart_reconciliation(tmp_path):
    child, argv = process(tmp_path, 'assembly')
    result = subprocess.run(argv + ['--cleanup'], capture_output=True, timeout=5)
    assert result.returncode != 0
    child.kill()
    child.communicate(timeout=5)
    # Next ordinary invocation reconciles before starting a fresh run.
    (tmp_path / 'boundary').unlink()
    next_child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 5
    while not (tmp_path / 'boundary').exists():
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert (tmp_path / 'removed').exists()
    next_child.terminate()
    next_child.communicate(timeout=5)


def test_cleanup_independent_failure_and_retry(tmp_path, monkeypatch):
    journal = Journal(tmp_path / 'operation.json', {})
    journal.services(['docker','compose'], {'web':True,'coordinator':True})
    calls = []
    def command(argv, **kwargs):
        calls.append(argv)
        if argv[-1] == 'web':
            raise RuntimeError('failure')
    monkeypatch.setattr('deploy.recovery_journal.subprocess.run', command)
    monkeypatch.setattr('deploy.recovery_journal.subprocess.check_output',
                        lambda argv, **kw: '{"Running":true}' if 'inspect' in argv else 'identifier')
    with pytest.raises(RuntimeError):
        journal.cleanup()
    assert any(argv[-1] == 'coordinator' for argv in calls)
    assert journal.data['cleanup_errors'] == ['service:web']
    monkeypatch.setattr('deploy.recovery_journal.subprocess.run', lambda *a, **kw: None)
    journal.cleanup()
    assert journal.data['cleanup_complete']


def test_disk_floor_preserves_evidence(tmp_path, monkeypatch):
    from deploy.daily_recovery import run
    from types import SimpleNamespace
    root = tmp_path / 'root'
    root.mkdir()
    failed = root / ('set-' + 'a' * 32)
    failed.mkdir()
    monkeypatch.setattr('deploy.daily_recovery.shutil.disk_usage', lambda _: SimpleNamespace(free=1))
    with pytest.raises(RuntimeError, match='disk'):
        run(dict(recovery_root=str(root), assembly={}, backup={}))
    assert failed.exists()


def test_production_compose_synthetic_configuration(tmp_path):
    import shutil
    if not shutil.which('docker'):
        pytest.skip('Docker Compose unavailable')
    env = dict(os.environ)
    required = ['POSTGRES_PASSWORD','MLDSAFAIL_SECRET_KEY','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET',
                'MLDSAFAIL_EVALUATOR_FINGERPRINT','MLDSAFAIL_HIDDEN_SUITE_VERSION',
                'MLDSAFAIL_WORKER_CLASS','MLDSAFAIL_MLWE_EPOCH_ID','MLDSAFAIL_DOMAIN',
                'ROOTLESS_DOCKER_SOCKET','WEB_IMAGE','COORDINATOR_IMAGE','WORKER_IMAGE',
                'CADDY_IMAGE','POSTGRES_IMAGE']
    env.update({key: 'synthetic' for key in required})
    env.update(PRODUCTION_EVALUATOR_ROOT='/srv/mldsafail-production-evaluator',
               ROOTLESS_DOCKER_SOCKET='/run/user/1000/docker.sock')
    argv = ['docker','compose','-f','compose.production.yaml','config','--format','json']
    result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    coordinator = json.loads(result.stdout)['services']['coordinator']
    mount = next(m for m in coordinator['volumes'] if m['source'] == env['PRODUCTION_EVALUATOR_ROOT'])
    assert mount['source'] == mount['target']
    assert coordinator['environment']['MLDSAFAIL_MLWE_EPOCH_PATH'] == mount['source'] + '/epoch'
    del env['PRODUCTION_EVALUATOR_ROOT']
    assert subprocess.run(argv, env=env, capture_output=True, timeout=30).returncode != 0


def test_container_ownership_mismatch_never_removed(tmp_path, monkeypatch):
    from types import SimpleNamespace
    journal = Journal(tmp_path / 'journal.json', {})
    journal.container('owned', 'sha256:'+'a'*64)
    calls = []
    def command(argv, **kw):
        calls.append(argv)
        return SimpleNamespace(stdout='identifier')
    monkeypatch.setattr('deploy.recovery_journal.subprocess.run', command)
    monkeypatch.setattr('deploy.recovery_journal.subprocess.check_output', lambda *a, **kw:
                        json.dumps([{'Name':'/owned','Image':'wrong','Config':{'Labels':{}}}]))
    with pytest.raises(RuntimeError):
        journal.cleanup()
    assert not any('rm' in argv for argv in calls)
    assert not journal.data['cleanup_complete']


@pytest.mark.parametrize('cleanup_failure', [False, True])
def test_verification_published_only_after_cleanup(tmp_path, monkeypatch, cleanup_failure):
    from deploy.daily_recovery import run
    state = tmp_path / 'state'
    config = dict(recovery_root=str(tmp_path / 'root'), assembly={},
                  backup=dict(repository='repo', backup_state=str(state)))
    def assemble(config, destination, operation):
        destination.mkdir()
        operation.data['cleanup_complete'] = False
        operation.save('maintenance intent')
    def upload(config, *args):
        atomic_json(state, dict(repository='repo', snapshot='snapshot', restore_verified=False))
    def verify(config, destination, operation):
        destination.mkdir()
        return dict(repository='repo', snapshot='snapshot', restore_verified=True, cleanup_complete=True)
    def cleanup(operation):
        operation.data.update(cleanup_complete=not cleanup_failure,
                              cleanup_errors=['service:web'] if cleanup_failure else [])
        operation.save('cleanup')
        if cleanup_failure:
            raise RuntimeError('failed cleanup')
    monkeypatch.setattr('deploy.daily_recovery.assemble', assemble)
    monkeypatch.setattr('deploy.daily_recovery.execute', upload)
    monkeypatch.setattr('deploy.daily_recovery.verify', verify)
    monkeypatch.setattr(Journal, 'cleanup', cleanup)
    monkeypatch.setattr('deploy.daily_recovery.validate_set', lambda _: {})
    if cleanup_failure:
        with pytest.raises(RuntimeError):
            run(config)
        assert not json.loads(state.read_text())['restore_verified']
    else:
        assert run(config)['daily_recovery_verified']
        assert json.loads(state.read_text())['cleanup_complete']
        assert not list((tmp_path / 'root').glob('restore-*'))
    record = json.loads(next((tmp_path / 'root/journals').glob('run-*.json')).read_text())
    assert record['cleanup_complete'] != cleanup_failure
    assert record['restore_verified'] != cleanup_failure


@pytest.mark.parametrize('boundary', ['coordinator', 'web', 'run'])
def test_assembly_maintenance_boundaries(tmp_path, monkeypatch, boundary):
    from deploy.assemble_recovery import assemble
    calls = []
    def output(argv, **kwargs):
        calls.append(argv)
        if 'ps' in argv:
            return argv[-1]
        if 'inspect' in argv:
            return '{"Running":true}'
        if ('stop' in argv and argv[-1] == boundary) or ('run' in argv and boundary == 'run'):
            raise InterruptedError()
        return ''
    monkeypatch.setattr('deploy.assemble_recovery.subprocess.check_output', output)
    with pytest.raises(InterruptedError):
        assemble(dict(env_file='/private/env', compose='/app/compose.private.yaml'), tmp_path / 'set')
    assert any(argv[-2:] == ['start','web'] for argv in calls)
    assert any(argv[-2:] == ['start','coordinator'] for argv in calls)


def test_completed_journal_configuration_rotation(tmp_path):
    path = tmp_path / 'operation.json'
    journal = Journal(path, {'setting': 1})
    journal.data.update(run_id='a' * 32, cleanup_complete=False)
    journal.save('interrupted')
    original = path.read_bytes()
    with pytest.raises(ValueError, match='configuration'):
        Journal(path, {'setting': 2})
    assert path.read_bytes() == original
    journal.data['cleanup_complete'] = True
    journal.save('cleanup')
    old = path.read_bytes()
    replacement = Journal(path, {'setting': 2})
    assert (tmp_path / ('operation-' + 'a' * 32 + '.json')).read_bytes() == old
    assert replacement.data['cleanup_complete']
    assert replacement.data['configuration'] != journal.data['configuration']
    assert Journal(path, {'setting': 2}).data == replacement.data


def test_retained_release_exact_inventory_and_cli(tmp_path):
    data = inventory(tmp_path)
    root = tmp_path / 'releases'
    destination = retain(data, root)
    for item in data['artifacts'].values():
        Path(item['path']).unlink()
    result = subprocess.run([sys.executable, '-m', 'scripts.retain_release', '--verify',
                             '--commit', data['source_commit'], '--root', str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    destination.chmod(0o700)
    (destination / 'extra').write_text('unexpected')
    destination.chmod(0o500)
    with pytest.raises(ValueError, match='list'):
        verify(root, data['source_commit'])
