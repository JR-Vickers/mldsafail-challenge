"""Snapshot continuation uses real files and fresh engine authority; never host acceptance."""
import pytest

from deploy.workload_installation import (
    Journal, LinuxBackend, RECOVERY_PROTOCOL, SNAPSHOTS, execute, identity, reconcile,
)
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_installation import Backend, packet


class SnapshotBackend(Backend):
    snapshot_substeps = LinuxBackend.snapshot_substeps
    snapshot_file = LinuxBackend.snapshot_file
    partial_reconcilable = LinuxBackend.partial_reconcilable
    continuation_before = LinuxBackend.continuation_before
    apply_acknowledgements = LinuxBackend.apply_acknowledgements
    acknowledge_apply = LinuxBackend.acknowledge_apply
    absent_reconcilable = LinuxBackend.absent_reconcilable
    reconciliation_status = LinuxBackend.reconciliation_status
    reconcilable = LinuxBackend.reconcilable

    interrupt = None
    def mutation_deadline(self): pass
    def apply(self, step, journal):
        if step['action'] != 'snapshot':return super().apply(step, journal)
        for name in SNAPSHOTS:
            self.snapshot_file(journal, name, canonical(dict(snapshot=name)))
            if name == self.interrupt:raise InterruptedError('snapshot acknowledged')
        self.calls.append(step['id'])
    def observe(self, step, journal):
        if step['action'] == 'snapshot':return {name:identity(journal.root/name) for name in SNAPSHOTS}
        return super().observe(step, journal)
    def valid_outcome(self, step, value, journal):
        if step['action'] == 'snapshot':
            return all(value[name].get('sha256') == digest(canonical(dict(snapshot=name))) for name in SNAPSHOTS)
        return super().valid_outcome(step, value, journal)


@pytest.mark.parametrize('version', [2, RECOVERY_PROTOCOL])
@pytest.mark.parametrize('count', [1, 2, 3, 4])
def test_snapshot_continuation_preserves_acknowledged_births(tmp_path, count, version):
    proposal, raw, review, authority = packet(tmp_path)
    journal=Journal(tmp_path/'journal',digest(raw));journal.append('recovery_protocol',version=version)
    backend = SnapshotBackend(tmp_path);backend.interrupt = SNAPSHOTS[count-1]
    with pytest.raises(InterruptedError):execute(proposal, raw, review, authority(), backend)
    saved = {name:identity(tmp_path/'journal'/name) for name in SNAPSHOTS[:count]}
    with pytest.raises(WorkloadBlocked, match='reconcile_required'):
        execute(proposal, raw, review, authority(), backend)
    reconcile(proposal, raw, review, authority(reconcile=True), backend)
    journal = Journal(tmp_path/'journal', digest(raw))
    assert journal.recovery_protocol == version
    assert journal.outcome('install:snapshot')['event'] == 'reconciled_partial'
    # Reconciliation only observes: the remaining files are still absent.
    assert all(identity(tmp_path/'journal'/name)['state']=='absent' for name in SNAPSHOTS[count:])
    backend.interrupt = None
    execute(proposal, raw, review, authority(), backend)
    assert all(identity(tmp_path/'journal'/name)==saved[name] for name in saved)
    rows = Journal(tmp_path/'journal', digest(raw)).rows
    assert len([row for row in rows if row['event']=='mutation_intent'])==4
    for row in rows:
        if row['event'] in ('mutation_intent','mutation_outcome'):
            assert row['step_id']=='install:snapshot'
            assert row['proposal_sha256']==digest(raw)
            assert row['expected_effect']['effect']=='exclusive_private_snapshot'


@pytest.mark.parametrize('change', ['replace', 'delete', 'symlink'])
def test_changed_snapshot_blocks_partial_recovery(tmp_path, change):
    proposal, raw, review, authority = packet(tmp_path)
    backend = SnapshotBackend(tmp_path);backend.interrupt = SNAPSHOTS[0]
    with pytest.raises(InterruptedError):execute(proposal, raw, review, authority(), backend)
    path = tmp_path/'journal'/SNAPSHOTS[0]
    path.rename(tmp_path/'preserved')
    if change=='replace':path.write_bytes(b'unknown')
    if change=='symlink':path.symlink_to(tmp_path/'missing')
    with pytest.raises(WorkloadBlocked):reconcile(proposal, raw, review, authority(reconcile=True), backend)
    assert (tmp_path/'preserved').exists()
    assert change!='symlink' or path.is_symlink()


def test_replacement_after_reconciliation_blocks_execution(tmp_path):
    proposal, raw, review, authority = packet(tmp_path)
    backend = SnapshotBackend(tmp_path);backend.interrupt = SNAPSHOTS[0]
    with pytest.raises(InterruptedError):execute(proposal, raw, review, authority(), backend)
    reconcile(proposal, raw, review, authority(reconcile=True), backend)
    path = tmp_path/'journal'/SNAPSHOTS[0];path.write_bytes(b'unknown')
    backend.interrupt = None
    with pytest.raises(WorkloadBlocked, match='partial_resources_changed'):
        execute(proposal, raw, review, authority(), backend)
    assert identity(tmp_path/'journal'/SNAPSHOTS[1])['state']=='absent'


def test_legacy_journal_cannot_acquire_partial_continuation(tmp_path):
    proposal, raw, review, authority = packet(tmp_path)
    journal = Journal(tmp_path/'journal', digest(raw));journal.append('legacy_checkpoint')
    backend = SnapshotBackend(tmp_path);backend.interrupt = SNAPSHOTS[0]
    with pytest.raises(InterruptedError):execute(proposal, raw, review, authority(), backend)
    with pytest.raises(WorkloadBlocked):reconcile(proposal, raw, review, authority(reconcile=True), backend)
    assert Journal(tmp_path/'journal', digest(raw)).recovery_protocol==1


@pytest.mark.parametrize('version', [1, 5, None])
def test_unknown_protocol_is_rejected(tmp_path, version):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64);journal.append('recovery_protocol',version=version)
    with pytest.raises(WorkloadBlocked,match='recovery_protocol_invalid'):Journal(root,'a'*64)


def test_partial_snapshot_is_not_a_completed_install_for_rollback(tmp_path):
    proposal,raw,review,authority=packet(tmp_path)
    backend=SnapshotBackend(tmp_path);backend.interrupt=SNAPSHOTS[0]
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority(),backend)
    reconcile(proposal,raw,review,authority(reconcile=True),backend)
    with pytest.raises(WorkloadBlocked,match='ambiguous_installation'):
        execute(proposal,raw,review,authority('rollback'),backend,phase='rollback')
    assert not any(call.startswith('rollback:') for call in backend.calls)
