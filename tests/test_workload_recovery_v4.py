"""Protocol-four recovery engineering; synthetic tests are not native acceptance."""
from copy import deepcopy

import pytest

from deploy.workload_installation import INSTALL, ROLLBACK, Journal, LinuxBackend, identity
from deploy.workload_mutation import classify, mutate
from deploy.workload_recovery_inventory import OPERATIONS, disposition, inventory, transition
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_installation_substeps import backend
from tests.test_workload_artifacts import archive
from deploy.workload_artifacts import archive_inventory
from tests.test_native_workload import fixture as native_fixture


def protocol_four(instance, journal, step):
    journal.append('recovery_protocol',version=4)
    journal.append('intent',step=step['id'],before={})


def test_inventory_covers_every_step_and_internal_effect_once():
    rows=inventory()
    assert {row['step'] for row in rows} == {'install:'+name for name in INSTALL}|{'rollback:'+name for name in ROLLBACK}
    assert len(rows)==len({(row['step'],row['effect']) for row in rows})
    assert set(OPERATIONS)==set(INSTALL)|set(ROLLBACK)
    assert all(row['observer']=='LinuxBackend.observe:'+row['operation'] for row in rows)
    assert {'daemon_image','format','mount','service_manager','dependency_tree','unit'} <= {row['kind'] for row in rows}


@pytest.mark.parametrize('effect',inventory(),ids=lambda row:row['step']+'/'+row['effect'])
def test_each_effect_has_conservative_before_unacknowledged_and_acknowledged_rules(effect):
    args=dict(identity_matches=True,postconditions=True)
    if not effect['mutation']:
        assert disposition(effect,acknowledged=False,**args)=='verify_read_only'
        return
    # Before an effect, fresh authority is still necessary; merely observing
    # desired settings after an unacknowledged effect gives no ownership.
    assert disposition(effect,acknowledged=False,**args)=='unacknowledged_preserve_and_block'
    assert disposition(effect,acknowledged=True,**args)=='completed'
    for field in ('identity_matches','postconditions'):
        changed=dict(args);changed[field]=False
        assert disposition(effect,acknowledged=True,**changed)=='replaced_or_incomplete_preserve_and_block'
    if effect['kind'] in ('daemon_image','format','mount','service_manager'):
        assert disposition(effect,acknowledged=False,safe_absence=True,**args)=='unacknowledged_preserve_and_block'


@pytest.mark.parametrize('version',[1,2,3,4])
def test_historical_journals_never_upgrade_implicitly(tmp_path,version):
    root=tmp_path/'journal';root.mkdir(mode=0o700);journal=Journal(root,'a'*64)
    if version!=1:journal.append('recovery_protocol',version=version)
    else:journal.append('legacy_checkpoint')
    journal.append('intent',step='install:fixture',before={})
    target=tmp_path/'target'
    mutate(journal,'file',lambda:identity(target),lambda:target.write_bytes(b'owned'),
           expected_effect=dict(effect='exclusive_file',sha256=digest(b'owned')))
    reopened=Journal(root,'a'*64)
    assert reopened.recovery_protocol==version
    assert classify(reopened,'file',identity(target))=='completed'
    assert ('resource_identity' in reopened.rows[-1])==(version==4)


@pytest.mark.parametrize('field',['resource_identity','expected_transition','parent_intent_sha256',
                                'mutation_intent_sha256','operation','step_id'])
def test_v4_substep_rejects_receipt_substitution(tmp_path,field):
    instance,journal=backend(tmp_path);step=dict(id='install:configurations',action='configurations')
    protocol_four(instance,journal,step);target=instance.root/'owned'
    mutate(journal,'file',lambda:identity(target),lambda:target.write_bytes(b'owned'),
           expected_effect=dict(effect='exclusive_file'))
    journal.rows[-1][field]='substituted'
    with pytest.raises(WorkloadBlocked,match='binding_invalid'):classify(journal,'file',identity(target))


