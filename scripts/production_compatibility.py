"""Compare source-bound application rollback identities without changing cohorts."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(candidate, rollback):
    def subset(manifest, prefix):
        return {name: value for name, value in manifest['source_files_sha256'].items()
                if name.startswith(prefix)}
    def identity(files):
        return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    checks = {}
    inventories = {}
    for name, prefix in (('frozen_benchmark', 'src/mldsafail/benchmark_v050/'),
                         ('schema', 'migrations/'), ('hosted_evaluator', 'src/mldsafail/evaluator/')):
        left, right = subset(candidate, prefix), subset(rollback, prefix)
        checks[name] = bool(left) and left == right
        inventories[name] = dict(candidate_sha256=identity(left), rollback_sha256=identity(right),
                                 changed_files=sorted(key for key in left.keys() | right.keys()
                                                      if left.get(key) != right.get(key)))
    for name in ('uv.lock', 'deploy/worker-linux-amd64.requirements.txt'):
        left = candidate['source_files_sha256'].get(name)
        right = rollback['source_files_sha256'].get(name)
        checks[name] = bool(left) and left == right
    return dict(schema='mldsafail.production-source-compatibility.v1',
                candidate_source=candidate['source_commit'], rollback_source=rollback['source_commit'],
                checks=checks, inventories=inventories, compatible=all(checks.values()),
                same_environment_required=True, production_activation=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-manifest', type=Path, required=True)
    parser.add_argument('--rollback-manifest', type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.candidate_manifest.read_text()), json.loads(args.rollback_manifest.read_text()))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['compatible'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
