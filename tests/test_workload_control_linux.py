import sys
import pytest
from deploy.workload_control_linux import CASES,execute
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.mark.skipif(sys.platform!='linux',reason='real /proc and Linux resource limits required')
@pytest.mark.parametrize('control,scenario',sorted(CASES))
def test_owned_linux_process_injection_and_cleanup(tmp_path,control,scenario):
    row=execute(control,scenario,tmp_path/'case')
    assert row['origin']=='local_linux' and row['installed_native_eligible'] is False
    assert row['after']['processes']
    assert row['after']['limits']==dict(address_space_bytes=64*1024**2,pids=32)
    assert row['fixture_cleanup']['live_runtime_resources_after'] is False
    assert all(item['returncode'] is not None for item in row['fixture_cleanup']['runtime_after']['processes'])
    if control=='durable_launch_intent':
        call='create' if scenario=='lost_create_ack' else 'start'
        assert row['observations'][call+'_calls']==1
        assert row['observations']['replay_'+call+'_calls']==0
    if scenario in ('surviving_worker','daemon_replacement'):
        assert row['after']['live'] is True
        assert all(item['returncode'] is None for item in row['after']['processes'])


def test_linux_fixture_refuses_unsupported_before_creating_paths(tmp_path):
    with pytest.raises(WorkloadBlocked):execute('bounded_output','log_exhaustion',tmp_path/'case')
    assert not (tmp_path/'case').exists()