EXTERNAL=('quiesce_supervisor','dependencies','images','inhibit_scheduling','inhibit_containers',
          'units','prerequisites','supervisor_unit','start_paused','stop_supervisor')


@pytest.mark.parametrize('action',EXTERNAL)
def test_external_operations_cannot_adopt_unacknowledged_desired_state(tmp_path,action):
    instance,journal=backend(tmp_path);step=dict(id=('rollback:' if action=='stop_supervisor' else 'install:')+action,action=action)
    protocol_four(instance,journal,step)
    assert not instance.reconcilable(step,dict(verified=True),journal)
    assert journal.rows[-1]['event']=='intent'


@pytest.mark.parametrize('action',EXTERNAL)
def test_acknowledged_operation_needs_exact_identity_and_complete_postconditions(tmp_path,monkeypatch,action):
    instance,journal=backend(tmp_path);step=dict(id=('rollback:' if action=='stop_supervisor' else 'install:')+action,action=action)
    protocol_four(instance,journal,step)
    current=dict(verified=True,identity=dict(inode=123));extra=dict(daemon_birth=1)
    monkeypatch.setattr(instance,'observe',lambda *args:deepcopy(current))
    monkeypatch.setattr(instance,'valid_outcome',lambda step,value,journal:value['verified'])
    monkeypatch.setattr(instance,'recovery_observation',lambda *args:deepcopy(extra))
    instance.acknowledge_apply(step,journal)
    receipt=journal.rows[-1]
    assert receipt['parent_intent_sha256']==digest(canonical(journal.rows[1]))
    assert receipt['expected_transition']==transition(step)
    assert instance.reconcilable(step,current,journal)
    invalid=dict(current,verified=False)
    assert not instance.reconcilable(step,invalid,journal)
    extra['daemon_birth']=2
    with pytest.raises(WorkloadBlocked,match='postconditions_changed'):instance.reconcilable(step,current,journal)


@pytest.mark.parametrize('field',['parent_intent_sha256','operation','resource_identity','expected_transition'])
def test_whole_operation_receipt_tampering_is_blocked(tmp_path,monkeypatch,field):
    instance,journal=backend(tmp_path);step=dict(id='install:images',action='images')
    protocol_four(instance,journal,step)
    monkeypatch.setattr(instance,'observe',lambda *args:dict(verified=True))
    monkeypatch.setattr(instance,'valid_outcome',lambda *args:True)
    monkeypatch.setattr(instance,'recovery_observation',lambda *args:{})
    instance.acknowledge_apply(step,journal);journal.rows[-1][field]='other'
    with pytest.raises(WorkloadBlocked,match='acknowledgement_binding_invalid'):
        instance.reconcilable(step,dict(verified=True),journal)


def copy_instance(tmp_path):
    instance,journal=backend(tmp_path);instance.bundle.rmdir()
    source=tmp_path/'frozen';source.mkdir(mode=0o700);rows={}
    for name,data in [('first.txt',b'first'),('nested/second.txt',b'second')]:
        target=source/name;target.parent.mkdir(exist_ok=True);target.write_bytes(data);target.chmod(0o600)
        rows[name]=dict(sha256=digest(data),bytes=len(data),mode=0o600)
    instance.recipe['bundle_root']=str(source);instance.source['manifest']['files']=rows
    journal.append('recovery_protocol',version=4)
    journal.append('outcome',step='install:create_release',observed=identity(instance.root))
    step=dict(id='install:copy_bundle',action='copy_bundle')
    journal.append('intent',step=step['id'],before=identity(instance.bundle))
    return instance,journal,step


