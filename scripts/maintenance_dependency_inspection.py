"""Read static dependency candidates without importing or executing their code.

SSH PATH resolution is evidence about that context only, not a unit's PATH.
Dynamic shell expressions and Python import hooks remain review blockers.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys


def inspect_path(name):
    path = Path(name)
    if not path.is_absolute() or '..' in path.parts or any(c in name for c in '$%*?{}'):
        return dict(status='dynamic_or_invalid_not_inspected')
    try:
        resolved = path.resolve(strict=True)
        st = resolved.stat()
        row = dict(resolved=str(resolved), uid=st.st_uid, mode=stat.S_IMODE(st.st_mode), size=st.st_size)
        if stat.S_ISREG(st.st_mode) and st.st_size <= 1048576:
            data = resolved.read_bytes()
            row.update(sha256=hashlib.sha256(data).hexdigest(),
                       text_hex=data.hex() if b'\0' not in data else None)
        elif stat.S_ISDIR(st.st_mode):
            children = sorted(p.name for p in resolved.iterdir())
            row.update(children=children[:256], children_truncated=len(children) > 256)
        else:
            row['status'] = 'not_regular_or_size_limited'
        return row
    except OSError as error:
        return dict(error=type(error).__name__)


def inspect(request):
    if set(request) != {'paths', 'commands', 'imports'} or any(len(v) > 512 for v in request.values()):
        raise ValueError('bounded static dependency request required')
    commands = {}
    for name in request['commands']:
        if not re.fullmatch('[a-zA-Z0-9_.+-]+', name):
            raise ValueError('literal command names required')
        resolved = shutil.which(name)
        commands[name] = dict(resolved=resolved, evidence=inspect_path(resolved) if resolved else None)
    imports = {}
    for name in request['imports']:
        if not re.fullmatch('[a-zA-Z0-9_.]+', name):
            raise ValueError('literal module names required')
        stem = name.replace('.', '/')
        candidates = []
        for directory in sys.path:
            if not directory or not Path(directory).is_dir():
                continue
            for suffix in ('.py', '/__init__.py'):
                path = Path(directory)/(stem+suffix)
                if path.exists():
                    candidates.append(dict(path=str(path), evidence=inspect_path(str(path))))
        imports[name] = dict(static_candidates=candidates, resolved=False,
                             limitation='service interpreter/sys.path, native extensions and import hooks require separate closure')
    return dict(uid=os.getuid(), hostname=os.uname().nodename, path_environment=os.environ.get('PATH'),
                interpreter=sys.executable, python_path=sys.path, commands=commands, imports=imports,
                paths={p: inspect_path(p) for p in request['paths']})


if __name__ == '__main__':
    print(json.dumps(inspect(json.load(sys.stdin)), sort_keys=True))
