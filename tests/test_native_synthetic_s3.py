import hashlib
from pathlib import Path
import pytest
from deploy import native_synthetic_s3 as native


def test_synthetic_native_refuses_other_platform_without_output(tmp_path, monkeypatch):
    monkeypatch.setattr(native.sys, 'platform', 'darwin')
    with pytest.raises(RuntimeError, match='Native Linux'):
        native.execute(tmp_path / 'output', tmp_path)
    assert not (tmp_path / 'output').exists()


def test_binary_digest_is_streamed(tmp_path):
    path = tmp_path / 'artifact'; path.write_bytes(b'x' * (3 * 1024 * 1024))
    assert native.digest(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_native_refuses_existing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(native.sys, 'platform', 'linux')
    output = tmp_path / 'existing'; output.mkdir()
    (output / 'earlier').write_text('preserved failure')
    with pytest.raises(ValueError, match='Fresh private'):
        native.execute(output, tmp_path)
    assert (output / 'earlier').read_text() == 'preserved failure'


def test_synthetic_cleanup_independent_and_retryable(tmp_path, monkeypatch):
    import json
    calls = []
    def failed(self): calls.append('client'); raise RuntimeError('injected')
    monkeypatch.setattr(native.Journal, 'cleanup', failed)
    (tmp_path / 'server-clients.json').write_text(json.dumps({'clients': [{'id': 'server'}]}))
    (tmp_path / 'server-clients.json').chmod(0o600)
    monkeypatch.setattr(native.owned_client, 'stop', lambda entry: calls.append(entry['id']))
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        native.cleanup(tmp_path)
    assert calls == ['client', 'server']
    assert not json.loads(list(tmp_path.glob('cleanup-*.json'))[0].read_text())['cleanup_complete']
    monkeypatch.setattr(native.Journal, 'cleanup', lambda self: None)
    assert native.cleanup(tmp_path)['cleanup_complete']
    assert len(list(tmp_path.glob('cleanup-*.json'))) == 2


def test_cleanup_cannot_race_held_execution_lock(tmp_path):
    with native.run_lock(tmp_path / 'run'):
        with pytest.raises(BlockingIOError):
            native.cleanup(tmp_path / 'run')
    assert not list(tmp_path.glob('run/cleanup-*.json'))
