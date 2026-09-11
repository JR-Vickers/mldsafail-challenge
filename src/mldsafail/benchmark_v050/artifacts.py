"""Record exact downloaded wheels, native dependencies, and interpreter artifacts."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys

paths = list(Path("/wheels").glob("*"))
paths += list(Path("/usr/local/lib/python3.12/site-packages").rglob("*.so*"))
paths += list(Path("/usr/lib").glob("*-linux-gnu/libgmp.so.*"))
paths += list(Path("/usr/lib").glob("*-linux-gnu/libmpfr.so.*"))
paths += [Path(sys.executable).resolve()]
print(json.dumps({"python": platform.python_version(), "architecture": platform.machine(),
                  "packages": {n: importlib.metadata.version(n) for n in ("fpylll", "cysignals")},
                  "native_packages": subprocess.check_output(["dpkg-query", "-W", "libgmp10", "libmpfr6"], text=True),
                  "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}}, sort_keys=True))
