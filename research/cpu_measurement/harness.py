"""Experimental host cgroup accounting. Never used by the production evaluator."""
from __future__ import annotations
import argparse
import os
import sys
import json
from pathlib import Path
import subprocess
import time
import uuid
import selectors
from research.cpu_measurement.ownership import Ownership


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


def run(image, parent, cgroup_parent, source, public_input, verify, timeout=60, evidence_metadata=None, ownership_directory=None):
    from mldsafail.benchmark_v050.execution import solver_snapshot
    from mldsafail.benchmark_v050.models import instance_from_dict
    public_input = json.loads(json.dumps(public_input))
    instance_from_dict(public_input)  # Fixed tiny profiles and serialization cap.
    import tempfile
    # A private journal survives owner death. No new invocation can reclaim an
    # interrupted generation until an operator independently proves cleanup.
    if ownership_directory is None:
        raise ValueError('Private durable ownership directory required')
    with Ownership(ownership_directory, parent) as owner:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'solver'
            solver_snapshot(source, snapshot)
            owner.mutation('invocation_intent', image=image)
            result = _run(image, parent, cgroup_parent, snapshot, public_input, verify, timeout, owner=owner)
            if evidence_metadata:
                result.update(evidence_metadata)
            result['cleanup_complete'] = True
            return owner.finish(result)


def _run(image, parent, cgroup_parent, source, public_input, verify, timeout=60, owner=None):
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
    if owner is not None:
        owner.mutation('container_create_intent', name=name, counter_before_usec=before)
    argv = ['docker', 'run', '--name', name, '--cgroup-parent', cgroup_parent,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '65534:65534',
            '--cpus', '1', '--memory', '2g', '--memory-swap', '2g', '--pids-limit', '64', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m',
            '--mount', f'type=bind,src={source.resolve()},dst=/solver,readonly',
            '-i', image]
    status = 'measurement_failed'
    raw = b''
    started = time.monotonic()
    process = None
    original = None
    cleanup_errors = []
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        if owner is not None:
            owner.mutation('input_delivery_intent', worker_pid=pid)
        payload = json.dumps({'instance': public_input, 'solver': 'contestant'}).encode()
        status, raw = capture(process, payload, started + timeout)
    except BaseException as error:
        original = error
    finally:
        # Each cleanup action is independent: a failed Docker removal must not
        # skip process cleanup. Preserve both the original and cleanup failures.
        if owner is not None:
            owner.mutation('cleanup_intent', name=name)
        try:
            subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=30)
        except BaseException as error:
            cleanup_errors.append(('container_remove', repr(error)))
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
            except BaseException as error:
                cleanup_errors.append(('process_cleanup', repr(error)))
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
    if original is not None or cleanup_errors:
        raise RuntimeError(json.dumps(dict(original=repr(original), cleanup_errors=cleanup_errors))) from original
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


def capture(process, payload, deadline, cap=1024 * 1024):
    """Bound each stream in memory; never spool unchecked contestant output."""
    buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
    with selectors.DefaultSelector() as selector:
        for stream in buffers:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE)
        remaining = memoryview(payload)
        while selector.get_map():
            if time.monotonic() >= deadline:
                return 'timeout', bytes(buffers[process.stdout])
            for key, mask in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                stream = key.fileobj
                if mask & selectors.EVENT_WRITE:
                    try:
                        count = os.write(stream.fileno(), remaining)
                        remaining = remaining[count:]
                    except BrokenPipeError:
                        remaining = remaining[:0]
                    if not remaining:
                        selector.unregister(stream)
                        stream.close()
                else:
                    data = os.read(stream.fileno(), min(65536, cap + 1 - len(buffers[stream])))
                    if not data:
                        selector.unregister(stream)
                    elif len(buffers[stream]) + len(data) > cap:
                        return 'output_limit', bytes(buffers[process.stdout])
                    else:
                        buffers[stream].extend(data)
        process.wait(timeout=max(.001, deadline - time.monotonic()))
        return ('exited' if process.returncode == 0 else 'crash'), bytes(buffers[process.stdout])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'cpu': fields(args.parent / 'cpu.stat'),
                      'events': fields(args.parent / 'cgroup.events'),
                      'native_run_required': True}))

if __name__ == '__main__':
    main()
