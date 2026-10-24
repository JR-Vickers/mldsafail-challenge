"""Finite fixture fault hooks; real owned files, no native acceptance evidence."""
from pathlib import Path

import pytest

from deploy.workload_fixture_faults import FaultInjector, SCHEMA, bind, resources, validate
from deploy.workload_installation import Journal, LinuxBackend, exclusive, identity, execute
from deploy.workload_recovery_inventory import inventory
from deploy.workload_mutation import mutate
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_installation import Backend, packet

GENERATION='a'*32


def unbound(step,resource='operation',boundary='intent'):
    return dict(schema=SCHEMA,fixture_only=True,recovery_protocol=4,step=step,resource=resource,boundary=boundary)


def setup_fault(tmp_path,plan,proposal=None):
    if proposal is None:proposal,_,_,_=packet(tmp_path)
    root=tmp_path/'fault-fixture';root.mkdir(mode=0o700)
    manifest=dict(schema='mldsafail.installation-fixture.v1',fixture_only=True,generation=GENERATION,
                  root=identity(root),recovery_fault_plan=bind(plan,GENERATION))
    raw=canonical(manifest);exclusive(root/'manifest.json',raw)
    injector=FaultInjector(root,manifest,digest(raw),proposal)
    return injector,proposal


def mutation_fixture(tmp_path,kind,boundary):
    proposal,_,_,_=packet(tmp_path)
    release=tmp_path/'release';release.mkdir(mode=0o700)
    source=proposal['identities'];source['resources']['release']['path']=str(release)
    source['manifest']['files']={'payload':dict(sha256=digest(b'owned'),bytes=5,mode=0o600)}
    source['manifest']['tools']={role:{} for role in ('interpreter','installer')}
    if kind=='bundle_directory':
        step='install:copy_bundle';path=release/'bundle';resource=step+':directory:'+str(path)
        action=lambda:path.mkdir(mode=0o700)
    elif kind=='bundle_file':
        step='install:copy_bundle';(release/'bundle').mkdir(mode=0o700)
        path=release/'bundle/payload';resource=step+':'+str(path)
        action=lambda:path.write_bytes(b'owned')
    elif kind=='tool_parent':
        step='install:tools';path=release/'tools';resource=step+':directory:'+str(path)
        action=lambda:path.mkdir(mode=0o700)
    else:
        step='install:tools';(release/'tools').mkdir(mode=0o700)
        path=release/'tools'/kind;resource=step+':'+kind
        def action():
            path.mkdir(mode=0o700);(path/'inert').write_bytes(b'owned')
    injector,_=setup_fault(tmp_path,unbound(step,resource,boundary),proposal)
    journal=Journal(tmp_path/'journal',digest(canonical(proposal)))
    journal.append('recovery_protocol',version=4);journal.append('intent',step=step,before=identity(path))
    return injector,journal,path,resource,action


@pytest.mark.parametrize('kind',['bundle_directory','bundle_file','tool_parent','interpreter','installer'])
@pytest.mark.parametrize('boundary',['intent','unacknowledged','applied'])
def test_real_artifact_faults_match_exact_resource_and_durable_boundary(tmp_path,kind,boundary):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,kind,boundary)
    with injector.scope(),pytest.raises(InterruptedError,match='disposable_fixture_recovery_fault'):
        mutate(journal,resource,lambda:identity(path),action,expected_effect=dict(effect='fixture_exclusive_creation'))
    assert path.exists()==(boundary!='intent')
    rows=[row for row in journal.rows if row.get('resource')==resource]
    assert rows[0]['event']=='mutation_intent'
    assert any(row['event']=='mutation_outcome' for row in rows)==(boundary=='applied')
    assert any(row['event']=='mutation_failed' for row in rows)==(boundary=='unacknowledged')
    injector.assert_fired(journal)
    record=next(row for row in journal.rows if row['event']=='fixture_recovery_fault_fired')
    assert record['mutation_intent_sha256']==digest(canonical(rows[0]))
    # One consumed marker never fires again, including after a fresh injector.
    marker=identity(injector.marker)
    assert injector.fire(journal,injector.plan['step'],resource,boundary) is False
    assert identity(injector.marker)==marker


class EngineBackend(Backend):
    acknowledge_apply=LinuxBackend.acknowledge_apply


MUTATING_STEPS=sorted({row['step'] for row in inventory()
                      if row['mutation']})


