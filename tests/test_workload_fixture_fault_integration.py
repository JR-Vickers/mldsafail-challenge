"""Actual driver fault wiring, with all engine effects disabled."""
from types import SimpleNamespace

import pytest

from deploy.workload_fixture_faults import bind
from deploy.workload_installation import Journal,exclusive,identity
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts import workload_installation_fixture as driver
from tests.test_workload_fixture_faults import unbound
from tests.test_workload_installation import packet


def test_rollback_fault_plan_survives_install_then_fires_only_at_bound_rollback(tmp_path,monkeypatch):
    import scripts.workload_fixture_worker as worker
    import deploy.workload_installation as engine
    proposal,_,_,_=packet(tmp_path);raw=canonical(proposal)
    root=tmp_path/'fixture';root.mkdir(mode=0o700)
    generation='a'*32
    manifest=dict(schema=driver.SCHEMA,fixture_only=True,generation=generation,root=identity(root),case='complete',
        recovery_fault_plan=bind(unbound('rollback:restore_activation',boundary='unacknowledged'),generation))
    frozen=canonical(manifest);exclusive(root/'manifest.json',frozen);binding=digest(frozen)
    scope=dict(fixture_only=True,fixture_generation=generation,fixture_manifest_sha256=binding)
    review=root/'review';authority=root/'authority';exclusive(review,canonical(scope));exclusive(authority,canonical(scope))
    instance=SimpleNamespace(root=root,manifest=manifest,binding=binding,require_target=lambda:None,
        proposal=lambda:(raw,proposal))
    monkeypatch.setattr(driver,'Fixture',lambda path:instance)
    monkeypatch.setattr(worker,'inherited_lock',lambda *args:None)
    journal_root=root/'engine';journal_root.mkdir(mode=0o700);journal=Journal(journal_root,digest(raw))
    journal.append('recovery_protocol',version=4)
    class Backend:
        def __init__(self,proposal):self.journal=journal
    monkeypatch.setattr(engine,'LinuxBackend',Backend)
    phases=[]
    def execute(proposal,raw,review,authority,backend,*,phase,fault):
        phases.append(phase)
        if phase=='rollback':
            journal.append('intent',step='rollback:restore_activation',before={})
            fault('rollback:restore_activation','unacknowledged')
    monkeypatch.setattr(engine,'execute',execute)
    driver.fixture_engine(root,phase='install',review=review,authority=authority,lock_fd=3)
    assert not (root/'recovery-fault-fired.json').exists()
    with pytest.raises(InterruptedError,match='rollback:restore_activation'):
        driver.fixture_engine(root,phase='rollback',review=review,authority=authority,lock_fd=3)
    assert phases==['install','rollback']
    assert len([row for row in journal.rows if row['event']=='fixture_recovery_fault_fired'])==1


def test_optional_v4_plan_cannot_combine_with_historical_interruption_case(tmp_path):
    root=tmp_path/'fixture'
    with pytest.raises(WorkloadBlocked,match='cannot_combine_historical_case'):
        driver.prepare(root,case='partial-snapshots',recovery_fault_plan=unbound('install:tools'))
    assert not root.exists()
