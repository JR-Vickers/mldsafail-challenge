"""Exclusive private evidence directories, durable records, and strict replay audit."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import uuid

from . import BENCHMARK_VERSION
from .constants import STUDY_VERSION, PROFILES
from .execution import disposition, fingerprint
from .generator import generate_mlwe
from .models import digest
from .scoring import CHALLENGE_CELLS, case_cost, eligibility, ranking, ranking_interval
from .solvers import DEFAULT_PARAMETERS
from .verify import verify_candidate

SETTINGS = {"warmups": 1, "repetitions": 3, "wall_seconds": 60, "memory_bytes": 2 * 1024**3,
            "cpus": 1, "tmp_bytes": 64 * 1024**2, "output_bytes": 2_000_000,
            "timing": "frozen-complete-worker-cpu", "reference": "primal-lll"}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def write(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError(f"refusing to overwrite evidence file {path.name}")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".partial")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Exclusive hard-link publication is atomic, even with competing writers.
    os.link(temporary, path)
    temporary.unlink()
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    return path


def seeds(nonce, profile):
    if not isinstance(nonce, str) or len(nonce) != 64 or any(c not in '0123456789abcdef' for c in nonce):
        raise ValueError("epoch nonce must be fresh 32-byte lowercase hex")
    values, counter = [], 0
    while len(values) < 20:
        material = f"{STUDY_VERSION}\0validation\0{profile}\0{nonce}\0{counter}".encode()
        value = int.from_bytes(hashlib.sha256(material).digest()[:8], 'big')
        if value not in values:
            values.append(value)
        counter += 1
    return values


def cases(nonce=None, smoke=False):
    result = []
    for profile, eta in CHALLENGE_CELLS:
        for seed in ([0] if smoke else seeds(nonce, profile)):
            public = generate_mlwe(profile, seed, eta).public
            result.append({"profile": profile, "eta": eta, "seed": seed,
                           "instance_id": public.instance_id, "input_digest": digest(public.to_dict())})
    random.Random(f"{STUDY_VERSION}:{'development' if smoke else 'validation'}:{nonce or 'committed'}:{smoke}").shuffle(result)
    return result


def manifest(kind, environment, grid, **extra):
    return {"benchmark_version": BENCHMARK_VERSION, "kind": kind, "id": uuid.uuid4().hex,
            "created_utc": datetime.now(timezone.utc).isoformat(), "settings": SETTINGS,
            "environment": environment, "cases": grid, **extra}


def aggregate(case, solver, outputs):
    if len(outputs) != 4:
        raise ValueError("one warmup and three repetitions required")
    repetitions = outputs[1:]
    successful = [r for r in repetitions if r['status'] == 'success']
    statuses = [r['status'] for r in repetitions]
    return {**case, "track": "mlwe", "solver": solver,
            "verification_result": len(successful) == 3,
            "status": statuses[0] if len(set(statuses)) == 1 else "mixed",
            "status_counts": dict(sorted(Counter(statuses).items())),
            "median_cpu_seconds": statistics.median(r['cpu_seconds'] for r in successful) if successful else None,
            "successful_cpu_seconds": [r['cpu_seconds'] for r in successful],
            "warmups": outputs[:1], "repetitions": repetitions}


def seal(path):
    files = {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(path.rglob('*')) if p.is_file() and p.name != 'COMPLETE.json'}
    write(path / 'COMPLETE.json', {"benchmark_version": BENCHMARK_VERSION, "files": files})


def check_seal(path):
    marker = read(path / 'COMPLETE.json')
    if set(marker) != {'benchmark_version', 'files'} or marker['benchmark_version'] != BENCHMARK_VERSION:
        raise ValueError("incompatible completion marker")
    actual = {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(path.rglob('*')) if p.is_file() and p.name != 'COMPLETE.json'}
    if marker['files'] != actual:
        raise ValueError("evidence file set or digest mismatch")


def check_manifest(m):
    if m['benchmark_version'] != BENCHMARK_VERSION or m['settings'] != SETTINGS:
        raise ValueError("incompatible benchmark version or settings")
    if m['environment']['trusted_fingerprint'] != fingerprint():
        raise ValueError("incompatible trusted code fingerprint")


def audit_records(path, m):
    expected = set()
    rows = []
    for index, case in enumerate(m['cases']):
        instance = generate_mlwe(case['profile'], case['seed'], case['eta']).public
        if instance.instance_id != case['instance_id'] or digest(instance.to_dict()) != case['input_digest']:
            raise ValueError("case derivation mismatch")
        outputs = []
        for rep in range(4):
            name = f'{index:03d}-{rep}.json'
            expected.add(name)
            envelope = read(path / 'records' / name)
            if set(envelope) != {'run_id', 'case_index', 'repetition', 'result'} or (
                envelope['run_id'], envelope['case_index'], envelope['repetition']) != (m['id'], index, rep):
                raise ValueError("record identity mismatch")
            result = envelope['result']
            if 'stdout' in result and not result.get('timeout') and not result.get('output_overflow') and not result.get('error'):
                raw = json.loads(result['stdout'])
                for field in ('candidate', 'cpu_seconds', 'wall_seconds', 'peak_rss_bytes', 'limits', 'solver_parameters', 'phase_cpu_seconds', 'diagnostic_counters'):
                    if raw.get(field) != result.get(field):
                        raise ValueError('worker stream differs from recorded result')
            verification = verify_candidate(instance, result.get('candidate'))
            if result['verification'] != verification or result['status'] != disposition(result):
                raise ValueError("candidate verification/status mismatch")
            if result['input_digest'] != case['input_digest'] or result['output_digest'] != digest(result.get('candidate')):
                raise ValueError("input/output digest mismatch")
            if result['status'] == 'success':
                for field in ('cpu_seconds', 'wall_seconds', 'evaluator_wall_seconds'):
                    value = result[field]
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError("invalid measurement")
                if result['evaluator_wall_seconds'] > 60 or result['peak_rss_bytes'] > SETTINGS['memory_bytes']:
                    raise ValueError("successful result exceeded limits")
                if result['limits']['rlimits_applied'] != ['RLIMIT_AS'] or type(result['limits']['cpu_affinity']) is not int:
                    raise ValueError("missing worker limits")
            if not result.get('error') and not result.get('timeout'):
                expected_params = {} if m['solver'] == 'contestant' else DEFAULT_PARAMETERS[m['solver']]
                if result['solver_parameters'] != expected_params:
                    raise ValueError("altered solver settings")
            outputs.append(result)
        rows.append(aggregate(case, m['solver'], outputs))
    if {p.name for p in (path / 'records').iterdir()} != expected:
        raise ValueError("missing or duplicate records")
    if len({r['instance_id'] for r in rows}) != len(rows):
        raise ValueError("duplicate cases")
    if read(path / 'aggregates.json') != rows:
        raise ValueError("altered aggregates")
    return rows


def audit_run(path, epoch=None, check_complete=True):
    path = Path(path)
    if check_complete:
        check_seal(path)
    m = read(path / 'manifest.json')
    check_manifest(m)
    if epoch is not None:
        em = read(Path(epoch) / 'manifest.json')
        if m.get('epoch_manifest_sha256') != sha(em) or m['environment'] != em['environment'] or m['cases'] != em['cases']:
            raise ValueError("incompatible epoch or execution environment")
    if m['solver'] == 'contestant':
        actual = {str(p.relative_to(path / 'solver')): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                  for p in (path / 'solver').rglob('*') if p.is_file()}
        if actual != m['solver_files']:
            raise ValueError("solver source mismatch")
    rows = audit_records(path, m)
    if (path / 'summary.json').exists() and read(path / 'summary.json') != summary(m, rows):
        raise ValueError('altered summary')
    return m, rows


def audit_epoch(path):
    path = Path(path)
    check_seal(path)
    m = read(path / 'manifest.json')
    check_manifest(m)
    if m['kind'] != 'epoch' or m['cases'] != cases(read(path / 'secret.json')['nonce']):
        raise ValueError("epoch derivation mismatch")
    rows = []
    for name in ('primal-lll', 'exhaustive', 'direct-linear'):
        child, values = audit_run(path / name, path)
        if child['solver'] != name:
            raise ValueError("epoch reference solver mismatch")
        rows.extend(values)
    if any(rep['status'] == 'invalid_answer' for row in rows for rep in row['warmups']):
        raise ValueError('invalid epoch warmup candidate')
    gates = eligibility(rows)
    if read(path / 'gates.json') != gates or not gates['numeric_eligibility']:
        raise ValueError("epoch viability gate failed")
    reference = [r for r in rows if r['solver'] == 'primal-lll']
    if read(path / 'reference-costs.json') != {r['instance_id']: case_cost(r) for r in reference}:
        raise ValueError("reference cost mismatch")
    return m, reference


def summary(m, rows, reference=None):
    # Whitelist shareable fields: no cases, seed, nonce, host ID, paths or candidates.
    result = {"benchmark_version": BENCHMARK_VERSION, "run_id": m['id'],
              "ranking": reference is not None, "cases": len(rows),
              "case_status_counts": dict(sorted(Counter(r['status'] for r in rows).items())),
              "repetition_status_counts": dict(sorted(Counter(rep['status'] for r in rows for rep in r['repetitions']).items())),
              "warmup_status_counts": dict(sorted(Counter(rep['status'] for r in rows for rep in r['warmups']).items())),
              "eligible": not any(rep['status'] == 'invalid_answer' for r in rows for rep in r['warmups'] + r['repetitions']),
              "cells": {}}
    for p, e in CHALLENGE_CELLS:
        cell = [r for r in rows if (r['profile'], r['eta']) == (p, e)]
        times = [r['median_cpu_seconds'] for r in cell if r['verification_result']]
        result['cells'][f'{p}/eta{e}'] = {'successes': sum(r['verification_result'] for r in cell), 'cases': len(cell),
            'successful_median_cpu_seconds': statistics.median(times) if times else None}
    if reference is not None and result['eligible']:
        named = [{**r, 'solver': m['id']} for r in rows]
        result['score'] = ranking(reference + named, m['id'])
        result['interval_95'] = list(ranking_interval(reference + named, m['id']))
    return result


def partial_diagnostics(path, epoch_manifest):
    """Reverify every available record without treating missing work as completed."""
    path = Path(path)
    m = read(path / 'manifest.json')
    check_manifest(m)
    if m.get('epoch_manifest_sha256') != sha(epoch_manifest) or m['cases'] != epoch_manifest['cases'] or m['environment'] != epoch_manifest['environment']:
        raise ValueError('incompatible partial run')
    seen = set()
    counts = Counter()
    for file in sorted((path / 'records').glob('*.json')):
        envelope = read(file)
        index, rep = envelope['case_index'], envelope['repetition']
        if type(index) is not int or type(rep) is not int or not 0 <= index < len(m['cases']) or not 0 <= rep < 4:
            raise ValueError('invalid partial record identity')
        if (index, rep) in seen or envelope['run_id'] != m['id'] or file.name != f'{index:03d}-{rep}.json':
            raise ValueError('duplicate or incompatible partial record')
        seen.add((index, rep))
        case = m['cases'][index]
        instance = generate_mlwe(case['profile'], case['seed'], case['eta']).public
        result = envelope['result']
        if result['input_digest'] != digest(instance.to_dict()) or result['output_digest'] != digest(result.get('candidate')) or result['verification'] != verify_candidate(instance, result.get('candidate')) or result['status'] != disposition(result):
            raise ValueError('partial record verification mismatch')
        counts[result['status']] += 1
    return {'benchmark_version': BENCHMARK_VERSION, 'run_id': m['id'], 'complete': False,
            'ranking': False, 'verified_records': len(seen), 'missing_records': len(m['cases']) * 4 - len(seen),
            'status_counts': dict(sorted(counts.items()))}
