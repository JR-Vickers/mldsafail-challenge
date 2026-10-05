"""HOST-only private gateway; fixed evaluator/cases/cohort supplied by operator."""
import base64
import hashlib
import fcntl
import stat
import json
import os
from pathlib import Path,PurePosixPath
import socket
import struct
import sys
import uuid
from deploy import owned_client
from deploy.recovery_journal import atomic_json
from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
from mldsafail.benchmark_v050.execution import solver_snapshot
from candidate_runtime.protocol import send,receive


def peer_identity(connection,worker_domain):
    pid,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    if uid!=os.getuid() or pid<=0:raise ValueError('Same-user native application peer required')
    identity=owned_client.identity(pid)
    membership=(Path('/proc')/str(pid)/'cgroup').read_text().splitlines()
    expected=Path(worker_domain['path']).relative_to('/sys/fs/cgroup').as_posix()
    if len(membership)!=1 or not membership[0].startswith('0::/'):
        raise ValueError('Unified native peer membership required')
    actual=membership[0][4:]
    if actual!=expected and not actual.startswith(expected+'/'):raise ValueError('Peer outside exact owned application domain')
    if owned_client.domain_identity(worker_domain['path'])!=worker_domain:raise ValueError('Owned application domain changed')
    if owned_client.identity(pid)!=identity:raise ValueError('Application peer changed')
    return identity


def snapshot(root,files):
    if not isinstance(files,dict) or not files or 'solver.py' not in files:raise ValueError('Public solver source required')
    total=0;root.mkdir(mode=0o700)
    for name,encoded in files.items():
        path=PurePosixPath(name)
        if not isinstance(name,str) or path.is_absolute() or any(part in {'.','..','.git'} for part in path.parts) or path.suffix!='.py' or path.as_posix()!=name:
            raise ValueError('Only approved public Python paths allowed')
        block=base64.b64decode(encoded,validate=True);total+=len(block)
        if len(block)>256*1024 or total>MAX_SERIALIZED_BYTES:raise ValueError('Public source exceeds frozen cap')
        destination=root/path;destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True);destination.write_bytes(block)
    approved=root.with_name(root.name+'-snapshot');solver_snapshot(root,approved)
    return approved


