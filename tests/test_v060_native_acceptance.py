import json
import hashlib
from dataclasses import asdict
import pytest
from research.mlwe_v060_preparation import native_acceptance,native_reference_audit
from research.mlwe_v060_preparation.epochs import private_cases
from research.mlwe_v060_preparation.contracts import Cohort
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v060.envelope import canonical
from deploy import owned_daemon


def test_native_prerequisite_rejects_mismatched_source_and_unsupported_claim(tmp_path):
    path=tmp_path/'receipt'
    receipt=dict(worker_image='sha256:'+'c'*64,worker_context_sha256='d'*64,worker_source_commit='e'*40,schema='mldsafail.v060-native-prerequisites.v1',supervisor_source_sha256='a'*64,native_faults_passed=True,native_pairs_passed=True,supervisor_review_passed=True,auditor_review_passed=True,evidence_refs=['retained-native-packet'])
    owned_daemon.publish(path,receipt)
    assert native_acceptance.require_prerequisites(path,supervisor_source_sha256='a'*64,worker_image='sha256:'+'c'*64,worker_context_sha256='d'*64,worker_source_commit='e'*40)==receipt
    with pytest.raises(RuntimeError): native_acceptance.require_prerequisites(path,supervisor_source_sha256='b'*64,worker_image='sha256:'+'c'*64,worker_context_sha256='d'*64,worker_source_commit='e'*40)
    owned_daemon.publish(path,dict(receipt,native_pairs_passed=False))
    with pytest.raises(RuntimeError): native_acceptance.require_prerequisites(path,supervisor_source_sha256='a'*64,worker_image='sha256:'+'c'*64,worker_context_sha256='d'*64,worker_source_commit='e'*40)


def test_reference_auditor_recomputes_all_cases_and_refuses_tampered_cost(tmp_path,monkeypatch):
    cohort=Cohort('0.6.0','fresh','a'*64,'fresh','worker','b'*64,'cgroup-v2-usage-usec')
    cases=[dict(case_id=str(i),public_input=__import__('json').loads(__import__('json').dumps(generate_mlwe(row['profile'],row['seed'],row['eta']).public.to_dict()))) for i,row in enumerate(private_cases('c'*64))]
    evidence=dict(decision=dict(eligible=True,penalized=False,cost_usec=1))
    rows=[]
    retained={}
    for case in cases:
        generations=[f'{int(case["case_id"])*3+n:032x}' for n in range(3)]
        rows.append(dict(case_id=case['case_id'],evidence=dict(evidence,generations=generations)))
        for generation in generations:retained[generation]=dict(public_input=case['public_input'])
    producer=dict(cohort_id=cohort.public_id,source_sha256='d'*64,cases=rows)
    table=dict(schema='mldsafail.mlwe-v060-reference.v1',benchmark_version='0.6.0',measurement_method='cgroup-v2-usage-usec',units='microseconds',cohort_id=cohort.public_id,epoch_id=cohort.epoch_id,epoch_manifest_sha256='e'*64,reference_source_commit='f'*40,worker_image='sha256:'+'a'*64,audit_receipt_sha256=hashlib.sha256(canonical(producer)).hexdigest(),costs_usec={case['case_id']:1 for case in cases})
    monkeypatch.setattr(owned_daemon,'read_private_json',lambda path,**kw:retained[path.stem])
    calls=[]
    monkeypatch.setattr(native_reference_audit,'independently_audited_case',lambda records,**kw:calls.append(records) or evidence)
    args=dict(cases=cases,directory=tmp_path,cohort=cohort,source_sha256='d'*64,worker_image='sha256:'+'a'*64,supervisor_source_sha256='a'*64,reference_source_commit='f'*40,epoch_manifest_sha256='e'*64,seal_path=tmp_path/'seal')
    result=native_reference_audit.audit_reference(dict(table=table,receipt=producer),**args)
    assert result['ready'] is True and len(calls)==100 and (tmp_path/'seal').exists()
    table['costs_usec']['0']=2
    with pytest.raises(ValueError,match='cost/disposition'):
        native_reference_audit.audit_reference(dict(table=table,receipt=producer),**dict(args,seal_path=tmp_path/'second'))


