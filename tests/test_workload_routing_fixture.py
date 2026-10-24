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


def test_routing_fixture_refuses_symlink_or_public_parent(tmp_path):
    owned=tmp_path/'owned';owned.mkdir(mode=0o700)
    alias=tmp_path/'alias';alias.symlink_to(owned,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink_path'):
        execute('coordinator_routing','deferred_admission',alias/'case')
    assert not (owned/'case').exists()
    owned.chmod(0o755)
    with pytest.raises(ValueError,match='private_parent_required'):
        execute('coordinator_routing','deferred_admission',owned/'case')
    assert not (owned/'case').exists()


def test_failed_dispatcher_retains_sql_observations_and_reaps_creator(tmp_path):
    import json
    from deploy.workload_routing_fixture import InertController
    class LostResult(InertController):
        def result(self,state):raise OSError('inert response acknowledgement lost')
    path=tmp_path/'routing'
    with pytest.raises(OSError,match='acknowledgement lost'):
        execute('coordinator_routing','result_after_cleanup',path,runtime_factory=LostResult)
    before=json.loads((path/'database-before-0.json').read_bytes())
    after=json.loads((path/'database-after-0.json').read_bytes())
    cleanup=json.loads((path/'runtime-cleanup.json').read_bytes())
    assert before['attempts']==0 and after['attempts']==1 and after['results']==0
    assert cleanup['processes'] and cleanup['returncode'] is not None and not cleanup['live']


def test_evidence_write_failure_cannot_suppress_termination_or_disposal(tmp_path,monkeypatch):
    import deploy.workload_routing_fixture as module
    from sqlalchemy import event
    controllers=[];disposed=[]
    class Tracked(module.InertController):
        def __init__(self):super().__init__();controllers.append(self)
    original_create=module.create_engine
    def engine(*args,**kwargs):
        created=original_create(*args,**kwargs)
        event.listen(created,'engine_disposed',lambda value:disposed.append(value))
        return created
    original_write=module.exclusive
    def fail_after(path,data):
        if path.name.startswith('database-after'):raise OSError('inert evidence disk exhausted')
        return original_write(path,data)
    monkeypatch.setattr(module,'create_engine',engine)
    monkeypatch.setattr(module,'exclusive',fail_after)
    with pytest.raises(OSError,match='evidence disk exhausted'):
        execute('coordinator_routing','result_after_cleanup',tmp_path/'routing',runtime_factory=Tracked)
    assert controllers[0].child is not None and controllers[0].child.poll() is not None
    assert not controllers[0].live and disposed
