"""Native-only experimental gate, never promotes a benchmark score."""
import argparse
import json
from pathlib import Path
import statistics
from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate


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
        for name in ['empty', 'clock_tampering', 'forged_timing', 'child', 'early_exit', 'malformed', 'hang']:
            for repetition in range(30 if name in {'empty', 'child'} else 1):
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
        grouped = {name: [row['authoritative_cpu_usec'] for row in rows if row['fixture'] == name]
                   for name in ['empty', 'child']}
        passed &= statistics.median(grouped['child']) > statistics.median(grouped['empty'])
        summary = {'passed': passed, 'experimental': True, 'native_executed': True,
                   'medians_usec': {name: statistics.median(values) for name, values in grouped.items()},
                   'coefficient_of_variation': {name: statistics.stdev(values) / statistics.mean(values)
                                               for name, values in grouped.items()}}
    except Exception:
        summary = {'passed': False, 'experimental': True, 'measurement_collection_failed': True}
    with (args.output / 'report.json').open('x') as stream:
        json.dump(summary, stream)
    raise SystemExit(0 if summary['passed'] else 1)

if __name__ == '__main__':
    main()
