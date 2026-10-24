"""Concrete, synthetic-only Linux installation-fixture resources.

This module is invoked by the fixture's locked, bounded worker, never by an
installation recipe. All resources are local to its root or explicitly named
in its frozen plan. No application database or production Docker endpoint is
accepted. The previous coordinator is never started.
"""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import time

from deploy.workload_installation import exclusive, identity, read_owned_file
from deploy.workload_release import canonical, digest, regular, verify
from mldsafail.evaluator.native_workload import NativeRuntime, process_birth, require, values


LABEL = 'org.mldsafail.installation-fixture'
ROLES = ('supervisor', 'native', 'controller')


def resource_plan(root, uid, unit_directory):
    root = Path(root)
    token = digest(str(root).encode())[:16]
    manager = f'/sys/fs/cgroup/user.slice/user-{uid}.slice/user@{uid}.service'
    compute = 'mldsafail-fixture-'+token+'.service'
    from deploy.workload_prerequisites import mount_unit
    mount_name, _ = mount_unit(dict(path=str(root/'output'), backing_file=str(root/'output.ext4')))
    return dict(root=str(root), token=token, manager=manager, heavy=manager+'/mldsafail.slice/mldsafail-heavy.slice',
                cgroups=[manager+'/mldsafail.slice',manager+'/mldsafail.slice/mldsafail-heavy.slice'],
                compute=compute, unit_directory=unit_directory, mount_unit=mount_name,
                containers={role:'mldsafail-fixture-'+token+'-'+role for role in ('web', 'proxy', 'database')},
                units=[str(Path(unit_directory)/name) for name in
                       ('mldsafail-heavy.slice', 'mldsafail-workload-supervisor.service', compute)],
                privileged_units=['/etc/systemd/system/'+mount_name,
                                  '/etc/systemd/system/local-fs.target.wants/'+mount_name],
                owned_trees=['wheels','previous','release','frozen','engine-journal','output','gate','gate-previous'],
                owned_files=['signing.key','synthetic-postgres.env','output.ext4','current','proposal.json','baseline.json',
                             'rollback-compatibility.json',*[role+'-template.json' for role in ROLES]],
                preserve=['output', 'output.ext4', 'previous', 'engine-journal', 'artifacts'])


