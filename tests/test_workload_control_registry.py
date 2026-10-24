import copy

import pytest

from deploy.workload_control_registry import registry, get_runner
from deploy.workload_control_fixture import execute
from deploy.workload_controls import SCENARIOS
from mldsafail.evaluator.workload import WorkloadBlocked


CASES=[(control,scenario) for control,cases in SCENARIOS.items() for scenario in cases]


def test_registry_exact_inventory():
    rows=registry()
    assert len(rows)==27
    assert {(row['control'],row['scenario']) for row in rows}==set(CASES)
    for changed in (rows[:-1],rows+[rows[0]]):
        with pytest.raises(WorkloadBlocked,match='coverage_invalid'):registry(changed)
    changed=copy.deepcopy(rows);changed[0]['injection']='arbitrary'
    with pytest.raises(WorkloadBlocked,match='unsupported'):registry(changed)
    with pytest.raises(WorkloadBlocked,match='not_allowlisted'):get_runner('unknown','unknown')


@pytest.mark.parametrize('control,scenario',CASES)
def test_every_fixture_injection_records_raw_observation(tmp_path,control,scenario):
    result=execute(control,scenario,tmp_path/'case')
    assert result['origin']=='synthetic' and result['installed_native_eligible'] is False
    assert result['trace'][0]['event']=='injection'
    assert result['trace'][1]['event']=='observation'
    assert result['trace'][0]['monotonic_ns']<=result['trace'][1]['monotonic_ns']
    assert result['before'] and result['after']
    with pytest.raises(FileExistsError):execute(control,scenario,tmp_path/'case')


@pytest.mark.parametrize('control,scenario,reason',[
    ('inspected_births','daemon_replacement','runtime_identity_changed'),
    ('inspected_births','container_restart','ownership_lost'),
    ('ancestor_limits','parent_oom','operation_oom'),
    ('ancestor_limits','ancestor_limit_change','launch_resource_deferral'),
    ('bounded_output','log_exhaustion','log_budget'),
    ('bounded_output','generation_quota_exhaustion','generation_budget'),
    ('verified_cleanup','surviving_worker','termination_unverified'),
    ('abnormal_exit','controller_disconnect','dispatcher_heartbeat_lost'),
    ('explicit_resume','failed_preflight','resource_deferral'),
])
def test_failure_injection_reaches_real_gate_rejection(tmp_path,control,scenario,reason):
    result=execute(control,scenario,tmp_path/'case')
    assert reason in result['errors']
    assert result['state']['paused']
    assert result['observations'].get('results',0)==0


@pytest.mark.parametrize('scenario,call',[('lost_create_ack','create'),('lost_start_ack','start')])
def test_lost_ack_does_not_replay_effect(tmp_path,scenario,call):
    result=execute('durable_launch_intent',scenario,tmp_path/'case')
    assert result['after']['calls'].count(call)==1
    assert result['observations']['replay_'+call+'_calls']==0
    assert result['state']['phase']=='launch_intent'
    assert result['state']['paused']


def test_daemon_replacement_preserves_unknown_resource(tmp_path):
    result=execute('inspected_births','daemon_replacement',tmp_path/'case')
    assert result['observations']['replacement_kills']==0
    assert result['after']['live'] is True


def test_fresh_resume_requires_zero_live_resources(tmp_path):
    result=execute('explicit_resume','fresh_preflight',tmp_path/'case')
    assert result['observations']==dict(resources=0,resumed=True)


def test_monitor_runs_during_blocked_creator(tmp_path):
    result=execute('continuous_monitor','stuck_control_io',tmp_path/'case')
    assert result['observations']['monitor_continued']
    assert result['observations']['abort_latency_ms']<1100
    assert 'stale_launch_response' in result['errors']


