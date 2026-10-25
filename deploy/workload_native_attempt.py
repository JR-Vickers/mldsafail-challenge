"""Immutable original native-control attempt budget across single-use packets."""
from pathlib import Path
import re
import time

from deploy.workload_installation import Journal,exclusive,identity,private
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.native_workload import require

SCHEMA='mldsafail.native-control-attempt.v1'
ACK='mldsafail.native-control-attempt-creation.v1'


def _selection(protocol):
    require(protocol['origin']=='installed_native','native_attempt_origin_invalid')
    context=protocol['identities']['native_context'];generation=context.get('attempt_generation')
    require(type(generation) is str and re.fullmatch('[a-f0-9]{32}',generation),'native_attempt_generation_required')
    parent=Path(protocol['identities']['authority_journal']['path'])
    proposal=protocol['identities']['installation']['proposal']['sha256']
    require(re.fullmatch('[a-f0-9]{64}',proposal),'native_attempt_proposal_invalid')
    return generation,parent,proposal


def bind(protocol,claim,*,now=None):
    """Called after exact owner claim, before startup or control effects."""
    now=time.monotonic() if now is None else now
    generation,parent,proposal=_selection(protocol)
    require(identity(claim['path'])==claim and private(claim['path'])[1].get('protocol')==protocol,
        'native_attempt_current_owner_claim_changed')
    ledger_root=parent/('native-control-attempt-ledger-'+proposal)
    try:ledger_root.mkdir(mode=0o700)
    except FileExistsError:pass
    ledger=Journal(ledger_root,proposal)
    directory=parent/('native-control-attempt-'+generation)
    with ledger.locked():
        intents=[row for row in ledger.rows if row['event']=='native_attempt_intent' and row.get('generation')==generation]
        outcomes=[row for row in ledger.rows if row['event']=='native_attempt_created' and row.get('generation')==generation]
        require(len(intents)<=1 and len(outcomes)<=1,'native_attempt_duplicate_creation')
        if not intents:
            require(not outcomes and not directory.exists() and not directory.is_symlink(),'native_attempt_unknown_namespace_preserve')
            ledger.append('native_attempt_intent',generation=generation,claim=claim,path=str(directory))
            directory.mkdir(mode=0o700)
            value=dict(schema=SCHEMA,generation=generation,host={key:protocol['identities'][key] for key in ('hostname','uid','boot_id')},
                proposal_sha256=proposal,started_monotonic=now,budget_seconds=1800,cleanup_reserve_seconds=300,original_claim=claim)
            exclusive(directory/'attempt.json',canonical(value))
            ack=dict(schema=ACK,generation=generation,record=identity(directory/'attempt.json'),original_claim=claim)
            exclusive(directory/'creation.json',canonical(ack))
            ledger.append('native_attempt_created',generation=generation,record=identity(directory/'attempt.json'),
                ack=identity(directory/'creation.json'),parent_intent_sha256=digest(canonical(ledger.rows[-1])))
            outcomes=[ledger.rows[-1]]
        require(outcomes,'native_attempt_creation_unacknowledged_preserve')
        proof=dict(record=outcomes[0]['record'],ack=outcomes[0]['ack'],ledger=identity(ledger_root),
            creation_sha256=digest(canonical(outcomes[0])))
    verify(protocol,proof,now=now)
    return proof


def verify(protocol,proof,*,now=None):
    """Observe budget/provenance only; no reset, repair or authority claim."""
    now=time.monotonic() if now is None else now
    generation,parent,proposal=_selection(protocol);directory=parent/('native-control-attempt-'+generation)
    require(type(proof) is dict and set(proof)=={'record','ack','ledger','creation_sha256'} and
        proof['record'].get('path')==str(directory/'attempt.json') and proof['ack'].get('path')==str(directory/'creation.json') and
        identity(proof['record']['path'])==proof['record'] and identity(proof['ack']['path'])==proof['ack'],
        'native_attempt_record_or_ack_replaced')
    value=private(proof['record']['path'])[1];ack=private(proof['ack']['path'])[1]
    require(set(value)=={'schema','generation','host','proposal_sha256','started_monotonic','budget_seconds','cleanup_reserve_seconds','original_claim'} and
        value['schema']==SCHEMA and value['generation']==generation and value['proposal_sha256']==proposal and
        value['host']=={key:protocol['identities'][key] for key in ('hostname','uid','boot_id')} and
        type(value['started_monotonic']) in (int,float) and value['started_monotonic']<=now and
        type(value['budget_seconds']) is int and value['budget_seconds']==1800 and
        type(value['cleanup_reserve_seconds']) is int and value['cleanup_reserve_seconds']==300,
        'native_attempt_identity_or_budget_changed')
    require(ack==dict(schema=ACK,generation=generation,record=proof['record'],original_claim=value['original_claim']),
        'native_attempt_creation_ack_changed')
    original=value['original_claim'];require(Path(original['path']).parent==parent and identity(original['path'])==original,
        'native_attempt_original_claim_changed')
    consumed=private(original['path'])[1]
    require(consumed.get('schema')=='mldsafail.native-authorization-intent.v3' and
        consumed.get('disposition')=='claimed_requires_final_receipt_or_reconciliation' and
        Path(original['path']).name=='native-authority-'+consumed.get('authorization_sha256','')+'.consumed' and
        consumed.get('protocol',{}).get('identities',{}).get('native_context',{}).get('attempt_generation')==generation and
        consumed['protocol']['identities']['installation']['proposal']['sha256']==proposal,
        'native_attempt_original_claim_missing')
    ledger_path=parent/('native-control-attempt-ledger-'+proposal)
    require(proof['ledger'].get('path')==str(ledger_path) and identity(ledger_path)==proof['ledger'],'native_attempt_ledger_replaced')
    ledger=Journal(ledger_path,proposal)
    intents=[row for row in ledger.rows if row['event']=='native_attempt_intent' and row.get('generation')==generation]
    rows=[row for row in ledger.rows if row['event']=='native_attempt_created' and row.get('generation')==generation]
    require(len(intents)==len(rows)==1 and rows[0]['parent_intent_sha256']==digest(canonical(intents[0])) and
        digest(canonical(rows[0]))==proof['creation_sha256'] and rows[0]['record']==proof['record'] and rows[0]['ack']==proof['ack'] and
        intents[0]['claim']==original,'native_attempt_creation_provenance_changed')
    deadline=value['started_monotonic']+1500
    require(now<deadline,'native_attempt_work_budget_expired')
    return deadline
