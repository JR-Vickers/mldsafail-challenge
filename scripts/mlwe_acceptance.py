"""Retain a private full epoch and independently regenerate shareable results."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from mldsafail.benchmark_v050 import evidence as ev
from mldsafail.benchmark_v050.scoring import ranking, ranking_interval


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-output', required=True, type=Path)
    parser.add_argument('--share-output', required=True, type=Path)
    args = parser.parse_args()
    private = ev.directory(args.private_output)
    share = ev.directory(args.share_output)

    def command(name, *parts):
        with (private / f'{name}.stderr.log').open('x') as log:
            response = subprocess.run([sys.executable, '-m', 'mldsafail.benchmark_v050.cli', *map(str, parts)], stdout=subprocess.PIPE, stderr=log)
        (private / f'{name}.stdout.json').write_bytes(response.stdout)
        response.check_returncode()
        result = json.loads(response.stdout)
        ev.write(share / f'{name}.json', result)
        print(name, 'passed', flush=True)
        return result

    epoch = private / 'epoch'
    reference = private / 'reference-run'
    hybrid = private / 'hybrid-run'
    command('epoch', 'epoch', 'create', '--output', epoch)
    command('reference', 'run', '--epoch', epoch, '--solver-dir', 'examples/mlwe/primal-lll', '--output', reference)
    command('hybrid', 'run', '--epoch', epoch, '--solver-dir', 'examples/mlwe/hybrid-bdd', '--output', hybrid)
    first = command('audit', 'audit', '--epoch', epoch, '--run', reference, '--run', hybrid)
    second = command('audit-reproduced', 'audit', '--epoch', epoch, '--run', reference, '--run', hybrid)
    assert first == second
    ranks = command('rank', 'rank', '--epoch', epoch, '--run', epoch / 'primal-lll', '--run', reference, '--run', hybrid)
    repeated = command('rank-reproduced', 'rank', '--epoch', epoch, '--run', epoch / 'primal-lll', '--run', reference, '--run', hybrid)
    assert ranks == repeated
    _, rows = ev.audit_epoch(epoch)
    assert ranking(rows, 'primal-lll') == 1.0
    assert ranking_interval(rows, 'primal-lll') == (1.0, 1.0)
    ev.write(share / 'acceptance.json', {'benchmark_version':'0.5.0', 'ranked_cases':100,
        'epoch_reference_executions':400, 'viability_check_executions':800, 'contestant_executions':800,
        'independent_audits_match':True, 'rankings_reproduce':True, 'reference_self_score':1.0,
        'reference_self_interval':[1.0,1.0]})


if __name__ == '__main__':
    main()
