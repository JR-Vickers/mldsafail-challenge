"""Native-only experimental gate, never promotes a benchmark score."""
import argparse
import json
from pathlib import Path
import statistics
from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate



def measurement_gates(rows):
    """Predeclared adoption gates; empty-worker CV is diagnostic only."""
    grouped = {name: [row for row in rows if row['fixture'] == name]
               for name in ('empty', 'child')}
    if any(len(values) < 30 for values in grouped.values()):
        raise ValueError('At least 30 paired measurements required')
    cpu = {name: [row['authoritative_cpu_usec'] for row in values]
           for name, values in grouped.items()}
    if any(value <= 0 for values in cpu.values() for value in values):
        raise ValueError('Positive authoritative CPU required')
    cv = {name: statistics.stdev(values) / statistics.mean(values)
          for name, values in cpu.items()}
    walls = sorted(row['wall_seconds'] for row in grouped['empty'])
    import math
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
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    instance = generate_mlwe('small', 0, 1).public
    fixtures = Path(__file__).parent / 'fixtures'
    rows = []
    passed = True
    try:
        schedule = [(name, repetition) for repetition in range(30) for name in ('empty', 'child')]
        schedule += [(name, 0) for name in ('clock_tampering', 'forged_timing', 'early_exit', 'malformed', 'hang')]
        for name, repetition in schedule:
            result = run(args.image, args.parent, args.cgroup_parent, fixtures / name,
                         instance.to_dict(), lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                         timeout=2 if name == 'hang' else 60)
            result.update(fixture=name, repetition=repetition)
            with (args.output / f'{name}-{repetition}.json').open('x') as stream:
                json.dump(result, stream)
            rows.append(result)
            expected = {'empty': 'no_answer', 'clock_tampering': 'no_answer',
                        'forged_timing': 'malformed', 'child': 'no_answer',
                        'early_exit': 'malformed', 'malformed': 'malformed', 'hang': 'timeout'}[name]
            passed &= result['status'] == expected and result['authoritative_cpu_usec'] > 0
        summary = measurement_gates(rows)
        summary.update(passed=passed and summary['passed'], experimental=True, native_executed=True)
    except Exception:
        summary = {'passed': False, 'experimental': True, 'measurement_collection_failed': True}
    with (args.output / 'report.json').open('x') as stream:
        json.dump(summary, stream)
    raise SystemExit(0 if summary['passed'] else 1)

if __name__ == '__main__':
    main()
