"""Build a minimal worker image, excluding generators and all evaluator evidence."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from .execution import IMAGE, WORKER_FILES, fingerprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=IMAGE)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--wheel-dir", type=Path, help="optional offline wheels; pinned hashes are still enforced")
    args = parser.parse_args()
    root = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix="mlwe-build-") as tmp:
        context = Path(tmp)
        wheels = context / "wheels"
        wheels.mkdir()
        if args.wheel_dir:
            for wheel in args.wheel_dir.glob("*.whl"):
                shutil.copyfile(wheel, wheels / wheel.name)
        package = context / "mldsafail" / "benchmark_v050"
        package.mkdir(parents=True)
        (package.parent / "__init__.py").write_text("")
        for name in WORKER_FILES:
            shutil.copyfile(root / name, package / name)
        for name in ("Dockerfile", "requirements.txt", "artifacts.py"):
            shutil.copyfile(root / name, context / name)
        command = ["docker", "build", "--label", f"org.mldsafail.trusted={fingerprint()}", "-t", args.tag]
        if args.no_cache:
            command.append("--no-cache")
        subprocess.run(command + [tmp], check=True)


if __name__ == "__main__":
    main()