@pytest.mark.parametrize('step',MUTATING_STEPS)
@pytest.mark.parametrize('boundary',['intent','unacknowledged','applied'])
def test_whole_operation_hook_uses_existing_engine_boundaries_without_extra_effects(tmp_path,step,boundary):
    """Exercise engine dispatch with inert filesystem operation stand-ins."""
    proposal,raw,review,authority=packet(tmp_path)
    injector,_=setup_fault(tmp_path,unbound(step,boundary=boundary),proposal)
    backend=EngineBackend(tmp_path)
    phase=step.split(':')[0]
    if phase=='rollback':execute(proposal,raw,review,authority(),backend)
    def fault(actual,point):injector.operation(backend.journal,actual,point)
    with injector.scope(),pytest.raises(InterruptedError,match='disposable_fixture_recovery_fault'):
        execute(proposal,raw,review,authority(phase),backend,phase=phase,fault=fault)
    journal=Journal(tmp_path/'journal',digest(raw));injector.assert_fired(journal)
    target=tmp_path/step.replace(':','-')
    assert target.exists()==(boundary!='intent')
    pending=journal.outcome(step);assert pending['event']=='intent'
    acknowledgements=[row for row in journal.rows if row['event']=='resource_acknowledgement' and row['step_id']==step]
    assert bool(acknowledgements)==(boundary=='applied')
    assert backend.calls.count(step)==(boundary!='intent')


@pytest.mark.parametrize('version',[1,2,3])
def test_optional_v4_faults_do_not_upgrade_historical_journals(tmp_path,version):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,'bundle_file','intent')
    # Build a separate historical journal; never change its header in place.
    root=tmp_path/'historical';root.mkdir(mode=0o700)
    old=Journal(root,journal.binding)
    if version!=1:old.append('recovery_protocol',version=version)
    old.append('intent',step=injector.plan['step'],before=identity(path))
    with injector.scope(),pytest.raises(WorkloadBlocked,match='protocol_four_required'):
        mutate(old,resource,lambda:identity(path),action)
    assert old.recovery_protocol==version and not path.exists() and not injector.marker.exists()


def test_absent_plan_is_disabled_and_context_resets_after_interruption(tmp_path):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,'bundle_file','intent')
    with injector.scope(),pytest.raises(InterruptedError):mutate(journal,resource,lambda:identity(path),action)
    untouched=tmp_path/'unrelated'
    mutate(journal,'unrelated',lambda:identity(untouched),lambda:untouched.write_bytes(b'normal'))
    assert untouched.read_bytes()==b'normal'
    disabled=FaultInjector(tmp_path,{},'not-used',{})
    with disabled.scope():assert disabled.operation(None,'not-a-step','intent') is False
    disabled.assert_fired(None)
    assert not (tmp_path/'recovery-fault-fired.json').exists()


@pytest.mark.parametrize('field,value',[
    ('generation','b'*32),('recovery_protocol',3),('fixture_only',False),('step','install:arbitrary'),
    ('resource','/bin/sh'),('resource','install:copy_bundle:/tmp/../escape'),('boundary','outcome'),
    ('boundary',[]),('argv',['/bin/true']),('command','anything')])
def test_plan_rejects_stale_generation_unknown_points_and_execution_fields(tmp_path,field,value):
    plan=bind(unbound('install:copy_bundle'),GENERATION);plan[field]=value
    with pytest.raises(WorkloadBlocked):validate(plan,GENERATION)


def test_proposal_binding_rejects_resource_outside_frozen_inventory(tmp_path):
    proposal,_,_,_=packet(tmp_path)
    plan=bind(unbound('install:copy_bundle','install:copy_bundle:/unowned/file'),GENERATION)
    with pytest.raises(WorkloadBlocked,match='resource_not_in_proposal'):validate(plan,GENERATION,proposal)
    assert all(step in MUTATING_STEPS for step,resource in resources(proposal))


