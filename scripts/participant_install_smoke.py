"""Verify an owner-supplied participant wheel in a new isolated local install.

No login, submission, publication or mutable existing installation is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def isolated_environment():
    environment = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        environment.pop(name, None)
    environment['PYTHONNOUSERSITE'] = '1'
    return environment


def validate_installed_identity(identity, install):
    install = Path(install).resolve()
    package = Path(identity['package_path']).resolve()
    if Path(identity['prefix']).resolve() != install or install not in package.parents:
        raise RuntimeError('Imported participant package is outside the fresh installation')


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
                                    stderr=subprocess.STDOUT, timeout=180,
                                    env=isolated_environment())
        (destination / (name + '.log')).chmod(0o600)
        record['checks'].append({'check': name, 'returncode': result.returncode})
        save()
        if result.returncode:
            raise RuntimeError('Participant smoke failed: ' + name)
    installer = Path(__file__).resolve().with_name('install.sh')
    install = destination / 'installed'
    run('install', ['sh', str(installer), str(wheel), expected, str(install)])
    run('installed-identity', [str(install / 'bin/python'), '-c',
        'import importlib.metadata,json,platform,sys,mldsafail; from pathlib import Path; print(json.dumps({"python":platform.python_version(),"platform":platform.platform(),"package":importlib.metadata.version("mldsafail-challenge"),"package_path":str(Path(mldsafail.__file__).resolve()),"prefix":sys.prefix}))'])
    record['installed_identity'] = json.loads((destination / 'installed-identity.log').read_text())
    validate_installed_identity(record['installed_identity'], install)
    if record['installed_identity']['package'] != record['package_version']:
        raise RuntimeError('This smoke protocol requires participant package 0.5.1')
    save()
    executable = str(install / 'bin/mldsafail')
    run('help', [executable, '--help'])
    workspace = destination / 'mlwe-workspace'
    run('mlwe-clone', [executable, 'clone', str(workspace)])
    candidates = list(workspace.rglob('solver.py'))
    if not any(hashlib.sha256(path.read_bytes()).hexdigest() == record['starter_sha256'] for path in candidates):
        raise RuntimeError('Approved starter bytes do not match installed clone')
    record['checks'].append({'check': 'approved-starter-bytes', 'passed': True})
    save()
    run('public-development-help', [executable, 'run', '--help'])
    if '--ledger' not in (destination / 'public-development-help.log').read_text():
        raise RuntimeError('Installed public development metadata contract is absent')
    run('installed-dependencies', [str(install / 'bin/python'), '-m', 'pip', 'freeze', '--all'])
    run('public-fixture-verification', [str(install / 'bin/python'), '-c',
        "from mldsafail.benchmark_v050.generator import generate_mlwe; "
        "from mldsafail.benchmark_v050.models import RecoveredSecret; "
        "from mldsafail.benchmark_v050.verify import verify_candidate; "
        "x=generate_mlwe('small',0,1); "
        "assert verify_candidate(x.public,RecoveredSecret(x.planted_s1,x.planted_s2).to_dict())['verified']"])
    record.update(complete=True, supported_workflow='public-mlwe-development',
                  solver_execution_tested=False, native_acceptance=False)
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
