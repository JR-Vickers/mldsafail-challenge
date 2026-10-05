import json
from types import SimpleNamespace
import pytest
from research.cpu_measurement import supervisor


def arguments(tmp_path):
    return SimpleNamespace(socket=tmp_path/'supervisor.sock',image='sha256:'+'a'*64,
        parent=tmp_path/'parent',cgroup_parent='owned-worker.slice',
        ownership_directory=tmp_path/'ownership',epoch='isolated-native-lifecycle')


def test_disconnected_dispatch_preserves_original_failure_and_private_evidence(tmp_path,monkeypatch):
    args=arguments(tmp_path);original=RuntimeError('specific native admission failure')
    def failed(*args,**kwargs):raise original
    monkeypatch.setattr(supervisor,'run',failed)
    with pytest.raises(RuntimeError) as caught:supervisor.dispatch(args,'child')
    assert caught.value is original
    receipt=tmp_path/'last-dispatch.json';record=json.loads(receipt.read_text())
    assert record['state']=='failed' and record['fixture']=='child'
    assert record['error_type']=='RuntimeError' and 'specific native admission failure' in record['error']
    assert receipt.stat().st_mode&0o777==0o600


def test_dispatch_publication_failure_preserves_execution_error(tmp_path,monkeypatch):
    from research.cpu_measurement import ownership
    original=RuntimeError('native execution failed');actual=ownership.publish;calls=[]
    def failed(*args,**kwargs):raise original
    def publish(path,value):
        calls.append(value['state'])
        if value['state']=='failed':raise OSError('private fsync failed')
        actual(path,value)
    monkeypatch.setattr(supervisor,'run',failed);monkeypatch.setattr(ownership,'publish',publish)
    with pytest.raises(RuntimeError) as caught:supervisor.dispatch(arguments(tmp_path),'child')
    assert caught.value is original and calls==['intent','failed']
    assert 'publication failed' in original.__notes__[0]


def test_success_receipt_identifies_exact_completed_generation(tmp_path,monkeypatch):
    monkeypatch.setattr(supervisor,'run',lambda *args,**kwargs:{'generation':'b'*32,'status':'no_answer'})
    assert supervisor.dispatch(arguments(tmp_path),'child')['generation']=='b'*32
    record=json.loads((tmp_path/'last-dispatch.json').read_text())
    assert record['state']=='complete' and record['generation']=='b'*32


def test_ambiguous_positive_dispatch_publication_is_retracted(tmp_path,monkeypatch):
    from research.cpu_measurement import ownership
    actual=ownership.publish;original=OSError('directory fsync failed');states=[]
    def publish(path,record):
        actual(path,record);states.append(record['state'])
        if record['state']=='complete':raise original
    monkeypatch.setattr(ownership,'publish',publish)
    monkeypatch.setattr(supervisor,'run',lambda *args,**kwargs:{'generation':'b'*32})
    with pytest.raises(OSError) as caught:supervisor.dispatch(arguments(tmp_path),'child')
    assert caught.value is original and states==['intent','complete','failed']
    assert json.loads((tmp_path/'last-dispatch.json').read_text())['state']=='failed'


def test_dispatch_rejects_unapproved_paths_before_publishing_or_execution(tmp_path,monkeypatch):
    monkeypatch.setattr(supervisor,'run',lambda *args,**kwargs:pytest.fail('Unapproved source executed'))
    with pytest.raises(ValueError):supervisor.dispatch(arguments(tmp_path),'../external')
    assert not (tmp_path/'last-dispatch.json').exists()


def test_generation_complete_does_not_outrun_dispatch_publication(tmp_path,monkeypatch):
    from research.cpu_measurement import native_lifecycle
    generation='c'*32
    (tmp_path/'journal.json').write_text(json.dumps(dict(generation=generation,state='complete')))
    (tmp_path/'last-dispatch.json').write_text(json.dumps(dict(generation=generation,state='complete',fixture='child')))
    monkeypatch.setattr(native_lifecycle,'dispatch_status',lambda path:dict(state='intent',fixture='child'))
    assert native_lifecycle.completed_dispatch(tmp_path,'old',tmp_path/'supervisor.sock') is None
    monkeypatch.setattr(native_lifecycle,'dispatch_status',lambda path:dict(state='failed',fixture='child',error_type='OSError'))
    with pytest.raises(RuntimeError,match='OSError'):
        native_lifecycle.completed_dispatch(tmp_path,'old',tmp_path/'supervisor.sock')
    monkeypatch.setattr(native_lifecycle,'dispatch_status',lambda path:dict(state='complete',fixture='child',generation='different'))
    assert native_lifecycle.completed_dispatch(tmp_path,'old',tmp_path/'supervisor.sock') is None
    monkeypatch.setattr(native_lifecycle,'dispatch_status',lambda path:dict(state='complete',fixture='child',generation=generation))
    assert native_lifecycle.completed_dispatch(tmp_path,'old',tmp_path/'supervisor.sock')['generation']==generation


def test_readonly_dispatch_status_has_exact_bounded_request_shape():
    import socket
    for block,accepted in [(b'{"inspect_dispatch":true}\n',True),(b'{"inspect_dispatch":1}\n',False),
        (b'{"inspect_dispatch":true,"path":"/private"}\n',False)]:
        server,client=socket.socketpair()
        try:
            client.sendall(block)
            if accepted:assert supervisor.read_request(server)=={'inspect_dispatch':True}
            else:
                with pytest.raises(ValueError):supervisor.read_request(server)
        finally:server.close();client.close()
