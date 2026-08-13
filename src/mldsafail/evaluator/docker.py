"""Strict disposable Docker worker invocation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mldsafail.evaluator.envelope import EnvelopeError


@dataclass(frozen=True)
class WorkerLimits:
    cpus: str = "1.0"
    memory: str = "512m"
    pids: int = 64
    wall_seconds: int = 300
    tmpfs: str = "64m"


def docker_command(image: str, harness: Path, hidden_seeds: Path, signing_key: Path, metadata: dict[str, str], limits: WorkerLimits = WorkerLimits()) -> list[str]:
    command = [
        "docker", "run", "--rm", "--network=none", "--read-only", "--user=65532:65532",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", f"--cpus={limits.cpus}",
        f"--memory={limits.memory}", f"--pids-limit={limits.pids}",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={limits.tmpfs}",
        "--mount", f"type=bind,src={harness.resolve()},dst=/challenge,readonly",
        "--mount", f"type=bind,src={hidden_seeds.resolve()},dst=/run/secrets/hidden-seeds.json,readonly",
        "--mount", f"type=bind,src={signing_key.resolve()},dst=/run/secrets/result-key,readonly",
        "--workdir=/challenge",
    ]
    environment = metadata | {
        "MLDSAFAIL_HIDDEN_SEEDS_PATH": "/run/secrets/hidden-seeds.json",
        "MLDSAFAIL_RESULT_KEY_PATH": "/run/secrets/result-key",
    }
    for name in sorted(environment):
        command.extend(["--env", f"{name}={environment[name]}"])
    command.append(image)
    return command


def run_worker(image: str, harness: Path, hidden_seeds: Path, signing_key: Path, metadata: dict[str, str], limits: WorkerLimits = WorkerLimits()) -> dict:
    try:
        completed = subprocess.run(docker_command(image, harness, hidden_seeds, signing_key, metadata, limits), capture_output=True, text=True, timeout=limits.wall_seconds)
    except subprocess.TimeoutExpired:
        raise EnvelopeError("worker exceeded wall-time limit") from None
    output = completed.stdout[-65536:]
    marker = next((line.removeprefix("MLDSAFAIL_RESULT=") for line in reversed(output.splitlines()) if line.startswith("MLDSAFAIL_RESULT=")), None)
    if marker is None:
        raise EnvelopeError("worker emitted no result envelope")
    try:
        return json.loads(marker)
    except json.JSONDecodeError:
        raise EnvelopeError("worker emitted malformed result envelope") from None