class Gateway:
    def __init__(self,*,root,worker_domain,authority,evaluate_source):
        if sys.platform!='linux' or not hasattr(socket,'SO_PEERCRED'):raise RuntimeError('Native Linux Unix peer binding required')
        from deploy import owned_daemon
        self.root=owned_daemon._canonical(root);self.domain=worker_domain;self.authority=authority;self.evaluator=evaluate_source
        self.root.mkdir(mode=0o700,exist_ok=True)
        info=self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ValueError('Exclusive protected gateway root required')
        self.lock=os.open(self.root/'owner.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        self.server=None
        try:
            lockinfo=os.fstat(self.lock)
            if not stat.S_ISREG(lockinfo.st_mode) or lockinfo.st_uid!=os.getuid() or lockinfo.st_nlink!=1 or lockinfo.st_mode&0o077:
                raise ValueError('Private gateway lifecycle lock required')
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.lifecycle_path=self.root/'lifecycle.json';self.socket_path=self.root/'candidate.sock'
            if self.lifecycle_path.exists():
                old=owned_daemon.read_private_json(self.lifecycle_path)
                if old.get('schema')!='mldsafail.candidate-gateway-lifecycle.v1' or old.get('domain')!=worker_domain or old.get('cohort_id')!=authority.cohort_id:
                    raise ValueError('Retained gateway authority differs')
                if old.get('state')!='closed' and old.get('boot_id')==owned_client.boot_id():
                    try:alive=owned_client.identity(old['owner']['pid'])==old['owner']
                    except ProcessLookupError:alive=False
                    except FileNotFoundError:alive=False
                    if alive:raise RuntimeError('Prior gateway owner remains live')
                if self.socket_path.exists():
                    stale=self.socket_path.lstat()
                    if not stat.S_ISSOCK(stale.st_mode) or stale.st_ino!=old.get('socket_inode'):
                        raise RuntimeError('Retained gateway socket identity differs')
                    self.socket_path.unlink()
            elif self.socket_path.exists():raise RuntimeError('Unaccounted gateway socket remains fenced')
            self.lifecycle=dict(schema='mldsafail.candidate-gateway-lifecycle.v1',domain=worker_domain,
                cohort_id=authority.cohort_id,owner=owned_client.identity(os.getpid()),boot_id=owned_client.boot_id(),state='opening')
            atomic_json(self.lifecycle_path,self.lifecycle)
            self.server=socket.socket(socket.AF_UNIX);self.server.settimeout(30)
            self.server.bind(str(self.socket_path));os.chmod(self.socket_path,0o600);self.server.listen(1)
            self.socket_inode=self.socket_path.lstat().st_ino
            self.lifecycle.update(state='open',socket_inode=self.socket_inode)
            atomic_json(self.lifecycle_path,self.lifecycle)
        except BaseException:
            if self.server is not None:self.server.close()
            os.close(self.lock)
            raise
    def serve_once(self):
        connection,_=self.server.accept()
        with connection:
            identity=peer_identity(connection,self.domain);request=receive(connection,seconds=1)
            if request=={'operation':'authorize','cohort_id':self.authority.cohort_id}:
                self.authority.require_private(True)
                send(connection,{'authorized':True,'cohort_id':self.authority.cohort_id,'candidate_only':True,'contract_adopted':False});return 'authorized'
            if not isinstance(request,dict) or request.get('operation') not in {'evaluate','lookup'} or set(request)!=({'operation','request_id','binding'} if request.get('operation')=='lookup' else {'operation','request_id','files','binding','attempt_id'}):raise ValueError('Fixed gateway operations only')
            identifier=request['request_id']
            if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Durable request identity required')
            binding=request['binding']
            if not isinstance(binding,dict) or set(binding)!={'job_id','submission_id','cohort_id','source_sha256'} or binding.get('cohort_id')!=self.authority.cohort_id:
                raise ValueError('Exact job/cohort/source request binding required')
            for name in ('job_id','submission_id'):uuid.UUID(binding[name])
            if len(binding['source_sha256'])!=64 or any(c not in '0123456789abcdef' for c in binding['source_sha256']):raise ValueError('Source digest required')
            run=self.root/identifier
            if request['operation']=='lookup':
                journal=run/'journal.json'
                if not journal.exists():send(connection,{'fenced':True});return 'fenced'
                from deploy import owned_daemon
                retained=owned_daemon.read_private_json(journal)
                if retained.get('binding')!=binding:raise ValueError('Retained request binding differs')
                if retained.get('state')=='evaluated':send(connection,{'envelope':retained['envelope']});return 'reconciled'
                send(connection,{'fenced':True});return 'fenced'
            job_index=self.root/('job-'+str(uuid.UUID(binding['job_id']))+'.json')
            if job_index.exists():raise RuntimeError('Prior job remains fenced; never repeat evaluation under a new identity')
            uuid.UUID(request['attempt_id'])
            atomic_json(job_index,dict(request_id=identifier,binding=binding))
            if run.exists():raise RuntimeError('Prior request remains fenced; never repeat evaluation')
            run.mkdir(mode=0o700);journal=run/'journal.json';record={'request_id':identifier,'peer':identity,'binding':binding,'initial_attempt_id':request['attempt_id'],'state':'intent','passed':False}
            atomic_json(journal,record)
            try:
                uuid.UUID(request['attempt_id'])
                source=snapshot(run/'public-source',request['files'])
                from candidate_runtime.client import source_digest
                if source_digest(request['files'])!=binding['source_sha256']:raise ValueError('Independent public source digest differs')
                self.authority.require_private(True)
                def checkpoint():
                    if peer_identity(connection,self.domain)!=identity:raise RuntimeError('Owned application peer disappeared')
                    send(connection,{'checkpoint':True})
                    if receive(connection)!=dict(checkpoint_complete=True):raise RuntimeError('Application checkpoint unacknowledged')
                checkpoint()
                envelope=self.evaluator(source,checkpoint)
                record.update(state='evaluated',envelope=envelope);atomic_json(journal,record)
                send(connection,{'envelope':envelope});return 'evaluated'
            except BaseException as error:
                if record.get('state')!='evaluated':record.update(state='failed')
                record['failure_class']=type(error).__name__
                try:atomic_json(journal,record)
                except BaseException as publication:error.add_note('Gateway failure publication: '+type(publication).__name__)
                raise
    def close(self):
        errors=[]
        try:self.server.close()
        except BaseException as error:errors.append(error)
        try:
            if self.socket_path.exists():
                if self.socket_path.lstat().st_ino!=self.socket_inode:raise RuntimeError('Candidate socket ownership changed')
                self.socket_path.unlink()
        except BaseException as error:errors.append(error)
        try:
            self.lifecycle['state']='closed' if not errors else 'cleanup_incomplete'
            atomic_json(self.lifecycle_path,self.lifecycle)
        except BaseException as error:errors.append(error)
        try:os.close(self.lock)
        except BaseException as error:errors.append(error)
        if errors:raise RuntimeError('Independent candidate gateway cleanup incomplete') from errors[0]
