"""Real filesystem creation under synthetic orchestration, never host acceptance."""
import pytest
from deploy.workload_installation import LinuxBackend, Journal, identity, execute, reconcile, SNAPSHOTS
from deploy.workload_release import digest
from tests.test_workload_installation import Backend, packet
from mldsafail.evaluator.workload import WorkloadBlocked


class CreationBackend(Backend):
    """Use production reconciliation against an actual exclusively created dir."""
    apply_acknowledgements=LinuxBackend.apply_acknowledgements
    acknowledge_apply=LinuxBackend.acknowledge_apply
    absent_reconcilable=LinuxBackend.absent_reconcilable
    reconciliation_status=LinuxBackend.reconciliation_status
    reconcilable=LinuxBackend.reconcilable

    @property
    def destination(self):return self.root/'real-release'
    def before(self,step,journal):
        if step['action']=='create_release':
            actual=identity(self.destination)
            if actual['state']!='absent':raise WorkloadBlocked('unknown_creation_preserve')
            return actual
        return super().before(step,journal)
    def apply(self,step,journal):
        if step['action']=='create_release':
            self.destination.mkdir(mode=0o700);self.calls.append(step['id'])
        else:super().apply(step,journal)
    def observe(self,step,journal):
        if step['action']=='create_release':return identity(self.destination)
        return super().observe(step,journal)
    def valid_outcome(self,step,value,journal):
        if step['action']=='create_release':return value['state']=='observed'
        return super().valid_outcome(step,value,journal)


@pytest.mark.parametrize('boundary',['intent','unacknowledged','applied','outcome'])
def test_real_creation_recovery_never_adopts_unacknowledged_or_replays_completed(tmp_path,boundary):
    proposal,raw,review,authority=packet(tmp_path);backend=CreationBackend(tmp_path)
    def interrupt(step,point):
        if (step,point)==('install:create_release',boundary):raise InterruptedError('injected')
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority(),backend,fault=interrupt)
    if boundary=='unacknowledged':
        preserved=identity(backend.destination)
        with pytest.raises(WorkloadBlocked,match='identity_unacknowledged'):
            reconcile(proposal,raw,review,authority(reconcile=True),backend)
        assert identity(backend.destination)==preserved
        assert backend.calls.count('install:create_release')==1
        return
    if boundary!='outcome':reconcile(proposal,raw,review,authority(reconcile=True),backend)
    execute(proposal,raw,review,authority(),backend)
    assert backend.calls.count('install:create_release')==1
    rows=Journal(tmp_path/'journal',digest(raw)).rows
    if boundary=='intent':assert any(row['event']=='reconciled_absent' for row in rows)
    if boundary=='applied':assert any(row['event']=='reconciled' and row['step']=='install:create_release' for row in rows)


def test_acknowledged_creation_replacement_is_preserved_and_classified(tmp_path):
    proposal,raw,review,authority=packet(tmp_path);backend=CreationBackend(tmp_path)
    def interrupt(step,point):
        if (step,point)==('install:create_release','applied'):raise InterruptedError('injected')
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority(),backend,fault=interrupt)
    backend.destination.rename(tmp_path/'preserved-original')
    backend.destination.mkdir();(backend.destination/'unknown').write_bytes(b'preserve')
    with pytest.raises(WorkloadBlocked,match='identity_unacknowledged'):
        reconcile(proposal,raw,review,authority(reconcile=True),backend)
    assert (backend.destination/'unknown').read_bytes()==b'preserve'
    rows=Journal(tmp_path/'journal',digest(raw)).rows
    assert any(row['event']=='reconciliation_observation' and row['status']=='replaced' for row in rows)


def test_reconciled_absence_is_rechecked_before_creation(tmp_path):
    proposal,raw,review,authority=packet(tmp_path);backend=CreationBackend(tmp_path)
    def interrupt(step,point):
        if (step,point)==('install:create_release','intent'):raise InterruptedError('injected')
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority(),backend,fault=interrupt)
    reconcile(proposal,raw,review,authority(reconcile=True),backend)
    backend.destination.mkdir();(backend.destination/'unknown').write_bytes(b'preserve')
    with pytest.raises(WorkloadBlocked,match='unknown_creation_preserve'):
        execute(proposal,raw,review,authority(),backend)
    assert 'install:create_release' not in backend.calls


@pytest.mark.parametrize('action',['images','inhibit_scheduling','inhibit_containers','prerequisites',
                                   'activate','units','supervisor_unit','dependencies','configurations'])
def test_absence_does_not_authorize_replay_of_external_or_partial_effects(tmp_path,action):
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    journal=Journal(tmp_path/'journal',digest(raw));step=dict(id='install:'+action,action=action)
    absent=dict(state='absent',path=str(tmp_path/'resource'))
    journal.append('intent',step=step['id'],before=absent)
    assert not backend.absent_reconcilable(step,absent,journal)


@pytest.mark.parametrize('action',['create_release','enable_supervisor','snapshot'])
def test_prior_acknowledgement_prevents_absence_from_becoming_replay_permission(tmp_path,action):
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    journal=Journal(tmp_path/'journal',digest(raw));step=dict(id='install:'+action,action=action)
    absent=({name:dict(state='absent',path=str(tmp_path/name)) for name in SNAPSHOTS} if action=='snapshot'
            else dict(state='absent',path=str(tmp_path/'resource')))
    journal.append('intent',step=step['id'],before=absent)
    journal.append('resource_acknowledgement',step_id=step['id'],observed=dict(state='observed'))
    assert not backend.absent_reconcilable(step,absent,journal)


@pytest.mark.parametrize('replacement',['none','file','dangling_symlink'])
def test_rollback_after_reconciled_absent_enable_never_unlinks_unknown_marker(tmp_path,replacement):
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    backend.enable_path=tmp_path/'enabled';backend.root=tmp_path
    backend.command=lambda argv:(_ for _ in ()).throw(AssertionError('unrelated service mutation'))
    journal=Journal(tmp_path/'journal',digest(raw))
    absent=identity(backend.enable_path)
    journal.append('reconciled_absent',step='install:enable_supervisor',observed=absent)
    if replacement=='file':backend.enable_path.write_bytes(b'unknown')
    if replacement=='dangling_symlink':backend.enable_path.symlink_to(tmp_path/'missing')
    step=dict(id='rollback:stop_supervisor',action='stop_supervisor')
    if replacement=='none':
        backend.apply(step,journal)
        assert backend.valid_outcome(step,backend.observe(step,journal),journal)
    else:
        preserved=identity(backend.enable_path)
        with pytest.raises(WorkloadBlocked,match='enable_identity_changed'):backend.apply(step,journal)
        assert identity(backend.enable_path)==preserved
        assert not backend.valid_outcome(step,backend.observe(step,journal),journal)
    with pytest.raises(WorkloadBlocked,match='required_prior_outcome'):
        backend._outcome(journal,'install:enable_supervisor')