@pytest.mark.parametrize('change',[None,'replace','missing_receipt','extra','parent_replaced'])
def test_copy_bundle_continues_only_acknowledged_files_and_untouched_remainder(tmp_path,monkeypatch,change):
    instance,journal,step=copy_instance(tmp_path)
    original=instance.file_substep
    def interrupt(*args,**kwargs):
        original(*args,**kwargs)
        raise InterruptedError('after acknowledged file')
    monkeypatch.setattr(instance,'file_substep',interrupt)
    with pytest.raises(InterruptedError):instance.apply(step,journal)
    saved=identity(instance.bundle/'first.txt')
    monkeypatch.setattr(instance,'file_substep',original)
    if change=='replace':
        target=instance.bundle/'first.txt';target.rename(instance.root/'preserved');target.write_bytes(b'first');target.chmod(0o600)
    if change=='missing_receipt':journal.rows=[row for row in journal.rows if row['event']!='mutation_outcome']
    if change=='extra':(instance.bundle/'unknown').write_bytes(b'preserve')
    if change=='parent_replaced':
        instance.bundle.rename(instance.root/'preserved-bundle');instance.bundle.mkdir(mode=0o700)
        (instance.root/'preserved-bundle'/'first.txt').rename(instance.bundle/'first.txt')
    observed=instance.partial_observation(step,journal)
    assert instance.partial_reconcilable(step,observed,journal)==(change is None)
    if change:return
    # The same substeps cannot skip merely because receipts exist.
    with pytest.raises(WorkloadBlocked,match='substep_changed'):
        instance.directory_substep(step,journal,instance.bundle)
    journal.append('reconciled_partial',step=step['id'],observed=observed)
    journal.append('intent',step=step['id'],before=observed)
    instance.apply(step,journal)
    assert identity(instance.bundle/'first.txt')==saved
    assert (instance.bundle/'nested/second.txt').read_bytes()==b'second'
    assert len([row for row in journal.rows if row['event']=='mutation_intent' and row['resource'].endswith('/first.txt')])==1


def test_tool_continuation_skips_verified_tree_without_extraction_replay(tmp_path,monkeypatch):
    import deploy.workload_mutation as mutation
    instance,journal=backend(tmp_path);data=archive();(instance.bundle/'tool.tar.gz').write_bytes(data)
    instance.source['manifest']['tools']={role:dict(archive='tool.tar.gz',members=archive_inventory(data))
                                        for role in ('interpreter','installer')}
    step=dict(id='install:tools',action='tools');protocol_four(instance,journal,step)
    original=mutation.mutate
    def interrupt(*args,**kwargs):
        result=original(*args,**kwargs)
        if args[1]=='install:tools:interpreter':raise InterruptedError('acknowledged interpreter')
        return result
    monkeypatch.setattr(mutation,'mutate',interrupt)
    with pytest.raises(InterruptedError):instance.apply(step,journal)
    saved=identity(instance.root/'tools/interpreter')
    observed=instance.partial_observation(step,journal)
    assert instance.partial_reconcilable(step,observed,journal)
    journal.append('reconciled_partial',step=step['id'],observed=observed)
    journal.append('intent',step=step['id'],before=observed)
    monkeypatch.setattr(mutation,'mutate',original);instance.apply(step,journal)
    assert identity(instance.root/'tools/interpreter')==saved
    assert (instance.root/'tools/installer').is_dir()


@pytest.mark.parametrize('reload,fragment,missing', [('yes','bound',False),('no','substitute',False),('no','bound',True)])
def test_unit_operation_observer_rejects_reload_selection_and_missing_visibility(tmp_path,reload,fragment,missing):
    instance,journal=backend(tmp_path);step=dict(id='install:units',action='units')
    manager=tmp_path/'manager';manager.mkdir();instance.source['host']['user_manager']['path']=str(manager)
    def command(argv):
        name=argv[3];path=instance.source['installation']['unit_directory']+'/'+name
        rows=dict(LoadState='loaded',FragmentPath=path if fragment=='bound' else '/substituted',
                  SourcePath='',DropInPaths='',NeedDaemonReload=reload)
        if missing:rows.pop('NeedDaemonReload')
        return '\n'.join(key+'='+value for key,value in rows.items()).encode()
    instance.command=command
    with pytest.raises(WorkloadBlocked):instance.recovery_observation(step,journal)


