from types import SimpleNamespace
import json
from pathlib import Path
import socket
import tempfile
import threading
import pytest
from scripts import native_recovery_rpc_loss as runner
from research.cpu_measurement.native_transport import read_message


def test_real_proxy_retains_successful_ack_without_delivering_it():
    with tempfile.TemporaryDirectory(dir='/tmp') as directory:
        root = Path(directory)
        upstream_path = root / 'upstream.sock'
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(upstream_path)); server.listen(1)
        observed = []
        def upstream():
            with server.accept()[0] as connection:
                request, line = read_message(connection)
                observed.append(line)
                connection.sendall(b'HTTP/1.1 201 Created\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{"Id":"x"}')
        worker = threading.Thread(target=upstream)
        worker.start()
        proxy = runner.LostAcknowledgement(root, str(upstream_path), 'create')
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5); client.connect(str(proxy.path))
                client.sendall(b'POST /v1.56/containers/create HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}')
                assert client.recv(1) == b''
            proxy.close()
            packet = json.loads(proxy.receipt.read_text())
            assert packet['daemon_response_code'] == 201
            assert packet['actual_mutation_response_observed'] is True
            assert packet['response_delivered'] is False
            assert len(observed) == 1
        finally:
            server.close(); worker.join(5)
            assert not worker.is_alive()


@pytest.mark.parametrize('fault', ['same_epoch', 'wrong_old', 'barrier_errors', 'cleanup_false'])
def test_repair_acceptance_rejects_incomplete_or_wrong_proof(tmp_path, monkeypatch, fault):
    before = {'epoch':'old'}
    resolution = {'old_epoch':'old', 'new_epoch':'new', 'proof_file':'recovery-exact-context-rpc-repair.json'}
    after = {'epoch':'new'}
    barrier = {'schema':'mldsafail.owned-daemon-barrier.v1','shutdown_proven':True,'errors':[],
        'attempt_id':'recovery-exact-context','daemon_epoch':'old','daemon_manifest_sha256':'exact-context'}
    operation = SimpleNamespace(path=tmp_path/'operation.json', data={
        'daemon_mutations':[{'acknowledged':False,'resolved_by_barrier':resolution}], 'cleanup_complete':True})
    if fault == 'same_epoch': after['epoch'] = 'old'
    if fault == 'wrong_old': resolution['old_epoch'] = 'another'
    if fault == 'barrier_errors': barrier['errors'] = ['failed']
    if fault == 'cleanup_false': operation.data['cleanup_complete'] = False
    monkeypatch.setattr(runner.owned_daemon, 'load_manifest', lambda _:after)
    monkeypatch.setattr(runner.owned_daemon, 'fingerprint', lambda _:'exact-context')
    monkeypatch.setattr(runner.owned_daemon, 'read_private_json', lambda _:{'schema':'mldsafail.recovery-rpc-repair.v1','context':'exact-context',
        'attempt_id':'recovery-exact-context','barrier':barrier})
    with pytest.raises(ValueError): runner.validate_repair(operation, before, '/manifest')


def test_unbound_image_refused_before_commands_or_output(tmp_path):
    driver = SimpleNamespace(path=tmp_path/'driver.json', command=lambda *a, **k:pytest.fail('command admitted'))
    with pytest.raises(ValueError, match='preloaded'):
        runner.callback(driver, {'image':'sha256:'+'a'*64}, {'loaded_images':[]})
    assert not (tmp_path/'recovery-rpc-loss').exists()


def test_proxy_error_with_proven_quiescence_still_attempts_journal_cleanup(tmp_path, monkeypatch):
    import subprocess
    calls = []
    class Journal:
        def __init__(self, path, config): self.path=path;self.data={}
        def container(self, *a, **kw): pass
        def command(self, argv, **kw): raise subprocess.CalledProcessError(1,argv)
        def cleanup(self): calls.append('cleanup');self.data['cleanup_complete']=True
    class Proxy:
        def __init__(self, *a): self.path=tmp_path/'proxy.sock'
        def close(self): raise RuntimeError('diagnostic failure with closed executor')
        def quiescent(self): return True
    monkeypatch.setattr(runner,'Journal',Journal)
    monkeypatch.setattr(runner,'LostAcknowledgement',Proxy)
    monkeypatch.setattr(runner.owned_daemon,'load_manifest',lambda _:dict(epoch='old',socket='/private/socket'))
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','/private/manifest')
    with pytest.raises(RuntimeError,match='diagnostic failure'):
        runner.probe(tmp_path/'probe',{'image':'sha256:'+'a'*64,'api_version':'1.56'},'create')
    assert calls==['cleanup']
    result=json.loads((tmp_path/'probe/result.json').read_text())
    assert result['passed'] is False and result['cleanup_complete'] is True
    assert result['proxy_executor_quiescent'] is True


@pytest.mark.parametrize('response_code', [201, 500, None])
def test_owned_client_runtime_failure_requires_actual_successful_daemon_ack(tmp_path, monkeypatch, response_code):
    calls = []
    class Journal:
        def __init__(self, path, config): self.path=path;self.data={}
        def container(self, *a, **kw): pass
        def command(self, argv, **kw): raise RuntimeError('Owned native command failed; logs retained')
        def cleanup(self): calls.append('cleanup');self.data['cleanup_complete']=True
    class Proxy:
        def __init__(self, root, upstream, kind):
            self.path=root/'proxy.sock';self.receipt=root/'transport.json'
            runner.atomic_json(self.receipt, dict(operation='create',
                actual_mutation_response_observed=response_code is not None,
                response_delivered=False, daemon_response_code=response_code))
        def close(self): calls.append('proxy_closed')
        def quiescent(self): return True
    monkeypatch.setattr(runner,'Journal',Journal)
    monkeypatch.setattr(runner,'LostAcknowledgement',Proxy)
    monkeypatch.setattr(runner.owned_daemon,'load_manifest',lambda _:dict(epoch='old',socket='/owned/socket'))
    def validate(*args):
        assert calls[-1]=='cleanup'
        calls.append('validated');return dict(whole_barrier_verified=True)
    monkeypatch.setattr(runner,'validate_repair',validate)
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','/owned/manifest')
    if response_code == 201:
        result=runner.probe(tmp_path/'probe',dict(image='sha256:'+'a'*64,api_version='1.56'),'create')
        assert result['passed'] and result['native_executed']
        assert result['lost_ack_client_failure_class']=='RuntimeError'
        assert calls.count('validated')==2
    else:
        with pytest.raises(ValueError,match='successful daemon response loss'):
            runner.probe(tmp_path/'probe',dict(image='sha256:'+'a'*64,api_version='1.56'),'create')
        assert 'validated' not in calls
        assert json.loads((tmp_path/'probe/result.json').read_text())['passed'] is False
    assert calls[0]=='proxy_closed' and calls[-1]=='cleanup'
