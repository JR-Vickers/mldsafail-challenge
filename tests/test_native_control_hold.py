"""The native hold only denies admission; it never resumes computation."""
import copy
import threading
from pathlib import Path

import pytest

from mldsafail.evaluator.native_workload import NativeRuntime
from mldsafail.evaluator.workload import HostGate,ResourcePolicy,WorkloadBlocked
from mldsafail.evaluator.workload_socket import SupervisorProtocol
from tests.test_native_workload import fixture as native_fixture


@pytest.mark.parametrize('kind',['file','malformed','directory','symlink'])
def test_any_hold_inode_denies_before_native_io(native_fixture,kind):
    native,*_,calls=native_fixture
    path=native.root/'native-control-hold.json'
    if kind=='directory':path.mkdir()
    elif kind=='symlink':path.symlink_to(native.root/'absent-target')
    else:path.write_bytes(b'{}' if kind=='file' else b'invalid')
    before=list(calls)
    with pytest.raises(WorkloadBlocked,match='native_control_hold_active'):native.preflight(ResourcePolicy())
    assert calls==before


def test_clone_gate_is_not_granted_or_denied_by_another_roots_hold(native_fixture,tmp_path):
    native,*_=native_fixture
    assert native.preflight(ResourcePolicy())>0
    (native.root/'native-control-hold.json').write_bytes(b'bound installed gate denial')
    clone_root=tmp_path/'clone';clone_root.mkdir(mode=0o700)
    clone=NativeRuntime(dict(copy.deepcopy(native.config),root=str(clone_root)),run=native.run)
    assert clone.preflight(ResourcePolicy())>0
    with pytest.raises(WorkloadBlocked,match='native_control_hold_active'):native.preflight(ResourcePolicy())


def test_status_catches_resume_admitted_before_hold_without_waiting_for_io(native_fixture):
    native,*_=native_fixture
    entered=threading.Event();release=threading.Event();errors=[]
    with HostGate(native.root,native).locked() as gate:
        gate.acquire('administration',{'fixture':'hold-race'});gate.reconcile();gate.pause('fixture')
        original=native.preflight
        def admitted(policy):
            result=original(policy);entered.set()
            assert release.wait(2)
            return result
        native.preflight=admitted
        def resume():
            try:gate.resume()
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=resume);thread.start()
        try:
            assert entered.wait(1)
            (native.root/'native-control-hold.json').write_bytes(b'new owner-bound denial hold')
            protocol=SupervisorProtocol(gate,{'participant':{'role':'participant'}})
            status=protocol.dispatch(dict(id='status',method='status',argument={}))
            assert status['paused'] is True and status['inflight_launches']==0 and status['inflight_resumes']==1
        finally:release.set();thread.join(3)
        assert not thread.is_alive() and errors==[]
        status=protocol.dispatch(dict(id='status',method='status',argument={}))
        assert status['inflight_resumes']==0 and status['paused'] is False
        # The pre-existing resume may finish; the snapshot never certified idle,
        # and the installed gate still cannot acquire a new computational owner.
        with pytest.raises(WorkloadBlocked,match='native_control_hold_active'):gate.acquire('evaluation',{})


def test_failed_resume_always_clears_readonly_counter(native_fixture):
    native,*_=native_fixture
    with HostGate(native.root,native).locked() as gate:
        gate.acquire('administration',{'fixture':'hold'});gate.reconcile();gate.pause('fixture')
        (native.root/'native-control-hold.json').write_bytes(b'denied')
        with pytest.raises(WorkloadBlocked,match='native_control_hold_active'):gate.resume()
        assert gate.inflight_resumes==0 and gate.state['paused'] is True
