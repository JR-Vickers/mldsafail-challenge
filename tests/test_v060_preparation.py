"""Protocol/compatibility tests only; they establish no native acceptance."""
from dataclasses import asdict, replace
import json
import pytest
from research.mlwe_v060_preparation.contracts import (
    Cohort, IntegrationGates, UnsupportedBenchmark, cohort_records, participant_result, select_version)
from research.mlwe_v060_preparation.epochs import prepare_epoch, private_cases
from research.mlwe_v060_preparation.references import reference_costs


@pytest.fixture
def cohort():
    return Cohort('0.6.0', 'fresh-v060-epoch', 'a'*64, 'held-out-v060', 'cpu-cgroup-v060',
                  'b'*64, 'cgroup-v2-usage-usec')


def test_version_selection_preserves_existing_defaults_and_requires_all_gates():
    for default in ('0.4.0', '0.5.0'):
        assert select_version(None, current_default=default, enabled_versions={default}) == default
    gates = IntegrationGates(True, True, True, True, True)
    for missing in asdict(gates):
        with pytest.raises(UnsupportedBenchmark, match=missing):
            select_version('0.6.0', current_default='0.5.0', enabled_versions={'0.5.0','0.6.0'},
                           gates=replace(gates, **{missing: False}))
    assert select_version('0.6.0', current_default='0.5.0', enabled_versions={'0.6.0'}, gates=gates) == '0.6.0'
    for value in ('0.7.0', 0.6, '', False):
        with pytest.raises(UnsupportedBenchmark):
            select_version(value, current_default='0.5.0', enabled_versions={'0.5.0'})
    assert UnsupportedBenchmark.code == 'unsupported_benchmark' and UnsupportedBenchmark.status == 422


def test_cohorts_never_mix_versions_epochs_hosts_workers_or_unverified_results(cohort):
    accepted = dict(asdict(cohort), verified=True, eligible=True, submission_id='accepted', score=1.)
    rejected = [dict(accepted, **{name: 'other'}) for name in asdict(cohort)]
    rejected.extend((dict(accepted, eligible=False), dict(accepted, verified=False)))
    assert cohort_records([accepted, *rejected], cohort) == [accepted]
    public = participant_result(dict(accepted, nonce='secret', seed=123, evidence_path='/private/host'), cohort)
    assert set(public) == {'submission_id','benchmark_version','cohort_id','eligible','verified','score'}
    assert 'secret' not in json.dumps(public) and '/private' not in json.dumps(public)
    with pytest.raises(ValueError): participant_result(dict(accepted, score=float('nan')), cohort)
    with pytest.raises(ValueError): replace(cohort, benchmark_version='0.5.0')


def test_epoch_draft_is_fresh_tiny_private_and_has_no_reused_costs(tmp_path, cohort):
    artifact = dict(benchmark_version='0.6.0', measurement_method=cohort.measurement_method, image='sha256:'+'c'*64)
    first = prepare_epoch(tmp_path / 'first', cohort, worker_artifact=artifact)
    second = prepare_epoch(tmp_path / 'second', replace(cohort, epoch_id='another-fresh-epoch'), worker_artifact=artifact)
    assert first['ready'] is False and first['reference_costs_available'] is False
    assert len(first['cases']) == 100
    assert {row['seed'] for row in first['cases']}.isdisjoint({row['seed'] for row in second['cases']})
    assert (tmp_path / 'first').stat().st_mode & 0o777 == 0o700
    assert (tmp_path / 'first/secret.json').stat().st_mode & 0o777 == 0o600
    assert not (tmp_path / 'first/reference-costs.json').exists()
    with pytest.raises(FileExistsError): prepare_epoch(tmp_path / 'first', cohort, worker_artifact=artifact)
    with pytest.raises(ValueError, match='reused'):
        prepare_epoch(tmp_path / 'reused', cohort, worker_artifact=artifact, forbidden_epoch_ids={cohort.epoch_id})
    with pytest.raises(ValueError): prepare_epoch(tmp_path / 'v050', cohort, worker_artifact=dict(artifact, benchmark_version='0.5.0'))
    grid = private_cases('0'*64)
    assert len(grid) == 100 and len({row['instance_id'] for row in grid}) == 100
    for profile in ('small','medium'):
        assert {row['seed'] for row in grid if row['profile']==profile and row['eta']==1} == {
            row['seed'] for row in grid if row['profile']==profile and row['eta']==2}


