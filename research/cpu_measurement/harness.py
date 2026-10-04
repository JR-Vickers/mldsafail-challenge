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
import hashlib
import platform
import base64
import shutil
from research.cpu_measurement.ownership import Ownership, sync_tree, canonical_directory


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


def run(image, parent, cgroup_parent, source, public_input, verify, timeout=60, evidence_metadata=None, ownership_directory=None, epoch="isolated-native-feasibility"):
    from mldsafail.benchmark_v050.execution import solver_snapshot
    from mldsafail.benchmark_v050.models import instance_from_dict
    public_input = json.loads(json.dumps(public_input))
    instance_from_dict(public_input)  # Fixed tiny profiles and serialization cap.
    import tempfile
    # A private journal survives owner death. No new invocation can reclaim an
    # interrupted generation until an operator independently proves cleanup.
    if ownership_directory is None:
        raise ValueError('Private durable ownership directory required')
    if Path(ownership_directory).absolute() != canonical_directory(parent).absolute():
        raise ValueError('Ownership directory must be the canonical parent-scoped directory: ' + str(canonical_directory(parent)))
    with Ownership(ownership_directory, parent) as owner:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'solver'
            solver_snapshot(source, snapshot)
            # The worker UID must traverse its readonly bind root even when the
            # supervisor unit uses UMask=0077. Only this disposable mount tree
            # is readable; private archives remain behind owner-only paths.
            for path in [snapshot, *(path for path in snapshot.rglob('*') if path.is_dir())]:
                path.chmod(0o755)
            artifact_name = owner.record['generation'] + '-source'
            shutil.copytree(snapshot, owner.directory / artifact_name)
            archive = owner.directory / artifact_name
            for path in [archive, *(path for path in archive.rglob('*') if path.is_dir())]:
                path.chmod(0o700)
            sync_tree(owner.directory / artifact_name)
            binding = dict(
                source_sha256=hashlib.sha256(json.dumps({path.relative_to(snapshot).as_posix():
                    dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    for path in sorted(snapshot.rglob('*.py'))}, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                image=image, epoch=epoch,
                supervisor_source_sha256=hashlib.sha256(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(Path(__file__).parent.glob('*.py'))}, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                source_commit=subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[2]), 'rev-parse', 'HEAD'], timeout=10).decode().strip(),
                host=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),
                kernel=platform.release(), docker={'discovery_pending': True})
            if evidence_metadata and not set(evidence_metadata) <= {'fixture', 'repetition', 'suite_id', 'source_sha256', 'image', 'host_identity'}:
                raise ValueError('Untrusted evidence metadata field')
            owner.mutation('invocation_intent', image=image, source_artifact=artifact_name,
                           binding=binding, public_input=public_input, metadata=evidence_metadata or {})
            result = _run(image, parent, cgroup_parent, snapshot, public_input, verify, timeout, owner=owner)
            result.update(evidence_metadata or {})
            result['source_artifact'] = artifact_name
            result['binding'] = dict(binding, docker=result.pop('docker_identity'))
            result['cleanup_complete'] = True
            result = owner.finish(result)
            from research.cpu_measurement.audit import audit_journal
            audit_journal(owner.directory)
            return result


