"""Protocol-three receipt bindings and conservative file continuation."""
import pytest

from deploy.workload_installation import Journal, identity
from deploy.workload_mutation import classify, mutate
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_installation_substeps import backend


def journal_at(tmp_path, version=3):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64)
    journal.append('recovery_protocol',version=version)
    journal.append('intent',step='install:fixture',before=dict(state='absent'))
    return journal


def test_v3_receipt_binds_exact_parent_and_intent(tmp_path):
    journal=journal_at(tmp_path);target=tmp_path/'file'
    mutate(journal,'file',lambda:identity(target),lambda:target.write_bytes(b'owned'),
           expected_effect=dict(effect='exclusive_file'))
    intent,outcome=journal.rows[-2:]
    assert intent['parent_intent_sha256']==digest(canonical(journal.rows[1]))
    assert outcome['mutation_intent_sha256']==digest(canonical(intent))
    assert outcome['operation']=='exclusive_file'
    assert classify(journal,'file',identity(target))=='completed'


@pytest.mark.parametrize('field,value', [('step_id','other'),('operation','other'),
    ('expected_effect',{}),('parent_intent_sha256','b'*64),('mutation_intent_sha256','c'*64)])
def test_v3_cross_bound_receipt_is_rejected(tmp_path,field,value):
    journal=journal_at(tmp_path);target=tmp_path/'file'
    mutate(journal,'file',lambda:identity(target),lambda:target.write_bytes(b'owned'))
    journal.rows[-1][field]=value
    with pytest.raises(WorkloadBlocked,match='receipt_binding_invalid'):
        classify(journal,'file',identity(target))


def test_protocol_two_header_is_retained(tmp_path):
    journal=journal_at(tmp_path,2)
    assert Journal(journal.root,journal.binding).recovery_protocol==2


@pytest.mark.parametrize('change', ['delete','parent_symlink','parent_replaced'])
@pytest.mark.parametrize('version', [2,3])
def test_configuration_continuation_is_v3_only(tmp_path,monkeypatch,version,change):
    instance,journal=backend(tmp_path)
    journal.append('recovery_protocol',version=version)
    step=dict(id='install:configurations',action='configurations')
    paths={role:instance.root/(role+'.json') for role in ('native','service','coordinator')}
    instance.source['manifest']['configurations']={role:dict(path=str(path)) for role,path in paths.items()}
    import deploy.workload_configuration as configuration
    monkeypatch.setattr(configuration,'measured_resources',lambda source:{})
    monkeypatch.setattr(configuration,'hashes',lambda source,resources:{role:digest(b'owned') for role in paths})
    journal.append('intent',step=step['id'],before={role:identity(path) for role,path in paths.items()})
    def create():
        paths['native'].write_bytes(b'owned');paths['native'].chmod(0o600)
    instance.file_substep(step,journal,paths['native'],dict(sha256=digest(b'owned'),mode=0o600),create)
    observed={role:identity(path) for role,path in paths.items()}
    assert instance.partial_reconcilable(step,observed,journal)==(version==3)
    if version==2:return
    journal.append('reconciled_partial',step=step['id'],observed=observed)
    journal.append('intent',step=step['id'],before=observed)
    instance.file_substep(step,journal,paths['native'],dict(sha256=digest(b'owned'),mode=0o600),
                          lambda:pytest.fail('acknowledged file replayed'))
    assert identity(paths['native'])==observed['native']
    if change=='delete':paths['native'].unlink()
    else:
        saved=tmp_path/'saved-release';instance.root.rename(saved)
        if change=='parent_symlink':instance.root.symlink_to(saved,target_is_directory=True)
        else:
            instance.root.mkdir(mode=0o700)
            (saved/'native.json').rename(paths['native'])
        # File birth/bytes survive the parent replacement.
        assert identity(paths['native'])==observed['native']
        with pytest.raises(WorkloadBlocked):
            instance.file_substep(step,journal,paths['native'],dict(sha256=digest(b'owned'),mode=0o600),
                                  lambda:pytest.fail('replaced parent replayed'))
    assert not instance.partial_reconcilable(step,{role:identity(path) for role,path in paths.items()},journal)


@pytest.mark.parametrize('field', ['mutation_intent_sha256','parent_intent_sha256','step_id','operation'])
def test_snapshot_continuation_rejects_cross_bound_receipt(tmp_path,field):
    from tests.test_workload_snapshot_continuation import SnapshotBackend
    from tests.test_workload_installation import packet
    from deploy.workload_installation import SNAPSHOTS, execute
    proposal,raw,review,authority=packet(tmp_path)
    instance=SnapshotBackend(tmp_path);instance.interrupt=SNAPSHOTS[0]
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority(),instance)
    journal=Journal(tmp_path/'journal',digest(raw))
    outcome=next(row for row in journal.rows if row['event']=='mutation_outcome')
    outcome[field]='wrong'
    step=dict(id='install:snapshot',action='snapshot')
    if field=='step_id':
        assert not instance.partial_reconcilable(step,instance.observe(step,journal),journal)
    else:
        with pytest.raises(WorkloadBlocked):instance.partial_reconcilable(step,instance.observe(step,journal),journal)
    journal.append('reconciled_partial',step=step['id'],observed=instance.observe(step,journal))
    with pytest.raises(WorkloadBlocked):instance.snapshot_file(journal,SNAPSHOTS[0],canonical(dict(snapshot=SNAPSHOTS[0])))
