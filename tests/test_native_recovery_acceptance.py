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


def test_owned_child_cleanup_is_idempotent_after_exit(tmp_path, monkeypatch):
    import json
    from deploy.native_recovery_acceptance import stop_owned_child
    (tmp_path / 'owner-process.json').write_text(json.dumps({'pid': 123}))
    def missing(pid):
        raise FileNotFoundError()
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity', missing)
    assert stop_owned_child(tmp_path) == {'already_stopped': True}
    assert stop_owned_child(tmp_path) == {'already_stopped': True}


def test_reused_child_identity_never_signalled(tmp_path, monkeypatch):
    import json
    from deploy.native_recovery_acceptance import stop_owned_child
    (tmp_path / 'owner-process.json').write_text(json.dumps({'pid': 123, 'start_ticks': 10}))
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity',
                        lambda _: {'pid': 123, 'start_ticks': 11})
    with pytest.raises(RuntimeError, match='ownership mismatch'):
        stop_owned_child(tmp_path)


def test_pidfd_identity_change_prevents_signal_and_closes_descriptor(tmp_path, monkeypatch):
    import json
    import os
    from deploy.native_recovery_acceptance import stop_owned_child
    identity = {'pid': 123, 'start_ticks': 10, 'uid': os.getuid(),
                'cmdline': '00', 'boot_id': 'fixture-boot'}
    (tmp_path / 'owner-process.json').write_text(json.dumps(identity))
    records = iter([identity, dict(identity, start_ticks=11)])
    closed = []
    monkeypatch.setattr('deploy.native_recovery_acceptance.process_identity', lambda _: next(records))
    monkeypatch.setattr('deploy.native_recovery_acceptance.os.pidfd_open', lambda _: 99, raising=False)
    monkeypatch.setattr('deploy.native_recovery_acceptance.signal.pidfd_send_signal',
                        lambda *args: pytest.fail('Changed owner must never receive signal'), raising=False)
    monkeypatch.setattr('deploy.native_recovery_acceptance.os.close', lambda descriptor: closed.append(descriptor))
    with pytest.raises(RuntimeError, match='changed before cancellation'):
        stop_owned_child(tmp_path)
    assert closed == [99]
