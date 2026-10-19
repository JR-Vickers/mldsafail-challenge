from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts import production_diagnostic as diagnostic
from scripts import production_diagnostic_fixture as fixture
from mldsafail.web.models import Base, ApiToken, User, EvaluationJob
from mldsafail.web.services import verify_api_token


def test_public_workload_is_exact_repository_order():
    from mldsafail.development import public_cases
    assert diagnostic.public_workload() == public_cases()
    assert len(diagnostic.public_workload()) == 50


def test_allowance_charges_setup_and_reserves_cleanup():
    now = [100.0]
    allowance = diagnostic.Allowance(100, 3000, 900, clock=lambda: now[0])
    allowance.admit(2100)
    now[0] += 1
    with pytest.raises(TimeoutError): allowance.admit(2100)
    now[0] = 2200
    with pytest.raises(TimeoutError): allowance.admit(1)
    now[0] = 99
    with pytest.raises(TimeoutError): allowance.admit(1)
    with pytest.raises(ValueError): allowance.admit(float('nan'))


def test_ledger_retains_debit_and_fences_retries():
    ledger = dict(initial_debit_seconds=900, preflight=dict(complete=True, charged_seconds=300), generations=[])
    assert diagnostic.validate_ledger(ledger, 'baseline') == 1200
    baseline = dict(generation='baseline', charged_seconds=3000, complete=True, cleanup_verified=True)
    ledger['generations'].append(baseline)
    assert diagnostic.validate_ledger(ledger, 'post-fix') == 4200
    with pytest.raises(ValueError): diagnostic.validate_ledger(ledger, 'baseline')
    baseline['cleanup_verified'] = False
    with pytest.raises(ValueError): diagnostic.validate_ledger(ledger, 'post-fix')
    baseline['cleanup_verified'] = True
    baseline['charged_seconds'] = 3001
    with pytest.raises(ValueError): diagnostic.validate_ledger(ledger, 'post-fix')
    ledger['initial_debit_seconds'] = 0
    with pytest.raises(ValueError): diagnostic.validate_ledger(ledger, 'baseline')


@pytest.fixture
def database():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_canonical_restore_preserves_token_hash_ids_times_and_lease(database):
    now = datetime.now(timezone.utc)
    encoded, metadata = fixture.create(database, now=now)
    token = json.loads(encoded)['token']
    before = fixture._snapshot(database)
    assert verify_api_token(database, token, 'submission:read')
    assert fixture._snapshot(database) != before  # last_used_at must be reset
    assert fixture.restore(database, encoded, metadata, now=now, required_until=now + timedelta(hours=2)) == token
    assert fixture._snapshot(database) == before
    assert database.scalar(select(EvaluationJob)).lease_expires_at.replace(tzinfo=timezone.utc) == now + timedelta(hours=24)
    assert database.scalar(select(ApiToken)).scopes == ['submission:write', 'submission:read']
    assert verify_api_token(database, token, 'not-a-scope') is None
    stored = database.scalar(select(ApiToken))
    stored.revoked_at = now
    database.commit()
    assert verify_api_token(database, token, 'submission:read') is None
    fixture.restore(database, encoded, metadata, now=now)
    assert verify_api_token(database, token, 'submission:read')


def test_fixture_refuses_expiry_and_changes(database):
    now = datetime.now(timezone.utc)
    encoded, metadata = fixture.create(database, now=now)
    with pytest.raises(ValueError, match='expiry'):
        fixture.restore(database, encoded, metadata, now=now + timedelta(hours=24))
    with pytest.raises(ValueError, match='bytes'):
        fixture.restore(database, encoded + b' ', metadata)
    with pytest.raises(ValueError, match='empty'):
        fixture.create(database)


