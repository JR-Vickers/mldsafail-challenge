"""Canonical synthetic fixture serialization; never invokes an evaluator.

Call only against a separately owned diagnostic database. Restore refuses any
scientific/result rows and preserves the original token hash and timestamps.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json

from sqlalchemy import DateTime, func, select

from mldsafail.web.models import Base, User, Submission, EvaluationJob
from mldsafail.web.services import create_api_token
from scripts.production_diagnostic import digest, validate_fixture

TABLES = ('users', 'api_tokens', 'submissions', 'evaluation_jobs', 'audit_events', 'rate_limit_states')


def _assert_empty_elsewhere(session):
    for table in Base.metadata.sorted_tables:
        if table.name not in TABLES and session.scalar(select(func.count()).select_from(table)):
            raise ValueError('Nonfixture database state; restoration prohibited')


def _snapshot(session):
    rows = {}
    for name in TABLES:
        table = Base.metadata.tables[name]
        rows[name] = [{key: (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat() if isinstance(value, datetime) else value
                       for key, value in row.items()}
                      for row in session.execute(select(table).order_by(table.c.id)).mappings()]
    return rows


def create(session, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() != timedelta(0):
        raise ValueError('UTC creation time required')
    for table in Base.metadata.sorted_tables:
        if session.scalar(select(func.count()).select_from(table)):
            raise ValueError('Fresh empty diagnostic database required')
    user = User(display_name='synthetic-diagnostic', created_at=now, updated_at=now)
    session.add(user)
    session.flush()
    submission = Submission(user_id=user.id, repository_url='https://github.com/diagnostic/fixture',
        commit_sha='0' * 40, hypothesis='Synthetic diagnostic; dispatch disabled',
        benchmark_version='0.5.0', state='running', created_at=now, updated_at=now)
    session.add(submission)
    session.flush()
    expiry = now + timedelta(hours=24)
    session.add(EvaluationJob(submission_id=submission.id, status='running',
        lease_owner='synthetic-diagnostic', lease_expires_at=expiry))
    token, plaintext = create_api_token(session, user, 'synthetic-diagnostic', expires_at=expiry)
    # Normal creation/hash/scopes are preserved. Freeze one instant for expiry.
    token.created_at = now
    session.commit()
    rows = _snapshot(session)
    document = dict(schema='mldsafail.diagnostic-fixture-data.v1', rows=rows, token=plaintext)
    encoded = json.dumps(document, sort_keys=True, separators=(',', ':')).encode()
    metadata = dict(schema='mldsafail.diagnostic-fixture.v1', created_at=now.isoformat(),
        expires_at=expiry.isoformat(), dump_sha256=hashlib.sha256(encoded).hexdigest(), identity_sha256=digest(rows))
    _validate_rows(document, metadata)
    return encoded, metadata


def _validate_rows(data, metadata):
    from mldsafail.web.services import TOKEN_RE, password_hasher
    if set(data) != {'schema', 'rows', 'token'} or data['schema'] != 'mldsafail.diagnostic-fixture-data.v1' or set(data['rows']) != set(TABLES):
        raise ValueError('Exact canonical fixture required')
    rows = data['rows']
    if any(not isinstance(rows[name], list) or len(rows[name]) != (0 if name == 'rate_limit_states' else 1) for name in TABLES):
        raise ValueError('Exactly one synthetic fixture and no rate state required')
    user, token, submission, job, audit = [rows[name][0] for name in TABLES[:5]]
    if (user['display_name'] != 'synthetic-diagnostic' or user['is_admin'] is not False
            or token['user_id'] != user['id'] or submission['user_id'] != user['id']
            or job['submission_id'] != submission['id'] or audit['user_id'] != user['id']
            or token['scopes'] != ['submission:write', 'submission:read']
            or token['revoked_at'] is not None or token['last_used_at'] is not None
            or submission['state'] != 'running' or submission['benchmark_version'] != '0.5.0'
            or submission['repository_url'] != 'https://github.com/diagnostic/fixture'
            or submission['commit_sha'] != '0' * 40 or submission['cancel_requested'] is not False
            or any(submission[field] is not None for field in ('epoch_id', 'evaluator_fingerprint', 'hidden_suite_version', 'worker_class'))
            or job['status'] != 'running' or job['lease_owner'] != 'synthetic-diagnostic'
            or audit['event_type'] != 'api_token.created'):
        raise ValueError('Synthetic-only fixture relationships and authentication required')
    for value in (token['expires_at'], job['lease_expires_at']):
        expiry = datetime.fromisoformat(value)
        # SQLite engineering tests lose timezone information on roundtrip.
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry != datetime.fromisoformat(metadata['expires_at']):
            raise ValueError('Fixed token and lease expiry required')
    match = TOKEN_RE.fullmatch(data['token'])
    if not match or match[1] != token['prefix']:
        raise ValueError('Canonical token identity mismatch')
    try:
        password_hasher.verify(token['secret_hash'], match[2])
    except Exception:
        raise ValueError('Canonical token verification failed') from None
    if password_hasher.check_needs_rehash(token['secret_hash']):
        raise ValueError('Normal frozen hashing parameters required')


def restore(session, encoded, metadata, *, now=None, required_until=None):
    """Rollback every failed restoration; never commit a partial replacement."""
    try:
        return _restore(session, encoded, metadata, now=now, required_until=required_until)
    except BaseException:
        session.rollback()
        raise


def _restore(session, encoded, metadata, *, now=None, required_until=None):
    validate_fixture(metadata, now=now, required_until=required_until)
    if hashlib.sha256(encoded).hexdigest() != metadata['dump_sha256']:
        raise ValueError('Canonical fixture bytes changed')
    data = json.loads(encoded)
    if digest(data['rows']) != metadata['identity_sha256']:
        raise ValueError('Canonical fixture row identity changed')
    _validate_rows(data, metadata)
    _assert_empty_elsewhere(session)
    existing = _snapshot(session)
    identities = [({row['id'] for row in existing[name]}, {row['id'] for row in data['rows'][name]})
                  for name in TABLES if name != 'rate_limit_states']
    fresh = all(not current for current, _expected in identities)
    if (fresh and existing['rate_limit_states']) or (not fresh and any(current != expected for current, expected in identities)):
        raise ValueError('Database contains unowned fixture identities; restoration prohibited')
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in TABLES:
            session.execute(table.delete())
    for table in Base.metadata.sorted_tables:
        if table.name not in TABLES:
            continue
        for original in data['rows'][table.name]:
            row = dict(original)
            for column in table.columns:
                if isinstance(column.type, DateTime) and row.get(column.name) is not None:
                    row[column.name] = datetime.fromisoformat(row[column.name])
            session.execute(table.insert().values(**row))
    session.flush()
    if digest(_snapshot(session)) != metadata['identity_sha256']:
        raise ValueError('Restored fixture identity mismatch')
    session.commit()
    session.expire_all()
    return data['token']
