import pytest
from deploy.native_recovery_transport_loss import validate_reconnection


def test_actual_transport_proof_requires_same_boot_owner_and_strict_boolean():
    identity=dict(pid=100,start_ticks=42,uid=1000,boot_id='actual-boot',cmdline_sha256='actual-command')
    valid=dict(actual_ssh_drop=True,same_boot_id='actual-boot',same_owner_pid=100,owner_identity=identity)
    validate_reconnection(valid,'actual-boot',100,identity)
    for key,value in [('actual_ssh_drop',1),('same_boot_id','other-boot'),('same_owner_pid',101),('same_owner_pid',True)]:
        changed={**valid,key:value}
        with pytest.raises(ValueError):validate_reconnection(changed,'actual-boot',100,identity)
    with pytest.raises(ValueError):validate_reconnection({**valid,'synthetic_sigkill':True},'actual-boot',100,identity)

    with pytest.raises(ValueError):validate_reconnection({**valid,'owner_identity':{**identity,'start_ticks':43}},'actual-boot',100,identity)


def test_host_cleanup_independently_cancels_transport_after_vm_failure(tmp_path,monkeypatch):
    import json
    from deploy import qemu_isolated_recovery_powerloss as host
    root=tmp_path/'run';root.mkdir(mode=0o700)
    record=dict(vm_attempts=[dict(pid=1)],transport_client=dict(pid=2))
    path=root/'ownership.json';path.write_text(json.dumps(record));path.chmod(0o600)
    calls=[]
    def stop(entry):
        calls.append(entry['pid'])
        if entry['pid']==1:raise RuntimeError('first cleanup failure')
    monkeypatch.setattr(host.owned_vm,'stop',stop)
    with pytest.raises(RuntimeError,match='cleanup incomplete'):
        host.run(tmp_path/'base',root,tmp_path/'source',None,cleanup_only=True,transport_loss=True)
    assert calls==[1,2]
    receipt=json.loads(next(root.glob('*-cleanup.json')).read_text())
    assert receipt['owned_vm_stopped'] is False and receipt['owned_transport_stopped'] is False
