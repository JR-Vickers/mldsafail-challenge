import pytest
from mldsafail.benchmark_versions import IntegrationGates
from mldsafail.benchmark_v060.backend import HostBackend
from mldsafail.benchmark_v060.envelope import SCHEMA, sign, verify


def test_version_specific_authentication_and_tampering():
    key = b'x'*32
    payload = dict(schema=SCHEMA, benchmark_version='0.6.0', cohort_id='cohort', source_sha256='a'*64)
    envelope = sign(payload, key)
    assert verify(envelope, key, cohort_id='cohort', source_sha256='a'*64) == payload
    with pytest.raises(ValueError): verify(envelope, key, cohort_id='other', source_sha256='a'*64)
    envelope['payload'] = dict(payload, score=99)
    with pytest.raises(ValueError): verify(envelope, key, cohort_id='cohort', source_sha256='a'*64)
    with pytest.raises(ValueError): sign(dict(payload, benchmark_version='0.5.0'), key)


def test_host_case_four_invocations_and_no_infrastructure_replacement(monkeypatch, tmp_path):
    from mldsafail.benchmark_v060 import backend
    calls, audited = [], []
    def invocation(*args, **kwargs):
        calls.append(kwargs)
        return {'generation': str(len(calls))}
    monkeypatch.setattr(backend.harness, 'run', invocation)
    monkeypatch.setattr(backend.audit, 'audit_journal', lambda directory, generation: audited.append(generation))
    monkeypatch.setattr(backend.audit, 'case_cost', lambda records: {'generations': [r['generation'] for r in records]})
    gates = IntegrationGates(True, True, True, True, True)
    host = HostBackend(image='sha256:'+'a'*64, parent=tmp_path, cgroup_parent='test', epoch_id='new', gates=gates)
    result = host.evaluate_case(tmp_path, {}, lambda value: True)
    assert result['decision']['generations'] == ['2','3','4']
    assert audited == ['1','2','3','4'] and all(call['timeout']==60 for call in calls)
    def failed(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError('counter invalid')
    monkeypatch.setattr(backend.harness, 'run', failed)
    with pytest.raises(RuntimeError, match='counter invalid'): host.evaluate_case(tmp_path, {}, lambda value: True)
    assert len(calls) == 5
    with pytest.raises(ValueError): HostBackend(image='x', parent=tmp_path, cgroup_parent='test', epoch_id='new', gates=IntegrationGates())


def test_signed_case_rechecks_durable_binding_and_caller_record(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    from research.cpu_measurement import audit
    from mldsafail.benchmark_v060.envelope import independently_audited_case
    cohort = SimpleNamespace(epoch_id='fresh', public_id='cohort')
    binding = dict(source_sha256='a'*64, image='sha256:'+'b'*64,
                   supervisor_source_sha256='c'*64, epoch='fresh')
    records = [dict(generation=str(i), binding=binding) for i in range(3)]
    for record in records:
        (tmp_path / (record['generation']+'.json')).write_text(json.dumps(record))
    audited = []
    monkeypatch.setattr(audit, 'audit_journal', lambda directory, generation: audited.append(generation))
    monkeypatch.setattr(audit, 'case_cost', lambda values: {'eligible':True,'cost_usec':123})
    kwargs = dict(directory=tmp_path, cohort=cohort, source_sha256='a'*64,
                  worker_image='sha256:'+'b'*64, supervisor_source_sha256='c'*64)
    payload = independently_audited_case(records, **kwargs)
    assert payload['decision']['cost_usec'] == 123 and audited == ['0','1','2']
    assert len(payload['evidence_sha256']) == 3
    with pytest.raises(ValueError, match='binding'):
        independently_audited_case(records, **dict(kwargs, worker_image='sha256:'+'d'*64))
    with pytest.raises(ValueError, match='Caller record'):
        independently_audited_case([dict(records[0], forged=True), *records[1:]], **kwargs)


def test_complete_cohort_infra_failure_never_signs_or_retries(monkeypatch):
    from types import SimpleNamespace
    from mldsafail.benchmark_v060 import evaluation
    from mldsafail.benchmark_v050.generator import generate_mlwe
    from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
    cases = [dict(case_id=f'{profile}-{eta}-{seed}', public_input=__import__('json').loads(__import__('json').dumps(generate_mlwe(profile, seed, eta).public.to_dict())))
             for profile, eta in CHALLENGE_CELLS for seed in range(20)]
    cohort = SimpleNamespace(benchmark_version='0.6.0', epoch_id='fresh', public_id='cohort')
    calls=[]
    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError('accounting failure')
    backend = SimpleNamespace(epoch_id='fresh', evaluate_case=fail)
    monkeypatch.setattr(evaluation, 'require_reference_authority', lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluation, 'reference_costs', lambda *args, **kwargs: {case['case_id']:1 for case in cases})
    kwargs = dict(backend=backend, source='source', source_sha256='a'*64,
                  supervisor_source_sha256='b'*64, cohort=cohort, cases=cases, references={},
                  epoch_manifest_sha256='c'*64, reference_source_commit='d'*40,
                  reference_worker_image='sha256:'+'e'*64, reference_audit_sha256='f'*64, signing_key=b'x'*32)
    with pytest.raises(RuntimeError, match='accounting failure'): evaluation.evaluate(**kwargs)
    assert calls == [1]
    with pytest.raises(ValueError, match='Repeated public instance'):
        evaluation.evaluate(**dict(kwargs, cases=[cases[0], *cases[:-1]]))
    assert calls == [1]
    backend.image = 'sha256:'+'e'*64
    backend.directory = 'private'
    def good(source, public, verifier, **kwargs):
        return {'records': [{'public_input':public}]*3}
    backend.evaluate_case = good
    monkeypatch.setattr(evaluation, 'independently_audited_case',
                        lambda *args, **kwargs: {'decision':{'eligible':True,'cost_usec':2}})
    from mldsafail.benchmark_v060.envelope import verify
    payload = verify(evaluation.evaluate(**kwargs), b'x'*32, cohort_id='cohort', source_sha256='a'*64)
    assert payload['verified'] is True and payload['score'] == pytest.approx(2) and len(payload['cases']) == 100
    monkeypatch.setattr(evaluation, 'independently_audited_case',
                        lambda *args, **kwargs: {'decision':{'eligible':False,'cost_usec':None}})
    payload = verify(evaluation.evaluate(**kwargs), b'x'*32, cohort_id='cohort', source_sha256='a'*64)
    assert payload['verified'] is False and payload['score'] is None


def test_separate_queue_consumer_cannot_select_historical_version(tmp_path):
    from types import SimpleNamespace
    from mldsafail.benchmark_v060.coordinator import Coordinator
    from sqlalchemy import create_engine
    from mldsafail.web.models import Base
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    gates = IntegrationGates(True,True,True,True,True)
    with pytest.raises(ValueError, match='only v060'):
        Coordinator(engine=engine, cohort=SimpleNamespace(benchmark_version='0.5.0'), gates=gates,
                    work_root=tmp_path, evaluate_source=lambda *args: {}, signing_key=b'x'*32)
    consumer = Coordinator(engine=engine, cohort=SimpleNamespace(benchmark_version='0.6.0'), gates=gates,
                            work_root=tmp_path, evaluate_source=lambda *args: {}, signing_key=b'x'*32)
    assert consumer.run_once() is False


def test_v060_queue_rejects_cross_cohort_without_touching_historical_job(tmp_path):
    from types import SimpleNamespace
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from mldsafail.web.models import Base, User, Submission, EvaluationJob, ExperimentResult
    from mldsafail.benchmark_v060.coordinator import Coordinator
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        user = User(display_name='A'); database.add(user); database.flush()
        jobs=[]
        for version in ('0.5.0','0.6.0'):
            submission = Submission(user_id=user.id, repository_url='https://github.com/a/b.git',
                            commit_sha='a'*40, hypothesis='h', benchmark_version=version, epoch_id='wrong')
            database.add(submission); database.flush()
            job=EvaluationJob(submission_id=submission.id); database.add(job); jobs.append(job)
        database.commit()
        ids=[job.id for job in jobs]
    cohort=SimpleNamespace(benchmark_version='0.6.0', epoch_id='fresh', evaluator_fingerprint='b'*64,
                           hidden_suite_version='fresh-suite', worker_class='v060')
    called=[]
    coordinator=Coordinator(engine=engine, cohort=cohort, gates=IntegrationGates(True,True,True,True,True),
                        work_root=tmp_path, evaluate_source=lambda *args: called.append(1), signing_key=b'x'*32)
    assert coordinator.run_once() is True
    with Session(engine) as database:
        assert database.get(EvaluationJob,ids[0]).status == 'queued'
        assert database.get(EvaluationJob,ids[1]).status == 'complete'
        assert list(database.scalars(select(ExperimentResult))) == []
    assert called == []


def test_v060_worker_emits_candidate_without_cooperative_counters(monkeypatch, capsys):
    import io
    import json
    from types import SimpleNamespace
    from mldsafail.benchmark_v060 import worker
    from mldsafail.benchmark_v050.generator import generate_mlwe
    public = generate_mlwe('small', 123, 1).public.to_dict()
    request = json.dumps({'instance':public,'solver':'contestant'}).encode()
    monkeypatch.setattr(worker,'limits',lambda:None)
    monkeypatch.setattr(worker.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(request)))
    monkeypatch.setattr(worker.importlib.util,'spec_from_file_location',lambda *args: SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None)))
    monkeypatch.setattr(worker.importlib.util,'module_from_spec',lambda spec:SimpleNamespace(solve=lambda instance:None))
    worker.main()
    assert json.loads(capsys.readouterr().out) == {'candidate':None}


