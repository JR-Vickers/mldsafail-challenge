"""Pure version/cohort adapters prepared separately from frozen evaluators.

These helpers make no application/database changes. Gate receipts must be
independently accepted by an operator before enabling evaluator integration.
Production/default activation remains a separate owner decision.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import re

VERSIONS = frozenset({'0.4.0', '0.5.0', '0.6.0'})
METHODS = {'0.5.0': 'frozen-complete-worker-cpu', '0.6.0': 'cgroup-v2-usage-usec'}


class UnsupportedBenchmark(ValueError):
    code = 'unsupported_benchmark'
    status = 422


@dataclass(frozen=True)
class IntegrationGates:
    supervisor_review: bool = False
    auditor_review: bool = False
    native_faults: bool = False
    native_pairs: bool = False
    contract_adopted: bool = False

    def require(self):
        if any(type(value) is not bool for value in asdict(self).values()):
            raise ValueError('Gate decisions must be boolean')
        missing = [key for key, value in asdict(self).items() if not value]
        if missing:
            raise UnsupportedBenchmark('0.6.0 integration remains gated: ' + ', '.join(missing))


def select_version(requested, *, current_default, enabled_versions, gates=IntegrationGates()):
    """Omitted version retains caller's existing default; explicit 0.6.0 is gated."""
    if current_default not in VERSIONS:
        raise ValueError('Unrecognized configured default')
    version = current_default if requested is None else requested
    if not isinstance(version, str) or version not in VERSIONS or version not in enabled_versions:
        raise UnsupportedBenchmark('The requested benchmark version is unsupported.')
    if version == '0.6.0':
        gates.require()
    return version


@dataclass(frozen=True)
class Cohort:
    benchmark_version: str
    epoch_id: str
    evaluator_fingerprint: str
    hidden_suite_version: str
    worker_class: str
    environment_fingerprint: str
    measurement_method: str

    def __post_init__(self):
        if self.benchmark_version not in METHODS or self.measurement_method != METHODS[self.benchmark_version]:
            raise ValueError('MLWE cohort/version measurement mismatch')
        if any(not isinstance(value, str) or not value for value in asdict(self).values()):
            raise ValueError('Every cohort identity is mandatory')
        for field in ('evaluator_fingerprint', 'environment_fingerprint'):
            if not re.fullmatch('[0-9a-f]{64}', getattr(self, field)):
                raise ValueError('Cohort fingerprints must be SHA256 identities')

    @property
    def public_id(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def accepts(self, record):
        return record.get('verified') is True and record.get('eligible') is True and all(
            record.get(key) == value for key, value in asdict(self).items())


def cohort_records(records, cohort):
    """Strict full-cohort filtering; never convert old costs or mix environments."""
    return [record for record in records if cohort.accepts(record)]


def participant_result(record, cohort):
    """Public projection excludes host paths, private evidence, seeds and nonces."""
    if not cohort.accepts(record):
        raise ValueError('An unaudited or different-cohort record cannot publish')
    score = record.get('score')
    import math
    if type(score) not in (int, float) or not math.isfinite(score) or score <= 0:
        raise ValueError('Audited positive finite score required')
    if not isinstance(record.get('submission_id'), str) or not record['submission_id']:
        raise ValueError('Submission identity required')
    return dict(submission_id=record['submission_id'], benchmark_version=cohort.benchmark_version,
                cohort_id=cohort.public_id, eligible=True, verified=True, score=score)


@dataclass(frozen=True)
class RegisteredBackend:
    """Operator registration; participants cannot register execution handlers."""
    cohort: Cohort
    evaluate: object
    gates: IntegrationGates = IntegrationGates()
    private_rehearsal: bool = False

    def __post_init__(self):
        if not callable(self.evaluate):
            raise ValueError('Distinct evaluator handler required')
        if self.cohort.benchmark_version == '0.6.0':
            from mldsafail.benchmark_v060.candidate_authority import CandidateRehearsalAuthority
            if isinstance(self.gates,CandidateRehearsalAuthority):
                self.gates.require_private(self.private_rehearsal)
                if self.gates.cohort_id!=self.cohort.public_id: raise ValueError('Candidate registration cohort mismatch')
            self.gates.require()


class VersionRegistry:
    """Explicit dispatch, with no implicit fallback to a differently timed worker."""
    def __init__(self, backends=()):
        self.backends = {}
        for backend in backends:
            if not isinstance(backend, RegisteredBackend):
                raise ValueError('Trusted backend registration required')
            version = backend.cohort.benchmark_version
            if version in self.backends:
                raise ValueError('Duplicate evaluator version registration')
            self.backends[version] = backend

    def backend(self, version):
        try:
            return self.backends[version]
        except KeyError:
            raise UnsupportedBenchmark('The requested benchmark version is unsupported.') from None

    def evaluate(self, version, public_job):
        backend = self.backend(version)
        if public_job.get('benchmark_version') != version:
            raise ValueError('Job/version dispatch mismatch')
        fields = ('epoch_id', 'evaluator_fingerprint', 'hidden_suite_version', 'worker_class')
        if any(public_job.get(key) != getattr(backend.cohort, key) for key in fields):
            raise ValueError('Job belongs to a different evaluation cohort')
        result = backend.evaluate(public_job)
        if not isinstance(result, dict) or result.get('benchmark_version') != version:
            raise ValueError('Evaluator returned a different benchmark version')
        if any(result.get(key) != getattr(backend.cohort, key) for key in fields):
            raise ValueError('Evaluator returned a different evaluation cohort')
        return result


def application_cohort(config, requested=None):
    """Select legacy configured cohort, or an explicitly registered future one.

    Merely setting BENCHMARK_VERSION=0.6.0 never activates the new contract. Its
    default switch is separate from registration and needs an owner decision.
    """
    default = config['BENCHMARK_VERSION']
    version = default if requested is None else requested
    if version == '0.6.0':
        if requested is None and config.get('V060_DEFAULT_APPROVED') is not True:
            raise UnsupportedBenchmark('0.6.0 default activation requires an owner decision.')
        registry = config.get('BENCHMARK_VERSION_REGISTRY')
        if not isinstance(registry, VersionRegistry):
            raise UnsupportedBenchmark('The requested benchmark version is unsupported.')
        backend = registry.backend(version)
        from mldsafail.benchmark_v060.candidate_authority import CandidateRehearsalAuthority
        if isinstance(backend.gates,CandidateRehearsalAuthority):
            if requested is None or config.get('TESTING') is not True or config.get('V060_PRIVATE_CANDIDATE_REHEARSAL') is not True:
                raise UnsupportedBenchmark('Candidate registry requires explicit disposable rehearsal scope.')
            backend.gates.require()
            if backend.gates.cohort_id!=backend.cohort.public_id:
                raise UnsupportedBenchmark('Candidate registry authority mismatch.')
        cohort = backend.cohort
        return version, {key: getattr(cohort, key) for key in
                         ('epoch_id', 'evaluator_fingerprint', 'hidden_suite_version', 'worker_class')}
    if version != default or version not in {'0.4.0', '0.5.0'}:
        raise UnsupportedBenchmark('The requested benchmark version is unsupported.')
    return version, dict(epoch_id=config['MLWE_EPOCH_ID'],
                         evaluator_fingerprint=config['EVALUATOR_FINGERPRINT'],
                         hidden_suite_version=config['HIDDEN_SUITE_VERSION'],
                         worker_class=config['WORKER_CLASS'])
