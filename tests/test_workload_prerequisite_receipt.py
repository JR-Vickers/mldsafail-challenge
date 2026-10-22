import json
import subprocess
import sys
import pytest

from deploy.workload_installation import identity
from deploy.workload_prerequisites import root_exclusive_write,apply,absent_mount_namespace
from deploy.workload_release import digest
from mldsafail.evaluator.workload import WorkloadBlocked


def test_exclusive_writer_acknowledges_created_birth_and_bytes(tmp_path):
    path=tmp_path/'mount-unit';data=b'[Mount]\nWhat=/owned/fixture.ext4\n'
    argv=root_exclusive_write(path,data)
    assert argv[:3]==['/usr/bin/sudo','-n','/usr/bin/python3']
    # Run the same stdlib writer without elevation against this test's files.
    result=subprocess.run([sys.executable,*argv[3:]],capture_output=True,check=True)
    assert json.loads(result.stdout)==dict(identity(path,content=False),sha256=digest(data))
    assert path.read_bytes()==data
    failed=subprocess.run([sys.executable,*argv[3:]],capture_output=True)
    assert failed.returncode!=0 and path.read_bytes()==data


@pytest.mark.parametrize('change',[
    dict(LoadState='loaded',FragmentPath='/usr/lib/systemd/system/vendor.mount'),
    dict(LoadState='loaded',FragmentPath='/run/systemd/system/runtime.mount'),
    dict(LoadState='loaded',Transient='yes'),
    dict(ActiveState='failed'),
])
def test_existing_mount_namespace_blocks_before_any_allocation(tmp_path,change):
    output=dict(state='proposed',path=str(tmp_path/'output'),backing_file=str(tmp_path/'backing'),bytes=16*1024**2)
    source=dict(resources=dict(release=dict(path=str(tmp_path/'new')),output=output))
    row=dict(LoadState='not-found',ActiveState='inactive',FragmentPath='',SourcePath='',Transient='no');row.update(change)
    calls=[]
    def command(argv):
        calls.append(argv);assert 'show' in argv
        return '\n'.join(key+'='+value for key,value in row.items()).encode()
    with pytest.raises(WorkloadBlocked,match='namespace_not_absent'):apply(source,command,None)
    assert len(calls)==1 and not (tmp_path/'output').exists() and not (tmp_path/'backing').exists()


def test_mount_namespace_requires_complete_explicit_not_found_observation():
    with pytest.raises(WorkloadBlocked,match='observation_incomplete'):
        absent_mount_namespace('fixture.mount',lambda argv:b'LoadState=not-found\n')


def test_systemd_escaped_host_file_does_not_weaken_bundle_path_policy(tmp_path):
    from deploy.workload_installation import read_owned_file
    from deploy.workload_release import regular
    path=tmp_path/r'home-fixture\x2dv3.mount';path.write_bytes(b'[Mount]\n');path.chmod(0o600)
    assert read_owned_file(path,None)==(b'[Mount]\n',0o600)
    with pytest.raises(WorkloadBlocked,match='release_path_invalid'):regular(tmp_path,path.name)


@pytest.mark.parametrize('changed',['device','inode','offset','size_limit'])
def test_kernel_loop_binding_rejects_substituted_backing(changed):
    from deploy.workload_installed import loop_backing
    backing=dict(device=41,inode=52)
    observed=dict(device=41,inode=52,offset=0,size_limit=0,rdev=7)
    mounted=dict(source_device='/dev/loop7')
    assert loop_backing(mounted,backing,lambda argv:json.dumps(observed))==observed
    observed[changed]+=1
    with pytest.raises(WorkloadBlocked,match='backing_changed'):
        loop_backing(mounted,backing,lambda argv:json.dumps(observed))


def test_missing_mount_acknowledgement_blocks_adoption():
    from types import SimpleNamespace
    from deploy.workload_installed import verify_output_ownership
    with pytest.raises(WorkloadBlocked,match='ack_missing'):
        verify_output_ownership(dict(resources=dict(output={})),{},SimpleNamespace(rows=[]),None)


