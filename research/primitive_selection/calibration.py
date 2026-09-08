"""Development-only, single-observation exploratory solver calibration.

This evidence is separate from the warm-up/three-repetition comparison cohorts.
Every observation uses a fresh resource-capped subprocess and a 60-second parent
deadline. It cannot derive or accept held-out seeds.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .constants import DEVELOPMENT_SEEDS, ETAS, MEMORY_LIMIT_BYTES, PROFILES, WALL_LIMIT_SECONDS
from .generator import generate_mlwe, generate_msis
from .models import candidate_from_dict, canonical_json, digest
from .solvers import DEFAULT_PARAMETERS
from .verify import verify_mlwe, verify_msis


def audit_calibration(path: Path):
    """Independently regenerate inputs and reverify all exploratory answers."""
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("status") != "complete":
        raise ValueError("calibration is not complete")
    content = (path / "records.jsonl").read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest["records_sha256"]:
        raise ValueError("calibration records digest mismatch")
    for name, expected in manifest["source_digests"].items():
        if hashlib.sha256((path / "source" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("calibration source snapshot digest mismatch")
    if manifest["profiles"] != PROFILES or any(seed not in DEVELOPMENT_SEEDS for seed in manifest["seeds"]):
        raise ValueError("calibration configuration or development seed mismatch")
    tasks = (("mlwe", "direct-linear"), ("msis", "direct-linear"), ("msis", "sparse-relation"))
    if manifest["kind"] == "mlwe":
        tasks = tuple(("mlwe", solver) for solver in ("exhaustive", "primal-lll", "primal-bkz", "hybrid-bdd"))
    expected_keys = {(profile, eta, seed, track, solver) for profile in PROFILES for eta in ETAS
                     for seed in manifest["seeds"] for track, solver in tasks}
    seen = set()
    verified = 0
    for line in content.splitlines():
        record = json.loads(line)
        key = tuple(record[k] for k in ("profile", "eta", "seed", "track", "solver"))
        if key in seen or key not in expected_keys:
            raise ValueError("duplicate or unexpected calibration case")
        seen.add(key)
        if record["run_id"] != manifest["run_id"] or record["configuration_digest"] != manifest["configuration_digest"]:
            raise ValueError("calibration case provenance mismatch")
        instance = (generate_mlwe if record["track"] == "mlwe" else generate_msis)(
            record["profile"], record["seed"], record["eta"]).public
        if record["instance_id"] != instance.instance_id or record["input_digest"] != digest({
                "instance": instance.to_dict(), "solver": record["solver"]}):
            raise ValueError("calibration input digest mismatch")
        result = record["result"]
        if digest(result) != record["output_digest"]:
            raise ValueError("calibration output digest mismatch")
        if result.get("candidate") is not None:
            candidate = candidate_from_dict(result["candidate"])
            check = (verify_mlwe if record["track"] == "mlwe" else verify_msis)(instance, candidate)
            if check != result["verification"]:
                raise ValueError("calibration independent candidate verification mismatch")
            verified += int(check["verified"])
        elif result.get("verification", {}).get("verified"):
            raise ValueError("calibration claims success without a candidate")
    if seen != expected_keys or len(seen) != manifest["record_count"] or len(seen) != manifest["expected_records"]:
        raise ValueError("calibration is missing cases")
    return {"records": len(seen), "verified_candidates": verified, "audit": "passed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("mlwe", "simple"))
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--seed-count", type=int, default=10)
    args = parser.parse_args()
    if args.audit:
        print(json.dumps(audit_calibration(args.output)))
        return
    if args.kind is None:
        parser.error("--kind is required when collecting calibration")
    if not 1 <= args.seed_count <= len(DEVELOPMENT_SEEDS):
        parser.error("seed count must be within the ten development seeds")
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}
    snapshot = args.output / "source"
    snapshot.mkdir()
    for path in sorted(root.glob("*.py")):
        (snapshot / path.name).write_bytes(path.read_bytes())
    manifest = {"schema_version": "calibration-v1", "run_id": uuid.uuid4().hex,
                "created_at": datetime.now(UTC).isoformat(), "kind": args.kind, "status": "running",
                "interpretation": "exploratory, one observation per case; excluded from final cohort analysis",
                "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "source_digests": sources, "profiles": PROFILES, "solver_parameters": DEFAULT_PARAMETERS,
                "seeds": list(DEVELOPMENT_SEEDS[:args.seed_count]), "etas": ETAS,
                "wall_limit_seconds": WALL_LIMIT_SECONDS, "memory_limit_bytes": MEMORY_LIMIT_BYTES,
                "dependencies": {name: importlib.metadata.version(name) for name in ("fpylll", "cysignals")}}
    manifest["configuration_digest"] = digest({k: manifest[k] for k in (
        "source_digests", "profiles", "solver_parameters", "seeds", "etas", "wall_limit_seconds",
        "memory_limit_bytes", "dependencies")})
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    count = 0
    with (args.output / "records.jsonl").open("x") as handle:
        for profile in PROFILES:
            for eta in ETAS:
                for seed in DEVELOPMENT_SEEDS[:args.seed_count]:
                    tasks = (("mlwe", s) for s in ("exhaustive", "primal-lll", "primal-bkz", "hybrid-bdd"))
                    if args.kind == "simple":
                        tasks = (("mlwe", "direct-linear"), ("msis", "direct-linear"), ("msis", "sparse-relation"))
                    for track, solver in tasks:
                        generated = (generate_mlwe if track == "mlwe" else generate_msis)(profile, seed, eta)
                        request = {"instance": generated.public.to_dict(), "solver": solver}
                        module = "worker" if args.kind == "mlwe" else "simple_baselines"
                        started = time.perf_counter()
                        try:
                            completed = subprocess.run([sys.executable, "-m", f"research.primitive_selection.{module}"],
                                                       input=canonical_json(request), capture_output=True,
                                                       timeout=WALL_LIMIT_SECONDS, check=False)
                            result = json.loads(completed.stdout)
                            if completed.returncode:
                                result["process_returncode"] = completed.returncode
                        except subprocess.TimeoutExpired:
                            result = {"timeout": True, "error": "60-second calibration deadline exceeded"}
                        except json.JSONDecodeError:
                            result = {"error": "worker returned malformed output", "process_returncode": completed.returncode,
                                      "stderr": completed.stderr.decode(errors="replace")}
                        record = {"run_id": manifest["run_id"], "configuration_digest": manifest["configuration_digest"],
                                  "profile": profile, "eta": eta, "seed": seed, "track": track, "solver": solver,
                                  "input_digest": digest(request), "instance_id": generated.public.instance_id,
                                  "result": result, "output_digest": digest(result),
                                  "process_wall_seconds": time.perf_counter() - started}
                        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                        handle.flush()
                        count += 1
    manifest["record_count"] = count
    manifest["expected_records"] = len(PROFILES) * len(ETAS) * args.seed_count * (4 if args.kind == "mlwe" else 3)
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    manifest["status"] = "complete" if count == manifest["expected_records"] else "incomplete"
    manifest["records_sha256"] = hashlib.sha256((args.output / "records.jsonl").read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "status": manifest["status"], "records": count}))


if __name__ == "__main__":
    main()
