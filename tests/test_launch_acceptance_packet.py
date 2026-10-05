import hashlib
import json
import pytest
from scripts.launch_acceptance_packet import build_packet,serialize

SOURCE='a'*40


def task(name,status='passed',deps=(),mapping=()):
    return dict(id=name,requirement='Verify declared gate',sources=['user-plan'],dependencies=list(deps),environment='native host',
        criteria=['Declared criterion'],status=status,attempts=[],evidence=[dict(reference='docs/source.json#/passed',criteria_met=['Declared criterion'])] if status=='passed' else [],
        identities={'source_commit':SOURCE} if status=='passed' else {},next_action='Verify next criterion',checklist=list(mapping))


def setup_report(tmp_path,tasks=None,complete=False):
    docs=tmp_path/'docs';docs.mkdir(exist_ok=True)
    (docs/'source.json').write_text(json.dumps({'passed':True,'source_review_passed':True,'native_executed':False}))
    report={'checklist_source':{'status':'available' if complete else 'blocked_external','expected_entries':78},'tasks':tasks or [task('source',mapping=range(1,79) if complete else ())]}
    return report


def packet(tmp_path,report,**kwargs):
    raw=json.dumps(report,sort_keys=True).encode()
    return build_packet(report,root=tmp_path,source_commit=SOURCE,ledger_sha256=hashlib.sha256(raw).hexdigest(),source_tree_clean=True,**kwargs)


def test_draft_is_deterministic_and_never_infers_native_or_owner_approval(tmp_path):
    report=setup_report(tmp_path)
    first=packet(tmp_path,report);second=packet(tmp_path,report)
    assert serialize(first)==serialize(second)
    assert first['public_launch_approved'] is False and first['production_activation_attested'] is False
    assert first['completed_gates'][0]['evidence'][0]['kind']=='source_review_or_local'
    assert first['final_ready'] is False and first['checklist']['exact_mapping_complete'] is False


@pytest.mark.parametrize('status',['pending','ready','running','failed','waiting_dependency'])
def test_unfinished_executable_leaf_prevents_completion_even_without_ready_label(tmp_path,status):
    report=setup_report(tmp_path,[task('unfinished',status)])
    result=packet(tmp_path,report,final=True)
    assert result['agent_work_complete'] is False and result['final_ready'] is False
    assert result['unfinished_executable_tasks']==['unfinished']


def test_external_decision_does_not_hide_its_executable_prerequisite(tmp_path):
    implementation=task('implementation','ready');decision=task('owner-decision','blocked_external',['implementation'])
    decision['blocker']={'input':'Explicit owner decision','owner':'repository owner','requested_action':'Review prepared packet'}
    dependant=task('activation','waiting_dependency',['owner-decision'])
    report=setup_report(tmp_path,[implementation,decision,dependant])
    result=packet(tmp_path,report)
    assert result['unfinished_executable_tasks']==['implementation']
    assert result['external_inputs_and_decisions'][0]['blocked_descendants']==['activation']


def test_external_only_dependencies_can_complete_agent_work_but_missing_checklist_rejects_final(tmp_path):
    decision=task('owner','blocked_external');decision['blocker']={'input':'Approved external receiver','owner':'owner','requested_action':'Configure private receiver'}
    report=setup_report(tmp_path,[decision,task('acceptance','waiting_dependency',['owner'])])
    result=packet(tmp_path,report,final=True)
    assert result['agent_work_complete'] is True and result['final_ready'] is False
    assert result['unfinished_dependency_roots']['acceptance']==['owner']


def test_invalid_unsupported_pass_and_duplicate_mapping_are_rejected(tmp_path):
    report=setup_report(tmp_path,[task('first',mapping=[1]),task('second',mapping=[1])])
    with pytest.raises(ValueError,match='validation failed'):packet(tmp_path,report)
    report=setup_report(tmp_path);report['tasks'][0]['evidence']=[]
    with pytest.raises(ValueError,match='validation failed'):packet(tmp_path,report)


def test_private_paths_endpoints_addresses_and_raw_epoch_identity_are_omitted(tmp_path):
    decision=task('owner','blocked_external');decision['blocker']={'input':'Receiver https://internal.example/hooks/opaque at 192.168.1.8','owner':'owner','requested_action':'Read /home/operator/private/config.json'}
    passed=task('source');passed['identities'].update(epoch_id='b'*32,image='sha256:'+'c'*64,**{'source_/home/operator/private':'d'*64})
    passed['attempts']=[{'result':'Failed connection to 192.168.1.8 using /srv/private/jobs','evidence':'docs/source.json#/passed'}]
    result=packet(tmp_path,setup_report(tmp_path,[decision,passed]));rendered=serialize(result).decode()
    assert 'internal.example' not in rendered and '192.168.1.8' not in rendered and '/srv/private' not in rendered and '/home/operator' not in rendered
    assert 'b'*32 not in rendered and 'sha256:'+'c'*64 in rendered
    assert len(result['failed_or_partial_attempts'])==1


