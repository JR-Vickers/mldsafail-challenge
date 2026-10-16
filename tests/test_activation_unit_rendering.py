import hashlib
from pathlib import Path
import sys
import subprocess
import shutil
import pytest
from deploy.render_activation_units import render


def metadata(source):
    files = [*sorted((source/'deploy').glob('*.py')), *sorted((source/'research/cpu_measurement').glob('*.py')),
             source/'research/cpu_measurement/templates/owned-daemon.service.in']
    return dict(source_commit=subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip(), source_files_sha256={str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})


@pytest.fixture
def retained_source(tmp_path):
    source = tmp_path/'source'
    original = Path(__file__).resolve().parents[1]
    shutil.copytree(original/'deploy', source/'deploy', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(original/'research/cpu_measurement', source/'research/cpu_measurement', ignore=shutil.ignore_patterns('__pycache__'))
    subprocess.run(['git', 'init', str(source)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(source), '-c', 'user.name=Operator Fixture', '-c', 'user.email=fixture@example.invalid',
                    '-c', 'commit.gpgSign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Retained operator fixture'], check=True, capture_output=True)
    return source


def test_inactive_units_use_actual_activation_controller_and_terminal_cleanup(tmp_path, retained_source):
    source = retained_source
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


def test_operator_source_hash_mismatch_prevents_rendering(tmp_path, retained_source):
    source = retained_source
    identities = metadata(source)
    identities['source_files_sha256']['deploy/operator_activation.py'] = '0'*64
    with pytest.raises(ValueError, match='source hashes'):
        render(str(source), sys.executable, identities, {'fixture': str(tmp_path/'config')}, str(tmp_path/'never-created'))
    assert not (tmp_path/'never-created').exists()


def test_unrelated_claimed_source_commit_cannot_render_units(tmp_path, retained_source):
    identities = metadata(retained_source)
    identities['source_commit'] = 'a'*40
    with pytest.raises(ValueError, match='clean retained source commit'):
        render(str(retained_source), sys.executable, identities, {'fixture': str(tmp_path/'config')}, str(tmp_path/'never-created'))
    assert not (tmp_path/'never-created').exists()


def test_dirty_operator_source_cannot_render_units(tmp_path, retained_source):
    identities = metadata(retained_source)
    (retained_source/'deploy/operator_activation.py').write_text('# changed operator\n')
    with pytest.raises(ValueError, match='clean retained source commit'):
        render(str(retained_source), sys.executable, identities, {'fixture': str(tmp_path/'config')}, str(tmp_path/'never-created'))
