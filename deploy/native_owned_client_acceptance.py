"""Disposable Linux delegated-cgroup birth/descendant fault acceptance.

No Docker, network, benchmark data or staging credentials. Output is private.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import threading

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy import owned_client
from deploy.recovery_journal import atomic_json, safe_path
from deploy.recovery import private_file


def await_file(path, process, seconds=15):
    deadline = time.monotonic() + seconds
    while not path.exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError('Owned-client fixture boundary not reached')
        time.sleep(.02)


def owner(root, before):
    entries = []
    def save():
        atomic_json(root / 'ownership.json', {'clients': entries})
        if before and entries and entries[0].get('pid'):
            (root / 'before-release').touch()
            time.sleep(60)
    # Both leader and grandchild remain in inherited client cgroup.
    grandchild = ('import pathlib,sys,time,os,json;root=pathlib.Path(sys.argv[1]);'
                  'root.joinpath("descendant-ready").write_text(json.dumps({"pid":os.getpid()}));'
                  'time.sleep(20);root.joinpath("late-mutation").touch()')
    code = ('import pathlib,subprocess,sys,time;root=pathlib.Path(sys.argv[1]);'
            'root.joinpath("mutation").touch();'
            'subprocess.Popen([sys.executable,"-c",' + repr(grandchild) + ',str(root)]);'
            'time.sleep(.2)')
    owned_client.run([sys.executable, '-c', code, str(root)], entries, save, root, timeout=90)


class Fixture:
    """The fixture owner itself uses the same durable birth gate/domain."""
    def __init__(self, root, before):
        self.root = root
        self.entries = []
        self.error = None
        self.result = None
        def target():
            try:
                self.result = owned_client.run(
                    [sys.executable, str(Path(__file__).resolve()), '--owner', str(root),
                     *(['--before'] if before else [])], self.entries,
                    lambda: atomic_json(root / 'fixture-owner.json', {'clients': self.entries}),
                    root, timeout=120)
            except BaseException as error:
                self.error = type(error).__name__
        self.thread = threading.Thread(target=target)
        self.thread.start()

    def poll(self):
        return None if self.thread.is_alive() else (self.result.returncode if self.result else -1)

    def kill(self):
        if not self.entries:
            raise RuntimeError('Fixture ownership not published')
        owned_client.stop(self.entries[0])

    def wait(self, timeout):
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise RuntimeError('Fixture controller did not exit')
        return self.poll()


def _cleanup_locked(output):
    output = safe_path(output)
    if output.stat().st_uid != os.getuid() or output.stat().st_mode & 0o077:
        raise RuntimeError('Private owner-held evidence directory required')
    errors = []
    for root in (output / 'before-release', output / 'after-release'):
        # Controller cancellation closes the release pipe before child cleanup.
        for filename in ('fixture-owner.json', 'ownership.json'):
            try:
                path = root / filename
                if path.exists():
                    for entry in json.loads(private_file(path).read_text()).get('clients', []):
                        try:
                            owned_client.stop(entry)
                        except BaseException as error:
                            errors.append({'case': root.name, 'journal': filename,
                                           'client': entry.get('id'), 'error_type': type(error).__name__})
            except BaseException as error:
                errors.append({'case': root.name, 'journal': filename, 'error_type': type(error).__name__})
    atomic_json(output / ('cleanup-' + str(time.time_ns()) + '.json'),
                {'cleanup_complete': not errors, 'errors': errors})
    if errors:
        raise RuntimeError('Owned-client fixture cleanup incomplete')
    return {'cleanup_complete': True}


def _execute_locked(output):
    if sys.platform != 'linux':
        raise RuntimeError('Native Linux required')
    if output.exists() or output.resolve() != output:
        raise RuntimeError('Fresh canonical output required')
    if output.parent.stat().st_mode & 0o077:
        raise RuntimeError('Output parent must be private')
    output.mkdir(mode=0o700)
    source = Path(__file__).resolve().parents[1]
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'])
    if dirty:
        raise RuntimeError('Retained clean source required')
    report = {'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
              'python': sys.version, 'boot_id': owned_client.boot_id(),
              'helper_sha256': hashlib.sha256(Path(owned_client.__file__).read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'cases': [], 'passed': False}
    atomic_json(output / 'report.json', report)
    for before in (True, False):
        root = output / ('before-release' if before else 'after-release'); root.mkdir(mode=0o700)
        process = Fixture(root, before)
        errors = []
        entry = None
        try:
            await_file(root / ('before-release' if before else 'mutation'), process)
            descendant = None
            if not before:
                await_file(root / 'descendant-ready', process)
                descendant = owned_client.identity(json.loads((root / 'descendant-ready').read_text())['pid'])
                client = json.loads((root / 'ownership.json').read_text())['clients'][0]
                if descendant['pid'] not in [int(value) for value in (Path(client['cgroup']['path']) / 'cgroup.procs').read_text().split()]:
                    raise RuntimeError('Grandchild does not inherit the owned domain')
                deadline = time.monotonic() + 10
                while True:
                    try:
                        stat = (Path('/proc') / str(client['pid']) / 'stat').read_text()
                        exited = stat[stat.rindex(')') + 2:].split()[0] == 'Z'
                    except FileNotFoundError:
                        exited = True
                    if exited: break
                    if time.monotonic() >= deadline: raise RuntimeError('Fixture CLI leader remains executable')
                    time.sleep(.02)

            process.kill(); process.wait(timeout=15)  # Popen-owned fixture controller only.
            entry = json.loads((root / 'ownership.json').read_text())['clients'][0]
            path = owned_client.verify_domain(entry)
            if path is None:
                raise RuntimeError('Fixture domain vanished before cancellation')
            if before:
                deadline = time.monotonic() + 15
                while owned_client.populated(path):
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Unreleased bootstrap did not exit on gate EOF')
                    time.sleep(.02)
            # Exact inode mismatch must refuse even a genuinely owned populated domain.
            for field in ('inode', 'device', 'uid'):
                mismatch = copy.deepcopy(entry); mismatch['cgroup'][field] += 1
                try:
                    owned_client.stop(mismatch)
                except RuntimeError:
                    pass
                else:
                    raise RuntimeError('Domain mismatch was accepted')
            prior_boot = copy.deepcopy(entry); prior_boot['cgroup']['boot_id'] = 'different-boot'
            owned_client.stop(prior_boot)
            if owned_client.verify_domain(entry) is None:
                raise RuntimeError('Prior-boot receipt signalled current domain')
            if not before and not owned_client.populated(path):
                raise RuntimeError('Released descendant fixture is not populated')
            owned_client.stop(entry); owned_client.stop(entry)
            if before and (root / 'mutation').exists():
                raise RuntimeError('Mutation occurred before durable release')
            if (root / 'late-mutation').exists() or owned_client.verify_domain(entry) is not None:
                raise RuntimeError('Owned client cleanup proof failed')
            report['cases'].append({'case': root.name, 'passed': True, 'mismatch_refused': True,
                                    'domain_removed': True, 'repeated_cleanup': True,
                                    'leader_exit_verified': not before, 'descendant_identity': descendant})
        finally:
            if process.poll() is None:
                process.kill()
            try: process.wait(timeout=15)
            except BaseException as error: errors.append(type(error).__name__)
            try:
                if entry is None and (root / 'ownership.json').exists():
                    rows = json.loads((root / 'ownership.json').read_text())['clients']
                    entry = rows[0] if rows else None
                if entry is not None: owned_client.stop(entry)
            except BaseException as error: errors.append(type(error).__name__)
            report['cleanup_errors'] = errors
            atomic_json(output / 'report.json', report)
            if errors: raise RuntimeError('Native owned-client cleanup incomplete')
    report['passed'] = True
    atomic_json(output / 'report.json', report)
    return report


def execute(output):
    if sys.platform != 'linux': raise RuntimeError('Native Linux required')
    from deploy.native_synthetic_s3 import run_lock
    with run_lock(output): return _execute_locked(output)


def cleanup(output):
    from deploy.native_synthetic_s3 import run_lock
    with run_lock(output): return _cleanup_locked(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--owner', type=Path)
    parser.add_argument('--before', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if args.owner: owner(args.owner, args.before)
    elif args.output: print(json.dumps(cleanup(args.output) if args.cleanup else execute(args.output)))
    else: parser.error('--output required')
