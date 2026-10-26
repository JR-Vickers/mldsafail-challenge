from types import SimpleNamespace
import pytest
from scripts.workload_control_case import run_native
from mldsafail.evaluator.workload import WorkloadBlocked


def context(monkeypatch,receipt):
    import deploy.workload_native_context as module
    calls=[]
    def stage(*args):calls.append(args);return receipt
    monkeypatch.setattr(module.NativeContext,'open',lambda *args,**kwargs:SimpleNamespace(run_case=stage,cleanup_case=stage,postflight_case=stage))
    return calls


def test_native_case_is_only_an_observation_until_independent_postflight(monkeypatch):
    calls=context(monkeypatch,dict(origin='installed_native',case_observed=True,accepted=False))
    value=run_native('/bound/packet','explicit_resume','fresh_preflight','/bound/output','case')
    assert value['accepted'] is False and len(calls)==1


@pytest.mark.parametrize('receipt',[
    dict(origin='synthetic',case_observed=True,accepted=False),
    dict(origin='local_linux',case_observed=True,accepted=False),
    dict(origin='installed_native',case_observed=False,accepted=False),
    dict(origin='installed_native',case_observed=True,accepted=True),
])
def test_historical_or_incomplete_results_cannot_be_native_attestations(monkeypatch,receipt):
    context(monkeypatch,receipt)
    with pytest.raises(WorkloadBlocked):run_native('/bound/packet','explicit_resume','fresh_preflight','/bound/output','case')


def test_cleanup_zero_exit_requires_observed_verification(monkeypatch):
    context(monkeypatch,dict(verified=False))
    with pytest.raises(WorkloadBlocked):run_native('/bound/packet','explicit_resume','fresh_preflight','/bound/output','cleanup')
