import hashlib
import json
import pytest
from deploy.recovery import validate_set, private_file


def test_recovery_set_corruption_and_missing_material(tmp_path):
    file = tmp_path / 'snapshot'
    file.write_bytes(b'private test material')
    manifest = {'database_evidence_verified': True,
                'categories': {name: ['snapshot'] for name in
                  ['database', 'epoch', 'evidence', 'configuration', 'secrets', 'release', 'images']},
                'files': {'snapshot': hashlib.sha256(file.read_bytes()).hexdigest()}}
    (tmp_path / 'recovery.json').write_text(json.dumps(manifest))
    assert validate_set(tmp_path) == manifest
    file.write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        validate_set(tmp_path)
    file.unlink()
    with pytest.raises(ValueError):
        validate_set(tmp_path)


def test_private_material(tmp_path):
    file = tmp_path / 'password'
    file.write_text('test')
    file.chmod(0o644)
    with pytest.raises(ValueError):
        private_file(file)
    file.chmod(0o600)
    assert private_file(file) == file


def test_interrupted_upload_never_marks_backup_verified(tmp_path, monkeypatch):
    import subprocess
    from deploy.recovery import execute
    binary = tmp_path / 'restic'
    binary.write_bytes(b'pinned test binary')
    credentials = tmp_path / 'credentials'
    credentials.write_text('{"AWS_ACCESS_KEY_ID":"test","AWS_SECRET_ACCESS_KEY":"secret"}')
    credentials.chmod(0o600)
    password = tmp_path / 'password'
    password.write_text('test-password')
    password.chmod(0o600)
    state = tmp_path / 'state'
    config = {'restic_binary': str(binary), 'restic_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'password_file': str(password), 'credentials_file': str(credentials),
              'environment': 'staging', 'repository': 's3:https://storage.test/bucket/staging',
              'owner_retained_recovery_key': True, 'backup_state': str(state)}
    monkeypatch.setattr('deploy.recovery.validate_set', lambda _: {})
    def interrupted(*args, **kwargs):
        raise subprocess.TimeoutExpired('restic', 1)
    monkeypatch.setattr('deploy.recovery.subprocess.run', interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        execute(config, 'backup', tmp_path / 'sealed')
    assert not state.exists()
    config['owner_retained_recovery_key'] = False
    with pytest.raises(ValueError, match='retain'):
        execute(config, 'backup', tmp_path / 'sealed')


def test_assembly_failure_restores_original_service_states(tmp_path, monkeypatch):
    from deploy.assemble_recovery import assemble
    calls = []
    def output(argv, **kwargs):
        calls.append(argv)
        if 'ps' in argv:
            return argv[-1]
        if 'inspect' in argv:
            return '{"Running":true}'
        if 'run' in argv:
            raise RuntimeError('interrupted snapshot inspection')
        return ''
    monkeypatch.setattr('deploy.assemble_recovery.subprocess.check_output', output)
    config = {'env_file': '/private/env', 'compose': '/app/compose.private.yaml'}
    destination = tmp_path / 'set'
    with pytest.raises(RuntimeError):
        assemble(config, destination)
    assert any(argv[-2:] == ['start', 'web'] for argv in calls)
    assert any(argv[-2:] == ['start', 'coordinator'] for argv in calls)
    assert json.loads((destination / 'maintenance.json').read_text())['cleanup_complete']
    assert not (destination / 'recovery.json').exists()
