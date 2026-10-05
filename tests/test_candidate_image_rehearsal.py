import socket
import threading
from types import SimpleNamespace
import pytest
from candidate_runtime.rehearsal import serve_operation
from deploy import owned_client


@pytest.fixture(autouse=True)
def native_owner(monkeypatch):
    monkeypatch.setattr(owned_client,'identity',lambda pid:dict(pid=pid,start_ticks=1))


def test_dispatches_gateway_on_main_thread_and_preserves_operation_error():
    dispatched=[];ready=threading.Event()
    def dispatch():
        dispatched.append(threading.current_thread())
        ready.set()
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None),serve_once=dispatch)
    assert serve_operation(gateway,lambda cancel:ready.wait(2),seconds=3) is True
    assert dispatched and all(thread is threading.main_thread() for thread in dispatched)
    def fail(cancel):raise ValueError('original application failure')
    with pytest.raises(ValueError,match='original application failure'):
        serve_operation(gateway,fail,seconds=3)


def test_background_dispatch_is_rejected_before_operation():
    errors=[];called=[]
    def run():
        try:serve_operation(None,lambda cancel:called.append(True),seconds=1)
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=run);thread.start();thread.join(2)
    assert len(errors)==1 and isinstance(errors[0],RuntimeError) and not called


def test_gateway_failure_cancels_and_joins_blocked_operation():
    stopped=threading.Event()
    def operation(cancel):
        assert cancel.wait(2)
        stopped.set()
    def fail():raise ValueError('gateway disconnected')
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None),serve_once=fail)
    with pytest.raises(ValueError,match='gateway disconnected'):
        serve_operation(gateway,operation,seconds=3)
    assert stopped.is_set()


def test_deadline_cancels_and_joins_blocked_operation():
    stopped=threading.Event()
    def operation(cancel):
        cancel.wait(2);stopped.set()
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None))
    with pytest.raises(TimeoutError):serve_operation(gateway,operation,seconds=0)
    assert stopped.is_set()


def test_gateway_failure_stops_owned_transport_and_publishes_closed_lifecycle(monkeypatch,tmp_path):
    import json
    stopped=threading.Event();observed=[]
    entry={'id':'owned-operation'}
    journal=SimpleNamespace(data={'clients':[]})
    def operation(cancel):
        journal.data['clients'].append(entry)
        assert stopped.wait(2)
    def stop(value):
        observed.append(value);stopped.set()
    monkeypatch.setattr(owned_client,'stop',stop)
    def fail():raise ValueError('gateway interrupted')
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None),serve_once=fail)
    receipt=tmp_path/'lifecycle.json'
    with pytest.raises(ValueError,match='gateway interrupted'):
        serve_operation(gateway,operation,seconds=3,journal=journal,receipt=receipt)
    proof=json.loads(receipt.read_text())
    assert observed==[entry] and proof['state']=='closed' and proof['cleanup_complete'] is True
    assert proof['thread_alive'] is False and proof['cancel_requested'] is True


def test_surviving_io_thread_retains_negative_lifecycle(monkeypatch,tmp_path):
    import itertools
    import json
    from candidate_runtime import rehearsal
    release=threading.Event();finished=threading.Event()
    def operation(cancel):
        release.wait(2)
        finished.set()
    ticks=iter(itertools.count(0,100))
    monkeypatch.setattr(rehearsal.time,'monotonic',lambda:next(ticks))
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None))
    receipt=tmp_path/'negative.json'
    try:
        with pytest.raises(rehearsal.OperationCleanupIncomplete,match='runtime reuse prohibited'):
            serve_operation(gateway,operation,seconds=1,receipt=receipt)
        proof=json.loads(receipt.read_text())
        assert proof['state']=='cleanup_incomplete' and proof['cleanup_complete'] is False
        assert proof['thread_alive'] is True and proof['cancel_requested'] is True
    finally:
        monkeypatch.undo()
        release.set()
        assert finished.wait(2)
