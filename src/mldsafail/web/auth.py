"""GitHub OAuth and database-backed browser sessions."""

from __future__ import annotations

import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, abort, current_app, g, redirect, request, session, url_for
from sqlalchemy import select

from mldsafail.web.db import get_session
from mldsafail.web.models import BrowserSession, GithubIdentity, User, utcnow
from mldsafail.web.services import audit

auth = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()


def _safe_next(value: str | None) -> str:
    if not value:
        return url_for("profile")
    parsed = urlparse(value)
    return value if not parsed.scheme and not parsed.netloc and value.startswith("/") else url_for("profile")


def establish_session(user: User) -> None:
    database = get_session()
    session.clear()
    sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(seconds=current_app.config["PERMANENT_SESSION_LIFETIME"].total_seconds())
    database.add(BrowserSession(id=sid, user_id=user.id, csrf_token=csrf, expires_at=expires))
    audit(database, "browser_session.created", user.id)
    database.commit()
    session["sid"] = sid
    session.permanent = True


def init_auth(app):
    oauth.init_app(app)
    if app.config.get("GITHUB_CLIENT_ID"):
        oauth.register(
            name="github", client_id=app.config["GITHUB_CLIENT_ID"], client_secret=app.config["GITHUB_CLIENT_SECRET"],
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize", api_base_url="https://api.github.com/",
            client_kwargs={"scope": "read:user"},
        )
    app.register_blueprint(auth)

    @app.before_request
    def load_browser_user():
        g.current_user = None
        sid = session.get("sid")
        if not sid or not app.config.get("DATABASE_URL"):
            return
        database = get_session()
        browser = database.get(BrowserSession, sid)
        if browser is None or browser.revoked_at is not None:
            session.clear()
            return
        expiry = browser.expires_at
        if expiry.tzinfo is None:
            from datetime import timezone
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= utcnow():
            session.clear()
            return
        g.current_user = database.get(User, browser.user_id)
        g.csrf_token = browser.csrf_token

    @app.context_processor
    def auth_context():
        return {"current_user": getattr(g, "current_user", None), "csrf_token": getattr(g, "csrf_token", "")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "current_user", None):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def require_csrf() -> None:
    expected = getattr(g, "csrf_token", None)
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        abort(400, "invalid CSRF token")


@auth.get("/login")
def login():
    if not current_app.config.get("DATABASE_URL"):
        abort(404)
    session["login_next"] = _safe_next(request.args.get("next"))
    if not current_app.config.get("GITHUB_CLIENT_ID"):
        abort(503, "GitHub OAuth is not configured")
    return oauth.github.authorize_redirect(url_for("auth.callback", _external=True))


@auth.get("/callback")
def callback():
    token = oauth.github.authorize_access_token()
    response = oauth.github.get("user", token=token)
    response.raise_for_status()
    profile = response.json()
    database = get_session()
    subject = str(profile["id"])
    identity = database.scalar(select(GithubIdentity).where(GithubIdentity.github_subject == subject))
    if identity:
        user = identity.user
        user.display_name = profile.get("name") or profile["login"]
        user.avatar_url = profile.get("avatar_url")
        identity.login = profile["login"]
    else:
        user = User(display_name=profile.get("name") or profile["login"], avatar_url=profile.get("avatar_url"))
        database.add(user)
        database.flush()
        database.add(GithubIdentity(user_id=user.id, github_subject=subject, login=profile["login"]))
    database.commit()
    destination = _safe_next(session.get("login_next"))
    establish_session(user)
    return redirect(destination)


@auth.post("/logout")
@login_required
def logout():
    require_csrf()
    database = get_session()
    browser = database.get(BrowserSession, session.get("sid"))
    if browser:
        browser.revoked_at = utcnow()
        audit(database, "browser_session.revoked", browser.user_id)
        database.commit()
    session.clear()
    return redirect(url_for("index"))


@auth.post("/dev-login")
def dev_login():
    if not current_app.config.get("ALLOW_DEV_AUTH") or current_app.config.get("ENV") not in {"local", "test"}:
        abort(404)
    database = get_session()
    subject = "dev-identity"
    identity = database.scalar(select(GithubIdentity).where(GithubIdentity.github_subject == subject))
    if identity:
        user = identity.user
    else:
        user = User(display_name="Local Researcher", avatar_url=None)
        database.add(user); database.flush()
        database.add(GithubIdentity(user_id=user.id, github_subject=subject, login="local-researcher")); database.commit()
    establish_session(user)
    return redirect(url_for("profile"))