def test_candidate_authority_is_scoped_and_cannot_activate_default(tmp_path):
    from mldsafail.benchmark_v060.candidate_authority import CandidateRehearsalAuthority
    from mldsafail.benchmark_versions import RegisteredBackend,VersionRegistry,application_cohort,UnsupportedBenchmark
    from research.mlwe_v060_preparation.epochs import prepare_epoch
    image='sha256:'+'c'*64
    prerequisite=tmp_path/'prerequisite.json'
    owned_daemon.publish(prerequisite,dict(worker_image=image,worker_context_sha256='e'*64,worker_source_commit='d'*40,schema='mldsafail.v060-native-prerequisites.v1',supervisor_source_sha256='a'*64,native_faults_passed=True,native_pairs_passed=True,supervisor_review_passed=True,auditor_review_passed=True,evidence_refs=['native-packet']))
    image='sha256:'+'c'*64
    cohort=Cohort('0.6.0','fresh','a'*64,'fresh',image,'b'*64,'cgroup-v2-usage-usec')
    prepare_epoch(tmp_path/'epoch',cohort,worker_artifact=dict(benchmark_version='0.6.0',measurement_method=cohort.measurement_method,image=image,source_commit='d'*40,source_context_sha256='e'*64))
    authority=CandidateRehearsalAuthority(prerequisite,tmp_path/'epoch/manifest.json','d'*40,'a'*64,image,cohort.epoch_id,cohort.public_id)
    authority.require()
    with pytest.raises(ValueError,match='scope'):authority.require_private(False)
    with pytest.raises(ValueError,match='scope'):RegisteredBackend(cohort,lambda job:job,authority)
    registry=VersionRegistry([RegisteredBackend(cohort,lambda job:job,authority,private_rehearsal=True)])
    config=dict(BENCHMARK_VERSION='0.5.0',BENCHMARK_VERSION_REGISTRY=registry,TESTING=False,V060_PRIVATE_CANDIDATE_REHEARSAL=True)
    with pytest.raises(UnsupportedBenchmark,match='scope'):application_cohort(config,'0.6.0')
    config['TESTING']=True
    assert application_cohort(config,'0.6.0')[0]=='0.6.0'
    config.update(BENCHMARK_VERSION='0.6.0',V060_DEFAULT_APPROVED=True)
    with pytest.raises(UnsupportedBenchmark,match='scope'):application_cohort(config)
    from dataclasses import replace
    for swapped in (replace(authority,worker_image='sha256:'+'f'*64),replace(authority,source_commit='f'*40),replace(authority,epoch_id='other')):
        with pytest.raises(ValueError,match='mismatch'):swapped.require()


def test_environment_restoration_attempts_remaining_aliases_after_failure(monkeypatch):
    class Environment(dict):
        def __setitem__(self,key,value):
            if key=='fails':raise OSError('restore failure')
            super().__setitem__(key,value)
    environment=Environment()
    monkeypatch.setattr(native_acceptance.os,'environ',environment)
    errors=native_acceptance.restore_environment({'fails':'value','later':'restored','absent':None})
    assert len(errors)==1 and environment['later']=='restored' and 'absent' not in environment


def test_partial_application_startup_disposes_engine_and_unstarted_server():
    from types import SimpleNamespace
    import threading
    calls=[]
    engine=SimpleNamespace(dispose=lambda:calls.append('engine'))
    server=SimpleNamespace(server_close=lambda:calls.append('server'))
    thread=threading.Thread(target=lambda:None,daemon=True)
    assert native_acceptance.cleanup_application_resources(engine,server,thread)==[]
    assert calls==['server','engine']


def test_failed_application_cleanup_retains_failure_instead_of_behavior_pass(tmp_path):
    from types import SimpleNamespace
    calls=[]
    def close():calls.append('server');raise OSError('socket close')
    errors=native_acceptance.cleanup_application_resources(SimpleNamespace(dispose=lambda:calls.append('engine')),SimpleNamespace(server_close=close),None)
    assert calls==['server','engine']
    with pytest.raises(RuntimeError,match='cleanup failed'):
        native_acceptance.finalize_application(tmp_path,{'behavior_passed':True},None,errors)
    result=owned_daemon.read_private_json(tmp_path/'application.json')
    assert result['behavior_passed'] is True and result['passed'] is False and result['cleanup_complete'] is False


def test_failed_application_publication_preserves_original(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_daemon,'publish',lambda *a,**kw:(_ for _ in ()).throw(OSError('publication')))
    original=RuntimeError('setup original')
    native_acceptance.finalize_application(tmp_path,{},original,[])
    assert 'publication' in original.__notes__[0]


def test_publication_after_rename_failure_retries_negative_disposition(tmp_path,monkeypatch):
    actual=owned_daemon.publish
    calls=[]
    def publish(path,value):
        actual(path,value);calls.append(value['passed'])
        if len(calls)==1:raise OSError('directory fsync failed after rename')
    monkeypatch.setattr(owned_daemon,'publish',publish)
    with pytest.raises(RuntimeError,match='Application cleanup failed'):
        native_acceptance.finalize_application(tmp_path,{'behavior_passed':True},None,[])
    retained=json.loads((tmp_path/'application.json').read_text())
    assert calls==[True,False]
    assert retained['passed'] is False and retained['evidence_publication_failed'] is True


@pytest.mark.parametrize('field,replacement',[('worker_image','sha256:'+'f'*64),('worker_context_sha256','f'*64),('worker_source_commit','f'*40)])
def test_native_prerequisite_never_authorizes_another_worker_artifact(tmp_path,field,replacement):
    expected=dict(supervisor_source_sha256='a'*64,worker_image='sha256:'+'b'*64,worker_context_sha256='c'*64,worker_source_commit='d'*40)
    receipt=dict(expected,schema='mldsafail.v060-native-prerequisites.v1',native_faults_passed=True,native_pairs_passed=True,supervisor_review_passed=True,auditor_review_passed=True,evidence_refs=['actual-source-bound-native-packet'])
    path=tmp_path/'prerequisites';owned_daemon.publish(path,dict(receipt,**{field:replacement}))
    with pytest.raises(RuntimeError):native_acceptance.require_prerequisites(path,**expected)
    missing=dict(receipt);missing.pop(field);owned_daemon.publish(path,missing)
    with pytest.raises(RuntimeError):native_acceptance.require_prerequisites(path,**expected)
