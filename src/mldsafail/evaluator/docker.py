"""Strict disposable Docker worker invocation."""

from __future__ import annotations

import json
import base64
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


def docker_command(image: str, harness: Path, metadata: dict[str, str], limits: WorkerLimits = WorkerLimits()) -> list[str]:
    command = [
        "docker", "run", "--rm", "--network=none", "--read-only", "--user=65532:65532",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", f"--cpus={limits.cpus}",
        f"--memory={limits.memory}", f"--pids-limit={limits.pids}",
        "--ulimit=fsize=67108864:67108864", "--stop-timeout=5",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={limits.tmpfs}",
        "--mount", f"type=bind,src={harness.resolve()},dst=/challenge,readonly",
        "--workdir=/challenge", "--interactive",
    ]
    environment = metadata | {"PYTHONPATH": "/challenge/src"}
    for name in sorted(environment):
        command.extend(["--env", f"{name}={environment[name]}"])
    command.append(image)
    return command


def run_worker(image: str, harness: Path, signing_key: bytes, instances: list[dict], metadata: dict[str, str], limits: WorkerLimits = WorkerLimits()) -> dict:
    request_payload = json.dumps({
        "signing_key": base64.b64encode(signing_key).decode("ascii"),
        "instances": instances,
    }, separators=(",", ":"))
    try:
        completed = subprocess.run(docker_command(image, harness, metadata, limits), input=request_payload, capture_output=True, text=True, timeout=limits.wall_seconds)
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
