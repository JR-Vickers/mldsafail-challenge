from copy import deepcopy
import sys
import json
from deploy.workload_release import canonical,digest
import pytest
from deploy.workload_watchdog import execute,validate
from mldsafail.evaluator.workload import WorkloadBlocked


def protocol():
    row=lambda name:dict(name=name,argv=[sys.executable,'-c','pass'],seconds=1)
    data=dict(origin='synthetic',identities=dict(source='fixture',retained_services={}),fixture_cgroup='/sys/fs/cgroup/disposable',
        startup=row('startup'),cases=[row('one'),row('two')],cleanup=row('cleanup'),postflight=row('postflight'),timeout_seconds=8)
    raw=dict(schema='mldsafail.workload-control-postflight.v3',origin='synthetic',
        identities_sha256=digest(canonical(data['identities'])),paused=True,owned_resources=0,
        transactions='resolved',retained_before={},retained_after={})
    data['postflight']['argv']=[sys.executable,'-c','print('+repr(json.dumps(raw))+')']
    return data


def test_success_after_cleanup_and_postflight(tmp_path):
    receipt=execute(protocol(),tmp_path/'run',birth=lambda pid:dict(pid=pid))
    assert receipt['passed'] and receipt['cleanup_verified']
    assert [r['name'] for r in receipt['records']]==['startup','one','two','cleanup','postflight']


def test_timeout_stops_following_cases_and_runs_cleanup_once(tmp_path):
    data=protocol();data['cases'][0].update(argv=[sys.executable,'-c','import time;time.sleep(30)'],seconds=.05)
    receipt=execute(data,tmp_path/'run',birth=lambda pid:dict(pid=pid))
    assert not receipt['passed']
    assert [r['name'] for r in receipt['records']]==['startup','one','cleanup','postflight']
    assert receipt['records'][1]['timed_out']


def test_cleanup_failure_retains_blocked_ownership(tmp_path):
    data=protocol();data['cleanup']['argv']=[sys.executable,'-c','raise SystemExit(1)']
    receipt=execute(data,tmp_path/'run',birth=lambda pid:dict(pid=pid))
    assert receipt['ownership']=='blocked' and not receipt['passed']


def test_budget_reserves_startup_cleanup_and_final_inspection():
    data=protocol();data['timeout_seconds']=4
    with pytest.raises(WorkloadBlocked):validate(data)


def test_native_origin_requires_separate_authority_before_mutations(tmp_path):
    data=protocol();data['origin']='installed_native'
    with pytest.raises(WorkloadBlocked,match='native_authority_required'):execute(data,tmp_path/'run')
    assert not (tmp_path/'run').exists()


def test_zero_exit_alone_does_not_certify_paused_or_cleaned(tmp_path):
    data=protocol();data['postflight']['argv']=[sys.executable,'-c','pass']
    receipt=execute(data,tmp_path/'run',birth=lambda pid:dict(pid=pid))
    assert not receipt['passed'] and not receipt['paused'] and receipt['ownership']=='blocked'


@pytest.mark.parametrize('scope',['/sys/fs/cgroup/fixture/../fixture','/sys/fs/cgroup//fixture','/sys/fs/cgroup/fixture/'])
def test_fixture_path_alias_cannot_bypass_outside_check(scope):
    data=protocol();data['fixture_cgroup']=scope
    with pytest.raises(WorkloadBlocked,match='identities_missing'):validate(data)


def test_postflight_cannot_substitute_retained_service_baseline():
    from deploy.workload_watchdog import postflight_observation
    data=protocol()
    row=dict(schema='mldsafail.workload-control-postflight.v3',origin='synthetic',
        identities_sha256=digest(canonical(data['identities'])),paused=True,owned_resources=0,
        transactions='resolved',retained_before={'unrelated':True},retained_after={'unrelated':True})
    with pytest.raises(WorkloadBlocked,match='postflight_unresolved'):postflight_observation(json.dumps(row),data)
