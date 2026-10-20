import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from deploy.investigation_runtime import LoggedClient, NativeInvestigation, admit_resources


def test_native_adapter_refuses_this_unbound_host(tmp_path):
    runtime=NativeInvestigation(tmp_path,{},dict(docker=['docker']))
    with pytest.raises((RuntimeError,KeyError)):
        runtime.host_gate()
    assert not list(tmp_path.iterdir())


def test_logged_client_combined_cap_and_positive_stop(tmp_path):
    process=subprocess.Popen([sys.executable,'-c','print("too much")'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out=(tmp_path/'out').open('wb');err=(tmp_path/'err').open('wb')
    client=LoggedClient(process,out,err,{'bytes':128*1024**2-1})
    try:
        deadline=time.monotonic()+2
        with pytest.raises(RuntimeError,match='log_output_limit'):
            while time.monotonic()<deadline:
                client.poll();time.sleep(.01)
    finally:
        assert client.stop()
    assert process.poll() is not None


def test_hung_log_writer_cannot_report_stopped(tmp_path):
    process=subprocess.Popen([sys.executable,'-c','print("hello")'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    gate=threading.Event()
    class Hung(io.BytesIO):
        def write(self,data): gate.wait(5);return super().write(data)
    client=LoggedClient(process,Hung(),io.BytesIO(),{'bytes':0})
    try:
        deadline=time.monotonic()+2
        with pytest.raises(RuntimeError,match='write_deadline'):
            while time.monotonic()<deadline:
                client.poll();time.sleep(.01)
        with pytest.raises(RuntimeError,match='writer_remains'): client.stop()
    finally:
        gate.set()
        if client.output_thread: client.output_thread.join(timeout=1)
        client.stop()


def test_daemon_filter_is_explicit_label_and_restarts_rejected(tmp_path):
    runtime=NativeInvestigation(tmp_path,dict(operation_id='a'*32),dict(docker=['docker']))
    runtime.host_gate=lambda:True
    runtime.cleanup_authority=lambda:True
    seen=[]
    def command(args):
        seen.append(args)
        return b''
    runtime.command=command
    assert runtime.identity()
    assert seen[0][-1]=='label=org.mldsafail.capacity-investigation='+'a'*32
    assert runtime.stopped()


def test_resource_admission_rejects_expanded_limits():
    row=dict(Image='image',Config={'Image':'image'},HostConfig=dict(CgroupParent='parent',Memory=512*1024**2,
        NanoCpus=1000000000,PidsLimit=256,NetworkMode='none',PortBindings={},Privileged=False,
        ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges']))
    admit_resources(row,image='image',parent='parent',memory=512*1024**2,cpus=1,pids=256)
    row['HostConfig']['Memory']*=2
    with pytest.raises(RuntimeError):
        admit_resources(row,image='image',parent='parent',memory=512*1024**2,cpus=1,pids=256)


def test_audit_controller_mounts_and_socket_are_admitted_exactly():
    from deploy.investigation_runtime import admit_controller
    image='sha256:'+'b'*64
    packet={'controller':{'index':image}}
    command=dict(phase='audit',argv=['docker','run','--cgroup-parent','parent','--mount',
        'type=bind,src=/srv/epoch,dst=/srv/epoch,readonly','--entrypoint','/app/.venv/bin/python',image,'-c','audit-only'])
    row=dict(Image=image,Config=dict(Image=image,Entrypoint=['/app/.venv/bin/python'],Cmd=['-c','audit-only'],User='0:0',Env=[]),
        Mounts=[dict(Type='bind',Source='/srv/epoch',Destination='/srv/epoch',RW=False)],
        HostConfig=dict(CgroupParent='parent',Memory=512*1024**2,NanoCpus=1000000000,PidsLimit=256,
            NetworkMode='none',PortBindings={},Privileged=False,ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges']))
    admit_controller(row,packet,command)
    row['Mounts'].append(dict(Type='bind',Source='/run/docker.sock',Destination='/var/run/docker.sock',RW=True))
    with pytest.raises(RuntimeError,match='mounts'):
        admit_controller(row,packet,command)


def test_capacity_abort_does_not_block_emergency_cleanup(tmp_path):
    runtime=NativeInvestigation(tmp_path,dict(operation_id='a'*32),dict(docker=['docker']))
    def rejected():raise RuntimeError('filesystem_floor')
    runtime.host_gate=rejected
    runtime.cleanup_authority=lambda:True
    row=dict(Id='id',Config={'Labels':{'org.mldsafail.capacity-investigation':'a'*32}},State={'Running':True,'StartedAt':'birth'})
    runtime.controllers=[dict(container_id='id')]
    calls=[]
    def command(args):
        calls.append(args)
        if args[0]=='ps':return b'id'
        if args[0]=='inspect':return json.dumps([row]).encode()
        if args[0]=='kill':row['State']['Running']=False
        return b''
    runtime.command=command
    assert runtime.stop()
    assert ['kill','id'] in calls


def test_execution_and_cleanup_configuration_are_hash_bound(tmp_path):
    import hashlib
    from deploy.production_preparation import read_manifest
    from deploy.recovery_journal import atomic_json
    configuration={'docker':['docker'],'retained_services':['protected-service']}
    path=tmp_path/'configuration.json'
    atomic_json(path,configuration)
    expected=hashlib.sha256(path.read_bytes()).hexdigest()
    packet={'configuration_sha256':expected}
    value=read_manifest(path,expected_sha256=expected)
    runtime=NativeInvestigation(tmp_path,packet,value,configuration_sha256=expected)
    assert runtime.validate_configuration()
    atomic_json(path,dict(configuration,retained_services=[]))
    with pytest.raises(ValueError,match='digest'):
        read_manifest(path,expected_sha256=expected)
    changed=NativeInvestigation(tmp_path,packet,dict(configuration,retained_services=[]))
    with pytest.raises(ValueError,match='configuration_not_bound'):
        changed.cleanup()
