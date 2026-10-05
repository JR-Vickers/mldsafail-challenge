import socket
import threading
from types import SimpleNamespace
import pytest
from candidate_runtime.rehearsal import serve_operation


def test_dispatches_gateway_on_main_thread_and_preserves_operation_error():
    dispatched=[];ready=threading.Event()
    def dispatch():
        dispatched.append(threading.current_thread())
        ready.set()
    gateway=SimpleNamespace(server=SimpleNamespace(settimeout=lambda seconds:None),serve_once=dispatch)
    assert serve_operation(gateway,lambda:ready.wait(2),seconds=3) is True
    assert dispatched and all(thread is threading.main_thread() for thread in dispatched)
    def fail():raise ValueError('original application failure')
    with pytest.raises(ValueError,match='original application failure'):
        serve_operation(gateway,fail,seconds=3)


def test_background_dispatch_is_rejected_before_operation():
    errors=[];called=[]
    def run():
        try:serve_operation(None,lambda:called.append(True),seconds=1)
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=run);thread.start();thread.join(2)
    assert len(errors)==1 and isinstance(errors[0],RuntimeError) and not called
