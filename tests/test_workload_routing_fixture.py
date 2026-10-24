import pytest
from deploy.workload_routing_fixture import execute,CASES
from deploy.workload_controls import SCENARIOS


@pytest.mark.parametrize('control,scenario',sorted(CASES))
def test_real_dispatcher_paths_and_sql_observations(tmp_path,control,scenario):
    result=execute(control,scenario,tmp_path/'routing')
    assert all(result['observations'][key]==value for key,value in SCENARIOS[control][scenario].items())
    assert result['trace'][0]['monotonic_ns']<=result['trace'][-1]['monotonic_ns']
    if scenario=='result_after_cleanup':
        assert result['sql_trace'][0]['phase']=='commit_intent'
        assert result['process_births'] and result['process_returncode'] is not None
    else:
        assert result['after']['attempts']==0 and result['after']['results']==0
    with pytest.raises(FileExistsError):execute(control,scenario,tmp_path/'routing')
