"""Verify an owner-supplied participant wheel in a new isolated local install.

No login, submission, publication or mutable existing installation is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def smoke(wheel, expected, destination, starter):
    wheel, destination, starter = Path(wheel).resolve(), Path(destination).resolve(), Path(starter).resolve()
    if destination.exists():
        raise ValueError('Smoke destination must be new')
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
        raise ValueError('Wheel checksum mismatch')
    destination.mkdir(mode=0o700, parents=True)
    record = {'wheel_sha256': expected, 'starter_sha256': hashlib.sha256(starter.read_bytes()).hexdigest(),
              'package_version': '0.5.1', 'benchmark_version': '0.5.0', 'complete': False, 'checks': []}
    report = destination / 'smoke.json'
    def save():
        report.write_text(json.dumps(record, indent=2) + '\n')
        report.chmod(0o600)
    save()
    def run(name, arguments):
        # Logs remain local/protected; no network account operation is performed.
        with (destination / (name + '.log')).open('x') as output:
            result = subprocess.run(arguments, cwd=destination, stdout=output,
                                    stderr=subprocess.STDOUT, timeout=180)
        (destination / (name + '.log')).chmod(0o600)
        record['checks'].append({'check': name, 'returncode': result.returncode})
        save()
        if result.returncode:
            raise RuntimeError('Participant smoke failed: ' + name)
    installer = Path(__file__).resolve().with_name('install.sh')
    install = destination / 'installed'
    run('install', ['sh', str(installer), str(wheel), expected, str(install)])
    executable = str(install / 'bin/mldsafail')
    run('help', [executable, '--help'])
    workspace = destination / 'mlwe-workspace'
    run('mlwe-clone', [executable, 'clone', str(workspace)])
    candidates = list(workspace.rglob('solver.py'))
    if not any(hashlib.sha256(path.read_bytes()).hexdigest() == record['starter_sha256'] for path in candidates):
        raise RuntimeError('Approved starter bytes do not match installed clone')
    record['checks'].append({'check': 'approved-starter-bytes', 'passed': True})
    save()
    run('historical-clone', [executable, 'clone', '--benchmark-version', '0.4.0',
                             str(destination / 'historical-workspace')])
    run('historical-small', [executable, 'run', '--profile', 'small', '--no-record'])
    historical = json.loads((destination / 'historical-small.log').read_text())
    if historical['score'] != 3901:
        raise RuntimeError('Historical baseline smoke score changed')
    record.update(complete=True, historical_small_score=historical['score'])
    save()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--approved-starter', type=Path, required=True)
    args = parser.parse_args()
    try:
        record = smoke(args.wheel, args.sha256, args.destination, args.approved_starter)
        print(json.dumps({'participant_smoke_complete': record['complete'], 'wheel_sha256': record['wheel_sha256']}))
    except Exception:
        print(json.dumps({'participant_smoke_failed': True, 'partial_evidence_retained': True}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
