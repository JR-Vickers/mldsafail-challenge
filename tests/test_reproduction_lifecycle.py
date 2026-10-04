import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from scripts.reproduction_lifecycle import LABEL, ReproductionRun


def test_reproduction_requires_immutable_image_and_private_cleanup_authority(tmp_path):
    with pytest.raises(ValueError, match='Immutable'):
        ReproductionRun(tmp_path / 'fresh', ['mutable:tag'])
    root = tmp_path / 'owned'
    root.mkdir(mode=0o700)
    (root / 'journal.json').write_text(json.dumps({'run_id': 'a' * 32, 'attempts': []}))
    root.chmod(0o755)
    with pytest.raises(ValueError, match='Private'):
        with ReproductionRun(root, [], cleanup_only=True):
            pass


def test_reproduction_persists_intent_timeout_and_partial_output(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, ['sha256:' + 'a' * 64])
    run.journal = {'run_id': 'a' * 32, 'attempts': []}
    def command(argv, **kwargs):
        if argv[:2] == ['docker', 'create']:
            assert json.loads((tmp_path / 'journal.json').read_text())['attempts'][0]['phase'] == 'create_intent'
            assert '--label' in argv
            return SimpleNamespace(returncode=0)
        if argv[:2] == ['docker', 'start']:
            kwargs['stdout'].write(b'partial-output')
            raise subprocess.TimeoutExpired(argv, 65)
        if argv[:3] == ['docker', 'container', 'inspect']:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{'Config': {'Labels': {LABEL: 'a' * 32}}}]).encode())
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('scripts.reproduction_lifecycle.subprocess.run', command)
    with pytest.raises(subprocess.TimeoutExpired):
        run.invoke(run.images[0], ['-m', 'worker'], b'public-input')
    journal = json.loads((tmp_path / 'journal.json').read_text())
    assert journal['attempts'][0]['error_type'] == 'TimeoutExpired'
    assert next(tmp_path.glob('*.stdout')).read_bytes() == b'partial-output'


def test_reproduction_cleanup_rejects_other_owner_and_proves_remaining_inventory(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, [])
    run.journal = {'run_id': 'a' * 32, 'attempts': []}
    monkeypatch.setattr('scripts.reproduction_lifecycle.subprocess.check_output', lambda *_args, **_kwargs: b'container-id\n')
    monkeypatch.setattr('scripts.reproduction_lifecycle.subprocess.run', lambda *_args, **_kwargs:
        SimpleNamespace(returncode=0, stdout=json.dumps([{'Config': {'Labels': {LABEL: 'other'}}}]).encode()))
    assert run.cleanup() is False
    assert run.journal['remaining_owned_containers'] == ['container-id']
    assert run.journal['cleanup_errors'] == ['ValueError']
