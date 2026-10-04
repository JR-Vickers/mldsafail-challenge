"""Run admission gates in an owned disposable native PostgreSQL container."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


def run(image, output):
    if sys.platform != 'linux' or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('Native Linux and immutable database image required')
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True):
        raise ValueError('Retained source must be clean')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    identity = uuid.uuid4().hex
    name = 'launch-postgres-' + identity
    label = 'org.mldsafail.native-postgres=' + identity
    database = 'mldsafail_acceptance_' + identity
    password = uuid.uuid4().hex
    report = {'source_commit': commit, 'database_image': image, 'passed': False,
              'cleanup_complete': False, 'protocol': 'three synchronized native PostgreSQL admission/ownership tests in empty disposable database'}
    def command(args):
        return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=90).strip()
    try:
        command(['docker', 'run', '-d', '--name', name, '--label', label,
                 '--tmpfs', '/var/lib/postgresql/data:rw,nosuid,nodev',
                 '-p', '127.0.0.1::5432', '-e', 'POSTGRES_DB=' + database,
                 '-e', 'POSTGRES_USER=acceptance', '-e', 'POSTGRES_PASSWORD=' + password, image])
        deadline = time.monotonic() + 60
        while subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'acceptance', '-d', database], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError('Disposable PostgreSQL startup timed out')
            time.sleep(.5)
        info = json.loads(command(['docker', 'inspect', name]))[0]
        ports = info['NetworkSettings']['Ports']['5432/tcp']
        if len(ports) != 1 or ports[0]['HostIp'] != '127.0.0.1' or info['Image'] != image:
            raise RuntimeError('Disposable PostgreSQL identity/exposure mismatch')
        report['postgresql_version'] = command(['docker', 'exec', name, 'postgres', '--version'])
        environment = dict(os.environ, MLDSAFAIL_NATIVE_TEST_DATABASE_URL='postgresql+psycopg://acceptance:' + password + '@127.0.0.1:' + ports[0]['HostPort'] + '/' + database)
        with (output / 'tests.log').open('w') as log:
            result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_native_postgres_admission.py', '-q'], cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        report['test_exit_code'] = result.returncode
        if result.returncode:
            raise RuntimeError('Native admission tests failed; private log retained')
        report['tests_passed'] = True
    finally:
        try:
            owned = command(['docker', 'ps', '-aq', '--filter', 'label=' + label])
            for identifier in owned.splitlines():
                command(['docker', 'rm', '-f', identifier])
            report['cleanup_complete'] = not command(['docker', 'ps', '-aq', '--filter', 'label=' + label])
            report['passed'] = report.get('tests_passed', False) and report['cleanup_complete']
        except Exception as error:
            report['cleanup_error_type'] = type(error).__name__
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if not report['cleanup_complete']:
            raise RuntimeError('Owned disposable database cleanup incomplete')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(run(args.image, args.output)))