def test_timing_wrapper_preserves_args_returns_and_exceptions():
    from scripts.production_diagnostic_instrumentation import _CURRENT, timed
    rows = dict(hash_seconds=0.)
    marker = _CURRENT.set(rows)
    try:
        value = object()
        assert timed(lambda arg: arg, 'hash_seconds')(value) is value
        def fail(): raise RuntimeError('sensitive')
        with pytest.raises(RuntimeError, match='sensitive'):
            timed(fail, 'hash_seconds')()
        assert rows['hash_seconds'] > 0
        assert set(rows) == {'hash_seconds'}
    finally:
        _CURRENT.reset(marker)
    with pytest.raises(ValueError): timed(lambda: None, 'sql_parameters')


def test_fixture_rejects_self_consistent_wrong_epoch_and_rolls_back(database):
    from mldsafail.web.models import RateLimitState
    encoded, metadata = fixture.create(database)
    document = json.loads(encoded)
    document['rows']['submissions'][0]['epoch_id'] = 'forbidden'
    metadata['identity_sha256'] = diagnostic.digest(document['rows'])
    altered = json.dumps(document, sort_keys=True, separators=(',', ':')).encode()
    import hashlib
    metadata['dump_sha256'] = hashlib.sha256(altered).hexdigest()
    before = fixture._snapshot(database)
    with pytest.raises(ValueError, match='Synthetic-only'):
        fixture.restore(database, altered, metadata)
    assert fixture._snapshot(database) == before


def test_server_instrumentation_authentication_and_sanitization(database, monkeypatch):
    from mldsafail.web.app import create_app
    from mldsafail.web import services, api
    from scripts.production_diagnostic_instrumentation import install, TIMINGS
    # Restore module aliases at teardown; instrumentation is process-local.
    monkeypatch.setattr(services, 'password_hasher', services.password_hasher)
    monkeypatch.setattr(services, 'verify_api_token', services.verify_api_token)
    monkeypatch.setattr(api, 'verify_api_token', api.verify_api_token)
    encoded, metadata = fixture.create(database)
    token = json.loads(encoded)['token']
    rows, errors = [], []
    apps = []
    for _ in range(2):
        app = create_app(config_name='test', config={'DATABASE_URL': 'sqlite://'})
        engine = app.extensions['mldsafail_engine']
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            fixture.restore(session, encoded, metadata)
        install(app, rows.append, errors.append)
        apps.append(app)
    wrapper = services.verify_api_token
    assert getattr(wrapper, '_diagnostic_wrapped') is True
    for app in apps:
        client = app.test_client()
        assert client.get('/api/v1/me', headers={'Authorization': 'Bearer ' + token}).status_code == 200
        assert client.get('/api/v1/me', headers={'Authorization': 'Bearer mldsa_0000000000_' + 'a'*43}).status_code == 401
        assert client.get('/api/v1/me', headers={'Authorization': 'Bearer ' + token[:-1] + ('A' if token[-1] != 'A' else 'B')}).status_code == 401
    assert services.verify_api_token is wrapper
    assert len(rows) == 6 and not errors
    assert all(row['hash_seconds'] > 0 and row['query_seconds'] > 0 for row in rows)
    assert all(set(row) == TIMINGS | {'request_id', 'route', 'status', 'seconds'} for row in rows)
    assert token not in json.dumps(rows) and 'Authorization' not in json.dumps(rows)


def test_server_evidence_failure_leaves_response_and_marks_investigation(monkeypatch):
    from mldsafail.web.app import create_app
    from mldsafail.web import services, api
    from scripts.production_diagnostic_instrumentation import install
    monkeypatch.setattr(services, 'password_hasher', services.password_hasher)
    monkeypatch.setattr(services, 'verify_api_token', services.verify_api_token)
    monkeypatch.setattr(api, 'verify_api_token', api.verify_api_token)
    app = create_app(config_name='test', config={'DATABASE_URL': 'sqlite://'})
    errors = []
    def fail(_row): raise RuntimeError('secret')
    install(app, fail, errors.append)
    assert app.test_client().get('/health/ready').status_code == 200
    assert app.extensions['diagnostic_evidence_failed'] is True
    assert errors == ['evidence_publication_failed']


