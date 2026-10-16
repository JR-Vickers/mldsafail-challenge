"""Linux trusted-client gate, durable process identities and cgroup cleanup.

Each trusted CLI executes inside a fresh delegated cgroup. The durable birth
gate precedes mutation; cleanup kills and proves emptiness of that exact domain.
"""
import hashlib
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid


def identity(pid):
    root = Path('/proc') / str(pid)
    stat = (root / 'stat').read_text()
    fields = stat[stat.rindex(')') + 2:].split()
    return dict(pid=pid, start_ticks=int(fields[19]), uid=root.stat().st_uid,
                session=int(fields[3]), group=int(fields[2]),
                cmdline_sha256=hashlib.sha256((root / 'cmdline').read_bytes()).hexdigest(),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def domain_identity(path):
    path = Path(path)
    if path.is_symlink() or path.resolve() != path:
        raise RuntimeError('Owned cgroup path must be canonical')
    info = path.stat()
    return {'path': str(path), 'device': info.st_dev, 'inode': info.st_ino,
            'boot_id': boot_id(), 'uid': info.st_uid, 'mode': info.st_mode & 0o777}


def verify_domain(entry):
    expected = entry['cgroup']
    if expected['boot_id'] != boot_id():
        return None  # Reboot destroyed this kernel domain; never signal reuse.
    path = Path(expected['path'])
    if not path.exists():
        return None
    if domain_identity(path) != expected:
        raise RuntimeError('Owned cgroup identity mismatch')
    return path


def populated(path):
    values = dict(line.split() for line in (path / 'cgroup.events').read_text().splitlines())
    return values['populated'] == '1'


def stop(entry):
    if 'cgroup' not in entry:
        intent = entry.get('cgroup_intent')
        if intent is None or intent['parent']['boot_id'] != boot_id():
            return
        parent = Path(intent['parent']['path'])
        if domain_identity(parent) != intent['parent']:
            raise RuntimeError('Owned cgroup parent identity mismatch')
        path = parent / intent['name']
        if path.name != 'mldsafail-client-' + entry['id']:
            raise RuntimeError('Invalid owned cgroup intent')
        if path.exists():
            # No process may enter before the inode-bound receipt was saved.
            if populated(path):
                raise RuntimeError('Unacknowledged client domain unexpectedly populated')
            domain_identity(path)
            path.rmdir()
        return
    path = verify_domain(entry)
    if path is None:
        return
    # The birth gate moves the child before exec. All descendants inherit this
    # exact kernel domain, regardless of CLI exit or process/session changes.
    try:
        (path / 'cgroup.kill').write_text('1')
        deadline = time.monotonic() + 15
        while populated(path):
            if time.monotonic() >= deadline:
                raise RuntimeError('Owned client cgroup remains populated')
            time.sleep(.05)
        if verify_domain(entry) is not None:
            path.rmdir()
    except FileNotFoundError:
        # A concurrent exact-owned cleanup can remove an empty kernel domain.
        # Missing pseudo-files in an existing/replaced domain are not success.
        if verify_domain(entry) is not None:
            raise


def prepare_domain(entry, parent):
    if parent is None:
        raise RuntimeError('Explicit delegated operator client cgroup root required')
    parent = Path(parent)
    domain_identity(parent)
    parent_info = parent.stat()
    if parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o022:
        raise RuntimeError('Operator cgroup parent must have exclusive owner write access')
    if (parent / 'cgroup.type').read_text().strip() != 'domain':
        raise RuntimeError('Operator cgroup parent must be a domain')
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    native = False
    for row in mounts:
        before, after = row.split(' - ', 1)
        mount = Path(before.split()[4].replace('\\040', ' '))
        if after.split()[0] == 'cgroup2' and (parent == mount or mount in parent.parents):
            native = True
    if not native:
        raise RuntimeError('Operator parent requires native cgroup v2 filesystem')
    if not (parent / 'cgroup.procs').is_file():
        raise RuntimeError('Operator parent is not a native delegated cgroup')
    path = parent / ('mldsafail-client-' + entry['id'])
    entry['cgroup_intent'] = {'parent': domain_identity(parent), 'name': path.name}
    return path


def capture(process, payload, timeout, buffers, observe, cap=8 * 1024 * 1024):
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        source = payload if hasattr(payload, 'read') else None
        remaining = memoryview(source.read(65536) if source is not None else (payload or b''))
        if process.stdin is not None:
            os.set_blocking(process.stdin.fileno(), False)
            if remaining:
                selector.register(process.stdin, selectors.EVENT_WRITE)
            else:
                process.stdin.close()
        while selector.get_map() or process.poll() is None:
            observe()
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired('owned command', timeout)
            if not selector.get_map():
                time.sleep(min(.05, max(0, deadline - time.monotonic())))
            for key, mask in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                stream = key.fileobj
                if mask & selectors.EVENT_WRITE:
                    try:
                        remaining = remaining[os.write(stream.fileno(), remaining):]
                    except BrokenPipeError:
                        remaining = remaining[:0]
                        source = None
                    if not remaining and source is not None:
                        remaining = memoryview(source.read(65536))
                    if not remaining:
                        selector.unregister(stream)
                        stream.close()
                else:
                    name = 'stdout' if stream is process.stdout else 'stderr'
                    data = os.read(stream.fileno(), min(65536, cap + 1 - len(buffers[name])))
                    if not data:
                        selector.unregister(stream)
                    elif len(buffers[name]) + len(data) > cap:
                        raise RuntimeError('Owned command output limit exceeded')
                    else:
                        buffers[name].extend(data)
        process.wait()


def write_stream(stream, data):
    try:
        stream.write(data)
    except TypeError:
        stream.write(data.decode(errors='replace'))
    stream.flush()


def secure_created_domain(entry, domain):
    """Secure only the child just created by this invocation before admission."""
    created = domain_identity(domain)
    if created['uid'] != os.getuid():
        raise RuntimeError('Fresh child cgroup owner mismatch')
    entry['cgroup'] = created  # Exact birth retained even if permission setup fails.
    descriptor = os.open(domain, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino, info.st_uid) != (created['device'], created['inode'], created['uid']):
            raise RuntimeError('Fresh child cgroup identity changed before permissions')
        # cgroupfs can inherit 0775 despite mkdir mode/umask. No process may be
        # admitted until this newly owned inode is exclusive to its owner.
        os.fchmod(descriptor, 0o700)
        info = os.fstat(descriptor)
        secured = dict(created, mode=info.st_mode & 0o777)
        entry['cgroup'] = secured
        if ((info.st_dev, info.st_ino, info.st_uid) != (created['device'], created['inode'], created['uid']) or
                secured['mode'] != 0o700 or domain_identity(domain) != secured):
            raise RuntimeError('Fresh child cgroup identity or exclusive permissions changed')
        if not all((domain / name).is_file() for name in ('cgroup.procs', 'cgroup.events', 'cgroup.kill')):
            raise RuntimeError('Delegated client domain lacks required kernel controls')
        if populated(domain) or (domain / 'cgroup.procs').read_text().split():
            raise RuntimeError('Fresh child cgroup must be empty before admission')
    finally:
        os.close(descriptor)


def run(argv, entries, save, evidence_directory, *, timeout, env=None, stdout=None,
        stderr=None, text=False, check=True, capture_output=False, input=None, cwd=None, client_cgroup_root=None, stdin=None):
    if sys.platform != 'linux':
        raise RuntimeError('Durable owned clients require native Linux')
    import shutil
    if input is not None and stdin is not None:
        raise ValueError('input and stdin are mutually exclusive')
    payload = stdin if stdin is not None else input
    argv = [os.fspath(arg) for arg in argv]
    executable = shutil.which(argv[0], path=(env or os.environ).get('PATH'))
    if executable is None:
        raise FileNotFoundError('Owned executable unavailable')
    argv[0] = executable
    entry = dict(id=uuid.uuid4().hex, pid=None, finished=False, descendants=[],
                 expected_cmdline_sha256=hashlib.sha256(b'\0'.join(os.fsencode(arg) for arg in argv) + b'\0').hexdigest())
    entries.append(entry)
    parent = client_cgroup_root or (env or os.environ).get("MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT")
    domain = prepare_domain(entry, parent)
    save()
    try:
        domain.mkdir()
        secure_created_domain(entry, domain)
        save()
    except BaseException as error:
        try:
            stop(entry)
        except BaseException as cleanup_error:
            error.add_note('Domain setup cleanup failed: ' + type(cleanup_error).__name__)
        raise
    read_fd, write_fd = os.pipe()
    code = 'import os,sys;fd=int(sys.argv[1]);gate=os.read(fd,1);os.close(fd);os.execv(sys.argv[2],sys.argv[2:]) if gate==b"1" else sys.exit(0)'
    process = None
    original = None
    result = None
    cleanup_errors = []
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    try:
        process = subprocess.Popen([sys.executable, '-I', '-c', code, str(read_fd), *argv],
                                   pass_fds=(read_fd,), env=env, cwd=cwd, start_new_session=True,
                                   stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.close(read_fd)
        read_fd = None
        current = identity(process.pid)
        entry.update(current, bootstrap_cmdline_sha256=current['cmdline_sha256'])
        entry.pop('cmdline_sha256')
        (domain / 'cgroup.procs').write_text(str(process.pid))
        if process.pid not in [int(value) for value in (domain / 'cgroup.procs').read_text().split()]:
            raise RuntimeError('Bootstrap cgroup membership not established')
        save()  # Durable acknowledgement precedes the first possible mutation.
        os.write(write_fd, b'1')
        os.close(write_fd)
        write_fd = None
        def observe():
            if verify_domain(entry) is None:
                raise RuntimeError('Owned client domain disappeared during execution')
        capture(process, payload.encode() if isinstance(payload, str) else payload, timeout, buffers, observe)
        if process.returncode and check:
            raise RuntimeError('Owned native command failed; bounded private logs retained')
        result = subprocess.CompletedProcess(argv, process.returncode,
            (bytes(buffers['stdout']).decode() if text else bytes(buffers['stdout'])) if stdout is None else None,
            (bytes(buffers['stderr']).decode() if text else bytes(buffers['stderr'])) if stderr is None else None)
    except BaseException as error:
        original = error
    finally:
        def attempt(step, action):
            try:
                action()
            except BaseException as error:
                cleanup_errors.append({'step': step, 'error_type': type(error).__name__})
        for descriptor in (read_fd, write_fd):
            if descriptor is not None:
                attempt('gate_close', lambda descriptor=descriptor: os.close(descriptor))
        if process is not None:
            # Failed acknowledgement leaves a bootstrap blocked at its gate.
            if entry.get('pid') is None or original is not None:
                attempt('session_cancel', lambda: stop(entry))
                if process.poll() is None:
                    attempt('direct_child_cancel', process.kill)
            attempt('client_wait', lambda: process.wait(timeout=15))
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    attempt('stream_close', stream.close)
            def prove_domain():
                path = verify_domain(entry)
                if path is not None:
                    if populated(path):
                        # Leader exit never proves descendant exit.
                        stop(entry)
                    else:
                        try:
                            path.rmdir()
                        except FileNotFoundError:
                            if verify_domain(entry) is not None:
                                raise
                if process.poll() is None:
                    raise RuntimeError('Owned client is not reaped')
                entry['finished'] = True
            attempt('domain_empty_proof', prove_domain)
        for name, destination in [('stdout', stdout), ('stderr', stdout if stderr == subprocess.STDOUT else stderr)]:
            if destination not in (None, subprocess.DEVNULL):
                attempt(name + '_stream_write', lambda name=name, destination=destination: write_stream(destination, bytes(buffers[name])))
        if original is not None or cleanup_errors:
            entry['execution_error_type'] = type(original).__name__ if original is not None else None
            entry['failure_output'] = {}
            for name, data in buffers.items():
                entry['failure_output'][name] = {'observed_bytes': len(data), 'retained_bytes': min(len(data), 1024 * 1024), 'truncated': len(data) > 1024 * 1024}
                if data:
                    def publish_log(name=name, data=data):
                        path = Path(evidence_directory) / ('command-' + entry['id'] + '-' + name + '.log')
                        with path.open('xb') as stream:
                            os.fchmod(stream.fileno(), 0o600)
                            stream.write(data[:1024 * 1024])
                    attempt(name + '_failure_log', publish_log)
        entry['cleanup_errors'] = cleanup_errors
        attempt('final_ownership_save', save)
    if original is not None:
        if cleanup_errors:
            original.add_note('Independent owned-client cleanup errors: ' + repr(cleanup_errors))
        raise original
    if cleanup_errors:
        raise RuntimeError('Owned client cleanup incomplete: ' + repr(cleanup_errors))
    return result
