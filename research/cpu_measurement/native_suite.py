"""Native-only experimental gate, never promotes a benchmark score."""
import argparse
import json
from pathlib import Path
import statistics
import math
import time
import uuid
import hashlib
from research.cpu_measurement.ownership import publish
from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate



def measurement_gates(rows):
    """Predeclared adoption gates; empty-worker CV is diagnostic only."""
    grouped = {name: [row for row in rows if row['fixture'] == name]
               for name in ('empty', 'child')}
    if any(len(values) < 30 for values in grouped.values()):
        raise ValueError('At least 30 paired measurements required')
    pairs = [(row['fixture'], row.get('repetition')) for row in rows
             if row['fixture'] in grouped]
    if len(set(pairs)) != len(pairs) or {i for name, i in pairs if name == 'empty'} != {i for name, i in pairs if name == 'child'}:
        raise ValueError('Unique complete pairs required')
    selected = [row for row in rows if row['fixture'] in grouped]
    if [row['fixture'] for row in selected] != ['empty', 'child'] * len(grouped['empty']):
        raise ValueError('Sequential empty/child order required')
    provenance = None
    previous_end = -math.inf
    generations = set()
    for row in selected:
        if row.get('schema') != 'mldsafail.cpu-evidence.v1' or row.get('status') != 'no_answer' or row.get('cleanup_complete') is not True:
            raise ValueError('Complete audited measurement status required')
        identity = tuple(row.get(key) for key in ('suite_id', 'source_sha256', 'image', 'host_identity', 'parent_inode', 'parent_device'))
        if any(value is None for value in identity) or (provenance is not None and identity != provenance):
            raise ValueError('Consistent provenance required')
        provenance = identity
        generation = row.get('generation')
        if not generation or generation in generations:
            raise ValueError('Unique ownership generation required')
        generations.add(generation)
        values = [row.get(key) for key in ('authoritative_cpu_usec', 'wall_seconds', 'started_monotonic', 'finished_monotonic')]
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError('Finite measurement values required')
        if row['started_monotonic'] < previous_end or row['finished_monotonic'] < row['started_monotonic'] or row['wall_seconds'] < 0:
            raise ValueError('Nonoverlapping sequential measurements required')
        previous_end = row['finished_monotonic']
        if row.get('counter_after_usec', -1) - row.get('counter_before_usec', -1) != row['authoritative_cpu_usec']:
            raise ValueError('Counter delta mismatch')
    cpu = {name: [row['authoritative_cpu_usec'] for row in values]
           for name, values in grouped.items()}
    if any(value <= 0 for values in cpu.values() for value in values):
        raise ValueError('Positive authoritative CPU required')
    cv = {name: statistics.stdev(values) / statistics.mean(values)
          for name, values in cpu.items()}
    walls = sorted(row['wall_seconds'] for row in grouped['empty'])
    p95 = walls[math.ceil(.95 * len(walls)) - 1]
    medians = {name: statistics.median(values) for name, values in cpu.items()}
    gates = dict(deterministic_cpu_cv=cv['child'] <= .05,
                 empty_cpu_median=medians['empty'] <= 250_000,
                 empty_wall_p95=p95 <= 5,
                 descendant_accounting=medians['child'] > medians['empty'])
    return dict(passed=all(gates.values()), gates=gates, medians_usec=medians,
                coefficient_of_variation=cv, empty_wall_p95_seconds=p95,
                thresholds=dict(deterministic_cpu_cv_max=.05,
                                empty_cpu_median_usec_max=250_000,
                                empty_wall_p95_seconds_max=5))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--cgroup-parent', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ownership-directory', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    instance = generate_mlwe('small', 0, 1).public
    fixtures = Path(__file__).parent / 'fixtures'
    rows = []
    passed = True
    suite_id = uuid.uuid4().hex
    source_sha256 = hashlib.sha256(Path(__file__).read_bytes() + Path(__file__).with_name("harness.py").read_bytes()).hexdigest()
    host_identity = hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest()
    try:
        schedule = [(name, repetition) for repetition in range(30) for name in ('empty', 'child')]
        schedule += [(name, 0) for name in ('clock_tampering', 'forged_timing', 'early_exit', 'malformed', 'grandchild', 'output_flood', 'hang', 'descendant_hang')]
        for name, repetition in schedule:
            started = time.monotonic()
            result = run(args.image, args.parent, args.cgroup_parent, fixtures / name,
                         instance.to_dict(), lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                         timeout=2 if name in {'hang', 'descendant_hang'} else 60,
                         ownership_directory=args.ownership_directory,
                         evidence_metadata=dict(fixture=name, repetition=repetition, suite_id=suite_id,
                                                source_sha256=source_sha256, image=args.image, host_identity=host_identity))
            result.update(fixture=name, repetition=repetition, started_monotonic=started,
                          finished_monotonic=time.monotonic(), suite_id=suite_id,
                          source_sha256=source_sha256, image=args.image, host_identity=host_identity)
            publish(args.output / f'{name}-{repetition}.json', result)
            rows.append(result)
            expected = {'empty': 'no_answer', 'clock_tampering': 'no_answer',
                        'forged_timing': 'malformed', 'child': 'no_answer',
                        'early_exit': 'malformed', 'malformed': 'malformed', 'hang': 'timeout',
                        'grandchild': 'no_answer', 'output_flood': 'output_limit',
                        'descendant_hang': 'timeout'}[name]
            passed &= result['status'] == expected and result['authoritative_cpu_usec'] > 0
        summary = measurement_gates(rows)
        summary.update(passed=passed and summary['passed'], experimental=True, native_executed=True)
    except Exception as error:
        summary = {'passed': False, 'experimental': True, 'measurement_collection_failed': True,
                   'error_type': type(error).__name__, 'error': str(error)}
    publish(args.output / 'report.json', summary)
    raise SystemExit(0 if summary['passed'] else 1)

if __name__ == '__main__':
    main()
