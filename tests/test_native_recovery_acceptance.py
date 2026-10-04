import fcntl
from types import SimpleNamespace

import pytest

from deploy.native_recovery_acceptance import child, run


def test_fixture_requires_preloaded_immutable_image(tmp_path, monkeypatch):
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',
                        lambda _: pytest.fail('Docker must not run with unpinned image'))
    with pytest.raises(ValueError, match='immutable'):
        run(SimpleNamespace(output=tmp_path / 'new', image='alpine:latest'))


def test_competing_child_cannot_touch_services(tmp_path, monkeypatch):
    lock = (tmp_path / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr('deploy.native_recovery_acceptance.command',
                        lambda _: pytest.fail('Competing owner must not touch Docker'))
    with pytest.raises(BlockingIOError):
        child(tmp_path, 'race', False)
