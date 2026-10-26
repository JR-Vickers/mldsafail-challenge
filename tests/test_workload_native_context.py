"""Native provenance regressions only; no native execution authority is used."""
import copy
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from deploy import workload_native_context as context
from deploy.workload_installation import exclusive,identity,private
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.fixture
def proof(tmp_path,monkeypatch):
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    import deploy.workload_native_attempt as attempts
    monkeypatch.setattr(attempts,'verify',lambda protocol,proof:279)
    owner=tmp_path/'owner';owner.mkdir(mode=0o700);root=owner/('native-control-'+'a'*32);root.mkdir(mode=0o700)
    mono=[100.0];wall=[1000.0]
    monkeypatch.setattr(context,'time',SimpleNamespace(monotonic=lambda:mono[0],time=lambda:wall[0],sleep=lambda value:None))
    monkeypatch.setattr(context,'sys',SimpleNamespace(platform='linux'))
    real_path=Path
    monkeypatch.setattr(context,'Path',lambda value:SimpleNamespace(read_text=lambda:'boot')
        if str(value)=='/proc/sys/kernel/random/boot_id' else real_path(value))
    monkeypatch.setattr(context,'validate',lambda packet,**kwargs:packet)
    def write(path,value):
        exclusive(path,canonical(value));return {'path':str(path),'sha256':digest(canonical(value))}
    host=dict(hostname=socket.gethostname(),uid=os.getuid(),boot_id='boot')
    source=dict(host=host,installation={'gate_root':str(tmp_path/'global')},manifest={'files':{
        name:{'sha256':'1'*64} for name in REVIEW_FILES}})
    proposal=write(owner/'proposal',{'identities':source});inspection=write(owner/'inspection',{'captured_at':1000})
    facts=write(owner/'facts',dict(schema='mldsafail.native-control-packet-facts.v1',origin='host_observation',
        postgres_image='sha256:'+'b'*64,authority_journal=identity(owner),host=host))
    spec=dict(generation='a'*32,attempt_generation='d'*32,watchdog_root=str(root),postgres_image='sha256:'+'b'*64,
        control='shared_host_gate',scenario='cross_database_and_admin',case_output=str(root/'context/artifacts'/('case-'+'a'*32+'.json')),
        facts=facts,global_hold=dict(state='proposed',path=source['installation']['gate_root']+'/native-control-hold.json',
            creation='exclusive',precondition='absent',effect='deny_admission_only'))
    row=lambda name,seconds:dict(name=name,seconds=seconds,argv=['/usr/bin/true'])
    protocol=dict(origin='installed_native',identities=dict(native_context=spec,authority_journal=identity(owner),**host),
        startup=row('startup',30),cases=[row('case',90)],cleanup=row('cleanup',45),postflight=row('postflight',15),timeout_seconds=180)
    packet=dict(schema='v3-proof-unit-fixture',stage='installed',proposal=proposal,inspection=inspection,protocol=protocol)
    binding=digest(canonical(protocol))
    review=write(owner/'review',dict(decision='approved',implemented_by='builder',reviewed_by='reviewer',
        protocol_sha256=binding,source_sha256={name:'1'*64 for name in REVIEW_FILES}))
    authorization=write(owner/'authorization',dict(schema='mldsafail.workload-native-authority.v3',purpose='native_workload_control_only',
        authorized_by='owner',protocol_sha256=binding,review_sha256=review['sha256'],issued_at=995,expires_at=1175,nonce='c'*32))
    claim=owner/('native-authority-'+authorization['sha256']+'.consumed')
    write(claim,dict(schema='mldsafail.native-authorization-intent.v3',authorization_sha256=authorization['sha256'],protocol=protocol,
        disposition='claimed_requires_final_receipt_or_reconciliation'))
    watchdog=dict(pid=11,start_ticks=101);child=dict(pid=22,start_ticks=202)
    monkeypatch.setattr(context,'_ancestry',lambda:[child,watchdog])
    monkeypatch.setattr(context,'process_birth',lambda pid:copy.deepcopy(watchdog if pid==11 else child))
    rows=[protocol['startup'],*protocol['cases'],protocol['cleanup'],protocol['postflight']]
    stages=[dict(index=index,kind=kind,name=row['name'],intent_path=str(root/f'native-stage-{index}.json'),
        birth_path=str(root/f'native-stage-{index}-birth.json')) for index,(kind,row) in enumerate(zip(
            ('startup','case','cleanup','postflight'),rows))]
    supervision=dict(attempt={},schema=context.SUPERVISION,origin='installed_native',protocol_sha256=binding,watchdog=watchdog,
        root=identity(root),review=review,authorization=authorization,claim=identity(claim),deadline_monotonic=279,
        created_monotonic=99,watchdog_source_sha256='1'*64,stages=stages)
    write(root/'native-supervision.json',supervision);sup_sha=digest(canonical(supervision))
    stage=dict(schema=context.STAGE,supervision_sha256=sup_sha,protocol_sha256=binding,index=1,kind='case',name='case',
        argv_sha256=digest(canonical(rows[1]['argv'])),started_monotonic=99.5,deadline_monotonic=189.5)
    write(root/'native-stage-1.json',stage)
    birth=dict(schema=context.BIRTH,intent_sha256=digest(canonical(stage)),process=child,supervision_sha256=sup_sha)
    write(root/'native-stage-1-birth.json',birth)
    return SimpleNamespace(root=root,owner=owner,packet=packet,supervision=supervision,stage=stage,birth=birth,mono=mono,wall=wall,
        child=child,watchdog=watchdog)


