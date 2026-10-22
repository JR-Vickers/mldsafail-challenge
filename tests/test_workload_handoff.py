"""Synthetic handoff protocol cases; never installed-native evidence."""
from copy import deepcopy
import pytest

import deploy.workload_handoff as handoff
from mldsafail.evaluator.workload import WorkloadBlocked


def binding():
    return dict(identifier='user:1000:mldsafail-workload-supervisor.service',unit=dict(device=1,inode=2),
                active=True,process=dict(pid=3,start_ticks=4),socket=dict(state='observed',device=1,inode=5),
                supervisor_generation='generation',state=dict(workload_id='a'*32,reference_sha256='b'*64))


def test_changed_previous_birth_cannot_authorize_stopping_a_replacement(monkeypatch):
    expected=binding();actual=deepcopy(expected);actual['process']['start_ticks']+=1
    source=dict(rollback=dict(supervisor=expected));commands=[]
    monkeypatch.setattr(handoff,'observe',lambda *args:actual)
    with pytest.raises(WorkloadBlocked,match='observation_changed'):handoff.stop(source,commands.append)
    assert commands==[]


def test_only_exact_bound_active_unit_is_stopped(monkeypatch):
    expected=binding();source=dict(rollback=dict(supervisor=expected));commands=[]
    monkeypatch.setattr(handoff,'observe',lambda *args:deepcopy(expected))
    handoff.stop(source,commands.append)
    assert commands==[['/usr/bin/systemctl','--user','stop',handoff.NAME]]
    expected['active']=False;commands.clear();handoff.stop(source,commands.append)
    assert commands==[]


def test_stopped_acknowledgement_retains_old_ownership_and_requires_absent_socket(monkeypatch):
    expected=binding();actual=deepcopy(expected)
    actual.update(active=False,process=None,socket=dict(state='absent'),supervisor_generation=None)
    source=dict(rollback=dict(supervisor=expected))
    monkeypatch.setattr(handoff,'observe',lambda *args:actual)
    assert handoff.stopped(source,None)['verified']
    actual['state']['workload_id']='c'*32
    with pytest.raises(WorkloadBlocked,match='ownership_changed'):handoff.stopped(source,None)


@pytest.mark.parametrize('phase',['running','launch_intent','termination_intent','postflight','commit_intent','committed'])
def test_unresolved_work_or_transaction_cannot_enter_handoff(phase):
    with pytest.raises(WorkloadBlocked,match='not_quiescent'):
        handoff.state_summary(dict(paused=True,phase=phase,workload_id='a'*32,reference={},requests={}))


def test_pending_request_blocks_handoff_even_after_resources_are_empty():
    with pytest.raises(WorkloadBlocked,match='request_unresolved'):
        handoff.state_summary(dict(paused=True,phase='cleaned',workload_id='a'*32,reference={},
                                   requests={'1:1':dict(phase='intent')}))


def test_bootstrap_empty_ownership_is_permitted_but_arbitrary_acquired_state_is_not():
    state=dict(paused=True,phase='acquired',workload_id='a'*32,reference={'bootstrap':True},requests={})
    assert handoff.state_summary(state)['paused']
    state['reference']={}
    with pytest.raises(WorkloadBlocked,match='not_quiescent'):handoff.state_summary(state)


def test_complete_previous_supervisor_binding_compiles_without_authority():
    from deploy.workload_v3_fixture import inspection
    from deploy.workload_v3 import bootstrap
    from deploy.workload_release import digest,canonical
    source=inspection();name='user:1000:'+handoff.NAME
    owner=dict(source['scheduling']['owners']['compute.service'],disposition='retain',restart='on-failure',enabled=False)
    source['scheduling']['owners'][name]=owner;source['scheduling']['units'].append(name)
    source['inventory']['manager_settings'][name]=dict(ActiveState='active',UnitFileState='static',Restart='on-failure',Triggers='')
    path=source['installation']['unit_directory']+'/'+handoff.NAME
    sha=source['rollback']['manifest']['files']['generated/'+handoff.NAME]['sha256']
    source['inventory']['original_files'][path]=sha
    delegation=source['resources']['delegation'];delegation.pop('creation');delegation.pop('preserve')
    delegation.update(state='observed',device=1,inode=77)
    parent=delegation['ancestors'][0];parent.pop('creation');parent.pop('preserve')
    parent.update(state='observed',device=1,inode=78,limits=dict(delegation['ancestors'][1]['limits']))
    for key in ('subtree_control','control_permissions'):parent[key]=delegation['ancestors'][1][key]
    source['rollback']['supervisor']=dict(identifier=name,
        unit=dict(state='observed',path=path,device=1,inode=79,uid=1000,mode=0o600,sha256=sha),
        active=True,process=dict(pid=30,start_ticks=40),supervisor_generation='c'*32,
        socket=dict(state='observed',path='/srv/v3/old-gate/supervisor.sock',device=1,inode=80,uid=1000,mode=0o600),
        state=handoff.state_summary(dict(paused=True,phase='cleaned',workload_id='a'*32,reference={},requests={})))
    proposal=bootstrap(source,now=1100)
    assert proposal['execution_authority'] is False
    actions=[step['action'] for step in proposal['steps'] if step['phase']=='install']
    assert actions.index('quiesce_supervisor')<actions.index('units')
    assert actions.index('verify_release')<actions.index('activate')<actions.index('supervisor_unit')
    del source['rollback']['supervisor']
    with pytest.raises(WorkloadBlocked,match='observation_missing'):bootstrap(source,now=1100)


def test_status_request_counts_cannot_hide_unresolved_intents():
    state=dict(paused=True,phase='cleaned',workload_id='a'*32,reference={},
               request_counts=dict(intent=1,complete=2))
    with pytest.raises(WorkloadBlocked,match='request_unresolved'):handoff.state_summary(state)
    state['request_counts']['intent']=0
    assert handoff.state_summary(state)['paused']
    del state['request_counts']
    with pytest.raises(WorkloadBlocked,match='request_evidence_missing'):handoff.state_summary(state)
