"""V3 offline release freezing and verification; no installation authority.

Bundles exclude private configuration bytes. Their hashes are bound separately.
Publication is exclusive and failures retain the staging directory for inspection.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

from mldsafail.evaluator.native_workload import require

SCHEMA = 'mldsafail.workload-frozen-release.v3'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def relative(name):
    require(type(name) is str and name and str(PurePosixPath(name)) == name and
            not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts and
            '\\' not in name, 'release_path_invalid')
    return name


def stable_stat(info):
    return tuple(getattr(info, key) for key in ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid',
                                               'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def regular(root, name):
    """Refuse symlinks in every path component, including the root."""
    path = Path(root).absolute()
    for parent in (*reversed(path.parents), path):
        require(not parent.is_symlink(), 'release_symlink')
    for part in PurePosixPath(relative(name)).parts:
        path /= part
        require(not path.is_symlink(), 'release_symlink')
    require(path.exists(), 'release_missing_file:'+name)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'release_not_exclusive_regular')
    with path.open('rb') as stream:
        require(stable_stat(os.fstat(stream.fileno())) == stable_stat(before), 'release_changed')
        data = stream.read()
        require(stable_stat(os.fstat(stream.fileno())) == stable_stat(before) and stable_stat(path.lstat()) == stable_stat(before), 'release_changed')
    return data, stat.S_IMODE(before.st_mode)


def validate(manifest):
    require(set(manifest) - {'tools', 'dependency_plan', 'inclusion_policy'} == {'schema', 'benchmark_version', 'files', 'interpreter',
                              'worker_environment', 'evaluator_fingerprint', 'coordinator_image',
                              'configurations', 'dependencies', 'units'}, 'release_manifest_fields')
    require(manifest['schema'] == SCHEMA and manifest['benchmark_version'] == '0.5.0', 'release_schema')
    interpreter = dict(manifest['interpreter'])
    minimum_glibc = interpreter.pop('minimum_glibc', '2.17')
    require(minimum_glibc in ('2.17', '2.28'), 'release_glibc_baseline')
    require(interpreter == {'implementation': 'cpython', 'version': '3.12',
                                      'platform': 'linux', 'architecture': 'x86_64'}, 'release_interpreter')
    require(re.fullmatch('sha256:[a-f0-9]{64}', manifest['coordinator_image']) is not None and
            re.fullmatch('[a-f0-9]{64}', manifest['evaluator_fingerprint']) is not None,
            'release_image_or_evaluator')
    environment = manifest['worker_environment']
    require(type(environment) is dict and set(environment) == {'image_id', 'trusted_fingerprint', 'artifacts', 'host'}
            and re.fullmatch('sha256:[a-f0-9]{64}', environment['image_id']) is not None,
            'release_worker_environment')
    require(type(manifest['files']) is dict and manifest['files'], 'release_files_missing')
    for name, record in manifest['files'].items():
        relative(name)
        require(name != 'manifest.json' and set(record) == {'sha256', 'bytes', 'mode'} and
                re.fullmatch('[a-f0-9]{64}', record['sha256']) is not None and
                type(record['bytes']) is int and record['bytes'] >= 0 and
                record['mode'] in (0o600, 0o700), 'release_file_record')
    configs = manifest['configurations']
    require(set(configs) == {'supervisor', 'native', 'controller'} and
            len({row['path'] for row in configs.values()}) == 3, 'release_configurations')
    for row in configs.values():
        require(set(row) == {'path', 'sha256'} and Path(row['path']).is_absolute() and
                '..' not in Path(row['path']).parts and
                re.fullmatch('[a-f0-9]{64}', row['sha256']) is not None, 'release_configuration_binding')
    for category in ('dependencies', 'units'):
        names = manifest[category]
        require(type(names) is list and names and len(set(names)) == len(names) and
                set(names) <= set(manifest['files']), 'release_category_missing:'+category)
    require(all(name.startswith('offline/') and name.endswith('.whl') and
                ('-any.whl' in name or 'x86_64.whl' in name and 'linux' in name)
                for name in manifest['dependencies']), 'release_linux_wheels_required')
    require(all(name.startswith('generated/') for name in manifest['units']), 'release_units_missing')
    if 'tools' in manifest:
        from deploy.workload_artifacts import validate_tools
        validate_tools(manifest)
    return manifest


def verify(root, manifest):
    """The caller supplies the frozen approved manifest, never checkout hashes."""
    validate(manifest)
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'release_root_invalid')
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            require(not (Path(directory)/name).is_symlink(), 'release_symlink')
        for name in files:
            actual.add(str((Path(directory)/name).relative_to(root)))
    require(actual == set(manifest['files']) | {'manifest.json'}, 'release_unexpected_or_partial_files')
    frozen, _ = regular(root, 'manifest.json')
    require(frozen == canonical(manifest), 'release_manifest_changed')
    for name, record in manifest['files'].items():
        data, mode = regular(root, name)
        require(record == dict(sha256=digest(data), bytes=len(data), mode=mode), 'release_content_changed:'+name)
    from deploy.workload_wheels import inspect_wheel
    for name in manifest['dependencies']:
        inspect_wheel(root/name, manifest['files'][name]['sha256'], glibc_minor=int(manifest['interpreter'].get('minimum_glibc', '2.17').split('.')[1]))
    if 'tools' in manifest:
        from deploy.workload_artifacts import archive_inventory
        for row in manifest['tools'].values():
            require(archive_inventory((root/row['archive']).read_bytes()) == row['members'], 'release_tool_inventory_changed')
        from deploy.workload_dependencies import plan
        actual,requirements=plan((root/'uv.lock').read_bytes(),[root/name for name in manifest['dependencies']],python_full_version=manifest['tools']['interpreter']['version'])
        require(actual == manifest['dependency_plan'] and (root/'offline/requirements.txt').read_bytes() == requirements.encode(), 'release_dependency_plan_changed')
    return digest(frozen)


def freeze(source, destination, *, source_names, generated_units, wheels, bindings, extra_payload=None):
    """Create an inspectable bundle exclusively; never activate or overwrite it."""
    destination = Path(destination)
    require(not destination.exists() and not destination.is_symlink(), 'release_destination_exists')
    # The destination parent must already exist and contain no symlink components.
    for parent in (destination.parent, *destination.parent.parents):
        require(not parent.is_symlink(), 'release_symlink')
    payload = {}
    for name in source_names:
        require(name not in payload, 'release_duplicate_path')
        data, mode = regular(source, name)
        payload[relative(name)] = (data, 0o700 if mode & 0o111 else 0o600)
    for name, contents in generated_units.items():
        key = relative('generated/'+name)
        require(key not in payload, 'release_duplicate_path')
        payload[key] = (contents.encode(), 0o600)
    for wheel in wheels:
        wheel = Path(wheel)
        key = relative('offline/'+wheel.name)
        require(key not in payload, 'release_duplicate_path')
        data, _ = regular(wheel.parent, wheel.name)
        from deploy.workload_wheels import inspect_wheel
        inspect_wheel(wheel, digest(data), glibc_minor=int(bindings['interpreter'].get('minimum_glibc', '2.17').split('.')[1]))
        payload[key] = (data, 0o600)
    for name,data in (extra_payload or {}).items():
        require(relative(name) not in payload, 'release_duplicate_path')
        payload[name]=(data,0o600)
    manifest = dict(bindings, schema=SCHEMA, benchmark_version='0.5.0',
                    files={name: dict(sha256=digest(data), bytes=len(data), mode=mode)
                           for name, (data, mode) in payload.items()},
                    units=['generated/'+name for name in generated_units],
                    dependencies=['offline/'+Path(wheel).name for wheel in wheels])
    validate(manifest)
    destination.mkdir(mode=0o700)
    for name, (data, mode) in {**payload, 'manifest.json': (canonical(manifest), 0o600)}.items():
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('xb') as stream:
            os.chmod(path, mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    verify(destination, manifest)
    return manifest


def runtime_sources(source):
    """Explicit full-runtime inclusion policy, independent of caller file lists.

    Private configuration and generated artifacts are bound separately. Refuse
    links rather than following them into private or unrelated workspaces.
    """
    source = Path(source)
    repository = subprocess.run(['git', '-C', str(source), 'rev-parse', '--show-toplevel'],
                                check=True, capture_output=True, text=True).stdout.strip()
    require(Path(repository).resolve() == source.resolve(), 'release_source_repository_root_required')
    tracked = set(subprocess.run(['git', '-C', str(source), 'ls-files', '-z'],
                                 check=True, capture_output=True).stdout.decode().split('\0'))
    untracked=subprocess.run(['git','-C',str(source),'ls-files','--others','--exclude-standard','-z'],
                             check=True,capture_output=True).stdout.decode().split('\0')
    require(not any(name.startswith(('src/mldsafail/','deploy/','scripts/','migrations/')) and
                    Path(name).suffix in ('.py','.sh','.mako') for name in untracked),
            'release_untracked_runtime_source')
    required = {'pyproject.toml', 'uv.lock', 'README.md', 'alembic.ini', '.dockerignore',
                'config/profiles.toml', 'config/benchmark.toml',
                'compose.production.yaml', 'Dockerfile.coordinator',
                'deploy/worker-linux-amd64.requirements.txt',
                'examples/mlwe/primal-lll/solver.py'}
    for folder in ('src/mldsafail', 'deploy', 'scripts', 'migrations'):
        directory = source/folder
        require(directory.is_dir() and not directory.is_symlink(), 'release_runtime_directory_missing:'+folder)
        for relative_name in tracked:
            if not relative_name.startswith(folder+'/'):
                continue
            path = Path(relative_name)
            if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
                continue
            if folder == 'src/mldsafail':
                require(path.suffix in ('.py', '.toml', '.json', '.html', '.css', '.js',
                                        '.svg', '.png', '.txt', '.md', '.lock') or
                        path.name == 'Dockerfile', 'release_unclassified_package_data:'+relative_name)
            elif path.suffix not in ('.py', '.sh', '.mako'):
                continue
            required.add(relative_name)
    for name in required:
        regular(source, name)
    require('src/mldsafail/evaluator/workload_service.py' in required and
            'scripts/prepare_workload_packet.py' in required and
            any(name.startswith('migrations/versions/') for name in required),
            'release_runtime_incomplete')
    return sorted(required)


def freeze_runtime(source, destination, *, generated_units, wheels, bindings,
                   interpreter_archive, installer_archive):
    """Freeze all runtime sources and lock-derived offline tool/dependency inputs."""
    from deploy.workload_artifacts import describe
    from deploy.workload_dependencies import plan
    source=Path(source);wheels=list(wheels)
    tools=dict(interpreter=describe(interpreter_archive,role='interpreter',version='3.12.10',entrypoint='python/bin/python3.12'),
               installer=describe(installer_archive,role='installer',version='0.13.1',entrypoint='uv-x86_64-unknown-linux-gnu/uv'))
    dependency_plan,requirements=plan((source/'uv.lock').read_bytes(),wheels,python_full_version='3.12.10')
    names=runtime_sources(source)
    policy=dict(name='tracked-complete-runtime-v1',sources=names)
    extra={row['archive']:regular(Path(path).parent,Path(path).name)[0]
           for row,path in ((tools['interpreter'],interpreter_archive),(tools['installer'],installer_archive))}
    extra['offline/requirements.txt']=requirements.encode()
    return freeze(source,destination,source_names=names,generated_units=generated_units,wheels=wheels,
                  bindings=dict(bindings,tools=tools,dependency_plan=dependency_plan,inclusion_policy=policy),extra_payload=extra)


def public_manifest(manifest):
    """Redact owner-private paths and environment details for review artifacts."""
    validate(manifest)
    return dict(schema='mldsafail.workload-public-release.v3',benchmark_version=manifest['benchmark_version'],
        private_manifest_sha256=digest(canonical(manifest)),execution_authority=False,
        interpreter=manifest['interpreter'],coordinator_image=manifest['coordinator_image'],
        worker_image=manifest['worker_environment']['image_id'],
        worker_environment_sha256=digest(canonical(manifest['worker_environment'])),
        evaluator_fingerprint=manifest['evaluator_fingerprint'],
        configurations={role:dict(sha256=row['sha256']) for role,row in manifest['configurations'].items()},
        files=manifest['files'],dependencies=manifest['dependencies'],units=manifest['units'])


def remaining_allocation(manifest,installed_files,completed=()):
    """Conservative byte budget with block rounding, metadata and journal reserve."""
    sizes=[]
    if 'copy_bundle' not in completed:
        sizes.extend(row['bytes'] for row in manifest['files'].values());sizes.append(len(canonical(manifest)))
    if 'tools' not in completed:
        sizes.extend(row.get('bytes',0) for tool in manifest.get('tools',{}).values() for row in tool['members'].values())
    if 'dependencies' not in completed:sizes.extend(row['bytes'] for row in installed_files.values())
    return sum(((size+4095)//4096)*4096+4096 for size in sizes)+64*1024**2
