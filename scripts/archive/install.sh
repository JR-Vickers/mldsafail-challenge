#!/bin/sh
# Install an owner-supplied release wheel into a new isolated environment.
set -eu
if [ "$#" -ne 3 ]; then
    echo 'Usage: sh scripts/install.sh RELEASE.whl SHA256 NEW_INSTALL_DIRECTORY' >&2
    exit 2
fi
wheel=$1
expected=$2
target=$3
python3 - "$wheel" "$expected" "$target" <<'PY'
import hashlib, pathlib, sys
wheel, expected, target = sys.argv[1:]
p = pathlib.Path(wheel)
if not p.is_file() or p.suffix != '.whl' or len(expected) != 64:
    raise SystemExit('Supply a release wheel and its verified SHA-256.')
if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
    raise SystemExit('Wheel checksum mismatch.')
if pathlib.Path(target).exists():
    raise SystemExit('Installation directory must be new.')
PY
python3 -m venv "$target"
"$target/bin/python" -m pip install "$wheel"
echo "Installed in $target/bin; no existing executables were replaced."
echo 'Configure staging explicitly: mldsafail login TOKEN --server "$STAGING_SERVER"'
