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


def regular(root, name):
    """Refuse symlinks in every path component, including the root."""
    path = Path(root).absolute()
    for parent in (*reversed(path.parents), path):
        require(not parent.is_symlink(), 'release_symlink')
    for part in PurePosixPath(relative(name)).parts:
        path /= part
        require(not path.is_symlink(), 'release_symlink')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'release_not_exclusive_regular')
    with path.open('rb') as stream:
        require(os.fstat(stream.fileno()) == before, 'release_changed')
        data = stream.read()
        require(os.fstat(stream.fileno()) == before and path.lstat() == before, 'release_changed')
    return data, stat.S_IMODE(before.st_mode)


def validate(manifest):
    require(set(manifest) == {'schema', 'benchmark_version', 'files', 'interpreter',
                              'worker_environment', 'evaluator_fingerprint', 'coordinator_image',
                              'configurations', 'dependencies', 'units'}, 'release_manifest_fields')
    require(manifest['schema'] == SCHEMA and manifest['benchmark_version'] == '0.5.0', 'release_schema')
    require(manifest['interpreter'] == {'implementation': 'cpython', 'version': '3.12',
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
    return digest(frozen)


def freeze(source, destination, *, source_names, generated_units, wheels, bindings):
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
        payload[key] = (data, 0o600)
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
