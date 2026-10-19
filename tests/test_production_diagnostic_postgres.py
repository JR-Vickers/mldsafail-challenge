"""Opt-in disposable local PostgreSQL correctness test, never a deployed database."""
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from mldsafail.web.models import Base, ApiToken, EvaluationJob
from mldsafail.web.services import verify_api_token
from scripts import production_diagnostic_fixture as fixture


def test_postgres_fixture_roundtrip():
    url = os.environ.get('MLDSAFAIL_DIAGNOSTIC_TEST_POSTGRES')
    if not url:
        pytest.skip('Explicit disposable local PostgreSQL URL required')
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if parsed.host not in ('127.0.0.1', 'localhost') or parsed.database != 'diagnostic_fixture_test':
        raise ValueError('Dedicated loopback test database required')
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            now = datetime.now(timezone.utc)
            encoded, metadata = fixture.create(session, now=now)
            original = fixture._snapshot(session)
            token = fixture.restore(session, encoded, metadata, required_until=now + timedelta(hours=3))
            assert fixture._snapshot(session) == original
            assert verify_api_token(session, token, 'submission:read')
            fixture.restore(session, encoded, metadata)
            assert fixture._snapshot(session) == original
            assert session.scalar(select(ApiToken)).expires_at == now + timedelta(hours=24)
            assert session.scalar(select(EvaluationJob)).lease_expires_at == now + timedelta(hours=24)
            with pytest.raises(ValueError, match='expiry'):
                fixture.restore(session, encoded, metadata, now=now + timedelta(hours=24))
            assert fixture._snapshot(session) == original
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
