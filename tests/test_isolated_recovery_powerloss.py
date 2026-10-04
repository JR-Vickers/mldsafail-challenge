import hashlib
import json
import pytest
from deploy import native_recovery_powerloss as gate


def boundary():
    return {'schema':'mldsafail.synthetic-powerloss-boundary.v1','synthetic_only':True,'boot_id':'old',
            'daemon_manifest':{'unit':'owned','unit_fragment_sha256':'sha','leader':{'boot_id':'old'}}}


def test_real_changed_boot_required_before_old_unit_inspection(monkeypatch):
    monkeypatch.setattr(gate.owned_client,'boot_id',lambda:'old')
    monkeypatch.setattr(gate.owned_daemon,'_unit',lambda unit:pytest.fail('same boot cannot claim power loss'))
    with pytest.raises(ValueError,match='changed guest boot'):gate.validate_reboot(boundary())


def test_old_active_or_reconfigured_daemon_cannot_authorize_recovery(monkeypatch):
    monkeypatch.setattr(gate.owned_client,'boot_id',lambda:'new')
    for state in [{'unit_fragment_sha256':'sha','ActiveState':'active'},
                  {'unit_fragment_sha256':'different','ActiveState':'inactive'}]:
        monkeypatch.setattr(gate.owned_daemon,'_unit',lambda unit:state)
        with pytest.raises(ValueError,match='old dedicated unit'):gate.validate_reboot(boundary())


def test_synthetic_payload_contains_public_tiny_instance_only():
    row=json.loads(gate.payload())
    assert row['scope']=='synthetic-recovery-only'
    public=row['public_instance']
    assert public['profile']=='small'
    assert set(public)=={'A','dimensions','eta','instance_id','profile','ring','schema_version','study_version','t','track'}


def test_prepare_failure_attempts_cleanup_without_masking_original(tmp_path,monkeypatch):
    original=ValueError('synthetic SQL failure')
    attempted=[]
    class Journal:
        def __init__(self,*args):pass
        def cleanup(self):attempted.append('cleanup');raise RuntimeError('cleanup failed')
    monkeypatch.setattr(gate,'Journal',Journal)
    def database(*args):raise original
    monkeypatch.setattr(gate,'database',database)
    with pytest.raises(ValueError) as caught:
        gate.prepare_callback(None,{'state_root':str(tmp_path/'pre-driver')},{'id':'owned'})
    assert caught.value is original and attempted==['cleanup']
    assert original.__notes__==['Independent preparation cleanup failed: RuntimeError']


def test_vm_inherited_extra_writable_drive_is_rejected_before_provision():
    from pathlib import Path
    from deploy.qemu_isolated_recovery_powerloss import isolated_argv
    with pytest.raises(ValueError,match='allowlist'):
        isolated_argv(Path('/base'),Path('/new'),['qemu-system-aarch64','-drive','file=/foreign'],2222)


def test_vm_base_open_file_or_failed_probe_refuses_boot(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from deploy import qemu_isolated_recovery_powerloss as host
    for result in (SimpleNamespace(returncode=0,stdout=b'123',stderr=b''),SimpleNamespace(returncode=2,stdout=b'',stderr=b''),SimpleNamespace(returncode=1,stdout=b'',stderr=b'inspection failure')):
        monkeypatch.setattr(host.subprocess,'run',lambda *args,**kwargs:result)
        with pytest.raises(RuntimeError,match='quiescence unproved'):host.require_base_quiescent(Path('/base'))
