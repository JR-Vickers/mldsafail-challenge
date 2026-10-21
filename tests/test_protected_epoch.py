"""Administrative ordering and failure contracts, with inert synthetic results."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

import pytest

from deploy import protected_epoch
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.evaluator.native_workload import publish
from mldsafail.evaluator.workload import HostGate
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from test_workload import Runtime


def test_admin_host_gate_precedes_pending_fence_and_cleans_before_receipt(tmp_path, monkeypatch):
    exercise(tmp_path, monkeypatch, pending=False)


def test_queued_work_blocks_admin_without_launch_and_releases_unused_host(tmp_path, monkeypatch):
    exercise(tmp_path, monkeypatch, pending=True)


def exercise(tmp_path, monkeypatch, *, pending):
    runtime = Runtime()
    key = tmp_path/'key'; key.write_bytes(b'k'*32)
    packet_path = tmp_path/'packet.json'; authorization = tmp_path/'authority.json'
    packet = dict(schema='mldsafail.production-operation.v4', operation_id='a'*32, roles=['create','audit'],
                  attempt=str(tmp_path/'attempt.json'), signing_key=str(key), result_receipt=str(tmp_path/'receipt.json'))
    publish(packet_path, packet); publish(authorization, {})
    monkeypatch.setattr(protected_epoch, 'authorize', lambda *args: None)
    monkeypatch.setattr(protected_epoch, 'validate', lambda packet, **kwargs: packet)
    events = []
    with HostGate(tmp_path/'gate', runtime).locked() as gate:
        protocol = SupervisorProtocol(gate, {'create':{'role':'create'}, 'audit':{'role':'audit'}})
        client = WorkloadClient(tmp_path/'socket', tmp_path/'client', transport=lambda path, request: protocol.dispatch(request))
        runtime.role = None
        original = runtime.launch
        def launch(state, specification):
            events.append(specification['role']); runtime.role = specification['role']
            return original(state, specification)
        runtime.launch = launch
        def result(state):
            return sign_envelope(dict(binding=dict(workload_id=state['workload_id'], role=runtime.role, reference=state['reference']),
                status='administrative_complete', result={'verified':True}), b'k'*32)
        runtime.result = result
        class Fence:
            def acquire(self):
                assert gate.state['kind'] == 'administration' and gate.state['phase'] == 'acquired'
                events.append('fence')
                if pending: raise RuntimeError('queued participant work')
            def verify(self): pass
            @contextmanager
            def phase(self, name, abort): yield
            def resources_stopped(self, callback):
                assert not runtime.live and callback()
                events.append('stopped')
            def release(self):
                assert not runtime.live
                events.append('release')
        if pending:
            with pytest.raises(RuntimeError):
                protected_epoch.run(packet_path, authorization, client=client, fence_factory=lambda *args: Fence())
            assert events == ['fence']
            assert not (tmp_path/'attempt.json').exists()
        else:
            protected_epoch.run(packet_path, authorization, client=client, fence_factory=lambda *args: Fence())
            assert events == ['fence','create','audit','stopped','release']
            assert (tmp_path/'receipt.json').exists()
        assert gate.state['phase'] == 'complete'
        assert not runtime.live


@pytest.mark.parametrize('receipt_written',[True,False])
def test_admin_commit_reconciliation_never_repeats_computation(tmp_path,monkeypatch,receipt_written):
    runtime=Runtime(); key=tmp_path/'key';key.write_bytes(b'k'*32)
    packet_path=tmp_path/'packet.json'; authority=tmp_path/'authority.json'
    packet=dict(schema='mldsafail.production-operation.v4',operation_id='a'*32,roles=['audit'],
        attempt=str(tmp_path/'attempt'),signing_key=str(key),result_receipt=str(tmp_path/'receipt.json'),
        fence_root=str(tmp_path/'fence'))
    publish(packet_path,packet);publish(authority,{})
    monkeypatch.setattr(protected_epoch,'authorize',lambda *args:None)
    monkeypatch.setattr(protected_epoch,'validate',lambda packet,**kwargs:packet)
    with HostGate(tmp_path/'gate',runtime).locked() as gate:
        protocol=SupervisorProtocol(gate,{'audit':{'role':'audit'}})
        client=WorkloadClient(tmp_path/'socket',tmp_path/'client',transport=lambda path,request:protocol.dispatch(request))
        runtime.result=lambda state:sign_envelope(dict(binding=dict(workload_id=state['workload_id'],role='audit',reference=state['reference']),
            status='administrative_complete',result={'verified':True}),b'k'*32)
        class Fence:
            def acquire(self):pass
            def verify(self):pass
            @contextmanager
            def phase(self,*args):yield
            def resources_stopped(self,callback):assert callback() and not runtime.live
            def release(self):pass
        acknowledge=client.acknowledge
        original_publish=protected_epoch.publish
        if receipt_written:
            monkeypatch.setattr(client,'acknowledge',lambda *args:(_ for _ in ()).throw(OSError('lost ack')))
        else:
            def outage(path,value):
                if str(path)==packet['result_receipt']:raise OSError('lost receipt write')
                return original_publish(path,value)
            monkeypatch.setattr(protected_epoch,'publish',outage)
        with pytest.raises(OSError):protected_epoch.run(packet_path,authority,client=client,fence_factory=lambda *args:Fence())
        assert gate.state['phase']=='commit_intent' and not runtime.live
        monkeypatch.setattr(client,'acknowledge',acknowledge)
        monkeypatch.setattr(protected_epoch,'publish',original_publish)
        runtime.launch=lambda *args:pytest.fail('repeated administrative computation')
        protected_epoch.reconcile(packet_path,client=client)
        assert gate.state['phase']==('complete' if receipt_written else 'committed')
        assert gate.state['paused'] is (not receipt_written)


def test_finalization_writes_candidate_configs_without_modifying_epoch(tmp_path,monkeypatch):
    from mldsafail.evaluator.envelope import canonical_payload
    from mldsafail.evaluator.native_workload import private_json
    monkeypatch.setattr(protected_epoch,'validate',lambda packet,**kwargs:packet)
    workload_id='a'*32
    epoch=tmp_path/'output'/workload_id/'epoch';epoch.mkdir(parents=True)
    audited=dict(epoch_id='new-epoch',epoch_path=str(epoch))
    for name,field in (('manifest.json','manifest_sha256'),('reference-costs.json','reference_sha256'),('COMPLETE.json','seal_sha256')):
        (epoch/name).write_bytes(b'synthetic-control-record')
        audited[field]=hashlib.sha256((epoch/name).read_bytes()).hexdigest()
    key=tmp_path/'key';key.write_bytes(b'k'*32)
    controller=tmp_path/'controller.json';native=tmp_path/'native.json';supervisor=tmp_path/'supervisor.json'
    publish(controller,dict(native_configuration=str(native),identity={'epoch_id':'old'},epoch_path='/old'))
    publish(native,dict(output=str(tmp_path/'output'),controller_configuration=str(controller)))
    publish(supervisor,dict(root=str(tmp_path/'gate'),helper=['/python','--configuration',str(native)]))
    candidate=tmp_path/'production.env';candidate.write_text('MLDSAFAIL_BENCHMARK_VERSION=0.5.0\n');candidate.chmod(0o600)
    destination=tmp_path/'final'
    packet=dict(schema='mldsafail.production-operation.v4',final_destination=str(destination),candidate=str(candidate),
                result_receipt=str(tmp_path/'receipt.json'),signing_key=str(key),supervisor_runtime={'evaluator_fingerprint':'b'*64},
                configurations={role:{'path':str(path)} for role,path in (('controller',controller),('native',native),('supervisor',supervisor))})
    packet_path=tmp_path/'packet.json';publish(packet_path,packet)
    digest=hashlib.sha256(packet_path.read_bytes()).hexdigest()
    results={'audit':sign_envelope(dict(binding=dict(workload_id=workload_id,role='audit',reference={'packet_sha256':digest}),result=audited),b'k'*32)}
    publish(Path(packet['result_receipt']),dict(binding=dict(workload_id=workload_id,packet_sha256=digest,
        result_sha256=hashlib.sha256(canonical_payload(results)).hexdigest()),results=results))
    protected_epoch.finalize(packet_path,destination)
    assert private_json(destination/'controller.json')['identity']['epoch_id']=='new-epoch'
    assert private_json(destination/'binding.json')['ready'] is False
    assert all((epoch/name).read_bytes()==b'synthetic-control-record' for name in ('manifest.json','reference-costs.json','COMPLETE.json'))
    assert private_json(controller)['identity']['epoch_id']=='old'