class Resources:
    def __init__(self, fixture):
        self.fixture = fixture
        self.root = fixture.root
        self.journal = fixture.journal
        self.plan = fixture.manifest['resource_plan']
        self.settings = json.loads(self.input('settings').read_bytes())
        require(set(self.settings) == {'coordinator_image', 'worker_environment', 'evaluator_fingerprint',
                                     'postgres_image', 'unit_directory', 'daemon_pid_file', 'daemon_executable'},
                'fixture_settings_fields')
        require(self.settings['unit_directory'] == str(Path.home()/'.config/systemd/user') == self.plan['unit_directory'],
                'fixture_unit_directory_changed')
        self.endpoint = ['/usr/bin/docker', '--host', f'unix:///run/user/{os.getuid()}/docker.sock']
        self.cleanup_mode = False
        bindings = [row['observed'] for row in self.journal.rows if row['event']=='fixture_daemon_bound']
        require(len(bindings)<=1,'fixture_daemon_binding_ambiguous')
        self._daemon_binding = bindings[0] if bindings else None

    def daemon_birth(self):
        pid_path = Path(self.settings['daemon_pid_file'])
        pid = int(regular(pid_path.parent,pid_path.name)[0])
        executable = Path(self.settings['daemon_executable'])
        return dict(process=process_birth(pid),executable=identity(executable,content=False),
                    socket=identity(self.endpoint[2].removeprefix('unix://'),content=False),
                    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())

    def check_daemon(self):
        if self._daemon_binding is not None:
            require(self.daemon_birth()==self._daemon_binding,'fixture_daemon_replaced_preserve')

    def input(self, name):
        require(name in self.fixture.manifest['inputs'], 'fixture_offline_input_missing:'+name)
        return self.root/'inputs'/name

    def run(self, argv, *, seconds=35):
        self.check_daemon()
        data = self.fixture.command(argv, cleanup=self.cleanup_mode, seconds=seconds).read_bytes()
        self.check_daemon()
        return data

    def docker(self, args, **kwargs):
        return self.run([*self.endpoint, *args], **kwargs)

    def unit(self, *args):
        return self.run(['/usr/bin/systemctl', '--user', *args])

    def allowed(self, path):
        path = Path(path)
        require(path.is_absolute() and '..' not in path.parts,'fixture_resource_path_invalid')
        require(not any(p.is_symlink() for p in path.parents), 'fixture_resource_parent_symlink')
        own = False
        if path.is_relative_to(self.root):
            parts = path.relative_to(self.root).parts
            own = bool(parts) and (parts[0] in self.plan['owned_trees'] or len(parts)==1 and parts[0] in self.plan['owned_files'])
        require(own or str(path) in self.plan['units']+self.plan['privileged_units']+self.plan['cgroups'],
                'fixture_resource_not_planned')

    def create(self, path, operation, observe=None):
        path = Path(path)
        self.allowed(path)
        require(identity(path, content=False)['state'] == 'absent', 'fixture_destination_exists:'+str(path))
        self.journal.append('fixture_resource_intent', path=str(path))
        operation()
        observed = (observe or (lambda: identity(path)))()
        self.journal.append('fixture_resource_created', path=str(path), observed=observed)
        return observed

    def mkdir(self, path):
        return self.create(path, lambda: Path(path).mkdir(mode=0o700))

    def write(self, path, data, mode=0o600):
        return self.create(path, lambda: exclusive(path, data, mode))

    def installation(self, release):
        release = self.root/release
        return dict(python=str(release/'.venv/bin/python'), release=str(release/'bundle'),
                    configuration=str(release/'config/supervisor.json'),
                    gate_root=str(self.root/('gate-previous' if release.name == 'previous' else 'gate')),
                    heavy_path=self.plan['heavy'], memory_ceiling=1024**3, uid=os.getuid(),
                    unit_directory=self.plan['unit_directory'])

    def daemon(self):
        info = json.loads(self.docker(['info', '--format', '{{json .}}']))
        require(info['Architecture'] in ('x86_64', 'amd64') and info['CgroupDriver'] == 'systemd' and
                info['CgroupVersion'] == '2' and any('rootless' in v for v in info['SecurityOptions']),
                'fixture_rootless_systemd_x86_64_daemon_required')
        pid_path = Path(self.settings['daemon_pid_file'])
        require(str(pid_path) == f'/run/user/{os.getuid()}/docker.pid', 'fixture_daemon_pid_path')
        pid = int(regular(pid_path.parent, pid_path.name)[0])
        executable = Path(self.settings['daemon_executable'])
        actual = executable.stat(); running = Path(f'/proc/{pid}/exe').stat()
        require((actual.st_dev,actual.st_ino)==(running.st_dev,running.st_ino), 'fixture_daemon_executable_changed')
        observed = self.daemon_birth()
        if self._daemon_binding is None:
            self.journal.append('fixture_daemon_bound',observed=observed,daemon_id=info['ID'])
            self._daemon_binding = observed
        require(observed==self._daemon_binding,'fixture_daemon_replaced_preserve')
        return dict(info=info, pid=pid, executable=str(executable),
                    executable_sha256=digest(regular(executable.parent, executable.name)[0]))

    def services(self, daemon):
        require(not self.docker(['ps', '-aq', '--no-trunc']).strip(), 'fixture_daemon_has_unowned_containers')
        retained = {}
        for role, name in self.plan['containers'].items():
            image = self.settings['postgres_image'] if role == 'database' else self.settings['coordinator_image']
            actual = json.loads(self.docker(['image', 'inspect', image]))[0]
            require(actual['Id'] == image and actual['Architecture'] == 'amd64' and actual['Os'] == 'linux',
                    'fixture_image_platform_changed')
            argv = ['create', '--name', name, '--label', LABEL+'='+self.fixture.manifest['generation'],
                    '--network=none', '--restart=no', '--log-driver=none', '--cpus=.25', '--pids-limit=64',
                    '--memory=192m' if role == 'database' else '--memory=32m',
                    '--memory-swap=192m' if role == 'database' else '--memory-swap=32m', '--read-only']
            if role == 'database':
                # Local synthetic authentication only; no exposed port or network.
                argv += ['--tmpfs', '/var/lib/postgresql/data:size=64m', '--tmpfs', '/var/run/postgresql:size=8m',
                         '--tmpfs', '/tmp:size=8m', '--env-file', str(self.root/'synthetic-postgres.env'),
                         image, 'postgres', '-c', 'shared_buffers=8MB',
                         '-c', 'max_connections=10']
            else:
                argv += ['--cap-drop=ALL', '--security-opt=no-new-privileges', '--entrypoint=/bin/sleep', image, 'infinity']
            self.journal.append('fixture_container_intent', name=name, image=image)
            identifier = self.docker(argv).decode().strip()
            row = json.loads(self.docker(['inspect', identifier]))[0]
            require(row['Id'] == identifier and row['Name'] == '/'+name and row['Image'] == image and
                    row['Config']['Labels'].get(LABEL) == self.fixture.manifest['generation'], 'fixture_container_identity')
            self.journal.append('fixture_container_created', name=name, id=identifier, created=row['Created'], image=image)
            self.docker(['start', identifier])
            row = json.loads(self.docker(['inspect', identifier]))[0]
            require(row['State']['Running'] and row['HostConfig']['NetworkMode'] == 'none' and
                    not row['NetworkSettings']['Ports'], 'fixture_container_not_isolated')
            retained[role] = dict(id=identifier, image=image, started_at=row['State']['StartedAt'], running=True)
            self.journal.append('fixture_container_started', role=role, observed=retained[role],
                                created=row['Created'], process=process_birth(row['State']['Pid']))
        db = retained['database']['id']
        self.docker(['exec', '--user', 'postgres', db, '/bin/sh', '-c',
                     'for i in $(seq 1 60); do pg_isready -q -U postgres -d workload_fixture && exit 0; sleep .25; done; exit 1'])
        self.docker(['exec', '--user', 'postgres', db, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
                     '-d', 'workload_fixture', '-c',
                     "CREATE TABLE inert_fixture_state(id integer PRIMARY KEY,value text NOT NULL); "
                     "INSERT INTO inert_fixture_state SELECT i,'fixture-'||i::text FROM generate_series(1,8) i;"])
        return retained

    def configurations(self, release, daemon, retained):
        installation = self.installation(release)
        python = str(self.root/release/'tools/interpreter/python/bin/python3.12')
        # Archive entrypoint bytes, not a fabricated identity.
        from deploy.workload_artifacts import describe
        tool = describe(self.input('interpreter_archive'), role='interpreter', version='3.12.10', entrypoint='python/bin/python3.12')
        controller = dict(native_configuration=str(self.root/release/'config/native.json'),
                          identity=dict(benchmark_version='0.5.0', evaluator_fingerprint=self.settings['evaluator_fingerprint'],
                                        hidden_suite_version='fixture-only', worker_class='fixture', epoch_id='fixture-no-epoch'),
                          epoch_path=str(self.root/'absent-epoch'), worker_image=self.settings['worker_environment']['image_id'],
                          signing_key=str(self.root/'signing.key'))
        heavy = Path(self.plan['heavy'])
        chain = []
        for path in (heavy, *heavy.parents):
            chain.append({key:identity(path)[key] for key in ('path', 'device', 'inode')})
            if str(path) == '/sys/fs/cgroup': break
        worker_image = json.loads(self.docker(['image', 'inspect', self.settings['worker_environment']['image_id']]))[0]
        native = dict(root=installation['gate_root'], heavy=str(heavy), heavy_birth=chain[0], ancestors=chain,
                      output=str(self.root/'output'), disk_root=str(self.root), docker=self.endpoint,
                      daemon_id=daemon['info']['ID'], boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                      python=installation['python'], python_sha256=tool['members'][tool['entrypoint']]['sha256'],
                      controller_configuration=str(self.root/release/'config/controller.json'),
                      controller_configuration_sha256=digest(canonical(controller)),
                      roles=dict(participant=dict(timeout_seconds=60)),
                      router=installation['release']+'/bin/docker',
                      worker=dict(image=self.settings['worker_environment']['image_id'],
                                  configuration=worker_image['Id'], platform_manifest=self.settings['worker_environment']['image_id']),
                      environment=dict(PYTHONPATH=installation['release']+'/src:'+installation['release'],
                                       PYTHONDONTWRITEBYTECODE='1'),
                      retained_services={role:row['id'] for role,row in retained.items()},
                      daemon_pid_file=self.settings['daemon_pid_file'], daemon_executable=daemon['executable'],
                      daemon_sha256=daemon['executable_sha256'])
        supervisor = dict(root=installation['gate_root'], socket=installation['gate_root']+'/supervisor.sock',
                          helper=[installation['python'], '-m', 'mldsafail.evaluator.native_workload', '--configuration',
                                  str(self.root/release/'config/native.json')], roles=dict(participant=dict(role='participant')))
        NativeRuntime(native)
        return dict(supervisor=supervisor, native=native, controller=controller)

    def release(self, release, daemon, retained, *, destination=None):
        from deploy.workload_release import freeze_runtime
        from deploy.workload_artifacts import extract
        from deploy.workload_dependencies import installed_inventory, project_entrypoints
        installation = self.installation(release)
        configs = self.configurations(release, daemon, retained)
        bindings = {key:self.settings[key] for key in ('coordinator_image', 'worker_environment', 'evaluator_fingerprint')}
        bindings.update(interpreter=dict(implementation='cpython', version='3.12', platform='linux', architecture='x86_64', minimum_glibc='2.28'),
                        configurations={role:dict(path=str(self.root/release/'config'/(role+'.json')),
                                                 sha256=digest(canonical(value))) for role,value in configs.items()},
                        private_artifacts=dict(signing_key=dict(sha256=identity(self.root/'signing.key')['sha256'], bytes=32)))
        source = Path(self.fixture.manifest['source_root'])
        for name, expected in self.fixture.manifest['source_hashes'].items():
            require(digest(regular(source,name)[0]) == expected, 'fixture_source_changed_new_generation_required')
        root = self.root/release
        self.mkdir(root)
        bundle = Path(destination) if destination else root/'bundle'
        self.journal.append('fixture_release_freeze_intent', path=str(bundle))
        wheels = sorted((self.root/'wheels').iterdir())
        manifest = freeze_runtime(source,bundle,installation=installation,wheels=wheels,bindings=bindings,
            interpreter_archive=self.input('interpreter_archive'),installer_archive=self.input('installer_archive'),
            image_archive=self.input('image_archive'))
        self.journal.append('fixture_release_frozen', path=str(bundle), manifest_sha256=digest(canonical(manifest)))
        if bundle != root/'bundle':
            shutil.copytree(bundle, root/'bundle')
            verify(root/'bundle', manifest)
        self.mkdir(root/'tools')
        for role, row in manifest['tools'].items():
            self.create(root/'tools'/role, lambda role=role,row=row:extract(regular(bundle,row['archive'])[0],root/'tools'/role,row['members']))
        prefix = ['/usr/bin/sudo','-n','/usr/bin/unshare','--net','--setgid='+str(os.getgid()),'--setuid='+str(os.getuid()),
                  '/usr/bin/env','PYTHONDONTWRITEBYTECODE=1',str(root/'tools/installer/uv-x86_64-unknown-linux-gnu/uv'),'--no-cache','--no-config']
        interpreter = str(root/'tools/interpreter/python/bin/python3.12')
        self.run([*prefix,'venv','--offline','--no-project','--python',interpreter,str(root/'.venv')])
        self.run([*prefix,'pip','install','--offline','--no-index','--no-deps','--python',installation['python'],
                  *[str(bundle/name) for name in manifest['dependencies']]])
        project_entrypoints(root/'bundle',root/'.venv')
        self.mkdir(root/'config')
        for role, value in configs.items(): self.write(root/'config'/(role+'.json'),canonical(value))
        if release=='release':
            self.journal.append('fixture_precomputation_inventory',root=identity(root),tree=self.tree(root))
        return manifest, installed_inventory(root/'.venv',interpreter=interpreter), configs

    def tree(self, root):
        result = {}
        for parent,dirs,files in os.walk(root,followlinks=False):
            for name in [*dirs,*files]:
                path = Path(parent)/name
                row = identity(path,content=False)
                require(row['uid']==os.getuid(),'fixture_precomputation_foreign_owner')
                if path.is_file() and not path.is_symlink():
                    require(path.lstat().st_nlink==1,'fixture_precomputation_shared_file')
                result[str(path.relative_to(root))] = row
        return result

    def inventory(self):
        from deploy.workload_registry import REFERENCE_FIELDS
        owners = {}; settings = {}; refs = {}; files = {}; registry = {}
        account = pwd.getpwuid(os.getuid()).pw_name
        for manager, uid, account_name, prefix in (('system',0,'root',['/usr/bin/sudo','-n','/usr/bin/systemctl']),
                                                  ('user',os.getuid(),account,['/usr/bin/systemctl','--user'])):
            names = set()
            for verb in ('list-units','list-unit-files'):
                raw = self.run([*prefix,verb,'--all','--type=service,timer,socket,path','--full','--plain','--no-legend','--no-pager'])
                names.update(line.split()[0] for line in raw.decode().splitlines() if line.strip())
                require(len(names)<=2048,'fixture_manager_inventory_limit')
            registry[manager+':'+str(uid)] = sorted(names)
            for name in sorted(names):
                identifier = manager+':'+str(uid)+':'+name
                fields = ('ActiveState','UnitFileState','Restart','Triggers',*REFERENCE_FIELDS)
                raw = self.run([*prefix,'show',name,'--all','--property='+','.join(fields)]).decode()
                row = dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
                require(set(row) == set(fields), 'fixture_inventory_incomplete')
                require(set(row['Triggers'].split()) <= names, 'fixture_inventory_unresolved_trigger')
                pause = manager == 'user' and name == self.plan['compute']
                owners[identifier] = dict(manager=manager, uid=uid, account=account_name,
                    restart=row['Restart'] or 'no', triggers=[manager+':'+str(uid)+':'+v for v in row['Triggers'].split()],
                    disposition='pause' if pause else 'retain', active=row['ActiveState']=='active',
                    enabled=row['UnitFileState'].startswith('enabled'),masked=row['UnitFileState'].startswith('masked'))
                settings[identifier] = {key:row[key] for key in ('ActiveState','UnitFileState','Restart','Triggers')}
                refs[identifier] = {key:row[key] for key in REFERENCE_FIELDS}
                paths = set(row['DropInPaths'].split())
                if row['FragmentPath']: paths.add(row['FragmentPath'])
                environment = row['EnvironmentFiles']
                matches = list(re.finditer(r'(\S+) \(ignore_errors=(?:yes|no)\)',environment))
                require(not environment or ' '.join(m[0] for m in matches)==environment,'fixture_environment_reference_syntax')
                paths.update(m[1] for m in matches)
                for path in paths:
                    require(Path(path).exists(),'fixture_missing_inherited_reference')
                    files[path] = digest(read_owned_file(path,self.run)[0])
                    require(len(files)<=2048,'fixture_reference_inventory_limit')
        receipt = digest(canonical(dict(owners=owners, settings=settings, references=refs, files=files)))
        scheduling = dict(unclassified=0,references_open=0,receipt_sha256=receipt,units=sorted(owners),
                          computational_units=[name for name,row in owners.items() if row['disposition']=='pause'],owners=owners)
        inventory = dict(receipt_sha256=receipt,raw_sha256=receipt,errors=0,truncations=0,unknown_owners=0,
                         unresolved_references=0,original_files=files,manager_settings=settings,manager_units=registry,
                         execution_references=refs,absent_files=[])
        return scheduling, inventory

    def fingerprint(self, source):
        from deploy.workload_installed import schema_fingerprint
        raw = self.docker(['exec','--user','postgres',source['rollback']['schema']['container_id'],'psql','-At',
                           '-U','postgres','-d','workload_fixture','-c',
                           'SELECT id,value FROM inert_fixture_state ORDER BY id;'])
        return dict(schema_sha256=schema_fingerprint(source),data_sha256=digest(raw))

    def provision(self):
        daemon = self.daemon()
        # Check the entire external namespace before creating even the first
        # container. A historical fixture's units/cgroups are not ours to adopt.
        for path in self.plan['units']+self.plan['privileged_units']+self.plan['cgroups']:
            require(identity(path,content=False)['state']=='absent','fixture_inherited_resource_preserve:'+path)
        loaded = self.unit('list-units','--all','--type=slice,service','--full','--plain','--no-legend','--no-pager').decode()
        names = {line.split()[0] for line in loaded.splitlines() if line.strip()}
        require(not names.intersection({'mldsafail.slice','mldsafail-heavy.slice','mldsafail-workload-supervisor.service',self.plan['compute']}),
                'fixture_loaded_unit_namespace_preserve')
        # Required offline inputs are real archives/wheels. No downloads here.
        self.input('interpreter_archive'); self.input('installer_archive'); self.input('image_archive')
        self.mkdir(self.root/'wheels')
        for name,row in self.fixture.manifest['inputs'].items():
            original = row.get('original_name','')
            if original.endswith('.whl'): self.write(self.root/'wheels'/original,regular(self.root/'inputs',name)[0])
        require(list((self.root/'wheels').iterdir()),'fixture_wheels_absent')
        from deploy.workload_units import render_v3
        from deploy.workload_prerequisites import apply, mount_unit
        directory = Path(self.plan['unit_directory'])
        require(directory.is_dir() and not directory.is_symlink(),'fixture_unit_directory_missing')
        for path in self.plan['units']+self.plan['privileged_units']:
            require(identity(path,content=False)['state']=='absent','fixture_inherited_resource_preserve:'+path)
        self.write(directory/'mldsafail-heavy.slice',render_v3(self.installation('previous'))['mldsafail-heavy.slice'].encode())
        self.unit('daemon-reload')
        source = dict(host=dict(uid=os.getuid()),resources=dict(release=dict(path=str(self.root/'release')),
            delegation=dict(state='proposed',path=self.plan['heavy']),
            output=dict(state='proposed',path=str(self.root/'output'),backing_file=str(self.root/'output.ext4'),
                        bytes=64*1024**2,filesystem='ext4',exclusive_backing_file=True)))
        # This existing helper records original backing/mount/loop ownership.
        apply(source,self.run,self.journal)
        for path in self.plan['cgroups']:
            self.journal.append('fixture_resource_created',path=path,observed=identity(path))
        self.write(self.root/'synthetic-postgres.env',('POSTGRES_DB=workload_fixture\nPOSTGRES_PASSWORD='+os.urandom(32).hex()+'\n').encode())
        retained = self.services(daemon)
        self.write(self.root/'signing.key',os.urandom(32))
        previous, previous_files, previous_configs = self.release('previous',daemon,retained)
        current, current_files, current_configs = self.release('release',daemon,retained,destination=self.root/'frozen')
        for role,value in current_configs.items():
            self.write(self.root/(role+'-template.json'),canonical(value))
        # Retire only the precomputation tree, after privileged inactivity census.
        self.retire_precomputation(current,current_files)
        self.write(self.root/'previous/.supervisor-enabled',canonical(dict(fixture_only=True,generation=self.fixture.manifest['generation'])))
        self.write(directory/'mldsafail-workload-supervisor.service',
                   regular(self.root/'previous/bundle','generated/mldsafail-workload-supervisor.service')[0])
        compute = directory/self.plan['compute']
        self.write(compute,('[Unit]\nConditionPathExists='+str(self.root/'permissions'/('user-'+str(os.getuid())+'.allow'))+
                           '\n[Service]\nExecStart=/usr/bin/sleep infinity\nRestart=always\n[Install]\nWantedBy=default.target\n').encode())
        self.unit('daemon-reload'); self.unit('enable',compute.name); self.unit('start',compute.name)
        self.unit('start','mldsafail-workload-supervisor.service')
        self.mkdir(self.root/'engine-journal')
        source = self.bootstrap(daemon,retained,previous,previous_files,current,current_files,current_configs)
        from deploy.workload_installed import observe_rollback
        from deploy.workload_handoff import observe
        receipt = observe_rollback(source)
        self.write(self.root/'rollback-compatibility.json',canonical(receipt))
        source['rollback']['compatibility_receipt_sha256'] = digest(canonical(receipt))
        source['rollback']['supervisor'] = observe(source,self.run)
        require(source['rollback']['supervisor']['active'],'fixture_previous_supervisor_not_active')
        self.create(self.root/'current',lambda:os.symlink(str(self.root/'previous'),self.root/'current'))
        source['resources']['activation'] = identity(self.root/'current')
        source['captured_at'] = time.time()
        from deploy.workload_v3 import bootstrap
        proposal = bootstrap(source)
        self.write(self.root/'proposal.json',canonical(proposal))
        self.write(self.root/'baseline.json',canonical(self.observations(proposal)))
        return dict(proposal_sha256=digest(canonical(proposal)),previous_compatibility=receipt)

    def retire_precomputation(self, manifest, installed_files):
        root = self.root/'release'
        before = identity(root)
        created = [row['observed'] for row in self.journal.rows if row['event']=='fixture_resource_created' and row['path']==str(root)]
        require(created==[before],'fixture_precomputation_creation_identity_changed')
        from deploy.workload_dependencies import installed_inventory
        from deploy.workload_artifacts import verify_installed_tools
        verify(root/'bundle',manifest); verify_installed_tools(root,manifest)
        require(installed_inventory(root/'.venv',interpreter=str(root/'tools/interpreter/python/bin/python3.12'))==installed_files,
                'fixture_precomputation_changed')
        require({p.name for p in root.iterdir()}=={'bundle','tools','.venv','config'},'fixture_precomputation_unknown_resource')
        require({p.name for p in (root/'config').iterdir()}=={role+'.json' for role in ROLES},'fixture_precomputation_unknown_configuration')
        for role,row in manifest['configurations'].items():
            require(identity(row['path']).get('sha256')==row['sha256'],'fixture_precomputation_configuration_changed')
        inventories = [row for row in self.journal.rows if row['event']=='fixture_precomputation_inventory']
        require(len(inventories)==1 and inventories[0]['root']==before,'fixture_precomputation_inventory_missing')
        bound_tree = inventories[0]['tree']
        require(self.tree(root)==bound_tree,'fixture_precomputation_inventory_changed')
        # Root visibility is mandatory; any inaccessible process/reference blocks.
        script = ('import os,pathlib,sys;root=sys.argv[1];hits=[];'
                  '\nfor proc in pathlib.Path("/proc").glob("[0-9]*"):\n'
                  ' try:\n  paths=[proc/"cwd",proc/"root",*(proc/"fd").iterdir()]\n'
                  '  for p in paths:\n'
                  '   try: v=os.readlink(p)\n'
                  '   except FileNotFoundError: continue\n'
                  '   if v==root or v.startswith(root+"/"):hits.append(str(p))\n'
                  '  if root+"/" in (proc/"maps").read_text():hits.append(str(proc/"maps"))\n'
                  ' except (FileNotFoundError,ProcessLookupError):continue\n'
                  'assert not hits,hits')
        self.run(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,str(root)])
        require(not any(line.split()[4]==str(root) or line.split()[4].startswith(str(root)+'/')
                        for line in Path('/proc/self/mountinfo').read_text().splitlines()),'fixture_precomputation_mounted')
        self.journal.append('fixture_precomputation_retire_intent',observed=before,manifest_sha256=digest(canonical(manifest)),
                            installed_files_sha256=digest(canonical(installed_files)),tree_sha256=digest(canonical(bound_tree)))
        require(identity(root)==before and self.tree(root)==bound_tree,'fixture_precomputation_replaced')
        shutil.rmtree(root)
        self.journal.append('fixture_precomputation_retired',observed=identity(root))

    def bootstrap(self, daemon, retained, previous, previous_files, current, current_files, configs):
        from deploy.workload_installed import cgroup_observation, mount, schema_fingerprint
        from deploy.workload_v3 import BOOTSTRAP
        from deploy.workload_configuration import validate_runtime_templates
        installation = self.installation('release')
        native = configs['native']
        runtime = NativeRuntime(native,run=self.run)
        runtime_identity = runtime.identity()
        heavy = Path(self.plan['heavy']); delegation = cgroup_observation(heavy)
        ancestors = []
        for path in heavy.parents:
            row = cgroup_observation(path); row['retained_service_ancestor'] = str(path)!=str(heavy.parent)
            ancestors.append(row)
            if str(path)=='/sys/fs/cgroup': break
        delegation['ancestors'] = ancestors
        scheduling, inventory = self.inventory()
        for name in ('mldsafail-heavy.slice','mldsafail-workload-supervisor.service'):
            path = str(Path(installation['unit_directory'])/name)
            inventory['original_files'][path] = digest(read_owned_file(path,self.run)[0])
        def proposed(path):return dict(state='proposed',path=str(path),creation='exclusive_owned_creation',preserve='current_and_rollback')
        tools = {role:dict(path=str(self.root/'release/tools'/role/row['entrypoint']),
                          sha256=row['members'][row['entrypoint']]['sha256'],bytes=row['members'][row['entrypoint']]['bytes'],version=row['version'])
                 for role,row in current['tools'].items()}
        bootstrap_python = self.root/'previous/tools/interpreter/python/bin/python3.12'
        bootstrap_row = dict(path=str(bootstrap_python),sha256=digest(regular(bootstrap_python.parent,bootstrap_python.name)[0]),
                             bytes=bootstrap_python.stat().st_size,version='3.12.10')
        host = dict(hostname=os.uname().nodename,uid=os.getuid(),boot_id=native['boot_id'],daemon_id=daemon['info']['ID'],
                    user_manager=identity(self.plan['manager']),runtime_identity=runtime_identity)
        containers = []
        for retained_row in retained.values():
            row = json.loads(self.docker(['inspect',retained_row['id']]))[0]
            containers.append(dict(id=row['Id'],daemon_id=host['daemon_id'],owner_uid=os.getuid(),restart_policy='no',running=True,
                disposition='retain',image=row['Image'],created_at=row['Created'],started_at=row['State']['StartedAt'],
                process_birth=process_birth(row['State']['Pid'])))
        uid_map = [[int(v) for v in line.split()] for line in Path(f'/proc/{daemon["pid"]}/uid_map').read_text().splitlines()]
        source = dict(schema=BOOTSTRAP,origin='local_linux',captured_at=time.time(),host=host,installation=installation,manifest=current,
            recipe=dict(bundle_root=str(self.root/'frozen'),artifact_root=str(self.root/'inputs'),**tools,
                bootstrap_interpreter=bootstrap_row,dependency_plan=current['dependency_plan'],installed_files=current_files,
                configuration_sources={role:str(self.root/(role+'-template.json')) for role in ROLES},
                configuration_templates={role:canonical(value).hex() for role,value in configs.items()},
                activation_pointer=str(self.root/'current'),proposal_path=str(self.root/'proposal.json'),journal_root=str(self.root/'engine-journal'),
                private_artifacts=dict(signing_key=dict(identity(self.root/'signing.key'),bytes=32))),
            resources=dict(release=proposed(self.root/'release'),socket=proposed(self.root/'gate/supervisor.sock'),delegation=delegation,
                output=dict(identity(self.root/'output'),**mount(self.root/'output'),bytes=64*1024**2),
                activation=dict(state='observed',path=str(self.root/'current'),device=0,inode=1,target=str(self.root/'previous'))),
            scheduling=scheduling,unit_directories={'user:'+str(os.getuid()):installation['unit_directory'],'system:0':'/etc/systemd/system'},
            permission_root=str(self.root/'permissions'),containers=containers,inventory=inventory,
            admission=dict(memory_available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024,
                           backing_free=shutil.disk_usage(self.root).free),
            rollback=dict(release=str(self.root/'previous'),target=str(self.root/'previous'),manifest=previous,
                manifest_sha256=digest(canonical(previous)),configuration_hashes={role:row['sha256'] for role,row in previous['configurations'].items()},
                coordinator_image=previous['coordinator_image'],schema_sha256='0'*64,installed_schema_sha256='0'*64,
                compatibility_receipt_sha256='0'*64,compatibility_receipt_path=str(self.root/'rollback-compatibility.json'),
                verified_files=True,installed_files=previous_files,python_sha256=bootstrap_row['sha256'],
                schema=dict(container_id=retained['database']['id'],database='workload_fixture',username='postgres')),
            retained_services=retained,uid_mapping=dict(coordinator_container_uid=0,supervisor_host_uid=os.getuid(),uid_map=uid_map,receipt_sha256=digest(canonical(uid_map))))
        schema = schema_fingerprint(source)
        source['rollback'].update(schema_sha256=schema,installed_schema_sha256=schema)
        validate_runtime_templates(source)
        return source

    def observations(self, proposal):
        from deploy.workload_installed import retained, original_settings, mount
        source = proposal['identities']
        return dict(retained_services=retained(source),database=self.fingerprint(source),original_settings=original_settings(source),
                    activation=identity(source['recipe']['activation_pointer']),output=dict(identity(self.root/'output'),**mount(self.root/'output')),
                    units={path:digest(read_owned_file(path,self.run)[0]) for path in self.plan['units']},
                    permission_files=[identity(self.root/'permissions'/('user-'+str(os.getuid())+'.allow'))])

    def postflight(self, proposal):
        from deploy.workload_installed import retained, scheduling, mount
        baseline = json.loads(regular(self.root,'baseline.json')[0])
        source = proposal['identities']
        require(retained(source)==baseline['retained_services'],'fixture_retained_service_changed')
        require(self.fingerprint(source)==baseline['database'],'fixture_database_changed')
        require(dict(identity(self.root/'output'),**mount(self.root/'output'))==baseline['output'],'fixture_output_changed')
        require(identity(self.root/'permissions'/('user-'+str(os.getuid())+'.allow'))['state']=='absent','fixture_computation_permission_present')
        from deploy.workload_installation import Journal
        journal = Journal(source['recipe']['journal_root'],digest(canonical(proposal)))
        inhibited = journal.outcome('install:inhibit_scheduling')
        if inhibited and inhibited['event'] in ('outcome','reconciled'):
            scheduling(proposal)
            from deploy.workload_installed import original_settings
            from deploy.workload_handoff import identifier
            actual = original_settings(source)
            expected = json.loads(canonical(baseline['original_settings']))
            for name in source['scheduling']['computational_units']:
                expected['manager_settings'][name]['ActiveState'] = actual['manager_settings'][name]['ActiveState']
            previous = identifier(source)
            if previous:
                started = journal.outcome('install:start_paused')
                stopped = journal.outcome('rollback:stop_supervisor')
                running = started and started['event'] in ('outcome','reconciled') and not (stopped and stopped['event'] in ('outcome','reconciled'))
                expected['manager_settings'][previous]['ActiveState'] = 'active' if running else 'inactive'
            require(actual==expected,'fixture_original_enable_mask_restart_settings_changed')
        else:
            # Before inhibition (snapshot/image interruptions), preserve the
            # baseline settings except the acknowledged previous handoff.
            from deploy.workload_installed import original_settings
            from deploy.workload_handoff import identifier
            actual = original_settings(source)
            expected = json.loads(canonical(baseline['original_settings']))
            handoff = journal.outcome('install:quiesce_supervisor')
            if handoff and handoff['event'] in ('outcome','reconciled'):
                expected['manager_settings'][identifier(source)]['ActiveState'] = 'inactive'
            require(actual==expected,'fixture_pre_inhibition_settings_changed')
        restored = journal.outcome('rollback:restore_units')
        if restored and restored['event'] in ('outcome','reconciled'):
            for path, expected in baseline['units'].items():
                require(digest(read_owned_file(path,self.run)[0])==expected,'fixture_original_unit_bytes_not_restored')
        require(values(Path(self.plan['heavy'])/'cgroup.events')['populated']==0,'fixture_heavy_descendants_present')
        return dict(verified=True,database=baseline['database'],retained_services=baseline['retained_services'],
                    output_preserved=True,permissions_absent=True,heavy_empty=True)

    def cleanup(self, proposal=None):
        self.cleanup_mode = True
        self.check_daemon()
        if proposal is None:
            return self.partial_cleanup()
        from deploy.workload_installation import Journal
        journal = Journal(proposal['identities']['recipe']['journal_root'],digest(canonical(proposal)))
        pending = [r['step'] for r in journal.rows if r['event']=='intent' and journal.outcome(r['step'])['event']=='intent']
        require(not pending,'fixture_unresolved_engine_transactions_preserve')
        receipt = self.postflight(proposal)
        db = proposal['identities']['rollback']['schema']['container_id']
        snapshot = self.docker(['exec','--user','postgres',db,'pg_dump','-U','postgres','-d','workload_fixture'])
        snapshot_record = self.fixture.artifact('database-snapshot',dict(fixture_only=True,sql_hex=snapshot.hex(),sha256=digest(snapshot)))
        for name in ('mldsafail-workload-supervisor.service',self.plan['compute']):
            state = self.unit('show',name,'--property=ActiveState','--value').strip()
            require(state in (b'inactive',b'failed'),'fixture_service_not_stopped')
        # Preserve output, inhibition, rollback and journals. Trial containers
        # remain available for failure diagnosis until a separately proved retire.
        return dict(receipt,cleanup_verified=True,retirement_complete=False,
                    disposition='stopped_computation_and_preserved_required_resources',
                    preserved=self.plan['preserve'],active_preserved_services=receipt['retained_services'],
                    database_snapshot=snapshot_record,
                    retention_exception=dict(owner='repository_owner',question='retained_fixture_installation_evidence',
                                             review_by_epoch=time.time()+7*86400),bulk_deleted=False)

    def partial_cleanup(self):
        """Stop only acknowledged computational units; never infer ownership."""
        stopped = []; preserved = []; unresolved = []
        created = {row['path']:row['observed'] for row in self.journal.rows if row['event']=='fixture_resource_created'}
        for name in ('mldsafail-workload-supervisor.service',self.plan['compute']):
            path = str(Path(self.plan['unit_directory'])/name)
            if path not in created:continue
            require(identity(path)==created[path],'fixture_partial_cleanup_unit_replaced')
            self.unit('stop',name)
            require(self.unit('show',name,'--property=ActiveState','--value').strip() in (b'inactive',b'failed'),
                    'fixture_partial_cleanup_unit_active')
            stopped.append(path)
        for row in self.journal.rows:
            if row['event']=='mutation_intent' and not any(r['event']=='mutation_outcome' and r.get('resource')==row['resource'] for r in self.journal.rows):
                unresolved.append(dict(resource=row['resource'],reason='unacknowledged_prerequisite_effect'))
            if row['event']=='fixture_resource_intent' and row['path'] not in created:
                unresolved.append(dict(path=row['path'],reason='unacknowledged_resource'))
            if row['event']=='fixture_container_intent':
                acknowledgements = [r for r in self.journal.rows if r['event']=='fixture_container_created' and r['name']==row['name']]
                if len(acknowledgements)!=1:
                    unresolved.append(dict(name=row['name'],reason='unacknowledged_container'));continue
                ack = acknowledgements[0]
                actual = json.loads(self.docker(['inspect',ack['id']]))[0]
                require(actual['Id']==ack['id'] and actual['Image']==ack['image'] and actual['Created']==ack['created'] and
                        actual['Config']['Labels'].get(LABEL)==self.fixture.manifest['generation'],
                        'fixture_partial_cleanup_container_replaced')
                preserved.append(dict(id=actual['Id'],running=actual['State']['Running'],reason='targeted_failure_evidence'))
        heavy = Path(self.plan['heavy'])
        if heavy.exists():
            expected = created.get(str(heavy))
            require(expected and identity(heavy)==expected,'fixture_partial_cleanup_cgroup_unacknowledged')
            require(values(heavy/'cgroup.events')['populated']==0,'fixture_partial_cleanup_cgroup_populated')
        for gate in ('gate','gate-previous'):
            state_path = self.root/gate/'workload.json'
            if state_path.exists():
                state = json.loads(regular(state_path.parent,state_path.name)[0])
                if state.get('paused') is not True or state.get('phase') not in ('cleaned','complete'):
                    unresolved.append(dict(path=str(state_path),reason='unresolved_runtime_transaction'))
        for row in self.journal.rows:
            if row['event']=='fixture_command_result':
                report = row.get('containment')
                if not report or report.get('errors') or report.get('remaining') or row.get('group_remaining') or row.get('cleanup_errors'):
                    unresolved.append(dict(command=row['command'],reason='descendant_termination_unverified'))
        return dict(cleanup_verified=not unresolved,retirement_complete=False,stopped_units=stopped,
                    preserved_containers=preserved,preserved_output=identity(self.root/'output',content=False),
                    unresolved=unresolved,bulk_deleted=False,
                    retention_exception=dict(owner='repository_owner',question='partial_fixture_failure',review_by_epoch=time.time()+7*86400))
