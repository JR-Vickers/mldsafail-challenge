"""Generation-bound disposable installation lifecycle; never VPS authority.

The private recipe names frozen provisioning/observation/retirement adapters.
Adapters are trusted fixture inputs, not production engine replacements. See
docs/WORKLOAD_INSTALLATION_FIXTURE.md for the input contract and current limits.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import math
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
from mldsafail.evaluator.workload import WorkloadBlocked


SCHEMA = 'mldsafail.installation-fixture.v1'
CASES = ('complete', 'partial-snapshots', 'partial-configurations',
         'unacknowledged-images', 'interrupted-rollback')
PHASES = ('prepare', 'provision', 'inspect', 'install', 'reconcile', 'rollback', 'cleanup')
LIMIT = 1024**2
IMPLEMENTATION_BLOCKERS = ()


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
    require(all(name == 'builtin' or name in recipe['inputs'] for name in recipe['adapters'].values()),
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


def prepare(root, *, recipe=None, case='complete', source=None, recovery_fault_plan=None):
    """Exclusive namespace creation. Even an unavailable host gets a durable record."""
    root = absolute(root)
    require(case in CASES, 'fixture_case_unknown')
    require(recovery_fault_plan is None or case=='complete','fixture_fault_plan_cannot_combine_historical_case')
    root.mkdir(mode=0o700)  # Never merge with or adopt an existing namespace.
    sync_directory(root.parent)
    exclusive(root/'prepare-intent.json', canonical(dict(schema=SCHEMA, fixture_only=True,
              root=identity(root), case=case, started_at=time.time())))
    try:
        return _prepare(root, recipe=recipe, case=case, source=source, recovery_fault_plan=recovery_fault_plan)
    except BaseException as error:
        exclusive(root/'prepare-failed.json', canonical(dict(schema=SCHEMA, fixture_only=True,
                  error=dict(type=type(error).__name__, message=str(error)),
                  ownership='preserve_exclusively_created_namespace', automatic_retry=False)))
        raise


def _prepare(root, *, recipe, case, source, recovery_fault_plan=None):
    generation = uuid.uuid4().hex
    bound_fault=None
    if recovery_fault_plan is not None:
        from deploy.workload_fixture_faults import bind
        bound_fault=bind(recovery_fault_plan,generation)
    with lifecycle_lock(root):
        for name in ('inputs', 'artifacts', 'journal', 'runtime-journal'):
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
                inputs[name] = dict(identity(destination), bytes=len(data), original_mode=mode, original_name=path.name)
        resource_plan = None
        source_root = source
        if value and set(value['adapters'].values()) == {'builtin'}:
            require('settings' in inputs,'fixture_settings_missing')
            settings = json.loads((root/'inputs/settings').read_bytes())
            from deploy.workload_units import absolute as unit_path
            for path in (root/'release/.venv/bin/python',root/'previous/.venv/bin/python',
                         root/'release/config/supervisor.json',root/'previous/config/supervisor.json',
                         root/'gate',root/'gate-previous',Path(settings['unit_directory'])):
                unit_path(str(path))
            from deploy.workload_fixture_resources import resource_plan as plan
            resource_plan = plan(root,value['target']['uid'],settings['unit_directory'])
            source_root = root/'source'
            source_root.mkdir(mode=0o700)
            for name, expected in source_hashes.items():
                data,mode = regular(source,name)
                require(digest(data)==expected,'fixture_source_changed_during_prepare')
                path = source_root/name
                path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                exclusive(path,data,0o700 if mode&0o111 else 0o600)
            # A local Git index supports the existing complete-release helper;
            # the original revision and every copied byte remain separately bound.
            prefix = ['git','-c','init.templateDir=','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false']
            for argv in ([*prefix,'init','-q',str(source_root)],
                         [*prefix,'-C',str(source_root),'add','.'],
                         [*prefix,'-C',str(source_root),'-c','user.name=Disposable Fixture','-c','user.email=fixture@invalid',
                          'commit','-qm','Exact fixture runtime snapshot']):
                subprocess.run(argv,check=True,capture_output=True,timeout=15)
        manifest = dict(schema=SCHEMA, fixture_only=True, generation=generation, case=case,
                        directories={name: identity(root/name) for name in ('inputs', 'artifacts', 'journal', 'runtime-journal',
                                     *(['source'] if source_root!=source else []))},
                        root=identity(root), host=host(), source_revision=revision,
                        source_status_sha256=digest(status.encode()),
                        source_hashes=source_hashes,
                        source_root=str(source_root), resource_plan=resource_plan,
                        driver_sha256=digest(Path(__file__).read_bytes()),
                        created_at=time.time(), budget_seconds=1800, cleanup_reserve_seconds=300,
                        final_paths={name: str(root/name) for name in
                                     ('release', 'previous', 'frozen', 'output', 'gate', 'proposal.json')},
                        recipe=value, inputs=inputs, environment=environment(),
                        implementation_blockers=list(IMPLEMENTATION_BLOCKERS),
                        execution_authority=False, vps_authority=False)
        if bound_fault is not None:manifest['recovery_fault_plan']=bound_fault
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
        executing = Path(__file__).resolve().parents[1]
        for name, expected in self.manifest['source_hashes'].items():
            require(digest(regular(executing,name)[0])==expected,'fixture_executing_source_changed')
        self.journal = Journal(self.root/'journal', self.binding)
        self.lifecycle_journal = self.journal
        for name, expected in self.manifest['directories'].items():
            require(identity(directory(self.root/name)) == expected, 'fixture_directory_replaced')
        for name, expected in self.manifest['inputs'].items():
            actual = identity(self.root/'inputs'/name)
            require(all(actual.get(k) == v for k, v in expected.items() if k not in ('bytes', 'original_mode', 'original_name')),
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
        attempt = next((r for r in self.lifecycle_journal.rows if r['event']=='fixture_attempt_started'),None)
        require(attempt is not None, 'fixture_attempt_not_started')
        remaining = (attempt['started_monotonic']-time.monotonic() if 'started_monotonic' in attempt
                     else attempt['started_at']-time.time())+(1800 if cleanup else 1500)
        require(0 < remaining <= 1800, 'fixture_attempt_expired_preserve_unresolved_ownership')
        return remaining

    def command(self, argv, *, cleanup=False, seconds=300):
        """Bounded Linux subreaper; raw output and descendant evidence stay private."""
        self.require_target()
        from deploy.workload_log import LogPipe
        from mldsafail.evaluator.native_workload import process_birth
        allowance = min(seconds, self.deadline(cleanup=cleanup))
        require(allowance > 4, 'fixture_cleanup_reserve_reached')
        token = uuid.uuid4().hex
        report = self.root/'artifacts'/(token+'-descendants.json')
        output = self.root/'artifacts'/(token+'.log')
        wrapper = Path(__file__).resolve().parents[1]/'deploy/workload_observation.py'
        self.journal.append('fixture_command_intent', command=token, argv_sha256=digest(canonical(argv)),
                            allowance=allowance)
        process = None
        failure = None
        birth = None
        cleanup_errors = []
        containment = None
        group_remaining = False
        try:
            with output.open('xb') as stream, LogPipe(stream,LIMIT) as pipe:
                os.chmod(output, 0o600)
                wrapped = [sys.executable, '-I', str(wrapper), str(report),str(allowance-3),*argv]
                inherited = ()
                if self.lock_fd is not None:
                    base = self.manifest['source_root']
                    code = ('import sys;sys.path[:0]='+repr([base+'/src',base])+
                            ';from scripts.workload_fixture_worker import wrap;wrap('+repr(str(self.root))+','+
                            str(self.lock_fd)+','+repr(str(report))+','+repr(allowance-3)+','+repr(argv)+')')
                    wrapped = [sys.executable,'-I','-B','-c',code]
                    inherited = (self.lock_fd,)
                process = subprocess.Popen(wrapped, stdout=pipe.write_fd, stderr=subprocess.STDOUT,
                                           start_new_session=True,
                                           pass_fds=inherited,
                                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
                birth = process_birth(process.pid)
                self.journal.append('fixture_command_birth', command=token, birth=birth)
                pipe.wait(process,timeout=allowance-1)
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
        recipe = self.manifest['recipe']
        require(recipe and set(recipe['adapters'].values())=={'builtin'} and self.manifest['resource_plan'],
                'fixture_builtin_resource_plan_required')
        from scripts.rehearse_workload_installation_fixture import component_review
        component_review(self)
        require(phase in ('provision','inspect','cleanup','peer-probe'),'fixture_builtin_operation_invalid')
        return self.worker(phase,cleanup=cleanup,seconds=1500 if phase=='provision' else 180)

    def worker(self, operation, *, cleanup=False, seconds=300, phase='install',review=None,authority=None,reconciliation=False,token=None):
        from scripts.workload_fixture_worker import inherited_lock
        inherited_lock(self.root,self.lock_fd)
        token = uuid.uuid4().hex if token is None else token
        require(type(token) is str and len(token)==32 and all(c in '0123456789abcdef' for c in token) and
            not any(row['event']=='fixture_worker_intent' and row.get('token')==token for row in self.journal.rows),
            'fixture_worker_token_reused_or_invalid')
        output = self.root/'artifacts'/('worker-'+token+'.json')
        from mldsafail.evaluator.native_workload import process_birth
        request = dict(token=token,operation=operation,output=str(output),phase=phase,reconciliation=reconciliation,
                       review_sha256=digest(private(review,parse=False)[0]) if review else None,
                       authority_sha256=digest(private(authority,parse=False)[0]) if authority else None,
                       parent=process_birth(os.getpid()))
        self.journal.append('fixture_worker_intent',**request)
        base = self.manifest['source_root']
        interpreter = sys.executable
        if operation=='engine':
            _,proposal = self.proposal()
            base = proposal['identities']['recipe']['bundle_root']
            interpreter = proposal['identities']['recipe']['bootstrap_interpreter']['path']
        code = ('import sys;sys.path[:0]='+repr([base+'/src',base])+
                ';from scripts.workload_fixture_worker import work;work('+repr(str(self.root))+','+str(self.lock_fd)+','+
                repr(token)+','+repr(operation)+','+repr(str(output))+',phase='+repr(phase)+',review='+repr(str(review) if review else None)+
                ',authority='+repr(str(authority) if authority else None)+',reconciliation='+repr(reconciliation)+')')
        self.command([interpreter,'-I','-B','-c',code],cleanup=cleanup,seconds=seconds)
        _,result = private(output)
        require(result['fixture_only'] is True and result['generation']==self.manifest['generation'] and
                result['token']==token and result['operation']==operation,'fixture_worker_result_binding')
        self.journal.append('fixture_worker_complete',token=token,observed=identity(output))
        return result['result']

    def require_control_inspection(self, reference=None):
        """A supervisor shock invalidates old observations, never historical packets."""
        runtime=Journal(self.root/'runtime-journal',self.binding)
        invalid=[row for row in runtime.rows if row['event']=='fixture_installed_inspection_invalidated']
        if not invalid:return
        target=digest(canonical(invalid[-1]))
        refreshed=[row for row in self.lifecycle_journal.rows if row['event']=='fixture_installed_inspection_refreshed' and
            row.get('runtime_invalidation_sha256')==target and row.get('generation')==self.manifest['generation']]
        require(bool(refreshed),'fixture_control_fresh_installed_inspection_required')
        observed=refreshed[-1]['observed']
        require(identity(observed['path'])==observed,'fixture_control_fresh_inspection_replaced')
        if reference is not None:
            require(reference==dict(path=observed['path'],sha256=observed['sha256']),
                'fixture_control_packet_inspection_invalidated')

    def control(self, control, scenario, *, packet_deadline=None):
        """Independently supervise case, cleanup and postflight within one packet."""
        entered=time.monotonic()
        require(packet_deadline is None or type(packet_deadline) in (int,float) and math.isfinite(packet_deadline),
            'fixture_control_parent_deadline_invalid')
        deadline=min(entered+180,packet_deadline) if packet_deadline is not None else entered+180
        started=deadline-180
        from scripts.workload_fixture_worker import inherited_lock
        from scripts.rehearse_workload_installation_fixture import component_review
        from deploy.workload_fixture_controls import CASES
        inherited_lock(self.root,self.lock_fd);self.require_target();component_review(self)
        require((control,scenario) in CASES,'fixture_control_native_adapter_not_implemented')
        require(deadline>time.monotonic() and self.deadline()>=deadline-time.monotonic(),
            'fixture_control_insufficient_attempt_budget')
        self.require_control_inspection()
        require(not any(row['event']=='fixture_control_disposition' and row.get('disposition')=='blocked_preserve'
            for row in self.lifecycle_journal.rows),'fixture_control_previous_failure_requires_handoff')
        require(not any(row['event']=='fixture_control_requested' and row.get('control')==control and
            row.get('scenario')==scenario for row in self.lifecycle_journal.rows),'fixture_control_case_already_attempted')
        requested=[row for row in self.lifecycle_journal.rows if row['event']=='fixture_control_requested']
        resolved={(row['control'],row['scenario']) for row in self.lifecycle_journal.rows if
            row['event']=='fixture_control_disposition' and row.get('disposition')=='verified_fixture_only' and
            (row.get('cleanup') or {}).get('verified') is True and (row.get('postflight') or {}).get('verified') is True}
        require(all((row['control'],row['scenario']) in resolved for row in requested),
            'fixture_control_prior_ownership_unresolved')
        require(deadline-time.monotonic()>64,'fixture_control_cleanup_budget_not_reserved')
        self.lifecycle_journal.append('fixture_control_requested',control=control,scenario=scenario,
            generation=self.manifest['generation'],envelope_seconds=180,started_monotonic=started,packet_deadline=deadline)
        result=None;case_error=None;cleanup_error=None;cleanup=None;postflight=None
        try:
            result=self.worker('control',seconds=min(120,max(0,deadline-time.monotonic()-60)),phase=control+':'+scenario)
        except BaseException as error:case_error=error
        requests=[row for row in self.lifecycle_journal.rows if row['event']=='fixture_worker_intent' and
            row['operation']=='control' and row['phase']==control+':'+scenario]
        require(len(requests)==1,'fixture_control_original_request_ambiguous')
        token=requests[0]['token'];selection=control+':'+scenario+':'+token
        try:
            cleanup=self.worker('control-cleanup',cleanup=True,seconds=min(45,max(0,deadline-time.monotonic())),phase=selection)
            require(cleanup.get('verified') is True,'fixture_control_independent_cleanup_unverified')
            postflight=self.worker('control-postflight',cleanup=True,seconds=min(15,max(0,deadline-time.monotonic())),phase=selection)
            require(postflight.get('verified') is True,'fixture_control_independent_postflight_unverified')
            require(time.monotonic()<deadline,'fixture_control_parent_packet_expired')
        except BaseException as error:cleanup_error=error
        self.lifecycle_journal.append('fixture_control_disposition',control=control,scenario=scenario,token=token,
            case_failure=dict(type=type(case_error).__name__,message=str(case_error)) if case_error else None,
            cleanup_failure=dict(type=type(cleanup_error).__name__,message=str(cleanup_error)) if cleanup_error else None,
            cleanup=cleanup,postflight=postflight,elapsed_seconds=time.monotonic()-started,
            disposition='blocked_preserve' if case_error or cleanup_error else 'verified_fixture_only')
        if cleanup_error:raise WorkloadBlocked('fixture_control_independent_cleanup_or_postflight_blocked') from cleanup_error
        if case_error:raise case_error
        result['independent_cleanup']=cleanup;result['independent_postflight']=postflight
        return result

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
        from scripts.workload_fixture_worker import inherited_lock
        inherited_lock(self.root,self.lock_fd)
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
        return self.worker('engine',phase=phase,review=review,authority=authority,reconciliation=reconciliation)

    def inspect(self):
        """Collection only, with a newly and exclusively published private report."""
        result = dict(schema=SCHEMA, fixture_only=True, generation=self.manifest['generation'],
                      manifest_sha256=self.binding, environment=environment(),
                      implementation_blockers=list(IMPLEMENTATION_BLOCKERS),
                      runtime_suitability_verified=False,
                      lifecycle_head=self.journal.head, execution_authority=False)
        if self.last('provision') and self.last('provision')['event']=='fixture_phase_complete':
            result['resources'] = self.adapter('inspect')
            result['runtime_suitability_verified'] = True
        artifact=self.artifact('inspection', result)
        if result.get('resources',{}).get('installed'):
            runtime=Journal(self.root/'runtime-journal',self.binding)
            invalid=[row for row in runtime.rows if row['event']=='fixture_installed_inspection_invalidated']
            self.lifecycle_journal.append('fixture_installed_inspection_refreshed',observed=artifact,
                generation=self.manifest['generation'],monotonic_ns=time.monotonic_ns(),
                runtime_invalidation_sha256=digest(canonical(invalid[-1])) if invalid else None)
        return artifact

    def transition(self, phase, *, authority=None, review=None, engine_phase='install'):
        if self.lock_fd is None:
            with lifecycle_lock(self.root) as fd:
                self.lock_fd=fd
                try:return self.transition(phase,authority=authority,review=review,engine_phase=engine_phase)
                finally:self.lock_fd=None
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
            self.journal.append('fixture_attempt_started', started_at=time.time(),started_monotonic=time.monotonic())
        elif phase != 'cleanup':
            require(self.last('provision') and self.last('provision')['event'] == 'fixture_phase_complete',
                    'fixture_provision_not_complete')
        self.journal.append('fixture_phase_intent', phase=phase)
        try:
            self.require_target()
            self.deadline(cleanup=phase == 'cleanup')
            if phase == 'provision':
                self.adapter('provision')
                self.proposal()
                self.adapter('peer-probe')
            elif phase in ('install', 'rollback', 'reconcile'):
                self.engine(engine_phase if phase == 'reconcile' else phase, reconciliation=phase == 'reconcile',
                            authority=authority, review=review)
            else:
                # The adapter must prove ownership/inactivity before any deletion.
                # No recursive removal or Docker prune is built into this driver.
                cleanup_result = self.adapter('cleanup', cleanup=True)
                require(cleanup_result.get('cleanup_verified') is True,'fixture_cleanup_ownership_unresolved_preserve')
            self.journal.append('fixture_phase_complete', phase=phase)
        except BaseException as error:
            self.journal.append('fixture_phase_failed', phase=phase,
                                error=dict(type=type(error).__name__, message=str(error)),
                                ownership='unresolved_preserve', automatic_retry=False)
            raise


def fixture_engine(root, *, phase, review, authority, reconciliation=False, lock_fd=None):
    """Fixture-only fault injection through existing Python boundaries."""
    from scripts.workload_fixture_worker import inherited_lock
    inherited_lock(root,lock_fd)
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
    from deploy.workload_fixture_faults import FaultInjector
    injector=FaultInjector(fixture.root,fixture.manifest,fixture.binding,proposal)
    historical_fault=fault
    def fault(step,point):
        historical_fault(step,point)
        injector.operation(backend.journal,step,point)
    if reconciliation:
        reconcile(proposal, raw, review_raw, authorized, backend, phase=phase)
    else:
        with injector.scope():
            execute(proposal, raw, review_raw, authorized, backend, phase=phase, fault=fault)
        plan=fixture.manifest.get('recovery_fault_plan')
        if plan is None or plan['step'].split(':',1)[0]==phase:injector.assert_fired(backend.journal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=(*PHASES, '_engine'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--recipe', type=Path)
    parser.add_argument('--recovery-fault-plan',type=Path)
    parser.add_argument('--case', choices=CASES, default='complete')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--engine-phase', choices=('install', 'rollback'), default='install')
    parser.add_argument('--reconcile-engine', action='store_true')
    args = parser.parse_args()
    if args.phase == 'prepare':
        plan=private(args.recovery_fault_plan)[1] if args.recovery_fault_plan else None
        value = prepare(args.root, recipe=args.recipe, case=args.case,recovery_fault_plan=plan)
        print(json.dumps(dict(generation=value['generation'], environment=value['environment'], execution_authority=False)))
        return
    require(args.recovery_fault_plan is None,'fixture_fault_plan_prepare_only')
    if args.phase == '_engine':
        # The child lock handoff is unfinished. Refuse the private worker route
        # rather than exposing an unlocked mutation entrypoint.
        raise RuntimeError('fixture_internal_worker_requires_inherited_lifecycle_lock')
    with lifecycle_lock(args.root) as fd:
        fixture = Fixture(args.root)
        fixture.lock_fd = fd
        if args.phase == 'inspect':
            print(json.dumps(fixture.inspect()))
        else:
            fixture.transition(args.phase, authority=args.authorization, review=args.review, engine_phase=args.engine_phase)


if __name__ == '__main__':
    main()