def test_reference_contract_rejects_legacy_seconds_and_cross_cohort_costs(cohort):
    table = dict(schema='mldsafail.mlwe-v060-reference.v1', benchmark_version='0.6.0',
                 measurement_method=cohort.measurement_method, units='microseconds', cohort_id=cohort.public_id,
                 epoch_id=cohort.epoch_id, epoch_manifest_sha256='d'*64, reference_source_commit='e'*40,
                 worker_image='sha256:'+'c'*64, audit_receipt_sha256='f'*64, costs_usec={'case':123})
    assert reference_costs(table, cohort, case_ids=['case'], epoch_manifest_sha256='d'*64, reference_source_commit='e'*40, worker_image='sha256:'+'c'*64, audit_receipt_sha256='f'*64) == {'case':123}
    for changed in (dict(table, benchmark_version='0.5.0'), dict(table, units='seconds'),
                    dict(table, epoch_id='old-epoch'), dict(table, reference_source_commit='a'*40),
                    dict(table, worker_image='sha256:'+'a'*64), dict(table, audit_receipt_sha256='a'*64), dict(table, costs_usec={'case':float('inf')}),
                    dict(table, costs_usec={'case':0}), {'case':.01}):
        with pytest.raises(ValueError): reference_costs(changed, cohort, case_ids=['case'], epoch_manifest_sha256='d'*64, reference_source_commit='e'*40, worker_image='sha256:'+'c'*64, audit_receipt_sha256='f'*64)


def test_dispatch_registry_has_no_v050_fallback_or_mislabeled_result(cohort):
    from mldsafail.benchmark_versions import RegisteredBackend, VersionRegistry
    v050 = replace(cohort, benchmark_version='0.5.0', measurement_method='frozen-complete-worker-cpu')
    called = []
    registry = VersionRegistry([RegisteredBackend(v050, lambda job: called.append(job))])
    with pytest.raises(UnsupportedBenchmark): registry.evaluate('0.6.0', {'benchmark_version':'0.6.0'})
    assert called == []
    gates = IntegrationGates(True, True, True, True, True)
    registry = VersionRegistry([RegisteredBackend(cohort, lambda job: asdict(cohort), gates)])
    assert registry.evaluate('0.6.0', asdict(cohort))['benchmark_version'] == '0.6.0'
    with pytest.raises(ValueError, match='mismatch'): registry.evaluate('0.6.0', {'benchmark_version':'0.5.0'})
    wrong = VersionRegistry([RegisteredBackend(cohort, lambda job: {'benchmark_version':'0.5.0'}, gates)])
    with pytest.raises(ValueError, match='different'): wrong.evaluate('0.6.0', asdict(cohort))
    with pytest.raises(ValueError, match='cohort'): registry.evaluate('0.6.0', dict(asdict(cohort), epoch_id='other'))