def test_http_comparison_alternates_and_sanitizes():
    from scripts.production_diagnostic_probes import request_comparison
    calls, snapshots = [], []
    def opener(request, timeout):
        calls.append((request.full_url, request.has_header('Authorization'), timeout))
        raise TimeoutError('sensitive-token')
    result = request_comparison('http://127.0.0.1:1234', 'sensitive-token', lambda: True,
        snapshots.append, request_open=opener, duration=.2, count=4, read_only_health=True)
    assert result['complete'] and result['termination_complete']
    assert len(result['requests']) == 4
    assert [row[1] for row in calls] == [False, True, False, True]
    assert all(row[2] == 2 for row in calls)
    assert 'sensitive-token' not in json.dumps(result)
    assert all(row['failed'] for row in result['requests'])
    assert any(row['incomplete'] for row in snapshots[0] if 'incomplete' in row)


def test_failed_initial_observation_prevents_http_dispatch():
    from scripts.production_diagnostic_probes import request_comparison
    def forbidden(*args, **kwargs): raise AssertionError('dispatched')
    result = request_comparison('http://127.0.0.1', 'unused', lambda: False,
        lambda rows: None, request_open=forbidden, duration=.1, count=2, read_only_health=True)
    assert not result['complete'] and not result['observation_valid']
    assert result['undispatched_requests'] == 2 and not result['requests']


@pytest.fixture
def frozen_protocol():
    cases = diagnostic.public_workload()
    protocol = dict(schema=diagnostic.SCHEMA, benchmark_version='0.5.0', worker_image=diagnostic.WORKER,
        private_epoch=False, private_acceptance=False, ranking=False, delivery=False,
        additional_spending=0, initial_debit_seconds=900, preflight_seconds=300,
        generation_seconds=3000, cleanup_reserve_seconds=900, aggregate_seconds=7200,
        http_comparison_requests=120, http_comparison_seconds=60, request_threads=10,
        request_timeout_seconds=2, legacy_seconds=60, legacy_outer_seconds=600,
        final_anonymous_requests=1500, final_authenticated_requests=60, final_seconds=300,
        monitor_invocations_per_condition=3, monitor_command_timeout_seconds=10,
        generation='baseline', public_cases=cases, workload_sha256=diagnostic.digest(cases),
        images={name: diagnostic.WORKER if name == 'worker' else 'sha256:'+'a'*64
                for name in ('web', 'worker', 'coordinator', 'postgres', 'caddy')},
        archives={name: 'b'*64 for name in ('web', 'worker', 'coordinator', 'postgres', 'caddy')})
    for field in ('source_sha256', 'configuration_sha256', 'instrumentation_sha256',
                  'legacy_source_sha256', 'cleanup_protocol_sha256', 'fixture_sha256'):
        protocol[field] = 'c'*64
    return protocol


@pytest.mark.parametrize('key,value', [
    ('private_epoch', True), ('delivery', True), ('additional_spending', 1),
    ('initial_debit_seconds', 0), ('generation_seconds', 3600),
    ('cleanup_reserve_seconds', 899), ('http_comparison_requests', 20),
    ('request_threads', 11), ('request_timeout_seconds', 3), ('legacy_outer_seconds', 601),
    ('final_anonymous_requests', 1499), ('final_authenticated_requests', 59),
    ('monitor_command_timeout_seconds', 11), ('generation', 'third'),
    ('http_comparison_seconds', True),
])
def test_protocol_rejects_stale_draft_and_relaxed_limits(frozen_protocol, key, value):
    diagnostic.validate_protocol(frozen_protocol)
    frozen_protocol[key] = value
    with pytest.raises(ValueError): diagnostic.validate_protocol(frozen_protocol)


def test_protocol_rejects_reordered_and_missing_cases(frozen_protocol):
    frozen_protocol['public_cases'] = list(reversed(frozen_protocol['public_cases']))
    frozen_protocol['workload_sha256'] = diagnostic.digest(frozen_protocol['public_cases'])
    with pytest.raises(ValueError): diagnostic.validate_protocol(frozen_protocol)