def test_separate_worker_context_excludes_private_evaluator_and_generator(tmp_path):
    from mldsafail.benchmark_v060.build import prepare_context
    record = prepare_context(tmp_path/'context')
    assert record['native_verified'] is False and record['image'] is None
    assert 'mldsafail/benchmark_v060/worker.py' in record['files']
    assert not any(any(word in path for word in ('generator','epoch','coordinator','backend','envelope')) for path in record['files'])
    assert 'mldsafail.benchmark_v060.worker' in (tmp_path/'context/Dockerfile').read_text()
    with pytest.raises(ValueError): prepare_context(tmp_path/'context')


def test_fresh_reference_protocol_never_seals_and_rejects_viability_failure(monkeypatch):
    import json
    from types import SimpleNamespace
    from mldsafail.benchmark_v060 import references
    from mldsafail.benchmark_v050.generator import generate_mlwe
    from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
    cases=[dict(case_id=f'{p}-{e}-{s}',public_input=json.loads(json.dumps(generate_mlwe(p,s,e).public.to_dict())))
           for p,e in CHALLENGE_CELLS for s in range(20)]
    cohort=SimpleNamespace(benchmark_version='0.6.0',epoch_id='fresh',public_id='cohort')
    backend=SimpleNamespace(epoch_id='fresh',image='sha256:'+'a'*64,directory='private',
                evaluate_case=lambda source,public,*args,**kwargs:{'records':[{'public_input':public,'generation':str(number)} for number in range(3)]})
    monkeypatch.setattr(references,'independently_audited_case',lambda *args,**kwargs:
                        {'decision':{'eligible':True,'cost_usec':123,'penalized':False}})
    kwargs=dict(backend=backend,cohort=cohort,source='source',source_sha256='b'*64,
                supervisor_source_sha256='c'*64,reference_source_commit='d'*40,
                epoch_manifest_sha256='e'*64,cases=cases)
    prepared=references.prepare_references(**kwargs)
    assert len(prepared['table']['costs_usec']) == 100
    assert prepared['receipt']['ready'] is False and 'epoch_sealing' in prepared['receipt']['remaining_gates']
    assert prepared['table']['epoch_id']=='fresh' and prepared['table']['units']=='microseconds'
    monkeypatch.setattr(references,'independently_audited_case',lambda *args,**kwargs:
                        {'decision':{'eligible':True,'cost_usec':60_000_000,'penalized':True}})
    with pytest.raises(ValueError,match='viability floor'): references.prepare_references(**kwargs)
