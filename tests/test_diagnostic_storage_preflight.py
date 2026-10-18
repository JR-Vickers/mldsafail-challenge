import io
import json
import tarfile
from types import SimpleNamespace

from scripts import diagnostic_storage_preflight as preflight


def image(path, payload):
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode='w') as stream:
        entry = tarfile.TarInfo('file'); entry.size = len(payload)
        stream.addfile(entry, io.BytesIO(payload))
    with tarfile.open(path, mode='w') as stream:
        for name, content in [('manifest.json', json.dumps([{'Layers': ['layer.tar']}]).encode()),
                              ('layer.tar', layer.getvalue())]:
            entry = tarfile.TarInfo(name); entry.size = len(content)
            stream.addfile(entry, io.BytesIO(content))


def test_identical_layers_are_deduplicated_and_failure_stops(tmp_path, monkeypatch):
    a, b = tmp_path / 'a.tar', tmp_path / 'b.tar'
    image(a, b'a' * 100); image(b, b'a' * 100)
    monkeypatch.setattr(preflight.shutil, 'disk_usage', lambda _: SimpleNamespace(free=5 * 1024**3 + 99))
    result = preflight.inspect([a, b])
    assert result['regular_file_lower_bound_bytes'] == 100
    assert result['unique_layers'] == 1 and result['provisioning_prohibited']
    assert not result['capacity_admitted'] and result['remote_writes'] == 0


def test_reused_name_with_different_bytes_is_not_deduplicated(tmp_path):
    import pytest
    a, b = tmp_path / 'a.tar', tmp_path / 'b.tar'
    image(a, b'a'); image(b, b'b')
    with pytest.raises(ValueError, match='identity changed'):
        preflight.inspect([a, b])
