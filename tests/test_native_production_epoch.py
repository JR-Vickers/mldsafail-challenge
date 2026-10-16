import hashlib
import json
from types import SimpleNamespace

import pytest

from deploy import owned_daemon
from scripts.native_production_epoch import callback


@pytest.fixture(autouse=True)
def host_floor(monkeypatch):
    monkeypatch.setattr('scripts.native_production_epoch.require_host_floor', lambda: None)


def setup(tmp_path):
    state = tmp_path / 'state'
    state.mkdir()
    protocol = dict(schema='mldsafail.production-epoch.v1', benchmark_version='0.5.0',
                    purpose='disposable_rehearsal_only', worker='sha256:' + 'a' * 64,
                    coordinator='sha256:' + 'b' * 64)
    protocol_path = tmp_path / 'production-epoch-protocol.json'
    owned_daemon.publish(protocol_path, protocol)
    review_path = tmp_path / 'review.json'
    owned_daemon.publish(review_path, dict(production_epoch_protocol_sha256=
                                         hashlib.sha256(protocol_path.read_bytes()).hexdigest()))
    return state, dict(review_packet=str(review_path), acceptance_source_sha256='c' * 64), dict(
        id='d' * 32, socket=str(tmp_path / 'docker.sock'), worker_slice='owned.slice',
        loaded_images=[protocol['worker'], protocol['coordinator']])


def test_failed_epoch_is_never_retried_or_audited(tmp_path):
    state, config, data = setup(tmp_path)
    calls = []
    def fail(argv, **kwargs):
        calls.append(kwargs['kind'])
        raise RuntimeError('frozen viability failed')
    journal = SimpleNamespace(path=state / 'driver.json', command=fail)
    with pytest.raises(RuntimeError, match='viability'):
        callback(journal, config, data)
    report = json.loads((state / 'rehearsal-epoch/report.json').read_text())
    assert report['passed'] is False and report['epoch_attempts'] == 1
    assert calls == ['fresh_epoch']
    with pytest.raises(FileExistsError):
        callback(journal, config, data)
    assert calls == ['fresh_epoch']


def test_epoch_requires_seal_before_independent_audit(tmp_path):
    state, config, data = setup(tmp_path)
    calls = []
    def unsealed(argv, **kwargs):
        calls.append(kwargs['kind'])
        return SimpleNamespace(stdout=b'', stderr=b'')
    with pytest.raises(RuntimeError, match='did not complete'):
        callback(SimpleNamespace(path=state / 'driver.json', command=unsealed), config, data)
    assert calls == ['fresh_epoch']


def test_complete_epoch_is_audited_in_separate_controller(tmp_path):
    state, config, data = setup(tmp_path)
    calls = []
    def command(argv, **kwargs):
        calls.append(kwargs['kind'])
        if kwargs['kind'] == 'fresh_epoch':
            epoch = state / 'rehearsal-epoch/evaluator/epoch'
            epoch.mkdir()
            (epoch / 'COMPLETE.json').write_text('{}')
            return SimpleNamespace(stdout=b'', stderr=b'')
        return SimpleNamespace(stdout=b'{"epoch_id":"fresh","reference_cases":100}', stderr=b'')
    receipt = callback(SimpleNamespace(path=state / 'driver.json', command=command), config, data)
    report = json.loads((state / 'rehearsal-epoch/report.json').read_text())
    assert receipt['passed'] and report['passed'] and report['independently_audited']
    assert calls == ['fresh_epoch', 'epoch_audit']


def test_unreviewed_protocol_never_executes_controller(tmp_path):
    state, config, data = setup(tmp_path)
    owned_daemon.publish(tmp_path / 'review.json', {})
    with pytest.raises(ValueError, match='reviewed'):
        callback(SimpleNamespace(path=state / 'driver.json'), config, data)
    assert not (state / 'rehearsal-epoch').exists()
