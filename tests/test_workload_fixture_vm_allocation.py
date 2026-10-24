"""Fresh case allocation never shares a writable trial namespace."""
import json

import pytest

from deploy.workload_installation import exclusive
from deploy.workload_release import canonical, digest
from scripts.workload_vm_fixture import allocate


def inputs(tmp_path):
    image=tmp_path/'cloud.img';exclusive(image,b'fixture-cloud-image')
    download=tmp_path/'download.json'
    exclusive(download,canonical(dict(url='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
                                      sha256=digest(image.read_bytes()))))
    return image,download


def test_each_case_gets_independent_base_bytes_and_namespace(tmp_path,monkeypatch):
    image,download=inputs(tmp_path)
    monkeypatch.setattr('scripts.workload_vm_fixture.subprocess.check_output',lambda *args,**kwargs:'')
    first=allocate(tmp_path/'first',image,download,case='complete')
    second=allocate(tmp_path/'second',image,download,case='partial-snapshots')
    assert (first/'base.img').stat().st_ino!=(second/'base.img').stat().st_ino
    assert (first/'base.img').stat().st_nlink==(second/'base.img').stat().st_nlink==1
    (first/'base.img').write_bytes(b'changed-copy')
    assert image.read_bytes()==(second/'base.img').read_bytes()==b'fixture-cloud-image'
    assert not json.loads((first/'allocation-complete.json').read_bytes())['namespaces_shared_with_previous_trial']


def test_active_image_is_never_copied(tmp_path,monkeypatch):
    image,download=inputs(tmp_path)
    monkeypatch.setattr('scripts.workload_vm_fixture.subprocess.check_output',
                        lambda *args,**kwargs:'qemu-system-x86_64 -drive file='+str(image))
    with pytest.raises(AssertionError):allocate(tmp_path/'new',image,download,case='complete')
    assert not (tmp_path/'new').exists()


def test_existing_namespace_and_changed_source_are_refused(tmp_path,monkeypatch):
    image,download=inputs(tmp_path)
    monkeypatch.setattr('scripts.workload_vm_fixture.subprocess.check_output',lambda *args,**kwargs:'')
    root=allocate(tmp_path/'new',image,download,case='complete')
    with pytest.raises(FileExistsError):allocate(root,image,download,case='partial-configurations')
    image.write_bytes(b'replacement-source')
    with pytest.raises(AssertionError):allocate(tmp_path/'other',image,download,case='complete')
    assert not (tmp_path/'other').exists()


