"""Pure admission and timing controls for the separate, no-epoch investigation.

This module grants no native lifecycle authority. Native admission additionally
requires an independently reviewed controller and a fresh ownership receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time

SCHEMA = 'mldsafail.production-diagnostic.v2'
WORKER = 'sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe'
INITIAL_DEBIT = 900
PREFLIGHT_SECONDS = 300
GENERATION_SECONDS = 3000
CLEANUP_SECONDS = 900
AGGREGATE_SECONDS = 7200


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def public_workload():
    # Use the repository's actual ordered enumerator, never a parallel seed list.
    from mldsafail.development import public_cases
    rows = public_cases()
    if len(rows) != 50:
        raise ValueError('Public development workload changed')
    return rows


def validate_fixture(metadata, *, now=None, required_until=None):
    """Expiry is fixed at creation; comparison phases may never renew it."""
    now = now or datetime.now(timezone.utc)
    required_until = required_until or now
    if set(metadata) != {'schema', 'created_at', 'expires_at', 'dump_sha256', 'identity_sha256'} or metadata['schema'] != 'mldsafail.diagnostic-fixture.v1':
        raise ValueError('Canonical fixture inventory required')
    created = datetime.fromisoformat(metadata['created_at'])
    expiry = datetime.fromisoformat(metadata['expires_at'])
    if (created.utcoffset() != timedelta(0) or expiry.utcoffset() != timedelta(0)
            or expiry - created != timedelta(hours=24) or created > now
            or expiry <= max(now, required_until)):
        raise ValueError('Fixed 24-hour fixture expiry does not cover comparison')
    for field in ('dump_sha256', 'identity_sha256'):
        if not isinstance(metadata[field], str) or not re.fullmatch('[0-9a-f]{64}', metadata[field]):
            raise ValueError('Immutable fixture identities required')
    return metadata


def validate_protocol(protocol, *, cases=None):
    """Validate declared comparisons without trusting stale draft defaults."""
    expected = dict(schema=SCHEMA, benchmark_version='0.5.0', worker_image=WORKER,
        private_epoch=False, private_acceptance=False, ranking=False, delivery=False,
        additional_spending=0, initial_debit_seconds=900, preflight_seconds=300,
        generation_seconds=3000, cleanup_reserve_seconds=900, aggregate_seconds=7200,
        http_comparison_requests=120, http_comparison_seconds=60, request_threads=10,
        request_timeout_seconds=2, legacy_seconds=60, legacy_outer_seconds=600,
        final_anonymous_requests=1500, final_authenticated_requests=60, final_seconds=300,
        monitor_invocations_per_condition=3, monitor_command_timeout_seconds=10)
    for key, value in expected.items():
        if type(protocol.get(key)) is not type(value) or protocol[key] != value:
            raise ValueError('Diagnostic protocol mismatch: ' + key)
    if protocol.get('generation') not in ('baseline', 'post-fix'):
        raise ValueError('Only two diagnostic generations permitted')
    rows = public_workload() if cases is None else cases
    if len(rows) != 50 or protocol.get('public_cases') != rows or protocol.get('workload_sha256') != digest(rows):
        raise ValueError('Exact ordered 50-case public workload required')
    for field in ('source_sha256', 'configuration_sha256', 'instrumentation_sha256', 'legacy_source_sha256', 'cleanup_protocol_sha256', 'fixture_sha256'):
        if not re.fullmatch('[0-9a-f]{64}', protocol.get(field, '')):
            raise ValueError('Frozen diagnostic inventory required: ' + field)
    images = protocol.get('images', {})
    archives = protocol.get('archives', {})
    if set(images) != {'web', 'coordinator', 'worker', 'postgres', 'caddy'} or images.get('worker') != WORKER:
        raise ValueError('Complete immutable image inventory required')
    for name, identity in images.items():
        if not re.fullmatch('sha256:[0-9a-f]{64}', identity) or not re.fullmatch('[0-9a-f]{64}', archives.get(name, '')):
            raise ValueError('Image and archive identities required')
    if set(archives) != set(images):
        raise ValueError('Exact archive inventory required')
    return protocol


@dataclass
class Allowance:
    """Monotonic allowance; setup/import/cleanup all share the start instant."""
    started: float
    seconds: int
    cleanup: int = 0
    clock: object = time.monotonic

    def admit(self, timeout):
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= self.seconds:
            raise ValueError('Finite positive phase ceiling required')
        if self.clock() < self.started or self.clock() + timeout > self.started + self.seconds - self.cleanup:
            raise TimeoutError('Diagnostic allowance exhausted; cleanup reserve protected')

    def elapsed(self):
        return max(0, self.clock() - self.started)


def validate_ledger(ledger, generation):
    """Irreversible start entries prevent retries after interruption.

    The private controller must hold its operation lock while validating and
    publishing the next entry. Unknown/partial prior cleanup fences generation 2.
    """
    if ledger.get('initial_debit_seconds') != INITIAL_DEBIT:
        raise ValueError('Existing 900-second debit must be retained')
    preflight = ledger.get('preflight', {})
    charged = preflight.get('charged_seconds')
    if preflight.get('complete') is not True or type(charged) is not int or not 0 <= charged <= PREFLIGHT_SECONDS:
        raise ValueError('Fresh bounded preflight receipt required')
    entries = ledger.get('generations')
    if not isinstance(entries, list) or len(entries) != (0 if generation == 'baseline' else 1) or generation not in ('baseline', 'post-fix'):
        raise ValueError('No retry, third generation or budget reset permitted')
    used = INITIAL_DEBIT + charged
    for entry in entries:
        charge = entry.get('charged_seconds')
        if (entry.get('generation') != 'baseline' or entry.get('complete') is not True
                or entry.get('cleanup_verified') is not True or type(charge) is not int
                or not 0 <= charge <= GENERATION_SECONDS):
            raise ValueError('Independently verified baseline cleanup required')
        used += charge
    if used + GENERATION_SECONDS > AGGREGATE_SECONDS:
        raise ValueError('Aggregate diagnostic allowance exhausted')
    return used