def _run(image, parent, cgroup_parent, source, public_input, verify, timeout=60, owner=None):
    """Caller supplies a new persistent delegated parent and independent verifier.

    parent is the host path; cgroup_parent is the daemon's corresponding path.
    Only approved tiny-instance Python workspaces may be supplied.
    """
    public_input = json.loads(json.dumps(public_input))
    if sys.platform != 'linux':
        raise RuntimeError('Native Linux host required')
    info = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], timeout=30))
    if owner is not None:
        owner.mutation('docker_discovered', docker=info)
    if str(info.get('CgroupVersion')) != '2' or not any('rootless' in option for option in info.get('SecurityOptions', [])):
        raise RuntimeError('Rootless Docker with cgroup v2 required')
    if not image.startswith('sha256:') or len(image) != 71:
        raise ValueError('Immutable worker image required')
    validate_delegation(parent)
    if fields(parent / 'cgroup.events')['populated']:
        raise RuntimeError('Dedicated parent is not empty')
    before = fields(parent / 'cpu.stat')['usage_usec']
    membership = []
    observations = []
    capture_evidence = {}
    name = 'cpu-proposal-' + uuid.uuid4().hex
    if owner is not None:
        owner.mutation('container_create_intent', name=name, image=image,
                       cgroup_parent=cgroup_parent, counter_before_usec=before)
    argv = ['docker', 'run', '--label', 'org.mldsafail.cpu-generation=' + (owner.record['generation'] if owner else 'isolated-unit-probe'),
            '--name', name, '--cgroup-parent', cgroup_parent,
            '--cgroupns', 'private', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
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
        if owner is not None:
            owner.mutation('host_client_spawned', pid=process.pid,
                           start_ticks=process_start_ticks(process.pid), **process_identity(process.pid))
        membership_deadline = time.monotonic() + 10
        while True:
            inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', name],
                                       capture_output=True, text=True, timeout=5)
            if inspected.returncode == 0:
                pid = json.loads(inspected.stdout).get('Pid', 0)
                if pid:
                    prove_membership(pid, parent)
                    worker_path = worker_cgroup(pid)
                    membership.append(dict(worker_pid=pid, cgroup=worker_path.as_posix()))
                    break
            if time.monotonic() >= membership_deadline:
                raise RuntimeError('Unable to prove worker accounting membership')
            time.sleep(.05)
        if owner is not None:
            owner.mutation('input_delivery_intent', worker_pid=pid)
        payload = json.dumps({'instance': public_input, 'solver': 'contestant'}, sort_keys=True, separators=(',', ':')).encode()
        last_counter = before
        def observe():
            nonlocal last_counter
            if owner is not None:
                owner.check_identity()
            prove_exclusive(parent, worker_path)
            usage = fields(parent / "cpu.stat")["usage_usec"]
            if usage < last_counter:
                raise RuntimeError("Accounting counter regressed during execution")
            last_counter = usage
            observed = time.monotonic()
            if not observations or observed - observations[-1]['monotonic'] >= .05:
                if len(observations) >= 10000:
                    raise RuntimeError('Accounting observation evidence limit exceeded')
                observations.append(dict(usage_usec=usage, monotonic=observed))
        observe()
        def delivered():
            if owner is not None:
                owner.mutation('input_delivered', bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        status, raw = capture(process, payload, started + timeout, observe=observe, evidence=capture_evidence, on_input=delivered)
    except BaseException as error:
        original = error
    finally:
        # Each cleanup action is independent: a failed Docker removal must not
        # skip process cleanup. Preserve both the original and cleanup failures.
        if owner is not None:
            try:
                owner.mutation('cleanup_intent', name=name)
            except BaseException as error:
                cleanup_errors.append(('cleanup_journal', repr(error)))
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
    if owner is not None and (original is not None or cleanup_errors):
        try:
            owner.update('running', failure_diagnostics=dict(
                schema='mldsafail.cpu-failure.v1', classification='infrastructure_failure',
                original=repr(original), cleanup_errors=cleanup_errors,
                membership=membership, observations=observations, capture=capture_evidence,
                counter_before_usec=before, authoritative_delta_available=False))
        except BaseException as journal_error:
            if original is not None:
                original.add_note('Failure evidence publication failed: ' + repr(journal_error))
    if isinstance(original, (KeyboardInterrupt, SystemExit)):
        for operation, detail in cleanup_errors:
            original.add_note(operation + ': ' + detail)
        raise original
    if original is not None or cleanup_errors:
        raise RuntimeError(json.dumps(dict(original=repr(original), cleanup_errors=cleanup_errors))) from original
    if owner is not None:
        owner.update('running', partial_measurement=dict(
            schema='mldsafail.cpu-partial.v1', status=status, counter_before_usec=before,
            membership=membership, observations=observations, capture=capture_evidence,
            authoritative_delta_available=False, cleanup_proof_pending=True))
    deadline = time.monotonic() + 10
    while fields(parent / 'cgroup.events')['populated']:
        if time.monotonic() >= deadline:
            raise RuntimeError('Descendants survived cleanup; measurement unavailable')
        time.sleep(.05)
    cpu = collect(parent, before)  # Missing measurements raise; never accept reported timing.
    execution_status = status
    verified = False
    if status != 'exited' and raw:
        try:
            output = json.loads(raw)
            candidate = output.get('candidate')
            from mldsafail.benchmark_v050.models import instance_from_dict
            from mldsafail.benchmark_v050.verify import verify_candidate
            if candidate is not None and not verify_candidate(instance_from_dict(public_input), candidate)['verified']:
                status = 'invalid'
        except (ValueError, TypeError, AttributeError):
            pass
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
    finished = time.monotonic()
    return {'status': status, 'execution_status': execution_status, 'verified': verified, 'authoritative_cpu_usec': cpu,
            'wall_seconds': finished - started, 'experimental': True,
            'measurement_method': 'cgroup-v2-usage-usec',
            'counter_before_usec': before, 'counter_after_usec': before + cpu,
            'accounting_parent': parent.resolve().as_posix(), 'observations': observations,
            'membership': membership, 'input_delivery': 'membership_proven_before_delivery',
            'termination': 'domain_empty', 'output_sha256': hashlib.sha256(raw).hexdigest(),
            'public_input': public_input, 'raw_stdout_base64': base64.b64encode(raw).decode(),
            'worker_returncode': process.returncode, 'capture': capture_evidence,
            'declared_timeout_seconds': timeout, 'started_monotonic': started,
            'deadline_monotonic': started + timeout, 'finished_monotonic': finished,
            'docker_identity': dict(cgroup_version=info['CgroupVersion'],
                                    cgroup_driver=info.get('CgroupDriver', 'unknown'),
                                    server_version=info.get('ServerVersion', 'unknown'))}


def process_identity(pid):
    status = (Path('/proc') / str(pid) / 'status').read_text().splitlines()
    uids = [line.split()[1] for line in status if line.startswith('Uid:')]
    if len(uids) != 1:
        raise RuntimeError('Missing host client UID identity')
    with (Path('/proc') / str(pid) / 'cmdline').open('rb') as stream:
        command = stream.read(128 * 1024 + 1)
    if not command or len(command) > 128 * 1024:
        raise RuntimeError('Missing or oversized host client command identity')
    return dict(uid=int(uids[0]), cmdline_sha256=hashlib.sha256(command).hexdigest())


def process_start_ticks(pid):
    return int((Path('/proc') / str(pid) / 'stat').read_text().rpartition(')')[2].split()[19])


def validate_delegation(parent):
    identity = parent.stat(follow_symlinks=False)
    if identity.st_uid != os.getuid() or identity.st_mode & 0o022:
        raise RuntimeError('Dedicated parent must have exclusive owner write access')
    if (parent / 'cgroup.type').read_text().strip() != 'domain':
        raise RuntimeError('Dedicated accounting parent must be a domain')
    if 'cpu' not in (parent / 'cgroup.controllers').read_text().split():
        raise RuntimeError('CPU controller delegation is missing')


def worker_cgroup(pid, cgroup_root=Path('/sys/fs/cgroup'), proc_root=Path('/proc')):
    lines = (proc_root / str(pid) / 'cgroup').read_text().splitlines()
    paths = [line[3:] for line in lines if line.startswith('0::')]
    if len(paths) != 1:
        raise RuntimeError('Missing unified cgroup membership')
    return cgroup_root / paths[0].lstrip('/')


def prove_exclusive(parent, authorized):
    """Reject populated siblings/direct parent members at each observation.

    Continuous ownership and exclusive trusted delegation remain prerequisites;
    polling alone cannot detect a transient trusted-host intruder.
    """
    parent = parent.resolve()
    authorized = authorized.resolve()
    if authorized == parent or not authorized.is_relative_to(parent):
        raise RuntimeError('Invalid authorized descendant domain')
    for path in [parent / 'cgroup.procs', *parent.rglob('cgroup.procs')]:
        domain = path.parent.resolve()
        try:
            members = path.read_text().strip()
        except FileNotFoundError:
            if domain != parent and not path.parent.exists():
                continue  # A removed empty descendant cannot contain processes.
            raise
        if not domain.is_relative_to(authorized) and members:
            raise RuntimeError('Unauthorized accounting domain member')


def capture(process, payload, deadline, cap=1024 * 1024, observe=lambda: None, evidence=None, on_input=lambda: None):
    """Bound each stream in memory; never spool unchecked contestant output."""
    buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
    def stop(status, overflow=None):
        if evidence is not None:
            evidence.update(stopped_monotonic=time.monotonic(), overflow=overflow, cap_bytes=cap,
                            stderr_base64=base64.b64encode(bytes(buffers[process.stderr])).decode(),
                            stderr_sha256=hashlib.sha256(bytes(buffers[process.stderr])).hexdigest(),
                            stdout_base64=base64.b64encode(bytes(buffers[process.stdout])).decode())
        return status, bytes(buffers[process.stdout])
    try:
        with selectors.DefaultSelector() as selector:
            for stream in buffers:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
            remaining = memoryview(payload)
            while selector.get_map() or process.poll() is None:
                observe()
                if time.monotonic() >= deadline:
                    return stop('timeout')
                if not selector.get_map():
                    time.sleep(min(.05, max(0, deadline - time.monotonic())))
                for key, mask in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                    stream = key.fileobj
                    if mask & selectors.EVENT_WRITE:
                        broken = False
                        try:
                            count = os.write(stream.fileno(), remaining)
                            remaining = remaining[count:]
                        except BrokenPipeError:
                            broken = True
                            remaining = remaining[:0]
                        if not remaining:
                            selector.unregister(stream)
                            stream.close()
                            if not broken:
                                on_input()
                    else:
                        data = os.read(stream.fileno(), min(65536, cap + 1 - len(buffers[stream])))
                        if not data:
                            selector.unregister(stream)
                        elif len(buffers[stream]) + len(data) > cap:
                            return stop('output_limit', dict(stream='stdout' if stream is process.stdout else 'stderr',
                                                             observed_bytes=len(buffers[stream]) + len(data)))
                        else:
                            buffers[stream].extend(data)
            process.wait()
            return stop('exited' if process.returncode == 0 else 'crash')
    except BaseException:
        stop('infrastructure_failure')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'cpu': fields(args.parent / 'cpu.stat'),
                      'events': fields(args.parent / 'cgroup.events'),
                      'native_run_required': True}))

if __name__ == '__main__':
    main()