def test_live_claim_and_exact_stage_are_required_together(proof):
    result=context.verify_supervision(proof.packet,proof.root,allowed_stage='case')
    assert result['stage']=='case' and result['child']['process']==proof.child
    with pytest.raises(WorkloadBlocked,match='current_stage_missing'):
        context.verify_supervision(proof.packet,proof.root,allowed_stage='cleanup')


@pytest.mark.parametrize('change',['claim_missing','not_ancestor','stage_expired','owner_expired','argv','birth','wrong_origin','review_source'])
def test_native_proof_rejects_missing_tampered_stale_or_wrong_origin_before_effect(proof,monkeypatch,change):
    if change=='claim_missing':Path(proof.supervision['claim']['path']).unlink()
    elif change=='not_ancestor':monkeypatch.setattr(context,'_ancestry',lambda:[proof.child])
    elif change=='stage_expired':proof.mono[0]=200
    elif change=='owner_expired':proof.wall[0]=1176
    elif change=='argv':
        value=dict(proof.stage,argv_sha256='f'*64);(proof.root/'native-stage-1.json').write_bytes(canonical(value))
    elif change=='birth':monkeypatch.setattr(context,'process_birth',lambda pid:dict(pid=pid,start_ticks=999))
    elif change=='wrong_origin':proof.packet['protocol']['origin']='synthetic'
    else:
        path=Path(proof.supervision['review']['path']);value=private(path)[1];value['source_sha256']={};path.write_bytes(canonical(value))
    with pytest.raises(WorkloadBlocked):context.verify_supervision(proof.packet,proof.root,allowed_stage='case')
    assert not (proof.root/'context').exists()


def test_native_settings_reject_extra_capability_or_unbound_output(proof):
    spec=proof.packet['protocol']['identities']['native_context']
    spec['arbitrary_command']=['/bin/true']
    with pytest.raises(WorkloadBlocked,match='settings_invalid'):context.settings(proof.packet)
    spec.pop('arbitrary_command');spec['case_output']=str(proof.owner/'outside')
    with pytest.raises(WorkloadBlocked,match='output_outside'):context.settings(proof.packet)


def test_inactive_stage_files_do_not_authorize_an_unrelated_live_process(proof,monkeypatch):
    monkeypatch.setattr(context,'_ancestry',lambda:[{'pid':33,'start_ticks':303},proof.watchdog])
    with pytest.raises(WorkloadBlocked,match='current_stage_missing'):context.verify_supervision(proof.packet,proof.root)


def test_native_context_does_not_allow_vm_installation_adapters():
    value=object.__new__(context.NativeContext)
    for name in ('adapter','engine','transition','control'):
        with pytest.raises(WorkloadBlocked):getattr(value,name)('install')


def test_native_attempt_verifier_is_in_independent_review_closure():
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    assert 'deploy/workload_native_attempt.py' in REVIEW_FILES
