import hashlib
from pathlib import Path
import sys
import pytest
from deploy.render_activation_units import render


def metadata(source):
    files = [*sorted((source/'deploy').glob('*.py')), *sorted((source/'research/cpu_measurement').glob('*.py')),
             source/'research/cpu_measurement/templates/owned-daemon.service.in']
    return dict(source_commit='a'*40, source_files_sha256={str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})


def test_inactive_units_use_actual_activation_controller_and_terminal_cleanup(tmp_path):
    source = Path(__file__).resolve().parents[1]
    output = tmp_path/'rendered'
    report = render(str(source), sys.executable, metadata(source),
                    {'fixture': str(tmp_path/'missing-private-fixture.json')}, str(output))
    unit = (output/'mldsafail-activation-fixture.service').read_text()
    assert 'Delegate=yes' in unit and 'KillMode=control-group' in unit
    assert '--unit %n' in unit and 'ExecStopPost=' in unit and '--cleanup' in unit
    assert 'User=' not in unit and 'system.slice' not in unit
    assert report['manager'] == 'systemd-user'
    assert report['installed'] is False and report['activated'] is False
    assert report['configuration']['fixture'] == 'missing_activation_blocked'


def test_operator_source_hash_mismatch_prevents_rendering(tmp_path):
    source = Path(__file__).resolve().parents[1]
    identities = metadata(source)
    identities['source_files_sha256']['deploy/operator_activation.py'] = '0'*64
    with pytest.raises(ValueError, match='source hashes'):
        render(str(source), sys.executable, identities, {'fixture': str(tmp_path/'config')}, str(tmp_path/'never-created'))
    assert not (tmp_path/'never-created').exists()
