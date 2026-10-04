import os
from pathlib import Path
import subprocess
import sys
import importlib.util
import json
import pytest
from deploy.operator_activation import activation_lock, current_configuration


def test_other_process_cannot_enter_activation_while_owner_is_active(tmp_path):
    tmp_path.chmod(0o700)
    program = ('from deploy.operator_activation import activation_lock; import sys; '
               'context=activation_lock(sys.argv[1]); context.__enter__()')
    with activation_lock(tmp_path):
        rival = subprocess.run([sys.executable, '-c', program, str(tmp_path)],
                               cwd=Path(__file__).parents[1], capture_output=True, timeout=10)
        assert rival.returncode != 0
        assert b'BlockingIOError' in rival.stderr
    next_owner = subprocess.run([sys.executable, '-c', program, str(tmp_path)],
                               cwd=Path(__file__).parents[1], capture_output=True, timeout=10)
    assert next_owner.returncode == 0, next_owner.stderr


def test_lock_does_not_follow_external_symlink(tmp_path):
    tmp_path.chmod(0o700)
    outside = tmp_path/'outside'
    outside.write_text('preserved')
    (tmp_path/'activation.lock').symlink_to(outside)
    with pytest.raises(OSError):
        with activation_lock(tmp_path):
            pass
    assert outside.read_text() == 'preserved'


def test_repeat_configuration_has_fresh_state_and_current_parent(monkeypatch, tmp_path):
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
        '0::/user.slice/unit.service\n' if path == Path('/proc/self/cgroup') else original(path, *a, **kw))
    template = {'operator_parent': '/stale/old-unit', 'state_root': '/old-state', 'image': 'retained'}
    first = current_configuration(template, tmp_path, 'mldsafail-activation-fixture.service')
    second = current_configuration(template, tmp_path, 'mldsafail-activation-fixture.service')
    assert first['state_root'] != second['state_root']
    assert first['operator_parent'] == '/sys/fs/cgroup/user.slice/unit.service'
    assert first['operator_unit'] == 'mldsafail-activation-fixture.service'
    assert template['operator_parent'] == '/stale/old-unit'
    assert first['acceptance_source_sha256'] == second['acceptance_source_sha256']


def test_lock_rejects_public_regular_file(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path/'activation.lock'
    path.write_text('')
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match='Private regular'):
        with activation_lock(tmp_path):
            pass


def test_repeat_native_gate_rejects_same_surviving_controller_and_incomplete_cleanup():
    spec = importlib.util.spec_from_file_location('repeat_gate', Path(__file__).parents[1]/'scripts/native_repeat_activation_verification.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def receipt(inode, epoch, state):
        return dict(schema='mldsafail.operator-activation-receipt.v1', passed=True,
                    cleanup_complete=True, job='fixture', native_cpu_gates_passed=False,
                    source_commit='source', source_sha256='digest',
                    operator_domain=dict(boot_id='boot', device=1, inode=inode),
                    daemon_epoch=epoch, driver_state=state)
    first, second = receipt(1, 'old', 'first'), receipt(2, 'new', 'second')
    module.assess([first, second], 'source', 'digest')
    second['operator_domain']['inode'] = 1
    with pytest.raises(RuntimeError, match='fresh controller'):
        module.assess([first, second], 'source', 'digest')
    second['operator_domain']['inode'] = 2
    second['cleanup_complete'] = False
    with pytest.raises(RuntimeError, match='completed fixture'):
        module.assess([first, second], 'source', 'digest')


def test_unreconciled_prior_activation_prevents_new_provision(monkeypatch, tmp_path):
    from deploy import operator_activation as activation
    from research.cpu_measurement import native_driver
    tmp_path.chmod(0o700)
    template = tmp_path/'template.json'
    template.write_text('{}')
    template.chmod(0o600)
    prior = tmp_path/('activation-'+'a'*32)
    prior.mkdir(mode=0o700)
    state = prior/'driver.json'
    state.write_text(json.dumps({'cleanup': {'cleanup_complete': False}}))
    state.chmod(0o600)
    attempts = []
    monkeypatch.setattr(activation, 'current_configuration', lambda *args: {'state_root': str(tmp_path/'fresh')})
    monkeypatch.setattr(native_driver, 'cleanup_state', lambda *a, **k: attempts.append('cleanup') or {'cleanup_complete': False})
    monkeypatch.setattr(native_driver, 'execute', lambda *a, **k: attempts.append('forbidden_new_daemon'))
    config = dict(schema='mldsafail.operator-activation.v1', driver_template=str(template),
                  activation_root=str(tmp_path), job='fixture', job_config=None, staging_socket=None)
    with pytest.raises(RuntimeError, match='Earlier activation remains fenced'):
        activation.execute(config, 'mldsafail-fixture.service')
    assert attempts == ['cleanup']


def test_daily_callback_keeps_stage_endpoint_and_injects_only_restore_manifest(monkeypatch, tmp_path):
    from deploy import operator_activation as activation, daily_recovery
    from research.cpu_measurement import native_driver
    tmp_path.chmod(0o700)
    template, private = tmp_path/'template.json', tmp_path/'daily.json'
    template.write_text('{}')
    private.write_text(json.dumps({'backup': {'repository': 'synthetic'}}))
    template.chmod(0o600)
    private.chmod(0o600)
    monkeypatch.setenv('DOCKER_HOST', 'unix:///isolated/newdaemon.sock')
    observed = []
    monkeypatch.setattr(activation, 'current_configuration', lambda *args:
        dict(state_root=str(tmp_path/'new'), source_commit='a'*40, acceptance_source_sha256='b'*64))
    def daily(config):
        observed.append((os.environ['DOCKER_HOST'], config['backup']))
        return {'daily_recovery_verified': True}
    monkeypatch.setattr(daily_recovery, 'run', daily)
    def driver(config, repository, *, acceptance, daemon_kind):
        root = Path(config['state_root'])
        root.mkdir(mode=0o700)
        journal = native_driver.Journal(root/'driver.json', {})
        receipt = acceptance(journal, config, {'manifest_path': '/private/new-owned-manifest.json'})
        assert receipt['passed'] is True
        return dict(provisioning={'operator_domain': {}}, registered_manifest={'epoch': 'new', 'worker_domain': {}}, cleanup={'cleanup_complete': True})
    monkeypatch.setattr(native_driver, 'execute', driver)
    config = dict(schema='mldsafail.operator-activation.v1', driver_template=str(template),
        activation_root=str(tmp_path), job='daily-recovery', job_config=str(private),
        staging_socket='/run/user/'+str(os.getuid())+'/docker.sock')
    activation.execute(config, 'mldsafail-offhost-backup.service')
    assert observed == [('unix:///run/user/'+str(os.getuid())+'/docker.sock',
                        {'repository': 'synthetic', 'owned_daemon_manifest': '/private/new-owned-manifest.json'})]
    assert os.environ['DOCKER_HOST'] == 'unix:///isolated/newdaemon.sock'
    assert json.loads(private.read_text()) == {'backup': {'repository': 'synthetic'}}