def test_legacy_loader_executes_checked_source_not_stale_bytecode(tmp_path):
    from scripts.production_diagnostic_probes import legacy_module
    import hashlib
    path = tmp_path/'legacy.py'
    path.write_text('IDENTITY = "actual checked source"\n')
    identity = hashlib.sha256(path.read_bytes()).hexdigest()
    assert legacy_module(path, identity).IDENTITY == 'actual checked source'
    path.write_text('IDENTITY = "changed"\n')
    with pytest.raises(ValueError): legacy_module(path, identity)
    link = tmp_path/'link.py'
    link.symlink_to(path)
    with pytest.raises(ValueError): legacy_module(link, hashlib.sha256(path.read_bytes()).hexdigest())


def test_http_evidence_failure_invalidates_and_stops_dispatch():
    from scripts.production_diagnostic_probes import request_comparison
    def fail(_rows): raise OSError('private pathname')
    result = request_comparison('http://127.0.0.1:1234', 'unused', lambda: True,
        fail, duration=.1, count=2, read_only_health=True)
    assert not result['complete'] and not result['evidence_complete']
    assert len(result['requests']) == 1 and result['requests'][0]['incomplete']
    assert 'private pathname' not in json.dumps(result)


def test_exact_legacy_source_instrumentation(tmp_path, monkeypatch):
    import hashlib
    import subprocess
    from scripts.production_diagnostic_probes import legacy_experiment
    from scripts import production_diagnostic_probes as probes
    source = subprocess.check_output(['git', 'show', '69cbd61:scripts/staging_read_load.py'])
    path = tmp_path/'legacy.py'
    path.write_bytes(source)
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b'{}'
    monkeypatch.setattr(probes.urllib.request, 'urlopen', lambda request, timeout: Response())
    snapshots = []
    result = legacy_experiment(path, hashlib.sha256(source).hexdigest(),
        'http://127.0.0.1:1234', 'synthetic-secret', lambda: True, snapshots.append, duration=.2)
    assert result['instrumentation_complete']
    rows = snapshots[-1]['requests']
    assert len(rows) == 2 and all(not row['incomplete'] for row in rows)
    assert all(row['http_finished_after_seconds'] >= row['http_started_after_seconds'] for row in rows)
    assert all(row['scheduled_after_seconds'] == 0 for row in rows)
    assert all(row['queue_delay_seconds'] >= 0 for row in rows)
    assert snapshots[-1]['observations']
    assert 'synthetic-secret' not in json.dumps(snapshots)


def test_slow_intent_publication_cannot_admit_late_http():
    import time
    from scripts.production_diagnostic_probes import request_comparison
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError('Late HTTP dispatch')
    result = request_comparison('http://127.0.0.1', 'unused', lambda: True,
        lambda rows: time.sleep(.15), request_open=forbidden, duration=.4, count=2, read_only_health=True)
    assert not result['complete'] and not result['pacing_valid']
    assert not calls and result['undispatched_requests'] == 2
    assert 'dispatched_after_seconds' not in result['requests'][0]


def test_restore_refuses_unowned_user_and_preserves_rows(database):
    encoded, metadata = fixture.create(database)
    database.add(User(display_name='unrelated owner'))
    database.commit()
    before = fixture._snapshot(database)
    with pytest.raises(ValueError, match='unowned'):
        fixture.restore(database, encoded, metadata)
    assert fixture._snapshot(database) == before


def test_restore_clears_authenticated_read_rate_state(database):
    from mldsafail.web.models import RateLimitState
    encoded, metadata = fixture.create(database)
    database.add(RateLimitState(bucket='authentication:127.0.0.1', count=60))
    database.commit()
    assert fixture._snapshot(database)['rate_limit_states']
    fixture.restore(database, encoded, metadata)
    assert fixture._snapshot(database)['rate_limit_states'] == []


def test_request_comparison_requires_reviewed_read_only_observer():
    from scripts.production_diagnostic_probes import request_comparison
    def forbidden(): raise AssertionError('Observer started without review')
    with pytest.raises(ValueError, match='Read-only'):
        request_comparison('http://127.0.0.1', 'unused', forbidden, lambda rows: None)
