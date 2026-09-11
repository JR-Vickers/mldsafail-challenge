"""Disposable Docker execution with bounded streams and evaluator-only validation."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from pathlib import Path
import selectors
import subprocess
import time
import uuid

from .constants import MAX_SERIALIZED_BYTES, MEMORY_LIMIT_BYTES, WALL_LIMIT_SECONDS
from .models import canonical_json, digest
from .verify import verify_candidate

IMAGE = "mldsafail-mlwe:0.5.0"
WORKER_FILES = ("__init__.py", "constants.py", "models.py", "ring.py", "embedding.py",
                "verify.py", "solvers.py", "simple_baselines.py", "worker.py")


def command(args):
    return subprocess.check_output(args, text=True).strip()


def fingerprint():
    root = Path(__file__).parent
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts})


def environment(image=IMAGE):
    if platform.python_version() != "3.12.10":
        raise ValueError("the frozen sampler requires evaluator Python 3.12.10")
    inspected = json.loads(command(["docker", "image", "inspect", image]))[0]
    image_id = inspected["Id"]
    label = inspected["Config"].get("Labels", {}).get("org.mldsafail.trusted")
    if label != fingerprint():
        raise ValueError("worker image does not match trusted fingerprint; rebuild it")
    artifacts = json.loads(command(["docker", "run", "--rm", "--network=none", "--read-only",
                                   "--entrypoint=cat", image_id, "/artifacts.json"]))
    info = json.loads(command(["docker", "info", "--format", "{{json .}}"] ))
    return {"image_id": image_id, "trusted_fingerprint": fingerprint(), "artifacts": artifacts,
            "host": {k: info[k] for k in ("ID", "Architecture", "NCPU", "MemTotal", "KernelVersion", "OperatingSystem", "ServerVersion")}}


def solver_snapshot(source: Path, dest: Path):
    source = source.resolve()
    if not (source / "solver.py").is_file():
        raise ValueError("solver directory must contain solver.py")
    dest.mkdir()
    files = {}
    for p in sorted(source.rglob("*")):
        if p.is_symlink():
            raise ValueError("solver symlinks are forbidden")
        if p.is_file():
            if p.suffix != ".py":
                raise ValueError("only Python source files are approved solver files")
            data = p.read_bytes()
            if sum(v["bytes"] for v in files.values()) + len(data) > MAX_SERIALIZED_BYTES:
                raise ValueError("solver source exceeds 2 MB")
            rel = p.relative_to(source)
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o444)
            files[str(rel)] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return files


def disposition(result):
    if result.get("candidate") is not None and not result.get("verification", {}).get("verified"):
        return "invalid_answer"
    if result.get("timeout"):
        return "timeout"
    if result.get("memory_limit") or result.get("peak_rss_bytes", 0) > MEMORY_LIMIT_BYTES:
        return "memory_failure"
    if result.get("error"):
        return "crash"
    if result.get("verification", {}).get("verified"):
        return "success"
    if any(k.endswith("cap_exceeded") or k == "search_space_skipped"
           for k in result.get("diagnostic_counters", {})):
        return "applicability_cap"
    return "no_candidate"


def invoke(instance, solver, image_id, solver_dir=None, deadline=WALL_LIMIT_SECONDS):
    name = "mlwe-" + uuid.uuid4().hex
    args = ["docker", "run", "--name", name, "--network=none", "--read-only",
            "--user=65534:65534", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--cpus=1", "--memory=2g", "--memory-swap=2g", "--pids-limit=64",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "--log-driver=none", "-i"]
    if solver_dir is not None:
        args += ["--mount", f"type=bind,src={Path(solver_dir).resolve()},dst=/solver,readonly"]
    args += [image_id]
    payload = canonical_json({"instance": instance.to_dict(), "solver": solver})
    started = time.perf_counter()
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    timeout = overflow = False
    try:
        process.stdin.write(payload)
        process.stdin.close()
        selector = selectors.DefaultSelector()
        for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        while selector.get_map():
            if time.perf_counter() - started >= deadline:
                timeout = True
                break
            for key, _ in selector.select(min(.1, max(0, deadline - (time.perf_counter() - started)))):
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = MAX_SERIALIZED_BYTES - sum(map(len, streams.values()))
                streams[key.data].extend(chunk[:max(0, remaining)])
                if len(chunk) > remaining:
                    overflow = True
                    break
            if overflow:
                break
        selector.close()
        if timeout or overflow:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
            process.kill()
        process.wait(timeout=10)
        elapsed = time.perf_counter() - started
        timeout = timeout or elapsed > deadline
        state_result = subprocess.run(["docker", "inspect", "--format", "{{json .State}}", name], capture_output=True, text=True, timeout=10)
        state = json.loads(state_result.stdout) if state_result.returncode == 0 else {}
        try:
            result = json.loads(streams["stdout"])
            if not isinstance(result, dict):
                raise ValueError("worker result is not an object")
        except (ValueError, UnicodeError):
            result = {"error": "missing or malformed worker response"}
        if overflow:
            result["error"] = "worker output exceeded 2 MB"
        if process.returncode and not timeout:
            result["error"] = "worker exited unsuccessfully"
        if timeout:
            result["timeout"] = True
        if state.get("OOMKilled"):
            result["memory_limit"] = True
        result["verification"] = verify_candidate(instance, result.get("candidate"))
        if not result.get("error") and not timeout:
            cpu = result.get("cpu_seconds")
            if type(cpu) not in (float, int) or not math.isfinite(cpu) or cpu < 0:
                result["error"] = "invalid worker CPU measurement"
        result.update(evaluator_wall_seconds=elapsed, exit_code=process.returncode,
                      docker_state=state, output_overflow=overflow,
                      stdout=streams["stdout"].decode("utf-8", errors="replace"),
                      stderr=streams["stderr"].decode("utf-8", errors="replace"),
                      input_digest=digest(instance.to_dict()),
                      output_digest=digest(result.get("candidate")))
        result["status"] = disposition(result)
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
