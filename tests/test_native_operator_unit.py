"""Wrong service identity must fail before any executable is released."""
from pathlib import Path
import os
import pytest
from scripts import native_operator_unit as runner


@pytest.mark.parametrize('field,value', [
    ('InvocationID', 'b' * 32), ('Delegate', 'no'), ('KillMode', 'process'),
    ('ControlGroup', '/foreign.service'), ('MainPID', '0'),
])
def test_foreign_or_undelegated_service_cannot_release_command(tmp_path, monkeypatch, field, value):
    unit = 'mldsafail-launch-test.service'
    group = '/user.slice/test/' + unit
    properties = dict(InvocationID='a' * 32, Delegate='yes', KillMode='control-group',
                      ControlGroup=group, MainPID=str(os.getpid()))
    properties[field] = value
    monkeypatch.setattr(runner.sys, 'platform', 'linux')
    monkeypatch.setattr(runner.os, 'getuid', lambda: 1000)
    monkeypatch.setenv('INVOCATION_ID', 'a' * 32)
    original_read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda self, *args, **kwargs:
        '0::' + group + '\n' if str(self) == '/proc/self/cgroup'
        else original_read(self, *args, **kwargs))
    monkeypatch.setattr(runner.subprocess, 'check_output', lambda *args, **kwargs:
        '\n'.join(key + '=' + val for key, val in properties.items()))
    released = []
    monkeypatch.setattr(runner.owned_client, 'run', lambda *args, **kwargs: released.append(True))
    journal = tmp_path / 'journal.json'
    with pytest.raises(RuntimeError, match='Actual service/controller identity'):
        runner.execute(unit, journal, ['touch', str(tmp_path / 'mutation')], 30)
    assert not released and not journal.exists() and not (tmp_path / 'mutation').exists()


def test_extended_budget_is_explicit_and_restricted_to_reviewed_rehearsal(tmp_path):
    command = [runner.sys.executable, '-B', '-m', 'scripts.native_production_rehearsal', '--config', str(tmp_path / 'config.json')]
    runner.validate_timeout(command, 21600, rehearsal_budget=True)
    with pytest.raises(ValueError, match='Bounded'):
        runner.validate_timeout(command, 21600)
    with pytest.raises(ValueError, match='reviewed production'):
        runner.validate_timeout(['sh', '-c', 'arbitrary'], 21600, rehearsal_budget=True)
    with pytest.raises(ValueError, match='Bounded'):
        runner.validate_timeout(command, 21601, rehearsal_budget=True)
