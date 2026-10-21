"""Inert rootless-image peer-authentication probe on a disposable socket only.

No production socket, Docker endpoint or database credential enters the image.
The caller must hold exact native-packet authority (or local rehearsal scope).
Unacknowledged container creation retains blocked ownership for reconciliation.
"""
import json
import os
from pathlib import Path
import socket
import threading
import time
import uuid

from deploy.workload_installation import exclusive,identity
from deploy.workload_release import canonical
from mldsafail.evaluator.native_workload import process_birth,require
from mldsafail.evaluator.workload_socket import PrivateSocket


def peer_uids(mapping):
    uid=mapping['coordinator_container_uid']
    rows=mapping['uid_map']
    accepted=[outside+uid-start for start,outside,count in rows if start<=uid<start+count]
    require(accepted==[os.getuid()],'socket_probe_owner_mapping_changed')
    for start,outside,count in rows:
        for candidate in (start,start+1):
            if start<=candidate<start+count and candidate!=uid and outside+candidate-start!=os.getuid():
                return uid,candidate
    require(False,'socket_probe_distinct_mapped_uid_missing')


def probe(image,mapping,journal,command,daemon_identity,*,seconds=40):
    require(type(seconds) is int and 15<=seconds<=60,'socket_probe_budget')
    uid,wrong=peer_uids(mapping)
    cleanup_deadline=time.monotonic()+seconds;deadline=cleanup_deadline-10
    original_daemon=daemon_identity(seconds=5)
    root=journal.root/('socket-probe-'+uuid.uuid4().hex)
    journal.append('socket_probe_intent',path=str(root),image=image,uid_mapping=mapping)
    root.mkdir(mode=0o700);path=root/'inert.sock'
    nonce=uuid.uuid4().hex;seen=[];stop=threading.Event();errors=[]
    class Protocol:
        def dispatch(self,request):
            require(request==dict(id=nonce,method='status',argument={}),'socket_probe_request')
            seen.append(time.monotonic_ns());return dict(inert_nonce=nonce)
    rows=[];blocked=False
    def checked(argv,*,cleanup=False):
        end=cleanup_deadline if cleanup else deadline
        require(time.monotonic()<end,'socket_probe_deadline')
        require(daemon_identity(seconds=max(.001,end-time.monotonic()))==original_daemon,'socket_probe_daemon_replaced')
        require(time.monotonic()<end,'socket_probe_deadline')
        return command(argv,seconds=max(.001,end-time.monotonic()))
    client=('import json,socket,sys,time;time.sleep(.3);s=socket.socket(socket.AF_UNIX);s.settimeout(3);'
            's.connect("/probe/inert.sock");s.sendall((json.dumps(dict(id=sys.argv[1],method="status",argument={}))+"\\n").encode());'
            '\ntry:data=s.recv(4096)\nexcept ConnectionResetError:data=b""\n'
            'assert (json.loads(data)["result"]["inert_nonce"]==sys.argv[1]) if sys.argv[2]=="accept" else not data;time.sleep(1)')
    with PrivateSocket(path,Protocol()) as server:
        # Only this inert fixture is relaxed so wrong UID reaches SO_PEERCRED.
        os.chmod(root,0o755);os.chmod(path,0o666)
        journal.append('socket_probe_socket',observed=identity(path))
        def serve():
            try:
                while not stop.is_set():server.poll(.05)
            except BaseException as error:errors.append(str(error))
        thread=threading.Thread(target=serve,name='inert-peer-probe');thread.start()
        try:
            for inside,expected in ((uid,'accept'),(wrong,'reject')):
                name='mldsafail-peer-probe-'+uuid.uuid4().hex
                label=uuid.uuid4().hex;identifier=None;created=None
                before=len(seen)
                journal.append('socket_probe_create_intent',name=name,image=image,label=label,inside_uid=inside)
                try:
                    identifier=checked(['create','--name',name,'--label','org.mldsafail.inert-probe='+label,
                        '--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                        '--memory=32m','--memory-swap=32m','--pids-limit=16','--cpus=1','--log-driver=none',
                        '--user',str(inside)+':'+str(inside),'--volume',str(root)+':/probe:ro',
                        '--entrypoint=/usr/local/bin/python',image,'-c',client,nonce,expected]).decode().strip()
                    actual=json.loads(checked(['inspect',identifier]))[0];created=actual['Created']
                    require(actual['Id']==identifier and actual['Image']==image and
                            actual['Config']['Labels'].get('org.mldsafail.inert-probe')==label and
                            actual['HostConfig']['Binds']==[str(root)+':/probe:ro'] and
                            actual['HostConfig']['NetworkMode']=='none','socket_probe_container_binding')
                    journal.append('socket_probe_created',id=identifier,created_at=created,name=name,label=label)
                    checked(['start',identifier])
                    actual=json.loads(checked(['inspect',identifier]))[0]
                    pid=actual['State']['Pid'];birth=process_birth(pid)
                    status=Path('/proc/'+str(pid)+'/status').read_text().splitlines()
                    host_uid=int(next(line.split()[1] for line in status if line.startswith('Uid:')))
                    expected_uids=[outside+inside-start for start,outside,count in mapping['uid_map'] if start<=inside<start+count]
                    require(expected_uids==[host_uid],'socket_probe_actual_mapping_changed')
                    journal.append('socket_probe_client',container_id=identifier,inside_uid=inside,host_uid=host_uid,birth=birth)
                    code=int(checked(['wait',identifier]).decode().strip())
                    require(code==0 and not errors and len(seen)-before==(1 if expected=='accept' else 0),
                            'socket_probe_peer_authentication_failed')
                    rows.append(dict(inside_uid=inside,observed_host_uid=host_uid,expected=expected,
                                     process=birth,container_id=identifier,created_at=created,exit_code=code))
                finally:
                    journal.append('socket_probe_case_observation',name=name,accepted_requests=len(seen)-before,inside_uid=inside)
                    if identifier is None:
                        blocked=True
                        journal.append('socket_probe_ambiguous_create',name=name,label=label)
                    else:
                        try:
                            actual=json.loads(checked(['inspect',identifier],cleanup=True))[0]
                            require(actual['Id']==identifier and actual['Created']==created and actual['Image']==image and
                                    actual['Config']['Labels'].get('org.mldsafail.inert-probe')==label,'socket_probe_cleanup_identity_changed')
                            checked(['rm','--force',identifier],cleanup=True)
                            require(not checked(['ps','-aq','--no-trunc','--filter','id='+identifier],cleanup=True).strip(),
                                    'socket_probe_container_cleanup_uncertain')
                            journal.append('socket_probe_removed',id=identifier,created_at=created)
                        except BaseException as error:
                            blocked=True
                            journal.append('socket_probe_cleanup_blocked',id=identifier,created_at=created,
                                           reason=str(error),ownership='blocked')
                            raise
        finally:
            stop.set();thread.join(timeout=2)
            require(not thread.is_alive(),'socket_probe_listener_cleanup_uncertain')
    require(not blocked and len(rows)==2,'socket_probe_ownership_blocked')
    root.rmdir()
    receipt=dict(origin='local_linux',image=image,daemon=original_daemon,uid_mapping=mapping,cases=rows,
                 production_socket_used=False,docker_socket_mounted=False,database_credentials_passed=False,
                 containers_after=0,socket_removed=not path.exists())
    journal.append('socket_probe_complete',receipt=receipt)
    return receipt
