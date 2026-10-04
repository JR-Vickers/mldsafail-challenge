"""Retain a minimal source-bound proposed worker context; no implicit Docker use."""
import hashlib
import json
import os
import re
import stat
import shutil
import subprocess
from pathlib import Path
from mldsafail.benchmark_v050.execution import WORKER_FILES


def parse_wheel_pins(path):
    pins={}
    for line in path.read_text().splitlines():
        if line.startswith('#'):continue
        match=re.fullmatch(r'([a-z0-9_]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})',line)
        if match is None: raise ValueError('Unsupported frozen wheel requirement')
        pins[match[1]]=(match[2],match[3])
    return pins


def frozen_wheel_pins():
    return parse_wheel_pins(Path(__file__).parent.parent/'benchmark_v050/requirements.txt')


def native_wheel_pins():
    path=Path(__file__).parent/'requirements.amd64.lock'
    if hashlib.sha256(path.read_bytes()).hexdigest()!='35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0':
        raise ValueError('Separately reviewed amd64 dependency lock required')
    return parse_wheel_pins(path)


def approved_wheels(directory,inventory):
    directory=Path(directory).absolute()
    if any(path.is_symlink() for path in (directory,*directory.parents)):
        raise ValueError('Wheel paths cannot contain symlinks')
    info=directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:
        raise ValueError('Owned immutable wheel directory required')
    if not isinstance(inventory,dict) or set(inventory)!={path.name for path in directory.iterdir()}:
        raise ValueError('Exact approved wheel inventory required')
    pins=native_wheel_pins();seen=set();result={}
    for name,expected in inventory.items():
        match=re.fullmatch(r'([a-z0-9_]+)-([^-]+)-cp312-cp312-(manylinux[^/]+x86_64)\.whl',name)
        if match is None or match[1] not in pins or match[1] in seen or (match[2],expected)!=pins[match[1]]:
            raise ValueError('Wheel must match reviewed amd64 package/version/hash and native platform')
        descriptor=os.open(directory/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022 or info.st_nlink!=1 or not 0<info.st_size<=128*1024*1024:
                raise ValueError('Bounded regular immutable wheel required')
            digest=hashlib.sha256()
            while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
            after=os.fstat(descriptor)
            if digest.hexdigest()!=expected or (after.st_size,after.st_mtime_ns)!=(info.st_size,info.st_mtime_ns):
                raise ValueError('Approved wheel bytes differ from reviewed architecture hash')
        finally:os.close(descriptor)
        seen.add(match[1]);result[name]=directory/name
    if seen!=set(pins):raise ValueError('Complete frozen dependency wheels required')
    return result


def wheel_protocol(config):
    """Optional exact private wheel protocol beside the fresh driver state root."""
    from deploy import owned_daemon
    path=Path(config['state_root']).parent/'v060-worker-protocol.json'
    if path.is_symlink():raise ValueError('Private wheel protocol cannot be a symlink')
    if not path.exists():return {}
    value=owned_daemon.read_private_json(path)
    if set(value)!={'schema','approved_wheel_directory','approved_wheel_sha256','provenance_receipt'} or value['schema']!='mldsafail.v060-worker-protocol.v1':
        raise ValueError('Strict approved offline wheel protocol required')
    approved_wheels(value['approved_wheel_directory'],value['approved_wheel_sha256'])
    provenance=owned_daemon.read_private_json(value['provenance_receipt'])
    if (set(provenance)!={'schema','source_image','architecture','wheel_sha256','artifacts_sha256'}
            or provenance['schema']!='mldsafail.v060-offline-wheel-provenance.v1'
            or provenance['architecture']!='linux/amd64'
            or provenance['source_image']!='sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe'
            or provenance['artifacts_sha256']!='0aaec49378c4b61c93fb5edf475fb619f5b7b7950406628283773ea6470eb01c'
            or provenance['wheel_sha256']!=value['approved_wheel_sha256']):
        raise ValueError('Exact retained native wheel provenance required')
    return dict(wheel_directory=value['approved_wheel_directory'],wheel_inventory=value['approved_wheel_sha256'],wheel_provenance=provenance)


def prepare_context(output, *, command=None, wheel_directory=None, wheel_inventory=None, wheel_provenance=None):
    output = Path(output)
    if output.exists():
        raise ValueError('New retained context directory required')
    wheels={} if wheel_directory is None else approved_wheels(wheel_directory,wheel_inventory)
    if wheel_directory is None and wheel_inventory is not None:raise ValueError("Wheel directory required")
    root = Path(__file__).parent
    frozen = root.parent/'benchmark_v050'
    files = {'Dockerfile':root/'Dockerfile', 'requirements.txt':root/'requirements.amd64.lock',
             'artifacts.py':frozen/'artifacts.py',
             'mldsafail/benchmark_v060/worker.py':root/'worker.py',
             'mldsafail/benchmark_v060/__init__.py':root/'__init__.py'}
    files.update({f'mldsafail/benchmark_v050/{name}':frozen/name for name in WORKER_FILES if name != "worker.py"})
    output.mkdir(mode=0o700, parents=True)
    (output/'wheels').mkdir()
    for relative, source in files.items():
        if source.is_symlink():
            raise ValueError('Source artifacts must be regular files')
        target = output/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source,target)
    for name,source in wheels.items():
        target=output/'wheels'/name
        shutil.copyfile(source,target,follow_symlinks=False)
        if not target.is_file() or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=wheel_inventory[name]:
            raise ValueError('Copied wheel changed from approved frozen bytes')
    if wheel_provenance is not None:
        (output/'wheel-provenance.json').write_text(json.dumps(wheel_provenance,sort_keys=True,separators=(',',':')))
    (output/'mldsafail/__init__.py').write_text('')
    manifest = {path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.rglob('*')) if path.is_file()}
    identity = hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def git_output(argv):
        value=command(argv) if command is not None else subprocess.check_output(argv,timeout=15)
        return value.decode() if isinstance(value,bytes) else value
    record = dict(schema='mldsafail.mlwe-v060-worker-context.v1', benchmark_version='0.6.0',
                  measurement_method='cgroup-v2-usage-usec', architecture='linux/amd64',
                  architecture_lock_sha256=manifest['requirements.txt'], source_sha256=identity, files=manifest,
                  native_verified=False, image=None,
                  source_commit=git_output(['git','-C',str(root),'rev-parse','HEAD']).strip(),
                  source_tree_clean=not bool(git_output(['git','-C',str(root),'status','--porcelain']).strip()))
    (output/'source-manifest.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    return record
