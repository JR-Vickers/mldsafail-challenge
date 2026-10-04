"""Retain a minimal source-bound proposed worker context; no implicit Docker use."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from mldsafail.benchmark_v050.execution import WORKER_FILES


def prepare_context(output, *, command=None):
    output = Path(output)
    if output.exists():
        raise ValueError('New retained context directory required')
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