def test_native_classification_requires_explicit_positive_native_attestation(tmp_path):
    report=setup_report(tmp_path)
    (tmp_path/'docs/native.json').write_text(json.dumps({'native_executed':True,'passed':True}))
    report['tasks'][0]['evidence'][0]['reference']='docs/native.json#/passed'
    assert packet(tmp_path,report)['completed_gates'][0]['evidence'][0]['kind']=='native_attested'


def test_final_requires_exact_mapping_clean_source_and_native_state_proof(tmp_path):
    report=setup_report(tmp_path,complete=True)
    state={'schema':'mldsafail.launch-handoff-state.v1','native_executed':True,'maintenance_reconciled':True,'live_state_verified':True,'passed':True,'evidence_refs':['docs/native.json#/passed']}
    (tmp_path/'docs/native.json').write_text(json.dumps({'passed':True,'native_executed':True}))
    (tmp_path/'docs/state.json').write_text(json.dumps(state))
    result=packet(tmp_path,report,final=True,state_reference='docs/state.json')
    assert result['final_ready'] is True and result['public_launch_approved'] is False
    state['native_executed']=False;(tmp_path/'docs/state.json').write_text(json.dumps(state))
    assert packet(tmp_path,report,final=True,state_reference='docs/state.json')['final_ready'] is False


def test_secret_bearing_input_is_rejected_before_snapshot(tmp_path):
    report=setup_report(tmp_path);report['tasks'][0]['identities']['access_key']='do not disclose'
    with pytest.raises(ValueError,match='validation failed'):packet(tmp_path,report)


def test_snapshot_write_preserves_history_and_retracts_postwrite_failure(monkeypatch,tmp_path):
    from scripts import launch_acceptance_packet as module
    result=packet(tmp_path,setup_report(tmp_path));result['final_ready']=True
    path=tmp_path/'snapshot.json';calls=[]
    def fsync(descriptor):
        calls.append(descriptor)
        if len(calls)==2:raise OSError('directory synchronization failed')
    monkeypatch.setattr(module.os,'fsync',fsync)
    with pytest.raises(OSError):module.write_snapshot(path,result)
    negative=json.loads(path.read_text())
    assert negative['snapshot_complete'] is False and negative['final_ready'] is False
    assert negative['publication_failed'] is True
    with pytest.raises(FileExistsError):module.write_snapshot(path,result)
    assert json.loads(path.read_text())==negative


@pytest.mark.parametrize('contradictory',[False,True])
def test_handoff_wrapper_cannot_promote_source_only_or_contradictory_native_refs(tmp_path,contradictory):
    report=setup_report(tmp_path,complete=True)
    if contradictory:
        proof={'native_executed':False,'scoped':{'native_executed':True,'passed':True}}
        ref='docs/contradictory.json#/scoped/passed'
        (tmp_path/'docs/contradictory.json').write_text(json.dumps(proof))
    else:ref='docs/source.json#/passed'
    state={'schema':'mldsafail.launch-handoff-state.v1','native_executed':True,'maintenance_reconciled':True,
        'live_state_verified':True,'passed':True,'evidence_refs':[ref]}
    (tmp_path/'docs/state.json').write_text(json.dumps(state))
    result=packet(tmp_path,report,final=True,state_reference='docs/state.json')
    assert result['final_ready'] is False and result['final_state_evidence']['native_state_attested'] is False
    assert 'Native maintenance and live-state handoff evidence is incomplete' in result['readiness_rejections']


@pytest.mark.parametrize('leaf,value',[('source_review_passed',True),('status','source_review_passed_native_gates_pending')])
def test_source_outcome_pointer_remains_source_even_in_native_document(tmp_path,leaf,value):
    report=setup_report(tmp_path,complete=True)
    (tmp_path/'docs/mixed.json').write_text(json.dumps({'native_executed':True,leaf:value}))
    state={'schema':'mldsafail.launch-handoff-state.v1','native_executed':True,'maintenance_reconciled':True,
        'live_state_verified':True,'passed':True,'evidence_refs':['docs/mixed.json#/'+leaf]}
    (tmp_path/'docs/state.json').write_text(json.dumps(state))
    assert packet(tmp_path,report,final=True,state_reference='docs/state.json')['final_ready'] is False
