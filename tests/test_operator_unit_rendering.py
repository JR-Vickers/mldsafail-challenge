import hashlib
import json
from pathlib import Path
import sys

import pytest

from deploy.render_operator_units import render


def inputs(tmp_path):
    source = tmp_path / 'operator-source'
    deploy = source / 'deploy'
    deploy.mkdir(parents=True)
    for name in ('__init__', 'daily_recovery', 'recovery', 'host_checks', 'helper'):
        (deploy / (name + '.py')).write_text('"""isolated source fixture"""\n')
    metadata = {'source_commit': 'a' * 40,
                'source_files_sha256': {str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in deploy.glob('*.py')}}
    configs = {name: str(tmp_path / (name + '.json')) for name in ('daily-recovery', 'recovery', 'monitor')}
    return source, metadata, configs


def test_inactive_unit_render_binds_source_interpreter_and_rootless_environment(tmp_path):
    source, metadata, configs = inputs(tmp_path)
    output = tmp_path / 'units'
    result = render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(output))
    assert result['activated'] is False and result['installed'] is False
    assert result['module_source_verified'] is True
    assert all(status == 'missing_activation_blocked' for status in result['configuration'].values())
    assert len(result['unit_sha256']) == 3
    backup = (output / 'mldsafail-offhost-backup.service').read_text()
    assert 'WorkingDirectory=' + str(source) in backup
    assert 'Environment=DOCKER_HOST=unix:///run/user/1001/docker.sock' in backup
    assert 'Environment=XDG_RUNTIME_DIR=/run/user/1001' in backup
    assert 'Delegate=yes' in backup
    assert 'Environment=MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT=/sys/fs/cgroup/system.slice/%n' in backup
    assert 'ExecStopPost=' + sys.executable + ' -m deploy.daily_recovery --cleanup' in backup
    assert '/srv/mldsafail/current' not in backup
    assert output.stat().st_mode & 0o077 == 0
    assert json.loads((output / 'render-report.json').read_text()) == result
    with pytest.raises(ValueError, match='new'):
        render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(output))


def test_unit_render_rejects_mutated_helpers_and_public_configs(tmp_path):
    source, metadata, configs = inputs(tmp_path)
    (source / 'deploy/helper.py').write_text('changed\n')
    with pytest.raises(ValueError, match='metadata'):
        render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(tmp_path / 'units'))
    (source / 'deploy/helper.py').write_text('"""isolated source fixture"""\n')
    config = Path(configs['monitor'])
    config.write_text('{}')
    config.chmod(0o644)
    with pytest.raises(ValueError, match='private'):
        render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(tmp_path / 'units'))


def test_unit_render_rejects_root_user_and_command_injection(tmp_path):
    source, metadata, configs = inputs(tmp_path)
    for user, uid in [('root', 0), ('root', 1001), ('bad user', 1001)]:
        with pytest.raises(ValueError):
            render(str(source), sys.executable, metadata, configs, user, uid, str(tmp_path / 'units'))
    configs['monitor'] += ';command'
    with pytest.raises(ValueError):
        render(str(source), sys.executable, metadata, configs, 'mldsafail', 1001, str(tmp_path / 'units'))


def test_monitor_only_needs_no_recovery_configuration(tmp_path):
    source, metadata, configs = inputs(tmp_path)
    output = tmp_path / 'monitor-units'
    result = render(str(source), sys.executable, metadata, {'monitor': configs['monitor']},
                    'mldsafail', 1001, str(output), monitor_only=True)
    assert set(result['unit_sha256']) == {'mldsafail-monitor.service', 'mldsafail-monitor.timer'}
    assert set(result['configuration']) == {'monitor'}
    assert 'OnUnitActiveSec=5min' in (output / 'mldsafail-monitor.timer').read_text()
    assert not (output / 'mldsafail-offhost-backup.service').exists()


def test_monitor_socket_is_explicit_and_private(tmp_path):
    source, metadata, configs = inputs(tmp_path)
    output = tmp_path / 'monitor-units'
    render(str(source), sys.executable, metadata, {'monitor': configs['monitor']},
           'mldsafail', 1001, str(output), monitor_only=True, docker_socket='/tmp/rehearsal/docker.sock')
    assert 'Environment=DOCKER_HOST=unix:///tmp/rehearsal/docker.sock' in (output / 'mldsafail-monitor.service').read_text()
