from copy import deepcopy
import sys
import pytest
from deploy.workload_watchdog import execute,validate
from mldsafail.evaluator.workload import WorkloadBlocked


def protocol():
    row=lambda name:dict(name=name,argv=[sys.executable,'-c','pass'],seconds=1)
    return dict(origin='synthetic',identities=dict(source='fixture'),fixture_cgroup='/sys/fs/cgroup/disposable',
        startup=row('startup'),cases=[row('one'),row('two')],cleanup=row('cleanup'),postflight=row('postflight'),timeout_seconds=8)


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
