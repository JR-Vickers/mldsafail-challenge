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
    def command(_self, argv, **kwargs):
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
    monkeypatch.setattr('scripts.reproduction_lifecycle.ReproductionRun.command', command)
    with pytest.raises(subprocess.TimeoutExpired):
        run.invoke(run.images[0], ['-m', 'worker'], b'public-input')
    journal = json.loads((tmp_path / 'journal.json').read_text())
    assert journal['attempts'][0]['error_type'] == 'TimeoutExpired'
    assert next(tmp_path.glob('*.stdout')).read_bytes() == b'partial-output'


def test_reproduction_cleanup_rejects_other_owner_and_proves_remaining_inventory(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, [])
    run.journal = {'run_id': 'a' * 32, 'attempts': []}
    def command(_self, argv, **_kwargs):
        data = b'container-id\n' if argv[:3] == ['docker', 'ps', '-aq'] else json.dumps([{'Config': {'Labels': {LABEL: 'other'}}}]).encode()
        return SimpleNamespace(returncode=0, stdout=data)
    monkeypatch.setattr('scripts.reproduction_lifecycle.ReproductionRun.command', command)
    assert run.cleanup() is False
    assert run.journal['remaining_owned_containers'] == ['container-id']
    assert run.journal['cleanup_errors'] == ['ValueError']


def test_cleanup_retains_client_failure_even_when_container_inventory_empty(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, [])
    run.journal = {'run_id': 'a' * 32, 'attempts': [], 'clients': [{'pid': 123}]}
    def refuse(_):
        raise RuntimeError('identity mismatch')
    monkeypatch.setattr('scripts.reproduction_lifecycle.owned_client.stop', refuse)
    monkeypatch.setattr('scripts.reproduction_lifecycle.ReproductionRun.command', lambda *_args, **_kwargs: SimpleNamespace(stdout=b''))
    assert run.cleanup() is False
    assert run.journal['cleanup_errors'] == ['RuntimeError']
    assert run.journal['remaining_owned_containers'] == []


def test_reproduction_cleanup_publication_failure_does_not_skip_removal_or_final_inventory(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, [])
    run.journal = {'run_id': 'a' * 32, 'clients': [], 'attempts': []}
    calls = []
    def command(_self, argv, **_kwargs):
        calls.append(argv)
        if argv[:3] == ['docker', 'ps', '-aq']:
            return SimpleNamespace(stdout=b'owned-container\n' if len(calls) == 1 else b'')
        if argv[:3] == ['docker', 'container', 'inspect']:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{'Config': {'Labels': {LABEL: 'a' * 32}}}]).encode())
        return SimpleNamespace(returncode=0, stdout=b'')
    monkeypatch.setattr('scripts.reproduction_lifecycle.ReproductionRun.command', command)
    monkeypatch.setattr(run, 'save', lambda: (_ for _ in ()).throw(OSError('publication failure')))
    assert run.cleanup() is False
    assert ['docker', 'rm', '-f', 'owned-container'] in calls
    assert calls[-1][:3] == ['docker', 'ps', '-aq']
    assert run.journal['remaining_owned_containers'] == []
    assert len(run.journal['cleanup_errors']) == 2


def test_reproduction_empty_inventory_does_not_clear_unknown_daemon_mutation(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, [])
    run.journal = {'run_id': 'a' * 32, 'clients': [], 'daemon_mutations': [{'acknowledged': False}]}
    monkeypatch.setattr('scripts.reproduction_lifecycle.ReproductionRun.command', lambda *_args, **_kwargs: SimpleNamespace(stdout=b''))
    assert run.cleanup() is False
    assert run.journal['remaining_owned_containers'] == []
    assert 'DaemonMutationUncertainty' in run.journal['cleanup_errors'][0]


def test_original_invocation_failure_survives_publication_and_removal_failure(tmp_path, monkeypatch):
    run = ReproductionRun(tmp_path, ['sha256:' + 'a' * 64])
    run.journal = {'run_id': 'a' * 32, 'attempts': []}
    saves = 0
    def save():
        nonlocal saves
        saves += 1
        if saves > 1:
            raise OSError('publication failure')
    monkeypatch.setattr(run, 'save', save)
    monkeypatch.setattr(run, 'command', lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError('original create failure')))
    monkeypatch.setattr(run, 'remove', lambda *_args: (_ for _ in ()).throw(RuntimeError('removal failure')))
    with pytest.raises(ValueError, match='original create failure') as caught:
        run.invoke(run.images[0], ['-m', 'worker'], b'public')
    assert len(caught.value.__notes__) == 2
    assert run.journal['attempts'][0]['error_type'] == 'ValueError'
