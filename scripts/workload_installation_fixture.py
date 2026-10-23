"""Generation-bound disposable installation lifecycle; never VPS authority.

The private recipe names frozen provisioning/observation/retirement adapters.
Adapters are trusted fixture inputs, not production engine replacements. See
docs/WORKLOAD_INSTALLATION_FIXTURE.md for the input contract and current limits.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import platform
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid

from deploy.workload_installation import Journal, exclusive, identity, private, sync_directory
from deploy.workload_release import canonical, digest, regular, runtime_sources, stable_stat
from mldsafail.evaluator.native_workload import require


SCHEMA = 'mldsafail.installation-fixture.v1'
CASES = ('complete', 'partial-snapshots', 'partial-configurations',
         'unacknowledged-images', 'interrupted-rollback')
PHASES = ('prepare', 'provision', 'inspect', 'install', 'reconcile', 'rollback', 'cleanup')
LIMIT = 1024**2
IMPLEMENTATION_BLOCKERS = ('concrete_provisioner_missing', 'concrete_resource_observer_missing',
                           'concrete_cleanup_missing', 'peer_uid_probe_runner_missing')


def absolute(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and str(path) != '/',
            'fixture_absolute_nonroot_path_required')
    require(not any(parent.is_symlink() for parent in (path, *path.parents)), 'fixture_symlink')
    return path


def directory(path):
    path = absolute(path)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) == 0o700, 'fixture_private_directory_required')
    return path


def host():
    return dict(platform=sys.platform, architecture=platform.machine(),
                hostname=socket.gethostname(), uid=os.getuid(),
                boot_id=(Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                         if sys.platform == 'linux' else None))


def environment():
    result = dict(host=host(), requirements=['linux', 'x86_64', 'systemd',
                  'cgroup-v2:cpu,memory,pids', 'rootless-docker', 'offline-runtime-kit'])
    blockers = []
    if sys.platform != 'linux':
        blockers.append('linux_required')
    if platform.machine() != 'x86_64':
        blockers.append('x86_64_required')
    if sys.platform == 'linux':
        if Path('/proc/1/comm').read_text().strip() != 'systemd':
            blockers.append('systemd_pid1_required')
        controllers = Path('/sys/fs/cgroup/cgroup.controllers')
        if not controllers.is_file() or not set(controllers.read_text().split()) >= {'cpu', 'memory', 'pids'}:
            blockers.append('cgroup_v2_controllers_required')
    result['blockers'] = blockers
    result['native_acceptance'] = False
    return result


def validate_recipe(recipe, root):
    require(set(recipe) == {'schema', 'fixture_only', 'target', 'inputs', 'adapters', 'resources'},
            'fixture_recipe_fields')
    require(recipe['schema'] == SCHEMA and recipe['fixture_only'] is True, 'fixture_recipe_scope')
    require(set(recipe['target']) == {'hostname', 'machine_id', 'uid'} and
            recipe['target']['hostname'].startswith('workload-rehearsal') and
            recipe['target']['uid'] > 0, 'fixture_disposable_target_required')
    require(set(recipe['adapters']) == {'provision', 'inspect', 'postflight', 'cleanup'},
            'fixture_adapters_required')
    require(all(name in recipe['inputs'] for name in recipe['adapters'].values()),
            'fixture_adapter_input_missing')
    require(all(name and name.isidentifier() for name in recipe['inputs']), 'fixture_input_name')
    paths = []
    for row in recipe['resources']:
        require(set(row) == {'path', 'kind', 'retention'} and
                row['kind'] in ('directory', 'file', 'unit', 'mount', 'cgroup', 'container', 'image') and
                row['retention'] in ('evidence', 'bulk', 'preserve'), 'fixture_resource_fields')
        require(type(row['path']) is str and row['path'], 'fixture_resource_path')
        if row['kind'] not in ('container', 'image'):
            path = absolute(row['path'])
            require(path != root, 'fixture_resource_cannot_be_namespace')
        paths.append((row['kind'], row['path']))
    require(len(set(paths)) == len(paths), 'fixture_duplicate_resource')


def prepare(root, *, recipe=None, case='complete', source=None):
    """Exclusive namespace creation. Even an unavailable host gets a durable record."""
    root = absolute(root)
    require(case in CASES, 'fixture_case_unknown')
    root.mkdir(mode=0o700)  # Never merge with or adopt an existing namespace.
    sync_directory(root.parent)
    exclusive(root/'prepare-intent.json', canonical(dict(schema=SCHEMA, fixture_only=True,
              root=identity(root), case=case, started_at=time.time())))
    try:
        return _prepare(root, recipe=recipe, case=case, source=source)
    except BaseException as error:
        exclusive(root/'prepare-failed.json', canonical(dict(schema=SCHEMA, fixture_only=True,
                  error=dict(type=type(error).__name__, message=str(error)),
                  ownership='preserve_exclusively_created_namespace', automatic_retry=False)))
        raise


def _prepare(root, *, recipe, case, source):
    generation = uuid.uuid4().hex
    with lifecycle_lock(root):
        for name in ('inputs', 'artifacts', 'journal'):
            (root/name).mkdir(mode=0o700)
        source = Path(source or Path(__file__).resolve().parents[1])
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
        names = runtime_sources(source)
        source_hashes = {name: digest(regular(source, name)[0]) for name in sorted(names)}
        inputs = {}
        value = None
        if recipe is not None:
            _, value = private(absolute(recipe))
            validate_recipe(value, root)
            for name, path in value['inputs'].items():
                path = absolute(path)
                data, mode = regular(path.parent, path.name)
                destination = root/'inputs'/name
                exclusive(destination, data, 0o600)
                inputs[name] = dict(identity(destination), bytes=len(data), original_mode=mode)
        manifest = dict(schema=SCHEMA, fixture_only=True, generation=generation, case=case,
                        directories={name: identity(root/name) for name in ('inputs', 'artifacts', 'journal')},
                        root=identity(root), host=host(), source_revision=revision,
                        source_status_sha256=digest(status.encode()),
                        source_hashes=source_hashes,
                        driver_sha256=digest(Path(__file__).read_bytes()),
                        created_at=time.time(), budget_seconds=1800, cleanup_reserve_seconds=300,
                        final_paths={name: str(root/name) for name in
                                     ('release', 'previous', 'frozen', 'output', 'gate', 'proposal.json')},
                        recipe=value, inputs=inputs, environment=environment(),
                        implementation_blockers=list(IMPLEMENTATION_BLOCKERS),
                        execution_authority=False, vps_authority=False)
        exclusive(root/'manifest.json', canonical(manifest))
        journal = Journal(root/'journal', digest(canonical(manifest)))
        journal.append('fixture_prepared', generation=generation,
                       blockers=manifest['environment']['blockers'] + ([] if value else ['fixture_kit_absent']))
    return manifest


@contextmanager
def lifecycle_lock(root):
    root = directory(root)
    before = identity(root)
    fd = os.open(root/'lifecycle.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600, 'fixture_lock_invalid')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(identity(root) == before and stable_stat(os.fstat(fd)) == stable_stat((root/'lifecycle.lock').lstat()),
                'fixture_lock_or_root_replaced')
        yield fd
    finally:
        os.close(fd)


class Fixture:
    def __init__(self, root):
        self.root = directory(root)
        raw, self.manifest = private(self.root/'manifest.json')
        self.binding = digest(raw)
        self.lock_fd = None
        require(self.manifest['schema'] == SCHEMA and self.manifest['fixture_only'] is True and
                self.manifest['root'] == identity(self.root), 'fixture_namespace_replaced')
        require(digest(Path(__file__).read_bytes()) == self.manifest['driver_sha256'],
                'fixture_driver_changed_new_generation_required')
        self.journal = Journal(self.root/'journal', self.binding)
        for name, expected in self.manifest['directories'].items():
            require(identity(directory(self.root/name)) == expected, 'fixture_directory_replaced')
        for name, expected in self.manifest['inputs'].items():
            actual = identity(self.root/'inputs'/name)
            require(all(actual.get(k) == v for k, v in expected.items() if k not in ('bytes', 'original_mode')),
                    'fixture_input_changed_new_generation_required')

    def last(self, phase):
        return next((r for r in reversed(self.journal.rows) if r.get('phase') == phase and
                     r['event'].startswith('fixture_phase_')), None)

    def require_target(self):
        facts = environment()
        require(not facts['blockers'], 'fixture_unsupported_environment:' + ','.join(facts['blockers']))
        recipe = self.manifest['recipe']
        require(recipe is not None, 'fixture_kit_absent')
        target = recipe['target']
        require(host() == self.manifest['host'] and target['hostname'] == socket.gethostname() and
                target['uid'] == os.getuid() and Path('/etc/machine-id').read_text().strip() == target['machine_id'],
                'fixture_target_changed')
        # A separate root-owned VM marker is necessary; a matching hostname is insufficient.
        marker = Path('/run/mldsafail-disposable-fixture.json')
        info = marker.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
                not info.st_mode & 0o022, 'fixture_root_owned_vm_marker_required')
        require(json.loads(marker.read_bytes()) == dict(schema=SCHEMA, fixture_only=True, **target),
                'fixture_vm_marker_changed')

    def deadline(self, *, cleanup=False):
        start = next((r['started_at'] for r in self.journal.rows if r['event'] == 'fixture_attempt_started'), None)
        require(start is not None, 'fixture_attempt_not_started')
        remaining = start + (1800 if cleanup else 1500) - time.time()
        require(0 < remaining <= 1800, 'fixture_attempt_expired_preserve_unresolved_ownership')
        return remaining

    def command(self, argv, *, cleanup=False, seconds=300):
        """Bounded Linux subreaper; raw output and descendant evidence stay private."""
        self.require_target()
        import resource
        from mldsafail.evaluator.native_workload import process_birth
        allowance = min(seconds, self.deadline(cleanup=cleanup))
        require(allowance > 4, 'fixture_cleanup_reserve_reached')
        token = uuid.uuid4().hex
        report = self.root/'artifacts'/(token+'-descendants.json')
        output = self.root/'artifacts'/(token+'.log')
        wrapper = Path(__file__).resolve().parents[1]/'deploy/workload_observation.py'
        self.journal.append('fixture_command_intent', command=token, argv_sha256=digest(canonical(argv)),
                            allowance=allowance)
        def bound():
            resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
        process = None
        failure = None
        birth = None
        cleanup_errors = []
        containment = None
        group_remaining = False
        try:
            with output.open('xb') as stream:
                os.chmod(output, 0o600)
                process = subprocess.Popen([sys.executable, '-I', str(wrapper), str(report),
                                            str(allowance-3), *argv], stdout=stream, stderr=stream,
                                           start_new_session=True, preexec_fn=bound,
                                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
                birth = process_birth(process.pid)
                self.journal.append('fixture_command_birth', command=token, birth=birth)
                process.wait(timeout=allowance-1)
        except BaseException as error:
            failure = dict(type=type(error).__name__, message=str(error))
        finally:
            try:
                if process is not None and process.poll() is None:
                    require(process_birth(process.pid) == birth, 'fixture_command_replaced')
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=1)
            except BaseException as error:
                cleanup_errors.append(dict(type=type(error).__name__, message=str(error)))
            try:
                containment = json.loads(report.read_bytes())
            except (OSError, ValueError) as error:
                cleanup_errors.append(dict(type=type(error).__name__, message=str(error)))
            if process is not None:
                try:
                    os.killpg(process.pid, 0)
                    group_remaining = True
                except ProcessLookupError:
                    pass
                except OSError as error:
                    cleanup_errors.append(dict(type=type(error).__name__, message=str(error)))
            try:
                output_identity = identity(output)
            except BaseException as error:
                output_identity = None
                cleanup_errors.append(dict(type=type(error).__name__, message=str(error)))
            self.journal.append('fixture_command_result', command=token, failure=failure,
                                returncode=process.returncode if process else None, birth=birth,
                                containment=containment, group_remaining=group_remaining,
                                cleanup_errors=cleanup_errors, output=output_identity)
        require(not cleanup_errors and not failure and containment and not group_remaining and not containment['errors'] and
                not containment['remaining'] and not containment['descendants'] and not containment['timed_out'],
                'fixture_command_or_descendant_termination_unverified')
        require(process.returncode == containment['returncode'] == 0, 'fixture_command_failed')
        require(output.stat().st_size < LIMIT, 'fixture_command_output_limit')
        return output

    def adapter(self, phase, *, cleanup=False):
        # Arbitrary external Python adapters cannot prove a resource allowlist,
        # read-only inspection or safe retirement. Keep this gate closed until
        # concrete built-in adapters and their resource receipts are implemented.
        require(False, 'fixture_concrete_'+phase+'_adapter_not_implemented')

    def artifact(self, label, value):
        path = self.root/'artifacts'/(label+'-'+uuid.uuid4().hex+'.json')
        exclusive(path, canonical(value))
        return identity(path)

    def proposal(self):
        from deploy.workload_v3 import validate_proposal
        raw, value = private(self.root/'proposal.json')
        validate_proposal(value)
        source = value['identities']
        require(source['origin'] == 'local_linux' and source['host']['hostname'] == socket.gethostname() and
                source['host']['uid'] == os.getuid(), 'fixture_proposal_wrong_host')
        paths = self.manifest['final_paths']
        require(source['resources']['release']['path'] == paths['release'] and
                source['rollback']['release'] == paths['previous'] and
                source['recipe']['bundle_root'] == paths['frozen'] and
                source['recipe']['proposal_path'] == paths['proposal.json'], 'fixture_final_paths_changed')
        from deploy.workload_release import verify
        verify(paths['frozen'], source['manifest'])
        for name, expected in self.manifest['source_hashes'].items():
            require(source['manifest']['files'].get(name, {}).get('sha256') == expected,
                    'fixture_engine_source_changed')
        return raw, value

    def engine(self, phase, *, reconciliation=False, authority=None, review=None):
        require(not IMPLEMENTATION_BLOCKERS, 'fixture_engineering_incomplete')
        raw, proposal = self.proposal()
        # Artifacts are supplied, never manufactured approval by the fixture.
        review_raw, reviewed = private(absolute(review))
        authority_raw, authorized = private(absolute(authority))
        for value in (reviewed, authorized):
            require(value.get('fixture_only') is True and value.get('fixture_generation') == self.manifest['generation'] and
                    value.get('fixture_manifest_sha256') == self.binding, 'fixture_authority_scope_changed')
        from deploy.workload_installation import authorize
        authorize(raw, review_raw, authorized, phase)
        require(bool(authorized.get('reconcile')) == reconciliation, 'fixture_reconcile_authority_changed')
        source = proposal['identities']
        recipe = source['recipe']
        argv = [recipe['bootstrap_interpreter']['path'], '-P', '-B', '-m', 'scripts.workload_installation_fixture',
                '_engine', str(self.root), '--review', str(review), '--authorization', str(authority),
                '--engine-phase', phase]
        if reconciliation:
            argv.append('--reconcile-engine')
        # Isolated Python loads the exact frozen engine, not the operator checkout.
        code = 'import runpy,sys;sys.path[:0]=' + repr([recipe['bundle_root']+'/src', recipe['bundle_root']]) + ';sys.argv=' + repr(argv[4:]) + ';runpy.run_module("scripts.workload_installation_fixture",run_name="__main__")'
        return self.command([argv[0], '-I', '-B', '-c', code])

    def inspect(self):
        """Collection only, with a newly and exclusively published private report."""
        result = dict(schema=SCHEMA, fixture_only=True, generation=self.manifest['generation'],
                      manifest_sha256=self.binding, environment=environment(),
                      implementation_blockers=list(IMPLEMENTATION_BLOCKERS),
                      runtime_suitability_verified=False,
                      lifecycle_head=self.journal.head, execution_authority=False)
        return self.artifact('inspection', result)

    def transition(self, phase, *, authority=None, review=None, engine_phase='install'):
        require(phase in PHASES and phase not in ('prepare', 'inspect'), 'fixture_phase_invalid')
        self.journal.reload()
        prior = self.last(phase)
        if phase not in ('reconcile', 'install', 'rollback'):
            require(prior is None, 'fixture_phase_already_attempted_preserve_evidence')
        elif prior:
            require(prior['event'] == 'fixture_phase_failed' and self.last('reconcile') and
                    self.last('reconcile')['event'] == 'fixture_phase_complete' and
                    self.journal.rows.index(self.last('reconcile')) > self.journal.rows.index(prior),
                    'fixture_fresh_reconciliation_required')
        if phase == 'provision':
            require(not any(r['event'] == 'fixture_attempt_started' for r in self.journal.rows), 'fixture_attempt_used')
            self.journal.append('fixture_attempt_started', started_at=time.time())
        elif phase != 'cleanup':
            require(self.last('provision') and self.last('provision')['event'] == 'fixture_phase_complete',
                    'fixture_provision_not_complete')
        self.journal.append('fixture_phase_intent', phase=phase)
        try:
            self.require_target()
            self.deadline(cleanup=phase == 'cleanup')
            require(not IMPLEMENTATION_BLOCKERS,
                    'fixture_engineering_incomplete:'+','.join(IMPLEMENTATION_BLOCKERS))
            if phase == 'provision':
                self.adapter('provision')
                _, proposal = self.proposal()
                from deploy.workload_installed import observe_rollback
                receipt = observe_rollback(proposal['identities'])
                self.artifact('rollback-compatibility', receipt)
            elif phase in ('install', 'rollback', 'reconcile'):
                self.engine(engine_phase if phase == 'reconcile' else phase, reconciliation=phase == 'reconcile',
                            authority=authority, review=review)
                if phase == 'install':
                    from deploy.workload_installed import collect
                    from deploy.workload_v3 import installed
                    _, proposal = self.proposal()
                    measured = collect(proposal)
                    installed(measured, proposal)
                    self.artifact('installed', measured)
                self.adapter('postflight')
            else:
                # The adapter must prove ownership/inactivity before any deletion.
                # No recursive removal or Docker prune is built into this driver.
                self.adapter('cleanup', cleanup=True)
                self.adapter('postflight', cleanup=True)
            self.journal.append('fixture_phase_complete', phase=phase)
        except BaseException as error:
            self.journal.append('fixture_phase_failed', phase=phase,
                                error=dict(type=type(error).__name__, message=str(error)),
                                ownership='unresolved_preserve', automatic_retry=False)
            raise


def fixture_engine(root, *, phase, review, authority, reconciliation=False):
    """Fixture-only fault injection through existing Python boundaries."""
    require(not IMPLEMENTATION_BLOCKERS, 'fixture_engineering_incomplete')
    fixture = Fixture(root)
    fixture.require_target()
    raw, proposal = fixture.proposal()
    review_raw, _ = private(review)
    _, authorized = private(authority)
    for value in (json.loads(review_raw), authorized):
        require(value.get('fixture_only') is True and value.get('fixture_generation') == fixture.manifest['generation'] and
                value.get('fixture_manifest_sha256') == fixture.binding, 'fixture_authority_scope_changed')
    from deploy.workload_installation import LinuxBackend, execute, reconcile
    case = fixture.manifest['case']
    marker = fixture.root/'fault-fired.json'
    def interrupt(point):
        if marker.exists() or marker.is_symlink():
            _, fired = private(marker)
            require(fired.get('fixture_only') is True and fired.get('generation') == fixture.manifest['generation'] and
                    set(fired) == {'fixture_only', 'generation', 'point'}, 'fixture_fault_marker_changed')
            recorded = [row for row in backend.journal.rows if row['event'] == 'fixture_fault_fired']
            require(len(recorded) == 1 and recorded[0]['observed'] == identity(marker),
                    'fixture_fault_marker_unacknowledged_or_replaced')
            return
        exclusive(marker, canonical(dict(fixture_only=True, generation=fixture.manifest['generation'], point=point)))
        backend.journal.append('fixture_fault_fired', observed=identity(marker))
        raise InterruptedError('disposable_fixture_fault:'+point)
    class Backend(LinuxBackend):
        def snapshot_file(self, journal, name, data):
            super().snapshot_file(journal, name, data)
            if case == 'partial-snapshots':
                interrupt('first_snapshot_acknowledgement')
        def file_substep(self, step, journal, path, expected, action):
            super().file_substep(step, journal, path, expected, action)
            if case == 'partial-configurations' and step['id'] == 'install:configurations':
                interrupt('first_configuration_acknowledgement')
    def fault(step, point):
        if (case == 'unacknowledged-images' and step == 'install:images' or
                case == 'interrupted-rollback' and step == 'rollback:restore_activation') and point == 'unacknowledged':
            interrupt(step+':'+point)
    backend = Backend(proposal)
    if reconciliation:
        reconcile(proposal, raw, review_raw, authorized, backend, phase=phase)
    else:
        execute(proposal, raw, review_raw, authorized, backend, phase=phase, fault=fault)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=(*PHASES, '_engine'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--recipe', type=Path)
    parser.add_argument('--case', choices=CASES, default='complete')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--engine-phase', choices=('install', 'rollback'), default='install')
    parser.add_argument('--reconcile-engine', action='store_true')
    args = parser.parse_args()
    if args.phase == 'prepare':
        value = prepare(args.root, recipe=args.recipe, case=args.case)
        print(json.dumps(dict(generation=value['generation'], environment=value['environment'], execution_authority=False)))
        return
    if args.phase == '_engine':
        # The child lock handoff is unfinished. Refuse the private worker route
        # rather than exposing an unlocked mutation entrypoint.
        raise RuntimeError('fixture_internal_worker_requires_inherited_lifecycle_lock')
    with lifecycle_lock(args.root):
        fixture = Fixture(args.root)
        if args.phase == 'inspect':
            print(json.dumps(fixture.inspect()))
        else:
            fixture.transition(args.phase, authority=args.authorization, review=args.review, engine_phase=args.engine_phase)


if __name__ == '__main__':
    main()
