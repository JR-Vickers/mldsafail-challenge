import base64
import json
from pathlib import Path
import socket
import threading
from types import SimpleNamespace
import pytest
from candidate_runtime import protocol,gateway


def test_source_registration_cannot_select_host_paths_or_escape(tmp_path):
    files={name:base64.b64encode(b'def solve(x): return None').decode() for name in ['solver.py','../solver.py']}
    with pytest.raises(ValueError,match='public Python paths'):gateway.snapshot(tmp_path/'source',files)
    assert not (tmp_path/'solver.py').exists()


def test_host_independently_snapshots_public_python_bytes(tmp_path):
    block=b'def solve(public_instance): return None\n'
    root=gateway.snapshot(tmp_path/'source',{'solver.py':base64.b64encode(block).decode()})
    assert (root/'solver.py').read_bytes()==block
    assert (root/'solver.py').stat().st_mode&0o777==0o444


def test_frame_cap_rejected_before_body_read():
    import struct
    server,client=socket.socketpair()
    try:
        client.sendall(struct.pack('!I',protocol.CAP+1))
        with pytest.raises(ValueError,match='cap'):protocol.receive(server)
    finally:server.close();client.close()


def test_private_gateway_requires_durable_request_before_evaluation(tmp_path,monkeypatch):
    import tempfile
    tmp_path=Path(tempfile.mkdtemp(prefix='gateway-',dir='/tmp'))
    monkeypatch.setattr(gateway.sys,'platform','linux');monkeypatch.setattr(socket,'SO_PEERCRED',17,raising=False)
    identity={'pid':123,'start_ticks':456};monkeypatch.setattr(gateway,'peer_identity',lambda *args:identity)
    monkeypatch.setattr(gateway.owned_client,'identity',lambda pid:identity)
    authority=SimpleNamespace(cohort_id='cohort',require_private=lambda value:None)
    request='a'*32;observed=[]
    def evaluate(source,checkpoint):
        retained=json.loads((tmp_path/'gateway'/request/'journal.json').read_text())
        assert retained['state']=='intent' and retained['peer']==identity
        checkpoint();observed.append(source);return {'signed':'tiny synthetic envelope'}
    value=gateway.Gateway(root=tmp_path/'gateway',worker_domain={},authority=authority,evaluate_source=evaluate)
    errors=[]
    def serve():
        try:value.serve_once()
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=serve);thread.start()
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.connect(str(value.socket_path))
            from candidate_runtime.client import source_digest
            files={'solver.py':base64.b64encode(b'def solve(x): return None').decode()}
            binding=dict(job_id='11111111-1111-4111-8111-111111111111',submission_id='22222222-2222-4222-8222-222222222222',cohort_id='cohort',source_sha256=source_digest(files))
            protocol.send(connection,{'operation':'evaluate','request_id':request,'files':files,'binding':binding,'attempt_id':'33333333-3333-4333-8333-333333333333'})
            for _ in range(2):
                assert protocol.receive(connection)=={'checkpoint':True};protocol.send(connection,{'checkpoint_complete':True})
            assert protocol.receive(connection)=={'envelope':{'signed':'tiny synthetic envelope'}}
        thread.join(timeout=5)
        assert not thread.is_alive() and not errors and len(observed)==1
        retained=json.loads((tmp_path/'gateway'/request/'journal.json').read_text())
        assert retained['state']=='evaluated' and retained['passed'] is False
    finally:
        value.close()
        import shutil
        shutil.rmtree(tmp_path)


def test_application_peer_outside_owned_domain_rejected(monkeypatch):
    import struct
    monkeypatch.setattr(socket,'SO_PEERCRED',17,raising=False)
    monkeypatch.setattr(gateway.os,'getuid',lambda:1000)
    peer=SimpleNamespace(getsockopt=lambda *args:struct.pack('3i',5,2000,2000))
    with pytest.raises(ValueError,match='Same-user'):gateway.peer_identity(peer,{})


def test_remote_authority_cannot_enable_default_or_nonprivate_application(monkeypatch):
    from candidate_runtime.client import RemoteCandidateAuthority
    from mldsafail.benchmark_versions import Cohort,RegisteredBackend,VersionRegistry,application_cohort,UnsupportedBenchmark
    cohort=Cohort('0.6.0','fresh','a'*64,'fresh-suite','worker','b'*64,'cgroup-v2-usage-usec')
    authority=RemoteCandidateAuthority('/candidate/gateway/candidate.sock',cohort)
    monkeypatch.setattr(RemoteCandidateAuthority,'require',lambda self:None)
    registry=VersionRegistry([RegisteredBackend(cohort,lambda job:job,authority,private_rehearsal=True)])
    assert authority.contract_adopted is False
    with pytest.raises(UnsupportedBenchmark,match='owner decision'):
        application_cohort({'BENCHMARK_VERSION':'0.6.0','BENCHMARK_VERSION_REGISTRY':registry})
    with pytest.raises(UnsupportedBenchmark,match='explicit disposable'):
        application_cohort({'BENCHMARK_VERSION':'0.5.0','BENCHMARK_VERSION_REGISTRY':registry,'TESTING':False},'0.6.0')


def test_fifo_private_configuration_rejected_without_blocking(tmp_path):
    import os
    from candidate_runtime.config import load
    path=tmp_path/'config.json';os.mkfifo(path,0o600)
    with pytest.raises(ValueError,match='bounded application'):load(path)


def test_lost_private_response_reuses_durable_job_identity_without_evaluation(tmp_path,monkeypatch):
    from candidate_runtime import client
    source=tmp_path/'source';source.mkdir();(source/'solver.py').write_text('def solve(x): return None')
    binding=dict(job_id='11111111-1111-4111-8111-111111111111',submission_id='22222222-2222-4222-8222-222222222222',cohort_id='cohort',source_sha256=client.source_digest(client.source_files(source)))
    requests=[]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(client,'connect',lambda path:Connection())
    def send(connection,value):
        retained=json.loads((tmp_path/'requests'/('11111111-1111-4111-8111-111111111111.json')).read_text())
        assert retained['request_id']==value['request_id'] and retained['binding']==binding
        requests.append(value)
    monkeypatch.setattr(client,'send',send)
    def lost(*args,**kwargs):raise TimeoutError('lost response')
    monkeypatch.setattr(client,'receive',lost)
    with pytest.raises(TimeoutError):client.evaluate('private',source,lambda:None,binding=binding,request_directory=tmp_path/'requests',attempt_id='33333333-3333-4333-8333-333333333333')
    monkeypatch.setattr(client,'receive',lambda *args,**kwargs:{'envelope':{'retained':'signed'}})
    assert client.evaluate('private',source,lambda:None,binding=binding,request_directory=tmp_path/'requests',attempt_id='44444444-4444-4444-8444-444444444444')=={'retained':'signed'}
    assert [request['operation'] for request in requests]==['evaluate','lookup']
    assert requests[0]['request_id']==requests[1]['request_id'] and 'files' not in requests[1]
