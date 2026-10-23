"""Actual artifact mutations with synthetic proposal inputs; no native acceptance."""
from pathlib import Path

import pytest

from deploy.workload_artifacts import archive_inventory
from deploy.workload_installation import Journal, LinuxBackend, identity
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_artifacts import archive
from tests.test_workload_installation import packet


def backend(tmp_path):
    proposal, raw, _, _ = packet(tmp_path)
    instance = LinuxBackend(proposal)
    instance.root = tmp_path/'release';instance.root.mkdir(mode=0o700)
    instance.bundle = instance.root/'bundle';instance.bundle.mkdir(mode=0o700)
    instance.source['resources']['release']['path']=str(instance.root)
    journal=Journal(tmp_path/'journal',digest(raw))
    return instance,journal


def test_copy_bundle_records_each_verified_file(tmp_path):
    instance,journal=backend(tmp_path)
    instance.bundle.rmdir()
    source=tmp_path/'frozen';source.mkdir(mode=0o700)
    rows={}
    for name,data in [('solver.txt',b'not executable'),('nested/metadata.json',b'{}')]:
        path=source/name;path.parent.mkdir(exist_ok=True)
        path.write_bytes(data);path.chmod(0o600)
        rows[name]=dict(sha256=digest(data),bytes=len(data),mode=0o600)
    instance.source['manifest']['files']=rows
    instance.recipe['bundle_root']=str(source)
    journal.append('outcome',step='install:create_release',observed=identity(instance.root))
    journal.append('intent',step='install:copy_bundle',before=identity(instance.bundle))
    instance.apply(dict(id='install:copy_bundle',action='copy_bundle'),journal)
    receipts=[row for row in journal.rows if row['event']=='mutation_outcome']
    assert len(receipts)==3
    assert all(row['step_id']=='install:copy_bundle' and row['observed']['sha256']==row['expected_effect']['sha256'] for row in receipts)
    assert (instance.bundle/'manifest.json').read_bytes()==canonical(instance.source['manifest'])


def test_tool_extraction_records_expanded_inventory_and_birth(tmp_path):
    instance,journal=backend(tmp_path)
    data=archive();(instance.bundle/'tool.tar.gz').write_bytes(data)
    instance.source['manifest']['tools']={role:dict(archive='tool.tar.gz',members=archive_inventory(data))
                                          for role in ('interpreter','installer')}
    journal.append('intent',step='install:tools',before=identity(instance.root/'tools'))
    instance.apply(dict(id='install:tools',action='tools'),journal)
    receipts=[row for row in journal.rows if row['event']=='mutation_outcome']
    assert len(receipts)==2
    for row in receipts:
        assert row['step_id']=='install:tools'
        assert row['observed']['inventory_sha256']==row['expected_effect']['inventory_sha256']
        assert row['observed']['identity']==identity(row['expected_effect']['path'])


def test_wrong_file_effect_is_not_acknowledged_and_never_replayed(tmp_path):
    instance,journal=backend(tmp_path);target=instance.root/'configuration'
    step=dict(id='install:configurations',action='configurations')
    journal.append('intent',step=step['id'],before=identity(target))
    with pytest.raises(WorkloadBlocked,match='effect_not_verified'):
        instance.file_substep(step,journal,target,dict(sha256=digest(b'approved'),mode=0o600),
                              lambda:target.write_bytes(b'wrong'))
    assert journal.rows[-1]['event']=='mutation_failed'
    assert not any(row['event']=='mutation_outcome' for row in journal.rows)
    with pytest.raises(WorkloadBlocked,match='destination_not_absent'):
        instance.file_substep(step,journal,target,dict(sha256=digest(b'approved')),lambda:None)
    assert target.read_bytes()==b'wrong'


def test_unacknowledged_tool_extraction_failure_preserves_partial_files(tmp_path,monkeypatch):
    import deploy.workload_artifacts as artifacts
    instance,journal=backend(tmp_path)
    data=archive();(instance.bundle/'tool.tar.gz').write_bytes(data)
    instance.source['manifest']['tools']={'interpreter':dict(archive='tool.tar.gz',members=archive_inventory(data))}
    def partial(data,target,members):
        target.mkdir(mode=0o700);(target/'partial').write_bytes(b'preserve')
        raise InterruptedError('lost extraction')
    monkeypatch.setattr(artifacts,'extract',partial)
    journal.append('intent',step='install:tools',before=identity(instance.root/'tools'))
    with pytest.raises(InterruptedError):instance.apply(dict(id='install:tools',action='tools'),journal)
    assert journal.rows[-1]['event']=='mutation_failed'
    assert journal.rows[-1]['observation_error'] is not None
    assert (instance.root/'tools/interpreter/partial').read_bytes()==b'preserve'
    assert not instance.partial_reconcilable(dict(id='install:tools'),{},journal)


def test_substep_reconciliation_observes_replacement_without_adoption(tmp_path):
    instance,journal=backend(tmp_path);target=instance.root/'configuration'
    step=dict(id='install:configurations',action='configurations')
    journal.append('intent',step=step['id'],before=identity(target))
    instance.file_substep(step,journal,target,dict(sha256=digest(b'approved')),
                          lambda:target.write_bytes(b'approved'))
    original=instance.observe_substeps(step,journal)
    assert original[0]['status']=='completed'
    target.rename(instance.root/'preserved');target.write_bytes(b'unknown')
    rows_before=list(journal.rows)
    observation=instance.observe_substeps(step,journal)
    assert observation[0]['status']=='replaced'
    assert observation[0]['observed']==identity(target)
    assert journal.rows==rows_before
    assert target.read_bytes()==b'unknown'


def test_dangling_symlink_is_observed_and_readlink_replacement_is_rejected(tmp_path,monkeypatch):
    import os
    target=tmp_path/'pointer';target.symlink_to(tmp_path/'missing')
    assert identity(target)['state']=='observed'
    original=os.readlink
    def replace(path,*args,**kwargs):
        value=original(path,*args,**kwargs)
        target.unlink();target.symlink_to(tmp_path/'other-missing')
        return value
    monkeypatch.setattr(os,'readlink',replace)
    with pytest.raises(WorkloadBlocked,match='identity_race'):identity(target)


def test_regular_file_replacement_between_lstat_and_open_is_rejected(tmp_path,monkeypatch):
    import os
    target=tmp_path/'file';target.write_bytes(b'original')
    replacement=tmp_path/'replacement';replacement.write_bytes(b'unknown')
    original=os.open
    def replace(path,*args,**kwargs):
        if Path(path)==target:os.replace(replacement,target)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(os,'open',replace)
    with pytest.raises(WorkloadBlocked,match='identity_race'):identity(target)
    assert target.read_bytes()==b'unknown'
