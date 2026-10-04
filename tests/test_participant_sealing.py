import hashlib
import os
import stat

import pytest

from scripts.seal_participant_artifacts import seal


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sealing_never_chmods_symlink_targets_or_partially_seals(tmp_path):
    root = tmp_path / 'owned'
    root.mkdir()
    external = tmp_path / 'shared-interpreter'
    external.write_text('executable')
    external.chmod(0o755)
    ordinary = root / 'wheel'
    ordinary.write_text('artifact')
    ordinary.chmod(0o600)
    (root / 'python').symlink_to(external)
    with pytest.raises(OSError):
        seal(root, {'wheel': digest(ordinary), 'python': digest(external)})
    assert stat.S_IMODE(external.stat().st_mode) == 0o755
    assert stat.S_IMODE(ordinary.stat().st_mode) == 0o600
    (root / 'directory').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        seal(root, {'directory/shared-interpreter': digest(external)})
    assert stat.S_IMODE(external.stat().st_mode) == 0o755
    os.link(external, root / 'hardlinked-interpreter')
    with pytest.raises(ValueError):
        seal(root, {'hardlinked-interpreter': digest(external)})
    assert stat.S_IMODE(external.stat().st_mode) == 0o755
    assert seal(root, {'wheel': digest(ordinary)}) == {'sealed_artifacts': 1}
    assert stat.S_IMODE(ordinary.stat().st_mode) == 0o400


def test_sealing_refuses_environment_and_escape_paths(tmp_path):
    for path in ('../external', '/external', 'installed/bin/python', '.venv/bin/python'):
        with pytest.raises(ValueError):
            seal(tmp_path, {path: 'a' * 64})
    link = tmp_path / 'symlink-root'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        seal(link, {'artifact': 'a' * 64})