@pytest.mark.parametrize('resource',[
    'output_backing','output_mountpoint','output_format','output_mount_unit',
    'output_daemon_reload','output_mount_activation','output_mount_owner','delegation_controllers',
    'delegation_start'])
@pytest.mark.parametrize('boundary',['intent','applied','outcome'])
def test_v4_concrete_prerequisite_boundaries_observe_and_block_uncertain_replay(tmp_path,monkeypatch,resource,boundary):
    """Real files with fixture-specific systemd/format calls; never native proof."""
    import pathlib
    import deploy.workload_installation as installation
    import deploy.workload_prerequisites as prerequisites
    from tests.test_workload_prerequisite_receipt import prerequisite_fixture
    source,command,journal=prerequisite_fixture(tmp_path,monkeypatch)
    journal.append('recovery_protocol',version=4)
    step=dict(id='install:prerequisites',action='prerequisites')
    journal.append('intent',step=step['id'],before={})
    if resource=='delegation_start':
        root=pathlib.Path(source['resources']['delegation']['path'])
        (root/'cgroup.subtree_control').unlink();root.rmdir()
        source['resources']['delegation']['state']='proposed'
        original_command=command
        def command(argv):
            if 'start' in argv and 'mldsafail-heavy.slice' in argv:
                root.mkdir();(root/'cgroup.subtree_control').write_text('')
                return b''
            return original_command(argv)
    def fault(name,point):
        if (name,point)==(resource,boundary):raise InterruptedError('injected boundary')
    with pytest.raises(InterruptedError):prerequisites.apply(source,command,journal,fault=fault)
    # Read using the same owned fixture namespace as the concrete adapter.
    fixture_identity=prerequisites.identity
    monkeypatch.setattr(installation,'identity',lambda value,**kwargs:fixture_identity(prerequisites.Path(value),**kwargs))
    instance=object.__new__(LinuxBackend);instance.source=source;instance.command=command
    observations=instance.observe_substeps(step,journal)
    target=next(row for row in observations if row['resource']==resource)
    assert target['status'] != 'observation_required'
    assert 'error' not in target
    assert (target['status']=='completed')==(boundary=='outcome')
    before={path:identity(path) for path in (pathlib.Path(source['resources']['output']['backing_file']),
                                          pathlib.Path(source['resources']['output']['path']))}
    # No protocol-four path authorizes continuation of partial formats/mounts.
    assert not instance.partial_reconcilable(step,{},journal)
    with pytest.raises(WorkloadBlocked):prerequisites.apply(source,command,journal)
    assert {path:identity(path) for path in before}==before


