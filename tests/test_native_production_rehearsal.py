"""Terminal failure paths must preserve negative rehearsal disposition."""
import contextlib
import json
from pathlib import Path

import pytest

from deploy import owned_daemon, owned_client, recovery_daemon
from scripts import native_production_rehearsal as native
from scripts import production_rehearsal_monitor_load as monitoring


def setup_terminal(tmp_path, monkeypatch):
    metadata = tmp_path / 'metadata.json'
    owned_daemon.publish(metadata, {})
    review = tmp_path / 'review.json'
    owned_daemon.publish(review, dict(production_terminal_cleanup_review_passed=True,
        acceptance_source_sha256=native.digest(native.__file__), operator_source_manifest=str(metadata),
        operator_source_manifest_sha256=native.digest(metadata)))
    state = tmp_path / 'driver.json'
    owned_daemon.publish(state, dict(schema='mldsafail.cpu-native-driver-state.v1', provisioning={'id': 'owned'}, socket='/tmp/owned.sock'))
    root = tmp_path / 'production'
    root.mkdir()
    owned_daemon.publish(root / 'journal.json', dict(dedicated_daemon=dict(provisioning={'id': 'owned'})))
    owned_daemon.publish(root / 'clients.json', {})
    (root / 'clients.json').write_text('[]')
    monkeypatch.setattr(native, 'verify_sources', lambda *a: None)
    monkeypatch.setattr(native.native_driver, 'validate', lambda *a: None)
    monkeypatch.setattr(native.production_rehearsal, 'cleanup_authority', lambda *a: None)
    monkeypatch.setattr(recovery_daemon, 'provision_lock', lambda *a: contextlib.nullcontext())
    monkeypatch.setattr(monitoring, 'stop_monitors', lambda *a: None)
    monkeypatch.setattr(native.native_driver, 'cleanup_state', lambda *a, **kw:
                        dict(cleanup_complete=True, daemon_barrier=dict(shutdown_proven=True)))
    return state, root, dict(review_packet=str(review))


@pytest.mark.parametrize('fault', ['missing_journal', 'corrupt_journal', 'changed_monitor', 'malformed_clients', 'missing_barrier', None])
def test_terminal_cleanup_requires_all_nested_and_daemon_proofs(tmp_path, monkeypatch, fault):
    state, root, config = setup_terminal(tmp_path, monkeypatch)
    daemon_calls = []
    def daemon(*args, **kwargs):
        daemon_calls.append(True)
        return dict(cleanup_complete=True, daemon_barrier=dict(shutdown_proven=fault != 'missing_barrier'))
    monkeypatch.setattr(native.native_driver, 'cleanup_state', daemon)
    if fault == 'missing_journal': (root / 'journal.json').unlink()
    if fault == 'corrupt_journal': (root / 'journal.json').write_text('{')
    if fault == 'malformed_clients': (root / 'clients.json').write_text('{}')
    if fault == 'changed_monitor':
        def changed(*a): raise RuntimeError('changed fragment')
        monkeypatch.setattr(monitoring, 'stop_monitors', changed)
    receipt = native.terminal_cleanup(state, config, tmp_path)
    assert daemon_calls == [True]
    assert receipt['complete'] is (fault is None)
    assert receipt['authoritative_result_available'] is False
    if fault is None:
        assert json.loads((root / 'journal.json').read_text())['terminal_cleanup'] is True
    else:
        assert receipt['errors']


def test_terminal_controller_rejects_unknown_driver_before_monitor_control(tmp_path, monkeypatch):
    state, root, config = setup_terminal(tmp_path, monkeypatch)
    owned_daemon.publish(state, dict(schema='unknown'))
    monkeypatch.setattr(monitoring, 'stop_monitors', lambda *a: pytest.fail('Unknown journal controlled monitor'))
    with pytest.raises(ValueError, match='retained native driver'):
        native.terminal_cleanup(state, config, tmp_path)
