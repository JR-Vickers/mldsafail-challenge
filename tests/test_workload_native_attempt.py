from copy import deepcopy
from pathlib import Path
import pytest
from deploy.workload_installation import identity
from deploy.workload_native_attempt import bind,verify
from deploy.workload_release import canonical
from mldsafail.evaluator.workload import WorkloadBlocked


def protocol(root,packet='a',attempt='b'):
    return dict(origin='installed_native',identities=dict(hostname='host',uid=1000,boot_id='boot',
        authority_journal=dict(path=str(root)),installation=dict(proposal=dict(sha256='f'*64)),
        native_context=dict(generation=packet*32,attempt_generation=attempt*32)))


def claim(root,protocol,letter):
    path=root/('native-authority-'+letter*64+'.consumed')
    path.write_bytes(canonical(dict(schema='mldsafail.native-authorization-intent.v3',authorization_sha256=letter*64,
        protocol=protocol,disposition='claimed_requires_final_receipt_or_reconciliation')));path.chmod(0o600)
    return identity(path)


def test_split_packets_keep_original_attempt_start_and_reserve(tmp_path):
    first=protocol(tmp_path);proof=bind(first,claim(tmp_path,first,'a'),now=100)
    second=protocol(tmp_path,packet='c');again=bind(second,claim(tmp_path,second,'c'),now=1100)
    assert proof==again and verify(second,again,now=1100)==1600
    with pytest.raises(WorkloadBlocked,match='work_budget_expired'):verify(second,again,now=1600)


def test_missing_attempt_header_with_existing_intent_is_never_recreated(tmp_path):
    data=protocol(tmp_path);proof=bind(data,claim(tmp_path,data,'a'),now=100)
    path=Path(proof['record']['path']);path.unlink()
    new=protocol(tmp_path,packet='c')
    with pytest.raises(WorkloadBlocked):bind(new,claim(tmp_path,new,'c'),now=200)
    assert not path.exists()


def test_replaced_identical_header_and_changed_boot_are_blocked(tmp_path):
    data=protocol(tmp_path);proof=bind(data,claim(tmp_path,data,'a'),now=100)
    changed=deepcopy(data);changed['identities']['boot_id']='newboot'
    with pytest.raises(WorkloadBlocked,match='identity_or_budget_changed'):verify(changed,proof,now=200)
    path=Path(proof['record']['path']);raw=path.read_bytes();path.rename(path.with_suffix('.preserved'));path.write_bytes(raw);path.chmod(0o600)
    with pytest.raises(WorkloadBlocked,match='record_or_ack_replaced'):verify(data,proof,now=200)


def test_packet_cannot_substitute_attempt_generation_or_create_unclaimed_budget(tmp_path):
    data=protocol(tmp_path);proof=bind(data,claim(tmp_path,data,'a'),now=100)
    changed=deepcopy(data);changed['identities']['native_context']['attempt_generation']='d'*32
    with pytest.raises(WorkloadBlocked):verify(changed,proof,now=200)
    with pytest.raises(WorkloadBlocked,match='current_owner_claim_changed'):
        bind(changed,proof['record'],now=200)


def test_interrupted_creation_ack_preserves_namespace(tmp_path):
    data=protocol(tmp_path);proof=bind(data,claim(tmp_path,data,'a'),now=100)
    ack=Path(proof['ack']['path']);ack.unlink()
    new=protocol(tmp_path,packet='c')
    with pytest.raises(WorkloadBlocked):bind(new,claim(tmp_path,new,'c'),now=200)
    assert not ack.exists() and Path(proof['record']['path']).exists()
