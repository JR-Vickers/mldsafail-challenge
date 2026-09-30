"""Architecture-specific hosted build, preserving the frozen ARM64 local build."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

from mldsafail.benchmark_v050 import execution
from mldsafail.benchmark_v050.models import digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="mldsafail-mlwe:0.5.0-linux-amd64")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    root = Path(execution.__file__).parent
    lock = Path(__file__).resolve().parents[3] / "deploy/worker-linux-amd64.requirements.txt"
    release = digest({"benchmark_version": "0.5.0", "platform": "linux/amd64",
                      "trusted_fingerprint": execution.fingerprint(),
                      "dependency_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
                      "dockerfile_sha256": hashlib.sha256((root / "Dockerfile").read_bytes()).hexdigest()})
    with tempfile.TemporaryDirectory(prefix="mlwe-amd64-build-") as temporary:
        context = Path(temporary)
        package = context / "mldsafail/benchmark_v050"
        package.mkdir(parents=True)
        (package.parent / "__init__.py").write_text("")
        (context / "wheels").mkdir()
        for name in execution.WORKER_FILES:
            shutil.copyfile(root / name, package / name)
        for name in ("Dockerfile", "artifacts.py"):
            shutil.copyfile(root / name, context / name)
        shutil.copyfile(lock, context / "requirements.txt")
        command = ["docker", "build", "--platform=linux/amd64", "--label",
                   f"org.mldsafail.trusted={execution.fingerprint()}", "--label",
                   f"org.mldsafail.release={release}", "-t", args.tag]
        if args.no_cache:
            command.append("--no-cache")
        subprocess.run(command + [str(context)], check=True)
    print(f"linux/amd64 release identity: {release}")


if __name__ == "__main__":
    main()