def test_fixed_entrypoint_refuses_wrong_origin_and_unbound_case(tmp_path,monkeypatch):
    from scripts import workload_control_case as entry
    from deploy.workload_release import canonical
    from deploy.workload_v3_fixture import inspection
    proposal={'identities':inspection()}
    packet={'proposal':{},'protocol':{'origin':'installed_native','cases':[]}}
    path=tmp_path/'packet';path.write_bytes(canonical(packet));path.chmod(0o600)
    monkeypatch.setattr(entry,'validate',lambda packet:packet)
    monkeypatch.setattr(entry,'load_reference',lambda row:proposal)
    with pytest.raises(WorkloadBlocked,match='native_context_adapter_required'):
        entry.run(path,'shared_host_gate','cross_database_and_admin',tmp_path/'output')
    packet['protocol']['origin']='synthetic';path.write_bytes(canonical(packet))
    with pytest.raises(WorkloadBlocked,match='not_bound'):
        entry.run(path,'shared_host_gate','cross_database_and_admin',tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_fixed_entrypoint_exclusive_output_and_replay(tmp_path,monkeypatch):
    from scripts import workload_control_case as entry
    from deploy.workload_release import canonical
    from deploy.workload_v3_fixture import inspection
    proposal={'identities':inspection()}
    output=tmp_path/'output';path=tmp_path/'packet'
    command=entry.case_command(path,proposal,'shared_host_gate','cross_database_and_admin',output)
    packet={'proposal':{},'protocol':{'origin':'synthetic','cases':[{'argv':command}]}}
    path.write_bytes(canonical(packet));path.chmod(0o600)
    monkeypatch.setattr(entry,'validate',lambda packet:packet)
    monkeypatch.setattr(entry,'load_reference',lambda row:proposal)
    result=entry.run(path,'shared_host_gate','cross_database_and_admin',output)
    assert result['observations']['acquired']==1
    assert output.exists() and (tmp_path/'output.result.json').exists()
    with pytest.raises(FileExistsError):entry.run(path,'shared_host_gate','cross_database_and_admin',output)


@pytest.mark.parametrize('field',['runner','injection','observer','cleanup','required_origin',
    'fixture_origin','native_runner','native_case','local_runner','owned_fixture_runner','owned_fixture_context','identity_bindings','extra'])
def test_registry_rejects_every_substituted_binding(field):
    rows=registry();rows[0][field]='substituted'
    with pytest.raises(WorkloadBlocked,match='unsupported'):registry(rows)


def test_observations_change_when_injection_is_not_seen(tmp_path,monkeypatch):
    from deploy import workload_control_fixture as fixture
    original=fixture.FixtureRuntime.sample
    def suppress_oom(self,state):
        sample=original(self,state);sample['oom_events']=0;return sample
    monkeypatch.setattr(fixture.FixtureRuntime,'sample',suppress_oom)
    result=fixture.execute('ancestor_limits','parent_oom',tmp_path/'case')
    assert 'operation_oom' not in result['errors']
    assert result['observations']['paused'] is False


def test_real_fixture_descendants_are_terminated(tmp_path):
    result=execute('common_cgroup','controller_worker_descendants',tmp_path/'case')
    descendants=result['fixture_cleanup']['descendants_after']
    assert len(descendants)==3 and all(row['returncode'] is not None for row in descendants)
    assert result['fixture_cleanup']['retained_host_resources_touched'] is False


def test_fixture_refuses_nonprivate_parent_before_effects(tmp_path):
    tmp_path.chmod(0o755)
    try:
        with pytest.raises(WorkloadBlocked,match='parent_not_private'):
            execute('shared_host_gate','cross_database_and_admin',tmp_path/'case')
        assert not (tmp_path/'case').exists()
    finally:tmp_path.chmod(0o700)


def test_case_assertions_fail_on_observed_cleanup_failure(tmp_path,monkeypatch):
    from deploy import workload_control_fixture as fixture
    from scripts.workload_control_case import assertions
    monkeypatch.setattr(fixture.FixtureRuntime,'terminate',lambda self,state:False)
    result=fixture.execute('verified_cleanup','empty_scope_and_absent_containers',tmp_path/'case')
    check=assertions(result)
    assert result['after']['live'] is True
    assert check['regression_passed'] is False and check['full_scenario_passed'] is False
    assert any(row['field']=='populated' and not row['passed'] for row in check['checks'])


def test_case_assertions_distinguish_process_scope_and_missing_measurements():
    from scripts.workload_control_case import assertions
    receipt=dict(control='verified_cleanup',scenario='empty_scope_and_absent_containers',
        origin='local_linux',scope='generation_owned_inert_processes_only',
        observations={'owned_processes':0},fixture_cleanup={'live_runtime_resources_after':False})
    check=assertions(receipt)
    assert check['full_scenario_passed'] is False
    assert check['unmeasured']==['populated','containers']


def test_cli_returns_failure_for_observation_without_full_assertions(tmp_path,monkeypatch,capsys):
    import sys
    from scripts import workload_control_case as entry
    monkeypatch.setattr(sys,'argv',['workload_control_case','--packet',str(tmp_path/'packet'),
        '--control','verified_cleanup','--scenario','empty_scope_and_absent_containers','--output',str(tmp_path/'output')])
    monkeypatch.setattr(entry,'run',lambda *args:dict(origin='local_linux',packet_sha256='a'*64,
        assertions={'regression_passed':True,'full_scenario_passed':False,'unmeasured':['containers']}))
    with pytest.raises(SystemExit) as status:entry.main()
    assert status.value.code==2
    assert '"full_scenario_passed": false' in capsys.readouterr().out
