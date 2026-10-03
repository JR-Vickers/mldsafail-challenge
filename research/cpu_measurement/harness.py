"""Experimental host cgroup accounting. Never used by the production evaluator."""
from __future__ import annotations
import argparse
import fcntl
import os
import sys
import json
from pathlib import Path
import subprocess
import time
import uuid


def fields(path):
    return {key: int(value) for key, value in (line.split() for line in path.read_text().splitlines())}


def collect(parent, before):
    if fields(parent / 'cgroup.events')['populated']:
        raise RuntimeError('Accounting domain still has descendants')
    after = fields(parent / 'cpu.stat')['usage_usec']
    if after < before:
        raise RuntimeError('CPU counter regressed')
    return after - before


def prove_membership(pid, parent, cgroup_root=Path('/sys/fs/cgroup'), proc_root=Path('/proc')):
    lines = (proc_root / str(pid) / 'cgroup').read_text().splitlines()
    paths = [line[3:] for line in lines if line.startswith('0::')]
    if len(paths) != 1:
        raise RuntimeError('Missing unified cgroup membership')
    actual = cgroup_root / paths[0].lstrip('/')
    if not actual.resolve().is_relative_to(parent.resolve()) or actual.resolve() == parent.resolve():
        raise RuntimeError('Worker is outside the dedicated accounting parent')


def run(image, parent, cgroup_parent, source, public_input, verify, timeout=60):
    from mldsafail.benchmark_v050.execution import solver_snapshot
    from mldsafail.benchmark_v050.models import instance_from_dict
    public_input = json.loads(json.dumps(public_input))
    instance_from_dict(public_input)  # Fixed tiny profiles and serialization cap.
    import tempfile
    # Trusted callers sharing this parent serialize its complete accounting lifetime.
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'solver'
            solver_snapshot(source, snapshot)
            return _run(image, parent, cgroup_parent, snapshot, public_input, verify, timeout)
    finally:
        os.close(descriptor)


def _run(image, parent, cgroup_parent, source, public_input, verify, timeout=60):
    """Caller supplies a new persistent delegated parent and independent verifier.

    parent is the host path; cgroup_parent is the daemon's corresponding path.
    Only approved tiny-instance Python workspaces may be supplied.
    """
    public_input = json.loads(json.dumps(public_input))
    if sys.platform != 'linux':
        raise RuntimeError('Native Linux host required')
    info = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], timeout=30))
    if str(info.get('CgroupVersion')) != '2' or not any('rootless' in option for option in info.get('SecurityOptions', [])):
        raise RuntimeError('Rootless Docker with cgroup v2 required')
    if not image.startswith('sha256:') or len(image) != 71:
        raise ValueError('Immutable worker image required')
    if fields(parent / 'cgroup.events')['populated']:
        raise RuntimeError('Dedicated parent is not empty')
    before = fields(parent / 'cpu.stat')['usage_usec']
    name = 'cpu-proposal-' + uuid.uuid4().hex
    argv = ['docker', 'run', '--name', name, '--cgroup-parent', cgroup_parent,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '65534:65534',
            '--cpus', '1', '--memory', '2g', '--memory-swap', '2g', '--pids-limit', '64', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m',
            '--mount', f'type=bind,src={source.resolve()},dst=/solver,readonly',
            '-i', image]
    # Output goes to bounded files: no unbounded PIPE buffering.
    import tempfile
    status = 'measurement_failed'
    raw = b''
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
        try:
            # The reviewed adapter blocks on stdin until host membership is proven.
            membership_deadline = time.monotonic() + 10
            while True:
                inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name],
                                           capture_output=True, text=True, timeout=5)
                if inspected.returncode == 0:
                    pid = json.loads(inspected.stdout).get('Pid', 0)
                    if pid:
                        prove_membership(pid, parent)
                        break
                if time.monotonic() >= membership_deadline:
                    raise RuntimeError('Unable to prove worker accounting membership')
                time.sleep(.05)
            payload = json.dumps({'instance': public_input, 'solver': 'contestant'}).encode()
            while True:
                try:
                    process.communicate(payload, timeout=.05)
                    break
                except subprocess.TimeoutExpired:
                    payload = None
                    if os.fstat(stdout.fileno()).st_size > 1024 * 1024 or os.fstat(stderr.fileno()).st_size > 1024 * 1024:
                        status = 'output_limit'
                        break
                    if time.monotonic() - started >= timeout:
                        status = 'timeout'
                        break
            if status not in {'timeout', 'output_limit'}:
                if os.fstat(stdout.fileno()).st_size > 1024 * 1024 or os.fstat(stderr.fileno()).st_size > 1024 * 1024:
                    status = 'output_limit'
                else:
                    stdout.seek(0)
                    raw = stdout.read(1024 * 1024)
                    status = 'exited' if process.returncode == 0 else 'crash'
        finally:
            # Kill the container and every descendant before collecting the parent.
            subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=30)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
    deadline = time.monotonic() + 10
    while fields(parent / 'cgroup.events')['populated']:
        if time.monotonic() >= deadline:
            raise RuntimeError('Descendants survived cleanup; measurement unavailable')
        time.sleep(.05)
    cpu = collect(parent, before)  # Missing measurements raise; never accept reported timing.
    verified = False
    if status == 'exited':
        try:
            output = json.loads(raw)
            candidate = output.get('candidate')
            from mldsafail.benchmark_v050.models import instance_from_dict
            from mldsafail.benchmark_v050.verify import verify_candidate
            verified = verify_candidate(instance_from_dict(public_input), candidate)["verified"]
            if verified:
                verified = verify(public_input, candidate)
            if type(verified) is not bool:
                raise TypeError('Verifier must return a boolean decision')
            status = 'verified' if verified else ('no_answer' if candidate is None else 'invalid')
        except (ValueError, TypeError, AttributeError):
            status = 'malformed'
    return {'status': status, 'verified': verified, 'authoritative_cpu_usec': cpu,
            'wall_seconds': time.monotonic() - started, 'experimental': True,
            'measurement_method': 'cgroup-v2-usage-usec',
            'counter_before_usec': before, 'counter_after_usec': before + cpu}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'cpu': fields(args.parent / 'cpu.stat'),
                      'events': fields(args.parent / 'cgroup.events'),
                      'native_run_required': True}))

if __name__ == '__main__':
    main()
