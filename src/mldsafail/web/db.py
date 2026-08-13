"""Database lifecycle helpers independent of Flask extensions."""

from __future__ import annotations

from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def init_database(app: Flask) -> None:
    url = app.config.get("DATABASE_URL")
    if not url:
        return
    engine = create_engine(url, pool_pre_ping=True)
    app.extensions["mldsafail_engine"] = engine
    app.extensions["mldsafail_sessionmaker"] = sessionmaker(
        engine, expire_on_commit=False, class_=Session
    )

    @app.teardown_appcontext
    def close_session(_error=None) -> None:
        session = g.pop("database_session", None)
        if session is not None:
            session.close()


def get_engine() -> Engine:
    from flask import current_app

    return current_app.extensions["mldsafail_engine"]


def get_session() -> Session:
    from flask import current_app

    if "database_session" not in g:
        factory = current_app.extensions["mldsafail_sessionmaker"]
        g.database_session = factory()
    return g.database_session