def prerequisite_fixture(tmp_path,monkeypatch):
    """Filesystem operations are real; systemd/mount/format observations synthetic."""
    import pathlib,os
    if not hasattr(os,'posix_fallocate'):
        monkeypatch.setattr(os,'posix_fallocate',lambda fd,offset,length:os.ftruncate(fd,offset+length),raising=False)
    import deploy.workload_prerequisites as prerequisites
    import deploy.workload_installed as installed
    from deploy.workload_installation import Journal
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    journal=Journal(root,'a'*64)
    system=tmp_path/'system';system.mkdir();(system/'local-fs.target.wants').mkdir()
    delegate=tmp_path/'heavy';delegate.mkdir();(delegate/'cgroup.subtree_control').write_text('')
    output=dict(state='proposed',path=str(tmp_path/'output'),backing_file=str(tmp_path/'backing'),bytes=4096)
    source=dict(resources=dict(release=dict(path=str(tmp_path/'new')),output=output,
                               delegation=dict(state='observed',path=str(delegate))),host=dict(uid=__import__('os').getuid()))
    def path(value):
        value=str(value)
        return pathlib.Path(value.replace('/etc/systemd/system',str(system),1))
    monkeypatch.setattr(prerequisites,'Path',path)
    def root_identity(value,**kwargs):
        row=identity(value,**kwargs)
        if pathlib.Path(value).is_relative_to(system) and row['state']=='observed':row['uid']=0
        return row
    monkeypatch.setattr(prerequisites,'identity',root_identity)
    namespace=dict(LoadState='not-found',ActiveState='inactive',FragmentPath='',SourcePath='',Transient='no')
    name,contents=prerequisites.mount_unit(output);unit=system/name
    def command(argv):
        if 'show' in argv:return '\n'.join(k+'='+v for k,v in namespace.items()).encode()
        if 'mkfs.ext4' in argv[2]:
            with pathlib.Path(output['backing_file']).open('r+b') as stream:stream.write(b'synthetic-format')
        elif argv[:3]==['/usr/bin/sudo','-n','/usr/bin/python3']:
            row=json.loads(subprocess.check_output([sys.executable,*argv[3:]]));row['uid']=0
            return json.dumps(row).encode()
        elif 'daemon-reload' in argv:
            namespace.update(LoadState='loaded',FragmentPath=str(unit))
        elif 'enable' in argv:
            (system/'local-fs.target.wants'/name).symlink_to(unit);namespace['ActiveState']='active'
        return b''
    monkeypatch.setattr(installed,'mount',lambda value:dict(filesystem='ext4',mount_options=['noexec','nosuid','nodev']))
    monkeypatch.setattr(installed,'loop_backing',lambda *args:dict(device=1,inode=2))
    def enable(root,uid):
        (delegate/'cgroup.subtree_control').write_text('cpu memory pids')
        return identity(delegate)
    monkeypatch.setattr(prerequisites,'enable_delegation',enable)
    return source,command,journal


PREREQUISITE_MUTATIONS=['output_backing','output_mountpoint','output_format','output_mount_unit',
                        'output_daemon_reload','output_mount_activation','output_mount_owner','delegation_controllers']


def test_prerequisite_mutations_all_have_ordered_intents_and_observed_outcomes(tmp_path,monkeypatch):
    source,command,journal=prerequisite_fixture(tmp_path,monkeypatch)
    apply(source,command,journal)
    intents=[row['resource'] for row in journal.rows if row['event']=='mutation_intent']
    outcomes=[row['resource'] for row in journal.rows if row['event']=='mutation_outcome']
    assert intents==outcomes==PREREQUISITE_MUTATIONS
    assert all('observed' in row for row in journal.rows if row['event']=='mutation_outcome')


@pytest.mark.parametrize('resource',PREREQUISITE_MUTATIONS)
@pytest.mark.parametrize('boundary',['intent','applied','outcome'])
def test_prerequisite_interruption_preserves_substep_evidence(tmp_path,monkeypatch,resource,boundary):
    source,command,journal=prerequisite_fixture(tmp_path,monkeypatch)
    def fault(name,point):
        if (name,point)==(resource,boundary):raise InterruptedError('injected')
    with pytest.raises(InterruptedError):apply(source,command,journal,fault=fault)
    intents=[row for row in journal.rows if row['event']=='mutation_intent']
    assert intents[-1]['resource']==resource
    rows=[row for row in journal.rows if row.get('resource')==resource]
    if boundary=='intent':assert rows[-1]['event']=='mutation_intent'
    if boundary=='applied':assert rows[-1]['event']=='mutation_failed' and rows[-1]['observed'] is not None
    if boundary=='outcome':assert rows[-1]['event']=='mutation_outcome'
