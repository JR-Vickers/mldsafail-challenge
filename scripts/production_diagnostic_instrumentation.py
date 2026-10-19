"""Opt-in diagnostic instrumentation, installed only in disposable web workers.

Wrappers delegate unchanged arguments/results/exceptions. No headers, SQL text,
parameters, credentials, response bodies or exception messages are collected.
"""
from contextvars import ContextVar
from functools import wraps
import time
import uuid

_CURRENT = ContextVar('diagnostic_request', default=None)
TIMINGS = frozenset(('authentication_seconds', 'hash_seconds', 'connection_seconds',
                     'query_seconds', 'commit_seconds'))
ROUTES = frozenset(('/health/ready', '/api/v1/me'))


def timed(function, field):
    if field not in TIMINGS:
        raise ValueError('Unapproved timing field')
    @wraps(function)
    def wrapped(*args, **kwargs):
        started = time.monotonic()
        try:
            return function(*args, **kwargs)
        finally:
            row = _CURRENT.get()
            if row is not None:
                row[field] += time.monotonic() - started
    return wrapped


def install(app, emit, on_error):
    """Install once after app creation, before serving requests.

    Hash verification still uses the exact original PasswordHasher, including
    dummy verification. Timings overlap (authentication includes DB/hash work).
    """
    from flask import g, request
    from sqlalchemy import event
    from sqlalchemy.orm import Session, sessionmaker
    from mldsafail.web import api, services
    if app.extensions.get('production_diagnostic_instrumentation'):
        raise ValueError('Diagnostic instrumentation already installed')
    if not callable(on_error):
        raise ValueError('Diagnostic evidence failure callback required')
    engine = app.extensions['mldsafail_engine']
    engine.connect = timed(engine.connect, 'connection_seconds')

    @event.listens_for(engine, 'before_cursor_execute')
    def before_query(_conn, _cursor, _statement, _parameters, context, _many):
        context._diagnostic_started = time.monotonic()

    @event.listens_for(engine, 'after_cursor_execute')
    def after_query(_conn, _cursor, _statement, _parameters, context, _many):
        row = _CURRENT.get()
        if row is not None:
            row['query_seconds'] += time.monotonic() - context._diagnostic_started

    @event.listens_for(engine, 'handle_error')
    def failed_query(context):
        execution = context.execution_context
        row = _CURRENT.get()
        if row is not None and execution is not None and hasattr(execution, '_diagnostic_started'):
            row['query_seconds'] += time.monotonic() - execution._diagnostic_started

    class DiagnosticSession(Session):
        commit = timed(Session.commit, 'commit_seconds')
    app.extensions['mldsafail_sessionmaker'] = sessionmaker(engine, expire_on_commit=False, class_=DiagnosticSession)

    # Proxy only verify; retain the original object, hashing parameters and errors.
    if not getattr(services.verify_api_token, '_diagnostic_wrapped', False):
        original_hasher = services.password_hasher
        class Hasher:
            verify = staticmethod(timed(original_hasher.verify, 'hash_seconds'))
            def __getattr__(self, name):
                return getattr(original_hasher, name)
        services.password_hasher = Hasher()
        services.verify_api_token = timed(services.verify_api_token, 'authentication_seconds')
        services.verify_api_token._diagnostic_wrapped = True
        api.verify_api_token = services.verify_api_token

    @app.before_request
    def begin():
        if request.path in ROUTES:
            g.diagnostic_started = time.monotonic()
            g.diagnostic_token = _CURRENT.set(dict.fromkeys(TIMINGS, 0.0))
            g.diagnostic_id = uuid.uuid4().hex

    @app.after_request
    def finish(response):
        if hasattr(g, 'diagnostic_token'):
            response.headers['X-Diagnostic-ID'] = g.diagnostic_id
            g.diagnostic_status = response.status_code
        return response

    @app.teardown_request
    def end(_error):
        if hasattr(g, 'diagnostic_token'):
            row = dict(_CURRENT.get())
            _CURRENT.reset(g.diagnostic_token)
            del g.diagnostic_token
            row.update(request_id=g.diagnostic_id, route=request.path,
                status=getattr(g, 'diagnostic_status', 500), seconds=time.monotonic() - g.diagnostic_started)
            try:
                emit(row)
            except Exception:
                app.extensions['diagnostic_evidence_failed'] = True
                try:
                    on_error('evidence_publication_failed')
                except Exception:
                    # The in-process flag remains authoritative even if the
                    # secondary evidence sink also fails.
                    pass
    app.extensions['production_diagnostic_instrumentation'] = True