@pytest.mark.parametrize('boundary',['intent','unacknowledged','acknowledged'])
@pytest.mark.parametrize('tamper',[None,'container_birth','daemon_birth'])
def test_concrete_container_policy_and_stop_recovery_boundaries(tmp_path,monkeypatch,boundary,tamper,native_fixture):
    """Concrete Docker adapter commands against an inert, file-backed daemon.

    No Docker daemon is contacted and these observations remain synthetic.
    """
    import json
    from mldsafail.evaluator.native_workload import NativeRuntime
    instance,journal=backend(tmp_path)
    identifier='c'*64
    row=dict(id=identifier,image='sha256:'+'d'*64,created_at='fixture-created',started_at='fixture-started',
             disposition='pause')
    instance.source['containers']=[row]
    store=tmp_path/'inert-daemon.json'
    record=dict(Id=identifier,Image=row['image'],Created=row['created_at'],
                State=dict(StartedAt=row['started_at'],Running=True),HostConfig=dict(RestartPolicy=dict(Name='always')))
    store.write_bytes(canonical(record))
    native_config=native_fixture[0].config
    raw=canonical(native_config)
    instance.source['recipe']['configuration_templates']['native']=raw.hex()
    instance.source['manifest']['configurations']['native']['sha256']=digest(raw)
    daemon=deepcopy(instance.source['host']['runtime_identity'])
    monkeypatch.setattr(NativeRuntime,'identity',lambda self:deepcopy(daemon))
    calls=[]
    def command(argv):
        current=json.loads(store.read_bytes());calls.append(argv)
        if 'inspect' in argv:return canonical([current])
        if 'update' in argv:current['HostConfig']['RestartPolicy']['Name']='no'
        elif 'stop' in argv:current['State']['Running']=False
        else:raise AssertionError(argv)
        store.write_bytes(canonical(current));return b''
    instance.command=command
    step=dict(id='install:inhibit_containers',action='inhibit_containers')
    journal.append('recovery_protocol',version=4)
    journal.append('intent',step=step['id'],before=instance.before(step,journal))
    if boundary!='intent':instance.apply(step,journal)
    if boundary=='acknowledged':instance.acknowledge_apply(step,journal)
    saved=store.read_bytes()
    if tamper=='container_birth':
        changed=json.loads(saved);changed['Created']='replaced';store.write_bytes(canonical(changed))
    if tamper=='daemon_birth':daemon['daemon_birth']['start_ticks']+=1
    if boundary=='intent' or tamper=='container_birth':
        with pytest.raises(WorkloadBlocked):instance.observe(step,journal)
    else:
        observed=instance.observe(step,journal)
        assert instance.valid_outcome(step,observed,journal)
        if boundary=='acknowledged' and tamper=='daemon_birth':
            with pytest.raises(WorkloadBlocked,match='daemon_changed'):instance.reconcilable(step,observed,journal)
        else:
            assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
    assert len([argv for argv in calls if 'update' in argv])==(boundary!='intent')
    assert len([argv for argv in calls if 'stop' in argv])==(boundary!='intent')
    # Reconciliation observers never call Docker update/stop or alter the fixture.
    if tamper!='container_birth':assert store.read_bytes()==saved


@pytest.mark.parametrize('action',['units','supervisor_unit','restore_units'])
@pytest.mark.parametrize('override',[None,'DropInPaths','SourcePath'])
def test_initial_unit_acknowledgement_rejects_unreviewed_loaded_sources(tmp_path,action,override):
    from tests.test_workload_installation import seal_snapshots
    instance,journal=backend(tmp_path)
    directory=tmp_path/'unit-directory';directory.mkdir()
    instance.source['installation']['unit_directory']=str(directory)
    manager=tmp_path/'manager';manager.mkdir();instance.source['host']['user_manager']['path']=str(manager)
    journal.append('recovery_protocol',version=4)
    step=dict(id=('rollback:' if action=='restore_units' else 'install:')+action,action=action)
    if action=='restore_units':
        originals={str(directory/name):dict(state='absent',path=str(directory/name)) for name in instance.proposal['units']}
        seal_snapshots(journal,originals)
        journal.append('outcome',step='install:units',observed={})
    else:
        for name in instance.unit_names(action):
            path=directory/name;path.write_text(instance.proposal['units'][name]);path.chmod(0o600)
    journal.append('intent',step=step['id'],before={})
    def command(argv):
        name=argv[3]
        fields=dict(LoadState='not-found' if action=='restore_units' else 'loaded',
                    FragmentPath='' if action=='restore_units' else str(directory/name),
                    SourcePath='',DropInPaths='',NeedDaemonReload='no')
        if override:fields[override]='/unreviewed/override'
        return '\n'.join(key+'='+value for key,value in fields.items()).encode()
    instance.command=command
    if override:
        with pytest.raises(WorkloadBlocked,match='loaded_unit_selection_changed'):instance.acknowledge_apply(step,journal)
        assert not any(row['event']=='resource_acknowledgement' for row in journal.rows)
    else:
        instance.acknowledge_apply(step,journal)
        assert instance.reconcilable(step,instance.observe(step,journal),journal)
