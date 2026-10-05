import json
from types import SimpleNamespace

import pytest

from scripts import native_application_acceptance as module


def test_requires_both_exact_images_before_native_mutations(tmp_path, monkeypatch):
    monkeypatch.setattr(module.native_postgres_acceptance, 'run', lambda *a: pytest.fail('Unexpected mutation'))
    with pytest.raises(RuntimeError, match='Exact retained'):
        module.acceptance(SimpleNamespace(path=tmp_path / 'driver.json'), {}, {'loaded_images': []})


def test_incomplete_postgres_cleanup_blocks_application_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(module.native_postgres_acceptance, 'run', lambda *a: None)
    monkeypatch.setattr(module.owned_daemon, 'read_private_json', lambda *a, **k: {'passed': True, 'cleanup_complete': False})
    journal = SimpleNamespace(path=tmp_path / 'driver.json', command=lambda *a, **k: pytest.fail('Unexpected application mutation'))
    with pytest.raises(RuntimeError, match='Complete native PostgreSQL'):
        module.acceptance(journal, {}, {'loaded_images': [module.DATABASE_IMAGE, module.WEB_IMAGE]})


def test_nonzero_application_exit_cannot_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(module.native_postgres_acceptance, 'run', lambda *a: None)
    monkeypatch.setattr(module.owned_daemon, 'read_private_json', lambda *a, **k: {'passed': True, 'cleanup_complete': True})
    identifier = 'a' * 64
    outputs = iter([identifier.encode(), json.dumps({'passed': True}).encode(), json.dumps([
        {'Id': identifier, 'Image': module.WEB_IMAGE, 'Name': '/mldsafail-token-probe-test',
         'State': {'Running': False, 'ExitCode': 1}}]).encode()])
    journal = SimpleNamespace(path=tmp_path / 'driver.json', command=lambda *a, **k: SimpleNamespace(stdout=next(outputs)))
    with pytest.raises(RuntimeError, match='expired-token acceptance failed'):
        module.acceptance(journal, {}, {'loaded_images': [module.DATABASE_IMAGE, module.WEB_IMAGE], 'id': 'test', 'worker_slice': 'isolated.slice'})
    probe = tmp_path / 'expired-token-probe.py'
    assert probe.stat().st_mode & 0o777 == 0o644
    assert probe.read_bytes() == module.Path(module.__file__).with_name('native_expired_token_probe.py').read_bytes()


def test_probe_staging_never_overwrites_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(module.native_postgres_acceptance, 'run', lambda *a: None)
    monkeypatch.setattr(module.owned_daemon, 'read_private_json', lambda *a, **k: {'passed': True, 'cleanup_complete': True})
    probe = tmp_path / 'expired-token-probe.py'
    probe.write_text('existing evidence')
    journal = SimpleNamespace(path=tmp_path / 'driver.json', command=lambda *a, **k: pytest.fail('Unexpected application mutation'))
    with pytest.raises(FileExistsError):
        module.acceptance(journal, {}, {'loaded_images': [module.DATABASE_IMAGE, module.WEB_IMAGE]})
    assert probe.read_text() == 'existing evidence'
