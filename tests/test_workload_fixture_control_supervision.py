"""Independent phase supervision preserves the original fixture attempt."""
import time

import pytest

from deploy.workload_installation import Journal
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.workload_installation_fixture import Fixture


def fixture(tmp_path,monkeypatch):
    import scripts.workload_fixture_worker as worker
    import scripts.rehearse_workload_installation_fixture as rehearsal
    value=object.__new__(Fixture);value.root=tmp_path;value.binding='a'*64;value.lock_fd=3
    value.manifest={'generation':'b'*32};value.require_target=lambda:None;value.deadline=lambda **kwargs:1800
    for name in ('journal','runtime-journal'):(tmp_path/name).mkdir(mode=0o700)
    value.journal=value.lifecycle_journal=Journal(tmp_path/'journal',value.binding)
    value.journal.append('fixture_attempt_started',started_monotonic=time.monotonic(),started_at=time.time())
    monkeypatch.setattr(worker,'inherited_lock',lambda *args:None)
    monkeypatch.setattr(rehearsal,'component_review',lambda *args:None)
    return value


@pytest.mark.parametrize('case_failure',[False,True])
def test_case_failure_still_gets_fresh_bound_cleanup_and_postflight(tmp_path,monkeypatch,case_failure):
    value=fixture(tmp_path,monkeypatch);calls=[];token='c'*32
    def worker(operation,**kwargs):
        calls.append((operation,kwargs))
        if operation=='control':
            value.journal.append('fixture_worker_intent',operation=operation,token=token,phase=kwargs['phase'])
            if case_failure:raise WorkloadBlocked('deliberate case interruption')
            return {'original_case':'observed'}
        return {'verified':True}
    value.worker=worker
    if case_failure:
        with pytest.raises(WorkloadBlocked,match='deliberate case interruption'):
            value.control('shared_host_gate','cross_database_and_admin')
    else:
        result=value.control('shared_host_gate','cross_database_and_admin')
        assert result['independent_cleanup']['verified'] and result['independent_postflight']['verified']
    assert [operation for operation,_ in calls]==['control','control-cleanup','control-postflight']
    assert 0<calls[0][1]['seconds']<=120 and calls[1][1]['seconds']<=45 and calls[2][1]['seconds']<=15
    assert all(row['phase']=='shared_host_gate:cross_database_and_admin:'+token for _,row in calls[1:])
    assert all(row['cleanup'] is True for _,row in calls[1:])
    assert len([row for row in value.journal.rows if row['event']=='fixture_attempt_started'])==1
    disposition=value.journal.rows[-1]
    assert disposition['disposition']==('blocked_preserve' if case_failure else 'verified_fixture_only')


def test_cleanup_failure_cannot_publish_success_or_start_another_case(tmp_path,monkeypatch):
    value=fixture(tmp_path,monkeypatch);calls=[]
    def worker(operation,**kwargs):
        calls.append(operation)
        if operation=='control':
            value.journal.append('fixture_worker_intent',operation=operation,token='c'*32,phase=kwargs['phase'])
            return {'original_case':'observed'}
        raise WorkloadBlocked('cleanup interrupted')
    value.worker=worker
    with pytest.raises(WorkloadBlocked,match='independent_cleanup_or_postflight_blocked'):
        value.control('shared_host_gate','cross_database_and_admin')
    assert calls==['control','control-cleanup']
    with pytest.raises(WorkloadBlocked,match='previous_failure_requires_handoff'):
        value.control('coordinator_routing','deferred_admission')
    assert calls==['control','control-cleanup']


def test_parent_interruption_latches_unresolved_prior_case(tmp_path,monkeypatch):
    value=fixture(tmp_path,monkeypatch)
    value.journal.append('fixture_control_requested',control='shared_host_gate',scenario='cross_database_and_admin')
    value.worker=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('must not start another worker'))
    with pytest.raises(WorkloadBlocked,match='prior_ownership_unresolved'):
        value.control('coordinator_routing','deferred_admission')


def test_short_external_packet_deadline_cannot_spend_cleanup_reserve(tmp_path,monkeypatch):
    value=fixture(tmp_path,monkeypatch)
    value.worker=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('must not start'))
    with pytest.raises(WorkloadBlocked,match='cleanup_budget_not_reserved'):
        value.control('shared_host_gate','cross_database_and_admin',packet_deadline=time.monotonic()+60)
    assert not any(row['event']=='fixture_control_requested' for row in value.journal.rows)
