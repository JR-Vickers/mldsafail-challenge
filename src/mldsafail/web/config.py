"""Explicit runtime configuration for local and hosted deployments."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BaseConfig:
    ENV: str = "local"
    DATABASE_URL: str | None = None
    SECRET_KEY: str = "local-development-only"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = False
    PERMANENT_SESSION_LIFETIME_SECONDS: int = 3600
    MAX_CONTENT_LENGTH: int = 64 * 1024
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None
    ALLOW_DEV_AUTH: bool = False
    BENCHMARK_VERSION: str = "0.3.0"
    EVALUATOR_FINGERPRINT: str = "development"
    HIDDEN_SUITE_VERSION: str = "unconfigured"
    WORKER_CLASS: str = "rootless-docker-v1"


@dataclass(frozen=True)
class LocalConfig(BaseConfig):
    ALLOW_DEV_AUTH: bool = True


@dataclass(frozen=True)
class TestConfig(BaseConfig):
    ENV: str = "test"
    SECRET_KEY: str = "test-secret"
    ALLOW_DEV_AUTH: bool = True


@dataclass(frozen=True)
class StagingConfig(BaseConfig):
    ENV: str = "staging"
    SESSION_COOKIE_SECURE: bool = True


@dataclass(frozen=True)
class ProductionConfig(BaseConfig):
    ENV: str = "production"
    SESSION_COOKIE_SECURE: bool = True


CONFIGS = {
    "local": LocalConfig,
    "test": TestConfig,
    "staging": StagingConfig,
    "production": ProductionConfig,
}


def load_config(name: str | None = None) -> dict[str, object]:
    environment = name or os.environ.get("MLDSAFAIL_ENV", "local")
    try:
        values = CONFIGS[environment]()
    except KeyError as error:
        raise ValueError(f"unknown MLDSAFAIL_ENV {environment!r}") from error
    config = dict(vars(values))
    mappings = {
        "DATABASE_URL": "MLDSAFAIL_DATABASE_URL",
        "SECRET_KEY": "MLDSAFAIL_SECRET_KEY",
        "GITHUB_CLIENT_ID": "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET": "GITHUB_CLIENT_SECRET",
        "EVALUATOR_FINGERPRINT": "MLDSAFAIL_EVALUATOR_FINGERPRINT",
        "HIDDEN_SUITE_VERSION": "MLDSAFAIL_HIDDEN_SUITE_VERSION",
        "WORKER_CLASS": "MLDSAFAIL_WORKER_CLASS",
    }
    for key, variable in mappings.items():
        if variable in os.environ:
            config[key] = os.environ[variable]
    if environment in {"staging", "production"}:
        if config["SECRET_KEY"] == "local-development-only":
            raise RuntimeError("MLDSAFAIL_SECRET_KEY is required for hosted environments")
        if not config["DATABASE_URL"]:
            raise RuntimeError("MLDSAFAIL_DATABASE_URL is required for hosted environments")
        if not config["GITHUB_CLIENT_ID"] or not config["GITHUB_CLIENT_SECRET"]:
            raise RuntimeError("GitHub OAuth credentials are required for hosted environments")
        if config["EVALUATOR_FINGERPRINT"] == "development":
            raise RuntimeError("MLDSAFAIL_EVALUATOR_FINGERPRINT is required for hosted environments")
        if config["HIDDEN_SUITE_VERSION"] == "unconfigured":
            raise RuntimeError("MLDSAFAIL_HIDDEN_SUITE_VERSION is required for hosted environments")
    return config
