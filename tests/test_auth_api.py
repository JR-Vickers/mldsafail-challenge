from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from mldsafail.web.app import create_app
from mldsafail.web.db import get_session
from mldsafail.web.models import ApiToken, AuditEvent, Base, BrowserSession, Submission, User, utcnow
from mldsafail.web.services import create_api_token, sanitize_log, verify_api_token


def hosted_app(tmp_path):
    app = create_app(config_name="test", config={"DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}"})
    Base.metadata.create_all(app.extensions["mldsafail_engine"])
    return app


def user_and_token(app):
    with app.app_context():
        database = get_session()
        user = User(display_name="Ada", avatar_url=None)
        database.add(user); database.commit()
        token, plaintext = create_api_token(database, user, "CLI")
        return user.id, token.id, plaintext


def test_argon_token_is_one_way_scoped_revocable_and_audited(tmp_path):
    app = hosted_app(tmp_path)
    user_id, token_id, plaintext = user_and_token(app)
    with app.app_context():
        database = get_session()
        stored = database.get(ApiToken, token_id)
        assert plaintext not in stored.secret_hash
        assert stored.scopes == ["submission:write", "submission:read"]
        assert verify_api_token(database, plaintext, "submission:read")[0].id == user_id
        assert stored.last_used_at is not None
        stored.revoked_at = utcnow(); database.commit()
        assert verify_api_token(database, plaintext) is None
        assert database.scalar(select(AuditEvent).where(AuditEvent.event_type == "api_token.created"))


def test_api_submission_idempotency_ownership_and_cancellation(tmp_path):
    app = hosted_app(tmp_path)
    _user_id, _token_id, plaintext = user_and_token(app)
    client = app.test_client()
    headers = {"Authorization": f"Bearer {plaintext}", "Idempotency-Key": "attempt-1"}
    payload = {"repository_url": "https://github.com/example/research", "commit_sha": "a" * 40, "hypothesis": "reduce allocations"}
    first = client.post("/api/v1/submissions", headers=headers, json=payload)
    assert first.status_code == 201
    identifier = first.json["submission"]["id"]
    repeated = client.post("/api/v1/submissions", headers=headers, json=payload)
    assert repeated.status_code == 200
    assert repeated.json["submission"]["id"] == identifier
    conflict = client.post("/api/v1/submissions", headers=headers, json=payload | {"hypothesis": "different"})
    assert conflict.status_code == 409
    assert conflict.json["error"]["code"] == "idempotency_conflict"
    assert client.get(f"/api/v1/submissions/{identifier}", headers=headers).status_code == 200
    cancelled = client.post(f"/api/v1/submissions/{identifier}/cancel", headers=headers)
    assert cancelled.json["submission"]["state"] == "cancelled"
    assert client.post(f"/api/v1/submissions/{identifier}/cancel", headers=headers).status_code == 409


def test_api_rejects_bad_source_contract_and_never_echoes_token(tmp_path):
    app = hosted_app(tmp_path)
    _user_id, _token_id, plaintext = user_and_token(app)
    headers = {"Authorization": f"Bearer {plaintext}", "Idempotency-Key": "bad"}
    cases = [
        ({"repository_url": "http://github.com/a/b", "commit_sha": "a" * 40, "hypothesis": "x"}, "invalid_repository"),
        ({"repository_url": "https://gitlab.com/a/b", "commit_sha": "a" * 40, "hypothesis": "x"}, "invalid_repository"),
        ({"repository_url": "https://github.com/a/b", "commit_sha": "main", "hypothesis": "x"}, "invalid_commit"),
        ({"repository_url": "https://github.com/a/b", "commit_sha": "a" * 40, "hypothesis": "x", "benchmark_version": "old"}, "unsupported_benchmark"),
    ]
    for payload, code in cases:
        response = app.post if False else app.test_client().post("/api/v1/submissions", headers=headers, json=payload)
        assert response.json["error"]["code"] == code
        assert plaintext.encode() not in response.data


def test_browser_session_csrf_and_dev_identity_gate(tmp_path):
    app = hosted_app(tmp_path)
    client = app.test_client()
    assert client.post("/auth/dev-login").status_code == 302
    assert client.get("/profile").status_code == 200
    assert client.post("/auth/logout", data={"csrf_token": "wrong"}).status_code == 400
    with client.session_transaction() as browser_cookie:
        sid = browser_cookie["sid"]
    with app.app_context():
        csrf = get_session().get(BrowserSession, sid).csrf_token
    assert client.post("/auth/logout", data={"csrf_token": csrf}).status_code == 302
    assert client.get("/profile").status_code == 302
    production = create_app(config_name="test", config={"DATABASE_URL": f"sqlite:///{tmp_path / 'prod.db'}", "ENV": "production", "ALLOW_DEV_AUTH": False})
    Base.metadata.create_all(production.extensions["mldsafail_engine"])
    assert production.test_client().post("/auth/dev-login").status_code == 404


def test_expired_token_and_log_redaction(tmp_path):
    app = hosted_app(tmp_path)
    with app.app_context():
        database = get_session()
        user = User(display_name="Grace", avatar_url=None); database.add(user); database.commit()
        _token, plaintext = create_api_token(database, user, "expired", expires_at=utcnow() - timedelta(seconds=1))
        assert verify_api_token(database, plaintext) is None
    log = f"failed {plaintext} at /run/secrets/hidden/seeds.json"
    assert plaintext not in sanitize_log(log)
    assert "/run/secrets" not in sanitize_log(log)
