import hashlib
import io
import json
import tarfile

import pytest

from scripts.participant_download import build


def source_fixture(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    for name, content in {
        'docs/PARTICIPANT_DOWNLOAD_README.md': '[contract](docs/PRIMITIVE_SELECTION_SPEC.md)\n',
        'docs/PRIMITIVE_SELECTION_SPEC.md': '[omitted operator context](PRIVATE.md) and [NIST](https://csrc.nist.gov/)\n',
        'examples/mlwe/primal-lll/solver.py': 'def solve(x): return None\n',
        'scripts/install.sh': '# public installer\n',
    }.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    monkeypatch.setattr('scripts.participant_download.subprocess.check_output',
                        lambda argv: b'' if '--porcelain' in argv else b'a' * 40 + b'\n')
    wheel = tmp_path / 'mldsafail_challenge-0.5.1-py3-none-any.whl'
    wheel.write_bytes(b'owner-reviewed-wheel-fixture')
    return source, wheel


def test_participant_archive_deterministic_allowlist_and_links(tmp_path, monkeypatch):
    source, wheel = source_fixture(tmp_path, monkeypatch)
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    first = build(source, wheel, tmp_path / 'first', checksum, {'source_commit':'b'*40,'wheel_sha256':checksum})
    second = build(source, wheel, tmp_path / 'second', checksum, {'source_commit':'b'*40,'wheel_sha256':checksum})
    assert first == second
    data = (tmp_path / 'first/participant-download-candidate.tar.gz').read_bytes()
    assert data == (tmp_path / 'second/participant-download-candidate.tar.gz').read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        assert all(item.isfile() and item.uid == 0 and item.mtime == 0 for item in archive)
        specification = archive.extractfile('mldsafail-participant-0.5.1/docs/PRIMITIVE_SELECTION_SPEC.md').read().decode()
        assert '(PRIVATE.md)' not in specification
        assert '[NIST](https://csrc.nist.gov/)' in specification
        fixtures = json.load(archive.extractfile('mldsafail-participant-0.5.1/public-fixtures.json'))
        assert len(fixtures) == 6
    assert first['publication_approved'] is False
    assert first['wheel_source_commit'] == 'b' * 40
    assert first['archive_documentation_source_commit'] == 'a' * 40


def test_participant_archive_rejects_broken_links_and_wrong_wheel(tmp_path, monkeypatch):
    source, wheel = source_fixture(tmp_path, monkeypatch)
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='checksum'):
        build(source, wheel, tmp_path / 'wrong', '0' * 64, {'source_commit':'b'*40,'wheel_sha256':checksum})
    (source / 'docs/PARTICIPANT_DOWNLOAD_README.md').write_text('[missing](missing.md)\n')
    with pytest.raises(ValueError, match='Broken'):
        build(source, wheel, tmp_path / 'broken', checksum, {'source_commit':'b'*40,'wheel_sha256':checksum})


def test_source_export_uses_historical_allowlist(tmp_path):
    import subprocess
    from scripts.participant_download import prepare_source
    source = tmp_path / 'repo'
    source.mkdir()
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    for name in ('pyproject.toml', 'LICENSE', 'examples/mlwe/primal-lll/solver.py',
                 'src/mldsafail/__init__.py', 'results/private.json',
                 'scripts/operator.py', 'docs/PARTICIPANT_DOWNLOAD_README.md'):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# fixture\n')
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test', '-c',
                    'user.email=test@example.invalid', '-c', 'commit.gpgsign=false',
                    'commit', '-qm', 'fixture'], check=True)
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip()
    (source / 'src/mldsafail/__init__.py').write_text('uncommitted replacement')
    with pytest.raises(ValueError, match='outside the checkout'):
        prepare_source(source, revision, source / 'export')
    destination = tmp_path / 'export'
    identity = prepare_source(source, revision, destination)
    assert (destination / 'src/mldsafail/__init__.py').read_text() == '# fixture\n'
    assert not (destination / 'results').exists()
    assert not (destination / 'scripts').exists()
    assert identity['wheel_source_commit'] == revision
    with pytest.raises(ValueError, match='New destination'):
        prepare_source(source, revision, destination)
