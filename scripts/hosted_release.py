"""Record a clean source commit and immutable hosted image/config identities."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from mldsafail.benchmark.integrity import compute_trusted_fingerprint
from mldsafail.benchmark_v050.execution import fingerprint


def command(*arguments):
    return subprocess.check_output(arguments, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if command("git", "status", "--porcelain"):
        raise SystemExit("Release requires a clean worktree.")
    commit = command("git", "rev-parse", "HEAD")
    paths = command("git", "ls-files").splitlines()
    sources = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}
    images = {}
    for role, tag in {"web": "mldsafail-web:hosted-0.5.0",
                      "coordinator": "mldsafail-coordinator:hosted-0.5.0",
                      "worker": "mldsafail-mlwe:0.5.0-linux-amd64"}.items():
        info = json.loads(command("docker", "image", "inspect", tag))[0]
        if info["Architecture"] != "amd64":
            raise SystemExit("Hosted images must be Linux x86_64.")
        images[role] = {"tag": tag, "id": info["Id"], "architecture": info["Architecture"],
                        "labels": info["Config"].get("Labels") or {}}
        if role != "worker" and images[role]["labels"].get("org.mldsafail.source") != commit:
            raise SystemExit("Application image does not match the frozen source commit.")
    result = {"benchmark_version": "0.5.0", "source_commit": commit,
              "source_tree": command("git", "rev-parse", "HEAD^{tree}"),
              "source_files_sha256": sources, "images": images,
              "dependency_lock_sha256": sources["uv.lock"],
              "worker_lock_sha256": sources["deploy/worker-linux-amd64.requirements.txt"],
              "configuration_sha256": sources["compose.private.yaml"],
              "historical_trusted_fingerprint": compute_trusted_fingerprint(),
              "mlwe_trusted_fingerprint": fingerprint(),
              "release_gate": "local acceptance; VPS acceptance pending"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(f"Recorded immutable source release {commit}.")


if __name__ == "__main__":
    main()