def test_vm_readiness_timeout_is_a_recorded_read_poll_not_a_failed_launch(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import subprocess
    from scripts.workload_vm_fixture import run
    root=tmp_path/'guest';root.mkdir(mode=0o700)
    exclusive(root/'base.img',b'base')
    exclusive(root/'download.json',canonical(dict(sha256=digest(b'base'))))
    polls=[]
    def command(argv,**kwargs):
        if argv[0]=='ssh-keygen':
            key=root/argv[-1];key.write_text('synthetic test key');key.with_name(key.name+'.pub').write_text('ssh-ed25519 synthetic')
        elif argv[0]=='ssh':
            polls.append(argv)
            if len(polls)==1:raise subprocess.TimeoutExpired(argv,10)
            (root/'stop').touch()
        elif argv[0]=='qemu-img':(root/'disk.qcow2').write_bytes(b'disk')
        elif argv[0]=='hdiutil':(root/'seed.iso').write_bytes(b'seed')
        elif argv[0]=='lsof':return SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
        elif argv[0] in ('ps','mount'):return SimpleNamespace(returncode=0,stdout='')
        else:raise AssertionError(argv)
        return SimpleNamespace(returncode=0,stdout=b'x86_64\nsystemd\ncgroup2fs\nPython 3.12.3\n')
    class Process:
        pid=123
        returncode=None
        def __init__(self,argv,**kwargs):
            self.args=argv
            if argv[0]!='qemu-system-x86_64':
                command(argv)
                self.returncode=0
        def poll(self):return self.returncode
        def terminate(self):self.returncode=0
        def kill(self):self.returncode=-9
        def wait(self,**kwargs):return self.returncode
    monkeypatch.setattr('scripts.workload_vm_fixture.subprocess.run',command)
    monkeypatch.setattr('scripts.workload_vm_fixture.subprocess.Popen',Process)
    monkeypatch.setattr('scripts.workload_vm_fixture.os.killpg',lambda *args:(_ for _ in ()).throw(ProcessLookupError()))
    run(root)
    assert len(polls)==2
    assert len(list(root.glob('readiness-poll-*.json')))==1
    assert json.loads((root/'stopped.json').read_bytes())['reaped']


def test_resume_rejects_replaced_writable_disk_before_launch(tmp_path,monkeypatch):
    import time
    from deploy.workload_installation import identity
    from scripts.workload_vm_fixture import resume,vm_argv
    root=tmp_path/'guest';root.mkdir(mode=0o700)
    for name in ('base.img','disk.qcow2','seed.iso'):exclusive(root/name,name.encode())
    owner=dict(origin='local_linux',port=12345,qemu_argv=vm_argv(root,12345),base_sha256=digest(b'base.img'))
    exclusive(root/'ownership.json',canonical(owner))
    artifacts={name:dict(identity(root/name,content=False),sha256=digest((root/name).read_bytes())) for name in ('base.img','disk.qcow2','seed.iso')}
    exclusive(root/'stopped.json',canonical(dict(reaped=True,process_group_empty=True,inactivity_verified=True,
        artifacts=artifacts,owner_sha256=digest(canonical(owner)),recorded_at=time.time())))
    replacement=root/'new-disk';exclusive(replacement,b'disk.qcow2');replacement.replace(root/'disk.qcow2')
    monkeypatch.setattr('scripts.workload_vm_fixture.inactive',lambda root:None)
    with pytest.raises(Exception,match='stopped_artifact_replaced'):resume(root)
    assert not list(root.glob('resume-*'))


def test_legacy_resume_requires_explicit_fresh_adoption_audit(tmp_path,monkeypatch):
    from scripts.workload_vm_fixture import resume,vm_argv
    root=tmp_path/'guest';root.mkdir(mode=0o700)
    for name in ('base.img','disk.qcow2','seed.iso'):exclusive(root/name,name.encode())
    exclusive(root/'ownership.json',canonical(dict(origin='local_linux',port=12345,qemu_argv=vm_argv(root,12345),base_sha256=digest(b'base.img'))))
    exclusive(root/'stopped.json',canonical(dict(reaped=True)))
    monkeypatch.setattr('scripts.workload_vm_fixture.inactive',lambda root:None)
    with pytest.raises(Exception,match='legacy_resume_audit_required'):resume(root)
    assert not list(root.glob('resume-*'))


def test_resume_generation_cannot_borrow_replaced_root_owner(tmp_path,monkeypatch):
    import time
    from deploy.workload_installation import identity
    from scripts.workload_vm_fixture import resume,vm_argv
    root=tmp_path/'guest';root.mkdir(mode=0o700)
    for name in ('base.img','disk.qcow2','seed.iso'):exclusive(root/name,name.encode())
    owner=dict(origin='local_linux',port=12345,qemu_argv=vm_argv(root,12345),base_sha256=digest(b'base.img'))
    exclusive(root/'ownership.json',canonical(owner));exclusive(root/'stopped.json',canonical(dict(reaped=True)))
    generation=root/('resume-'+'a'*32);generation.mkdir(mode=0o700)
    child=dict(parent_ownership_sha256=digest(canonical(owner)),pid=123)
    exclusive(generation/'ownership.json',canonical(child))
    artifacts={name:dict(identity(root/name,content=False),sha256=digest((root/name).read_bytes())) for name in ('base.img','disk.qcow2','seed.iso')}
    exclusive(generation/'stopped.json',canonical(dict(reaped=True,process_group_empty=True,inactivity_verified=True,
        artifacts=artifacts,owner_sha256=digest(canonical(child)),recorded_at=time.time()+1)))
    replacement=dict(owner,port=12346,qemu_argv=vm_argv(root,12346))
    (root/'ownership.json').unlink();exclusive(root/'ownership.json',canonical(replacement))
    monkeypatch.setattr('scripts.workload_vm_fixture.inactive',lambda root:None)
    with pytest.raises(Exception,match='parent_ownership_replaced'):resume(root)
    assert len(list(root.glob('resume-*')))==1