def test_api_and_cli_keep_defaults_and_select_v060_only_with_registration(tmp_path, cohort):
    from mldsafail.benchmark_versions import RegisteredBackend, VersionRegistry
    from mldsafail.cli import build_parser
    from mldsafail.web.app import create_app
    from mldsafail.web.db import get_session
    from mldsafail.web.models import Base, User
    from mldsafail.web.services import create_api_token
    app = create_app(config_name='test', config={'DATABASE_URL': f'sqlite:///{tmp_path / "app.db"}',
                     'BENCHMARK_VERSION':'0.5.0','MLWE_EPOCH_ID':'frozen-v050-epoch',
                     'EVALUATOR_FINGERPRINT':'c'*64,'HIDDEN_SUITE_VERSION':'v050','WORKER_CLASS':'frozen-worker'})
    with pytest.raises(UnsupportedBenchmark, match='owner decision'):
        create_app(config_name='test', config={'BENCHMARK_VERSION':'0.6.0'})
    Base.metadata.create_all(app.extensions['mldsafail_engine'])
    with app.app_context():
        database = get_session()
        user = User(display_name='Protocol test')
        database.add(user); database.commit()
        _, token = create_api_token(database, user, 'test')
        user_id = user.id
    client = app.test_client()
    headers = {'Authorization':f'Bearer {token}', 'Idempotency-Key':'v060-case'}
    payload = dict(repository_url='https://github.com/example/solver', commit_sha='a'*40,
                   hypothesis='protocol-only test', benchmark_version='0.6.0', solver_path='solver')
    assert client.post('/api/v1/submissions', json=payload, headers=headers).status_code == 422
    assert client.get('/api/v1/leaderboard?benchmark_version=0.6.0', headers=headers).status_code == 422
    gates = IntegrationGates(True, True, True, True, True)
    app.config['BENCHMARK_VERSION_REGISTRY'] = VersionRegistry([
        RegisteredBackend(cohort, lambda job: asdict(cohort), gates)])
    response = client.post('/api/v1/submissions', json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json['submission']['benchmark_version'] == '0.6.0'
    assert response.json['submission']['epoch_id'] == cohort.epoch_id
    assert client.post('/api/v1/submissions', json=payload, headers=headers).status_code == 200
    assert client.post('/api/v1/submissions', json={**payload, 'benchmark_version':'0.5.0'}, headers=headers).status_code == 409
    assert client.get('/api/v1/leaderboard', headers=headers).json['benchmark_version'] == '0.5.0'
    assert client.get('/api/v1/leaderboard?benchmark_version=0.6.0', headers=headers).json['benchmark_version'] == '0.6.0'
    assert client.post('/api/v1/submissions', json={**payload, 'benchmark_version':None}, headers=headers).status_code == 422
    from mldsafail.web.models import ExperimentResult, Submission
    with app.app_context():
        database = get_session()
        accepted = database.get(Submission, response.json['submission']['id'])
        accepted.state = 'accepted'
        identities = dict(epoch_id=cohort.epoch_id, evaluator_fingerprint=cohort.evaluator_fingerprint,
                          hidden_suite_version=cohort.hidden_suite_version, worker_class=cohort.worker_class,
                          benchmark_version='0.6.0', verified=True)
        records = [(accepted, identities)]
        variants = [dict(identities, **{field:'different'}) for field in
                    ('epoch_id','evaluator_fingerprint','hidden_suite_version','worker_class')]
        variants.append(dict(identities, verified=False))
        for variant in variants:
            submission = Submission(user_id=user_id, repository_url=payload['repository_url'],
                commit_sha='b'*40, hypothesis='Synthetic cohort-filter test', benchmark_version='0.6.0', state='accepted')
            database.add(submission); database.flush()
            records.append((submission, variant))
        for submission, identity in records:
            database.add(ExperimentResult(submission_id=submission.id, user_id=user_id, score=None,
                         mlwe_score=1., source_digest='f'*64, **identity))
        database.commit()
    ranked = client.get('/api/v1/leaderboard?benchmark_version=0.6.0', headers=headers).json['leaderboard']
    assert len(ranked) == 1 and ranked[0]['score'] == 1.
    assert ranked[0]['record']['benchmark_version'] == '0.6.0'
    assert ranked[0]['record']['schema_version'] == 'hosted-mlwe-v060-1'
    assert client.get('/api/v1/leaderboard', headers=headers).json['leaderboard'] == []
    parser = build_parser()
    assert parser.parse_args(['clone']).benchmark_version == '0.5.0'
    assert parser.parse_args(['clone','--benchmark-version','0.6.0']).benchmark_version == '0.6.0'
    from mldsafail.benchmark_versions import application_cohort
    with pytest.raises(UnsupportedBenchmark, match='owner decision'):
        application_cohort(dict(app.config, BENCHMARK_VERSION='0.6.0'))
