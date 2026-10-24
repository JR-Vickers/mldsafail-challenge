import pytest
from deploy.workload_packet_preparation import prepare,remaining_attempt,ENVELOPE
from deploy.workload_release import canonical
from deploy.workload_v3 import bootstrap
from deploy.workload_v3_fixture import inspection,installed
from mldsafail.evaluator.workload import WorkloadBlocked


def references(tmp_path):
    proposal=bootstrap(inspection(),now=1100)
    paths=[tmp_path/'proposal',tmp_path/'inspection']
    for path,value in zip(paths,[proposal,installed(proposal)]):
        path.write_bytes(canonical(value));path.chmod(0o600)
    return paths


def test_one_case_preparation_binds_frozen_refs_without_authority(tmp_path):
    proposal,observation=references(tmp_path)
    result=prepare(proposal,observation,packet_path=tmp_path/'packet',output_path=tmp_path/'case',
                   control='explicit_resume',scenario='failed_preflight',now=1100)
    assert result['execution_authority'] is False and result['blockers']
    assert result['timeout_seconds']==180 and sum(ENVELOPE.values())==180
    assert result['case_order']==['explicit_resume/failed_preflight']
    assert result['case_command'][-6:]==['--control','explicit_resume','--scenario','failed_preflight','--output',str(tmp_path/'case')]
    assert result['proposal']['sha256'] and result['inspection']['sha256']


def test_missing_inspection_is_blocker_not_invented_observation(tmp_path):
    proposal,_=references(tmp_path)
    result=prepare(proposal,None,packet_path=tmp_path/'packet',output_path=tmp_path/'case',
                   control='explicit_resume',scenario='failed_preflight',now=1100)
    assert result['inspection'] is None
    assert 'fresh_installed_inspection_required' in result['blockers']


@pytest.mark.parametrize('elapsed,passes',[(0,True),(1320,True),(1321,False),(1500,False),(-1,False)])
def test_split_packets_share_attempt_budget(tmp_path,elapsed,passes):
    proposal,observation=references(tmp_path)
    attempt=dict(started_monotonic=100,boot_id=inspection()['host']['boot_id'],generation='fixture-1')
    kwargs=dict(packet_path=tmp_path/'packet',output_path=tmp_path/'case',control='explicit_resume',
                scenario='failed_preflight',now=1100,attempt=attempt,now_monotonic=100+elapsed)
    if passes:assert prepare(proposal,observation,**kwargs)['attempt']==attempt
    else:
        with pytest.raises(WorkloadBlocked):prepare(proposal,observation,**kwargs)


def test_attempt_boot_change_never_resets_budget():
    with pytest.raises(WorkloadBlocked,match='identity_changed'):
        remaining_attempt(dict(started_monotonic=10,boot_id='old',generation='one'),now_monotonic=11,boot_id='new')


def test_unsupported_scenario_refused(tmp_path):
    with pytest.raises(WorkloadBlocked,match='scenario_unsupported'):
        prepare(None,None,packet_path=tmp_path/'packet',output_path=tmp_path/'case',control='arbitrary',scenario='command')
