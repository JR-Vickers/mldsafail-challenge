"""Synthetic controller results across real SQL transactions and the host gate."""
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from mldsafail.evaluator.coordinator import CoordinatorConfig
from mldsafail.evaluator.dispatcher import Dispatcher
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.evaluator.workload import HostGate, WorkloadBlocked
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from mldsafail.web.models import EvaluationAttempt, EvaluationJob, ExperimentResult, Submission, User
from mldsafail.web.services import create_submission
from test_hosted_mlwe import COHORT, REQUEST, database
from test_workload import Runtime


class Controller(Runtime):
    def __init__(self):
        super().__init__(); self.mode = 'accepted'; self.launches = 0
    def launch(self, state, specification):
        self.launches += 1
        return super().launch(state, specification)
    def result(self, state):
        reference = state['reference']
        identity = {**reference['identity'], 'source_digest': 'a'*64}
        if self.mode == 'infrastructure_failed':
            content = dict(status='infrastructure_failed', code='controller_failure')
        else:
            verified = self.mode != 'rejected'
            payload = dict(**identity, verified=verified, score=.91 if verified else None,
                           diagnostics={'eligible': verified}, failure_class=None if verified else 'invalid_answer')
            content = dict(status='evaluated', source_digest='a'*64, envelope=sign_envelope(payload, b'k'*32))
        return sign_envelope(dict(binding=dict(workload_id=state['workload_id'], role='participant', reference=reference),
                                  **content), b'k'*32)


@pytest.fixture
def system(tmp_path):
    engine = database(tmp_path)
    with Session(engine) as session:
        user = User(display_name='synthetic'); session.add(user); session.commit()
        submission, _ = create_submission(session, user, REQUEST, 'key', cohort=COHORT)
        identifier = submission.id
    key = tmp_path/'key'; key.write_bytes(b'k'*32); key.chmod(0o600)
    config = CoordinatorConfig(str(engine.url), tmp_path, tmp_path/'unused', 'image', '0.5.0',
        COHORT['evaluator_fingerprint'], COHORT['hidden_suite_version'], COHORT['worker_class'],
        tmp_path/'private', tmp_path/'epoch', COHORT['epoch_id'], key, True, tmp_path/'supervisor.sock')
    runtime = Controller()
    with HostGate(tmp_path/'gate', runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'participant': {'role':'participant'}})
        client = WorkloadClient(config.supervisor_socket, tmp_path/'client', transport=lambda path, request: protocol.dispatch(request))
        dispatcher = Dispatcher(config, client=client)
        yield dispatcher, gate, runtime, engine, identifier


@pytest.mark.parametrize('mode', ['accepted', 'rejected', 'infrastructure_failed'])
def test_dispatcher_cleanup_precedes_db_result_and_release(system, mode, monkeypatch):
    import mldsafail.evaluator.dispatcher as module
    dispatcher, gate, runtime, engine, identifier = system
    runtime.mode = mode
    original = module.apply_outcome
    def apply(database, binding, **kwargs):
        assert not runtime.live
        assert gate.state['phase'] == 'commit_intent'
        assert gate.state['workload_id'] == binding['workload_id']
        return original(database, binding, **kwargs)
    monkeypatch.setattr(module, 'apply_outcome', apply)
    assert dispatcher.run_once()
    assert gate.state['phase'] == 'complete'
    assert runtime.launches == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ExperimentResult)) == (1 if mode=='accepted' else 0)
        attempt = session.scalar(select(EvaluationAttempt))
        assert attempt.status == mode
        job = session.scalar(select(EvaluationJob))
        assert job.status == ('queued' if mode=='infrastructure_failed' else 'complete')


def test_resource_deferral_consumes_no_attempt(system):
    dispatcher, gate, runtime, engine, _ = system
    runtime.ceiling = 0
    assert not dispatcher.run_once()
    with Session(engine) as session:
        job = session.scalar(select(EvaluationJob))
        assert job.status == 'queued' and job.attempts == 0
        assert session.scalar(select(func.count()).select_from(EvaluationAttempt)) == 0
    assert gate.state is None


@pytest.mark.parametrize('committed', [True, False])
def test_ambiguous_db_commit_never_recomputes_or_inserts_orphan_result(system, monkeypatch, committed):
    import mldsafail.evaluator.dispatcher as module
    dispatcher, gate, runtime, engine, _ = system
    original = module.apply_outcome
    def outage(database, binding, **kwargs):
        if committed: original(database, binding, **kwargs)
        raise OSError('lost database acknowledgement')
    monkeypatch.setattr(module, 'apply_outcome', outage)
    with pytest.raises(OSError): dispatcher.run_once()
    assert gate.state['phase'] == 'commit_intent'
    assert not runtime.live
    monkeypatch.setattr(module, 'apply_outcome', original)
    gate.state['heartbeat_deadline'] = 0  # Simulate dispatcher disconnection, not a live competitor.
    gate._write()
    assert dispatcher.run_once()
    assert runtime.launches == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ExperimentResult)) == int(committed)
        assert session.scalar(select(EvaluationAttempt)).status == ('accepted' if committed else 'infrastructure_failed')


def test_another_database_cannot_claim_while_host_owned(system, tmp_path):
    dispatcher, gate, runtime, engine, _ = system
    dispatcher.client.acquire('administration', {'owner':{'database':'different'}})
    assert not dispatcher.run_once()
    with Session(engine) as session:
        assert session.scalar(select(EvaluationJob)).attempts == 0


def test_protection_failure_has_no_score_and_no_automatic_retry(system):
    dispatcher, gate, runtime, engine, _ = system
    original = runtime.launch
    def launch(*args):
        result = original(*args)
        runtime.sample_data['oom_events'] = 1
        return result
    runtime.launch = launch
    with pytest.raises(WorkloadBlocked): dispatcher.run_once()
    assert gate.state['paused'] and not runtime.live
    # Resetting the sample does not clear the durable pause or permit a retry.
    runtime.sample_data['oom_events'] = 0
    assert dispatcher.run_once()
    assert gate.state['paused'] and gate.state['phase'] == 'committed'
    assert not dispatcher.run_once()
    with Session(engine) as session:
        assert session.scalar(select(EvaluationJob)).status == 'failed'
        assert session.scalar(select(func.count()).select_from(ExperimentResult)) == 0
