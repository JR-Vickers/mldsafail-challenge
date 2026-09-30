"""Private PostgreSQL dump and restore gate; never prints database contents."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--compose", default="compose.database.yaml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-restore", action="store_true")
    args = parser.parse_args()
    prefix = ["docker", "compose", "--env-file", str(args.env_file), "-f", args.compose, "exec", "-T", "db"]
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    path = args.output / (stem + ".dump")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        subprocess.run(prefix + ["pg_dump", "-U", "mldsafail", "-d", "mldsafail", "--format=custom"],
                       stdout=stream, stderr=subprocess.DEVNULL, check=True, timeout=120)
        stream.flush()
        os.fsync(stream.fileno())
    restored = False
    if args.verify_restore:
        database = "restore_gate_" + uuid.uuid4().hex
        subprocess.run(prefix + ["createdb", "-U", "mldsafail", database],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        try:
            with path.open("rb") as stream:
                subprocess.run(prefix + ["pg_restore", "-U", "mldsafail", "-d", database, "--exit-on-error"],
                               stdin=stream, check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=120)
            # Both sides are dumps of the same immutable snapshot; this comparison
            # checks all restored schema/data, without exposing their contents.
            restored_dump = subprocess.check_output(prefix + ["pg_dump", "-U", "mldsafail", "-d", database,
                "--format=plain", "--no-owner", "--no-privileges"], stderr=subprocess.DEVNULL, timeout=120)
            original_dump = subprocess.check_output(prefix + ["pg_dump", "-U", "mldsafail", "-d", "mldsafail",
                "--format=plain", "--no-owner", "--no-privileges"], stderr=subprocess.DEVNULL, timeout=120)
            def normalized(data):
                return b"\n".join(line for line in data.splitlines()
                                   if not line.startswith((b"\\restrict ", b"\\unrestrict ")))
            if normalized(original_dump) != normalized(restored_dump):
                raise RuntimeError("restored database does not match the quiescent source")
            restored = True
        finally:
            # Exact disposable database created above; the application DB is untouched.
            subprocess.run(prefix + ["dropdb", "-U", "mldsafail", database], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    metadata = {"dump_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "restore_verified": restored, "quiescent_source_required": True}
    descriptor = os.open(args.output / (stem + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(metadata, stream, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"backup_created": True, "restore_verified": restored}))


if __name__ == "__main__":
    main()
