"""Interrupted mutations retain observations and never replay automatically."""
import pytest
from deploy.workload_installation import Journal, identity
from deploy.workload_mutation import mutate, classify
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.mark.parametrize('point', ['intent', 'applied', 'outcome'])
def test_interruption_records_actual_state_and_refuses_replay(tmp_path, point):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64);target=tmp_path/'resource'
    def fault(resource, boundary):
        if boundary==point:raise InterruptedError(boundary)
    def create():target.write_bytes(b'owned')
    with pytest.raises(InterruptedError):
        mutate(journal,'fixture',lambda:identity(target),create,fault=fault)
    assert classify(journal,'fixture',identity(target))=={
        'intent':'absent','applied':'ambiguous','outcome':'completed'}[point]
    with pytest.raises(WorkloadBlocked,match='already_attempted'):
        mutate(journal,'fixture',lambda:identity(target),create)
    if point=='applied':
        assert journal.rows[-1]['event']=='mutation_failed'
        assert journal.rows[-1]['observed']==identity(target)


def test_replaced_acknowledged_resource_is_not_adopted(tmp_path):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64);target=tmp_path/'resource'
    mutate(journal,'fixture',lambda:identity(target),lambda:target.write_bytes(b'owned'))
    target.write_bytes(b'unknown')
    assert classify(journal,'fixture',identity(target))=='replaced'
    assert target.read_bytes()==b'unknown'


def test_failed_observation_retains_original_failure(tmp_path):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64);changed=False
    def observe():
        if changed:raise PermissionError('unavailable')
        return dict(state='absent')
    def action():
        nonlocal changed
        changed=True
        raise RuntimeError('partial mutation')
    with pytest.raises(RuntimeError,match='partial mutation'):
        mutate(journal,'fixture',observe,action)
    row=journal.rows[-1]
    assert row['error']['type']=='RuntimeError' and row['observation_error']['type']=='PermissionError'
    assert row['observed'] is None
