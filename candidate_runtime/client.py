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


def evaluate(path,source,checkpoint):
    files=source_files(source)
    with connect(path) as connection:
        send(connection,dict(operation='evaluate',request_id=uuid.uuid4().hex,files=files))
        deadline=time.monotonic()+1200
        while True:
            value=receive(connection,seconds=max(.001,deadline-time.monotonic()))
            if value=={'checkpoint':True}:
                checkpoint();send(connection,{'checkpoint_complete':True})
            elif isinstance(value,dict) and set(value)=={'envelope'}:return value['envelope']
            else:raise RuntimeError('Candidate host evaluation failed')
