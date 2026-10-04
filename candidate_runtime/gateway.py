"""HOST-only private gateway; fixed evaluator/cases/cohort supplied by operator."""
import base64
import hashlib
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
        self.root=Path(root);self.domain=worker_domain;self.authority=authority;self.evaluator=evaluate_source
        if self.root.exists():raise ValueError('Fresh protected gateway root required')
        self.root.mkdir(mode=0o700);self.socket_path=self.root/'candidate.sock'
        self.server=socket.socket(socket.AF_UNIX);self.server.settimeout(30)
        try:self.server.bind(str(self.socket_path));os.chmod(self.socket_path,0o600);self.server.listen(1)
        except BaseException:self.server.close();raise
        self.socket_inode=self.socket_path.lstat().st_ino
    def serve_once(self):
        connection,_=self.server.accept()
        with connection:
            identity=peer_identity(connection,self.domain);request=receive(connection,seconds=1)
            if request=={'operation':'authorize','cohort_id':self.authority.cohort_id}:
                self.authority.require_private(True)
                send(connection,{'authorized':True,'cohort_id':self.authority.cohort_id,'candidate_only':True,'contract_adopted':False});return 'authorized'
            if not isinstance(request,dict) or set(request)!={'operation','request_id','files'} or request['operation']!='evaluate':raise ValueError('Fixed gateway operations only')
            identifier=request['request_id']
            if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Durable request identity required')
            run=self.root/identifier
            if run.exists():raise RuntimeError('Prior request remains fenced; never repeat evaluation')
            run.mkdir(mode=0o700);journal=run/'journal.json';record={'request_id':identifier,'peer':identity,'state':'intent','passed':False}
            atomic_json(journal,record)
            try:
                source=snapshot(run/'public-source',request['files'])
                self.authority.require_private(True)
                def checkpoint():
                    if owned_client.identity(identity['pid'])!=identity:raise RuntimeError('Owned application peer disappeared')
                    send(connection,{'checkpoint':True})
                    if receive(connection)!=dict(checkpoint_complete=True):raise RuntimeError('Application checkpoint unacknowledged')
                checkpoint()
                envelope=self.evaluator(source,checkpoint)
                record.update(state='evaluated',envelope=envelope);atomic_json(journal,record)
                send(connection,{'envelope':envelope});return 'evaluated'
            except BaseException as error:
                record.update(state='failed',failure_class=type(error).__name__)
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
        if errors:raise RuntimeError('Independent candidate gateway cleanup incomplete') from errors[0]
