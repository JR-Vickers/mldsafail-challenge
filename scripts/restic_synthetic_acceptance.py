"""Synthetic restic crypto/restore acceptance; never accesses a live repository."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

LINUX_BINARY_SHA256 = '01143daba61a1dc8afb0cb3d03ba83e6b118f55b6b146b27473a09efc3df13d6'


def run(binary, output):
    if hashlib.sha256(binary.read_bytes()).hexdigest() != LINUX_BINARY_SHA256:
        raise ValueError('Pinned Linux amd64 restic binary required')
    if output.exists():
        raise ValueError('Evidence output must be new')
    root = Path(tempfile.mkdtemp(prefix='restic-synthetic-'))
    source = root / 'source'
    source.mkdir(mode=0o700)
    (source / 'synthetic.txt').write_text('synthetic recovery smoke only')
    password = root / 'password'
    password.write_text('synthetic-test-password')
    password.chmod(0o600)
    env = {**os.environ, 'RESTIC_REPOSITORY': str(root / 'repository'),
           'RESTIC_PASSWORD_FILE': str(password), 'GOMAXPROCS': '2'}
    stages = []
    def call(*args, reject=False):
        result = subprocess.run([str(binary), '--no-cache', *args], env=env,
                                capture_output=True, timeout=120)
        passed = result.returncode != 0 if reject else result.returncode == 0
        stages.append({'operation': args[0], 'expected_rejection': reject, 'passed': passed})
        if not passed:
            raise RuntimeError('Synthetic restic gate failed')
    try:
        call('init')
        call('backup', str(source))
        call('check', '--read-data')
        call('restore', 'latest', '--target', str(root / 'restore'))
        restored = root / 'restore' / str(source).lstrip('/') / 'synthetic.txt'
        if restored.read_bytes() != (source / 'synthetic.txt').read_bytes():
            raise ValueError('Synthetic restore bytes differ')
        wrong = root / 'wrong-password'
        wrong.write_text('incorrect-test-password')
        wrong.chmod(0o600)
        env['RESTIC_PASSWORD_FILE'] = str(wrong)
        call('snapshots', reject=True)
        env['RESTIC_PASSWORD_FILE'] = str(password)
        pack = next(p for p in (root / 'repository/data').rglob('*') if p.is_file())
        pack.chmod(0o600)
        data = bytearray(pack.read_bytes())
        data[len(data) // 2] ^= 1
        pack.write_bytes(data)
        call('check', '--read-data', reject=True)
        report = {'passed': True, 'synthetic_encrypted_restore': True,
                  'wrong_password_rejected': True, 'corrupted_pack_rejected': True}
    except Exception:
        report = {'passed': False}
    report.update(stages=stages, s3_tested=False, native_rootless_tested=False)
    output.write_text(json.dumps(report, indent=2))
    output.chmod(0o600)
    # Retain failed fixtures; success fixtures may be removed explicitly by the owner.
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.binary, args.output)
    print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)
