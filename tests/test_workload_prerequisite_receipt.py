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
