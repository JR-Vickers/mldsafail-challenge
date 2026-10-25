import json
import os
from pathlib import Path
from types import SimpleNamespace
import socket
import time

import pytest
from deploy.workload_installation import identity
from deploy.workload_native_supervision import publish,stage_intent,stage_birth
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked


def protocol():
    row=lambda name,seconds:dict(name=name,seconds=seconds,argv=['/usr/bin/true'])
    return dict(origin='installed_native',identities={},fixture_cgroup='/sys/fs/cgroup/owned',
        startup=row('startup',30),cases=[row('case',90)],cleanup=row('cleanup',45),postflight=row('postflight',15),timeout_seconds=180)


def authority(tmp_path,monkeypatch,wall):
    import deploy.workload_watchdog as module
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    data=protocol();data['identities'].update(hostname=socket.gethostname(),uid=os.getuid(),boot_id='boot',authority_journal=identity(root))
    real_path=Path
    monkeypatch.setattr(module,'Path',lambda value:SimpleNamespace(read_text=lambda:'boot') if str(value)=='/proc/sys/kernel/random/boot_id' else real_path(value))
    monkeypatch.setattr(module,'time',SimpleNamespace(time=lambda:wall,monotonic=lambda:50.0))
    review=dict(decision='approved',implemented_by='builder',reviewed_by='reviewer',protocol_sha256=digest(canonical(data)))
    review_path=root/'review';review_path.write_bytes(canonical(review));review_path.chmod(0o600)
    grant=dict(schema='mldsafail.workload-native-authority.v3',purpose='native_workload_control_only',authorized_by='owner',
        protocol_sha256=digest(canonical(data)),review_sha256=digest(canonical(review)),issued_at=1000,expires_at=1180,nonce='a'*32)
    grant_path=root/'authority';grant_path.write_bytes(canonical(grant));grant_path.chmod(0o600)
    return module,data,review_path,grant_path,root


def test_owner_180_second_window_absorbs_validation_time_without_extension(tmp_path,monkeypatch):
    module,data,review,grant,root=authority(tmp_path,monkeypatch,1000.25)
    result=module.native_authority(data,review,grant,root/'output')
    assert result['deadline_monotonic']==229.75
    assert result['claim']['sha256'] and Path(result['claim']['path']).exists()
    with pytest.raises(WorkloadBlocked,match='consumed'):
        module.native_authority(data,review,grant,root/'output2')


def test_startup_delay_cannot_consume_case_cleanup_and_postflight_reserve(tmp_path,monkeypatch):
    module,data,review,grant,root=authority(tmp_path,monkeypatch,1031)
    with pytest.raises(WorkloadBlocked,match='startup_reserve_expired'):
        module.native_authority(data,review,grant,root/'output')
    assert not list(root.glob('*.consumed'))


def test_proofs_bind_stage_argv_birth_and_deadline_exclusively(tmp_path,monkeypatch):
    import deploy.workload_native_supervision as module
    monkeypatch.setattr(module,'process_birth',lambda pid:dict(pid=pid,start_ticks=123))
    data=protocol();root=tmp_path/'output';root.mkdir(mode=0o700)
    grant=dict(review=dict(path='/private/review',sha256='a'*64),authorization=dict(path='/private/authority',sha256='b'*64),claim=dict(path='/private/claim',sha256='c'*64))
    proof=publish(root,data,grant,time.monotonic()+180)
    stage=stage_intent(proof,1,data['cases'][0],time.monotonic()+90)
    observed=stage_birth(proof,1,dict(pid=10,start_ticks=20))
    assert stage['argv_sha256']==digest(canonical(data['cases'][0]['argv']))
    assert observed['intent_sha256']==digest(Path(proof['stages'][1]['intent_path']).read_bytes())
    with pytest.raises(FileExistsError):stage_birth(proof,1,dict(pid=10,start_ticks=20))
    with pytest.raises(WorkloadBlocked):stage_intent(proof,2,data['cleanup'],time.monotonic()-1)
    assert not Path(proof['stages'][2]['intent_path']).exists()


def test_synthetic_origin_cannot_emit_native_provenance(tmp_path):
    data=protocol();data['origin']='synthetic'
    with pytest.raises(WorkloadBlocked):publish(tmp_path,data,{},time.monotonic()+180)
    assert not (tmp_path/'native-supervision.json').exists()
