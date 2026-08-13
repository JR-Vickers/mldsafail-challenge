"""Canonical signed worker-result envelopes."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any


class EnvelopeError(ValueError):
    pass


def canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_envelope(payload: dict[str, Any], key: bytes) -> dict[str, Any]:
    return {"payload": payload, "signature": hmac.new(key, canonical_payload(payload), hashlib.sha256).hexdigest()}


def verify_envelope(envelope: dict[str, Any], key: bytes, expected: dict[str, str]) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"} or not isinstance(envelope["payload"], dict):
        raise EnvelopeError("invalid result envelope shape")
    signature = hmac.new(key, canonical_payload(envelope["payload"]), hashlib.sha256).hexdigest()
    if not isinstance(envelope["signature"], str) or not hmac.compare_digest(signature, envelope["signature"]):
        raise EnvelopeError("invalid result signature")
    payload = envelope["payload"]
    required = {"source_digest", "benchmark_version", "evaluator_fingerprint", "hidden_suite_version", "worker_class", "verified", "score", "diagnostics", "failure_class"}
    if set(payload) != required:
        raise EnvelopeError("invalid result payload fields")
    for key_name, value in expected.items():
        if payload.get(key_name) != value:
            raise EnvelopeError(f"unexpected {key_name}")
    score = payload["score"]
    if payload["verified"] is True and (isinstance(score, bool) or not isinstance(score, int) or score < 0):
        raise EnvelopeError("verified result has invalid score")
    if payload["verified"] is not True and score is not None:
        raise EnvelopeError("unverified result must not have a score")
    return payload
