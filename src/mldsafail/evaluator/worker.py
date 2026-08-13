"""Trusted supervisor: isolate solver execution, validate its shape, and sign."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

from mldsafail.evaluator.envelope import sign_envelope


def main() -> int:
    request = json.load(sys.stdin)
    sys.stdin.close()
    signing_key = base64.b64decode(request.pop("signing_key"), validate=True)
    # Participant modules are imported only by this child. It receives public
    # challenge objects, never the signing key, hidden seeds, or service creds.
    child = subprocess.run(
        [sys.executable, "-m", "mldsafail.evaluator.solver_child"],
        input=json.dumps({"instances": request["instances"]}, separators=(",", ":")),
        capture_output=True, text=True, timeout=280,
        env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "/challenge/src", "PYTHONUNBUFFERED": "1"},
    )
    verified, score, failure_class, results = False, None, None, []
    try:
        output = json.loads(child.stdout[-262144:])
        results = output["results"]
        if child.returncode or not isinstance(results, list) or len(results) != len(request["instances"]):
            raise ValueError("solver child did not return one result per instance")
        totals = [item["cost"]["total"] for item in results]
        if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in totals):
            raise ValueError("solver child returned invalid costs")
        score, verified = sum(totals), True
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        failure_class = "invalid_solver_output"
        results = []
    payload = {
        "source_digest": os.environ["MLDSAFAIL_SOURCE_DIGEST"],
        "benchmark_version": os.environ["MLDSAFAIL_BENCHMARK_VERSION"],
        "evaluator_fingerprint": os.environ["MLDSAFAIL_EVALUATOR_FINGERPRINT"],
        "hidden_suite_version": os.environ["MLDSAFAIL_HIDDEN_SUITE_VERSION"],
        "worker_class": os.environ["MLDSAFAIL_WORKER_CLASS"],
        "verified": verified, "score": score,
        "diagnostics": {"results": results}, "failure_class": failure_class,
    }
    print("MLDSAFAIL_RESULT=" + json.dumps(sign_envelope(payload, signing_key), sort_keys=True, separators=(",", ":")))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
