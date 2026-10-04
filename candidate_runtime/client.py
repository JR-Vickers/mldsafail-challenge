"""Application-only public-source transport; never instantiates HostBackend."""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time
import uuid
from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
from mldsafail.benchmark_v060.candidate_authority import CandidateRehearsalAuthority
from candidate_runtime.protocol import send,receive
from deploy import owned_daemon


def connect(path):
    path=Path(path)
    info=path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise ValueError('Private same-user candidate socket required')
    connection=socket.socket(socket.AF_UNIX);connection.settimeout(10)
    try:connection.connect(str(path));return connection
    except BaseException:connection.close();raise


class RemoteCandidateAuthority(CandidateRehearsalAuthority):
    def __init__(self,path,cohort):
        object.__setattr__(self,'socket_path',Path(path));object.__setattr__(self,'cohort',cohort)
        object.__setattr__(self,'cohort_id',cohort.public_id);object.__setattr__(self,'contract_adopted',False)
    def require(self):
        info=self.socket_path.lstat()
        identity=(info.st_dev,info.st_ino,info.st_uid,info.st_mode)
        if getattr(self,'_authorized_socket',None)==identity:return
        if getattr(self,'_authorized_socket',None) is not None:raise ValueError('Candidate gateway socket identity changed')
        with connect(self.socket_path) as connection:
            send(connection,dict(operation='authorize',cohort_id=self.cohort_id))
            value=receive(connection)
        if value!={'authorized':True,'cohort_id':self.cohort_id,'candidate_only':True,'contract_adopted':False}:
            raise ValueError('Private host candidate authorization failed')
        object.__setattr__(self,'_authorized_socket',identity)


def source_files(source):
    source=Path(source);result={};total=0
    for path in sorted(source.rglob('*')):
        if path.is_symlink():raise ValueError('Candidate snapshot links forbidden')
        if path.is_dir():continue
        if not path.is_file() or path.suffix!='.py':raise ValueError('Only regular Python public source allowed')
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or not 0<=before.st_size<=256*1024:raise ValueError('Bounded regular public Python source required')
            block=os.read(descriptor,256*1024+1);after=os.fstat(descriptor)
            if len(block)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                raise ValueError('Public snapshot changed during registration')
        finally:os.close(descriptor)
        total+=len(block)
        if total>MAX_SERIALIZED_BYTES:raise ValueError('Public source exceeds frozen cap')
        result[path.relative_to(source).as_posix()]=base64.b64encode(block).decode()
    if not result or 'solver.py' not in result:raise ValueError('Approved solver entry required')
    return result


def source_digest(files):
    material={name:dict(bytes=len(base64.b64decode(block,validate=True)),sha256=hashlib.sha256(base64.b64decode(block,validate=True)).hexdigest()) for name,block in files.items()}
    return hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def evaluate(path,source,checkpoint,*,binding,request_directory,attempt_id):
    files=source_files(source)
    if binding.get('source_sha256')!=source_digest(files):raise ValueError('Job-bound public source digest differs')
    directory=Path(request_directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('Private owned request directory required')
    uuid.UUID(attempt_id)
    intent_path=directory/(str(uuid.UUID(binding['job_id']))+'.json')
    if intent_path.exists():
        intent=owned_daemon.read_private_json(intent_path)
        if intent.get('binding')!=binding:raise RuntimeError('Retained request job/source identity changed')
        operation='lookup'
    else:
        intent=dict(schema='mldsafail.private-candidate-request.v1',request_id=uuid.uuid4().hex,binding=binding,
            initial_attempt_id=attempt_id,dispatch_uncertain=True)
        owned_daemon.publish(intent_path,intent)
        operation='evaluate'
    with connect(path) as connection:
        request=dict(operation=operation,request_id=intent['request_id'],binding=binding)
        if operation=='evaluate':request.update(files=files,attempt_id=attempt_id)
        send(connection,request)
        deadline=time.monotonic()+1200
        while True:
            value=receive(connection,seconds=max(.001,deadline-time.monotonic()))
            if value=={'checkpoint':True}:
                checkpoint();send(connection,{'checkpoint_complete':True})
            elif isinstance(value,dict) and set(value)=={'envelope'}:
                intent['response_reconciled']=True;owned_daemon.publish(intent_path,intent)
                return value['envelope']
            else:raise RuntimeError('Private request remains fenced; reconcile existing identity, never resubmit')