@pytest.mark.parametrize('change',['bytes','replacement','hardlink','missing_ack','root','proposal','manifest','plan','parent'])
def test_single_use_marker_tampering_blocks_without_second_interruption(tmp_path,change):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,'bundle_file','intent')
    with injector.scope(),pytest.raises(InterruptedError):mutate(journal,resource,lambda:identity(path),action)
    if change=='bytes':injector.marker.write_bytes(b'{}')
    elif change=='replacement':
        saved=injector.marker.read_bytes();injector.marker.rename(injector.root/'preserved')
        exclusive(injector.marker,saved)
    elif change=='hardlink':__import__('os').link(injector.marker,injector.root/'linked')
    elif change=='missing_ack':journal.rows=[row for row in journal.rows if row['event']!='fixture_recovery_fault_fired']
    elif change=='root':injector.root.rename(tmp_path/'preserved-root');injector.root.mkdir(mode=0o700)
    elif change=='proposal':journal.binding='b'*64
    elif change=='manifest':(injector.root/'manifest.json').write_bytes(b'{}')
    elif change=='plan':injector.plan['boundary']='unacknowledged'
    elif change=='parent':journal.rows=[row for row in journal.rows if row['event']!='intent']
    with pytest.raises(WorkloadBlocked):injector.fire(journal,injector.plan['step'],resource,'intent')
    assert not path.exists()


def test_crash_between_marker_creation_and_acknowledgement_preserves_uncertainty(tmp_path,monkeypatch):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,'bundle_file','intent')
    original=journal.append
    def append(event,**values):
        if event=='fixture_recovery_fault_fired':raise OSError('simulated journal failure')
        original(event,**values)
    monkeypatch.setattr(journal,'append',append)
    with injector.scope(),pytest.raises(OSError,match='simulated journal failure'):
        mutate(journal,resource,lambda:identity(path),action)
    assert injector.marker.exists() and not path.exists()
    monkeypatch.setattr(journal,'append',original)
    with pytest.raises(WorkloadBlocked,match='marker_unacknowledged_or_replaced'):
        injector.fire(journal,injector.plan['step'],resource,'intent')


def test_mismatched_point_and_unreached_target_do_not_claim_injection(tmp_path):
    injector,journal,path,resource,action=mutation_fixture(tmp_path,'bundle_file','intent')
    assert injector.fire(journal,injector.plan['step'],'operation','intent') is False
    assert not injector.marker.exists()
    with pytest.raises(WorkloadBlocked,match='target_not_reached'):injector.assert_fired(journal)
    assert not path.exists()


@pytest.mark.parametrize('resource',[
    'output_backing','output_mountpoint','output_format','output_mount_unit','output_daemon_reload',
    'output_mount_activation','output_mount_owner','delegation_start','delegation_controllers'])
@pytest.mark.parametrize('boundary',['intent','unacknowledged','applied'])
def test_scoped_prerequisite_faults_reach_concrete_owned_effect_boundaries(tmp_path,monkeypatch,resource,boundary):
    """Filesystem effects are real; manager/format/mount adapters are synthetic."""
    from tests.test_workload_prerequisite_receipt import prerequisite_fixture
    from deploy.workload_prerequisites import apply
    source,command,initial=prerequisite_fixture(tmp_path,monkeypatch)
    source['manifest']=dict(files={},configurations={})
    proposal=dict(identities=source)
    if resource=='delegation_start':
        root=Path(source['resources']['delegation']['path'])
        (root/'cgroup.subtree_control').unlink();root.rmdir()
        source['resources']['delegation']['state']='proposed'
        original_command=command
        def command(argv):
            if 'start' in argv and 'mldsafail-heavy.slice' in argv:
                root.mkdir();(root/'cgroup.subtree_control').write_text('');return b''
            return original_command(argv)
    injector,_=setup_fault(tmp_path,unbound('install:prerequisites',resource,boundary),proposal)
    journal=Journal(initial.root,digest(canonical(proposal)))
    journal.append('recovery_protocol',version=4);journal.append('intent',step='install:prerequisites',before={})
    with injector.scope(),pytest.raises(InterruptedError,match='disposable_fixture_recovery_fault'):
        apply(source,command,journal)
    injector.assert_fired(journal)
    rows=[row for row in journal.rows if row.get('resource')==resource and
          row['event'] in ('mutation_intent','mutation_outcome','mutation_failed')]
    assert rows[0]['event']=='mutation_intent'
    assert any(row['event']=='mutation_outcome' for row in rows)==(boundary=='applied')
    assert any(row['event']=='mutation_failed' for row in rows)==(boundary=='unacknowledged')
    saved={Path(source['resources']['output'][key]):identity(source['resources']['output'][key])
           for key in ('path','backing_file')}
    with pytest.raises(WorkloadBlocked):apply(source,command,journal)
    assert all(identity(path)==before for path,before in saved.items())
