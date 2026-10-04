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


def frozen_wheel_pins():
    pins={}
    for line in (Path(__file__).parent.parent/'benchmark_v050/requirements.txt').read_text().splitlines():
        match=re.fullmatch(r'([a-z0-9_]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})',line)
        if match is None: raise ValueError('Unsupported frozen wheel requirement')
        pins[match[1]]=(match[2],match[3])
    return pins


def approved_wheels(directory,inventory):
    directory=Path(directory).absolute()
    if any(path.is_symlink() for path in (directory,*directory.parents)):
        raise ValueError('Wheel paths cannot contain symlinks')
    info=directory.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:
        raise ValueError('Owned immutable wheel directory required')
    if not isinstance(inventory,dict) or set(inventory)!={path.name for path in directory.iterdir()}:
        raise ValueError('Exact approved wheel inventory required')
    pins=frozen_wheel_pins();seen=set();result={}
    for name,expected in inventory.items():
        match=re.fullmatch(r'([a-z0-9_]+)-([^-]+)-cp312-cp312-(manylinux[^/]+x86_64)\.whl',name)
        if match is None or match[1] not in pins or match[1] in seen or (match[2],expected)!=pins[match[1]]:
            raise ValueError('Wheel must match frozen package/version/hash and native platform')
        descriptor=os.open(directory/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022 or info.st_nlink!=1 or not 0<info.st_size<=128*1024*1024:
                raise ValueError('Bounded regular immutable wheel required')
            digest=hashlib.sha256()
            while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
            after=os.fstat(descriptor)
            if digest.hexdigest()!=expected or (after.st_size,after.st_mtime_ns)!=(info.st_size,info.st_mtime_ns):
                raise ValueError('Approved wheel bytes differ from frozen hash')
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
    if set(value)!={'schema','approved_wheel_directory','approved_wheel_sha256'} or value['schema']!='mldsafail.v060-worker-protocol.v1':
        raise ValueError('Strict approved offline wheel protocol required')
    approved_wheels(value['approved_wheel_directory'],value['approved_wheel_sha256'])
    return dict(wheel_directory=value['approved_wheel_directory'],wheel_inventory=value['approved_wheel_sha256'])


def prepare_context(output, *, command=None, wheel_directory=None, wheel_inventory=None):
    output = Path(output)
    if output.exists():
        raise ValueError('New retained context directory required')
    wheels={} if wheel_directory is None else approved_wheels(wheel_directory,wheel_inventory)
    if wheel_directory is None and wheel_inventory is not None:raise ValueError("Wheel directory required")
    root = Path(__file__).parent
    frozen = root.parent/'benchmark_v050'
    files = {'Dockerfile':root/'Dockerfile', 'requirements.txt':frozen/'requirements.txt',
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
    (output/'mldsafail/__init__.py').write_text('')
    manifest = {path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(output.rglob('*')) if path.is_file()}
    identity = hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def git_output(argv):
        value=command(argv) if command is not None else subprocess.check_output(argv,timeout=15)
        return value.decode() if isinstance(value,bytes) else value
    record = dict(schema='mldsafail.mlwe-v060-worker-context.v1', benchmark_version='0.6.0',
                  measurement_method='cgroup-v2-usage-usec', source_sha256=identity, files=manifest,
                  native_verified=False, image=None,
                  source_commit=git_output(['git','-C',str(root),'rev-parse','HEAD']).strip(),
                  source_tree_clean=not bool(git_output(['git','-C',str(root),'status','--porcelain']).strip()))
    (output/'source-manifest.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    return record
