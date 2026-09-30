"""Hosted adapter for the frozen local MLWE contract.

Only a verified, sealed epoch is selectable. Raw evidence stays on the evaluator
filesystem; the database receives the contract's whitelist summary only.
"""
from __future__ import annotations

from pathlib import Path

from mldsafail.benchmark_v050 import evidence as ev
from mldsafail.benchmark_v050.execution import environment, invoke, solver_snapshot
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.web.services import DomainError


class EvaluationCancelled(Exception):
    pass


class HostedMLWE:
    def __init__(self, epoch: Path, image: str, epoch_id: str):
        self.epoch = epoch
        self.manifest, self.reference = ev.audit_epoch(epoch)
        if self.manifest["id"] != epoch_id:
            raise ValueError("configured epoch identity mismatch")
        self.image = image
        self.check_environment()

    def check_environment(self):
        if environment(self.image) != self.manifest["environment"]:
            raise ValueError("execution environment changed; a new epoch is required")

    @property
    def evaluator_fingerprint(self):
        return ev.sha({"benchmark_version": "0.5.0", "environment": self.manifest["environment"],
                       "settings": ev.SETTINGS})

    def evaluate(self, source: Path, output: Path, identity: dict, key: bytes, checkpoint):
        self.check_environment()
        output = ev.directory(output)
        files = solver_snapshot(source, output / "solver")
        manifest = ev.manifest("run", self.manifest["environment"], self.manifest["cases"],
                               solver="contestant", solver_files=files,
                               epoch_manifest_sha256=ev.sha(self.manifest))
        ev.write(output / "manifest.json", manifest)
        ev.directory(output / "records")
        rows = []
        for index, case in enumerate(manifest["cases"]):
            instance = generate_mlwe(case["profile"], case["seed"], case["eta"]).public
            outputs = []
            for repetition in range(4):
                checkpoint()
                result = invoke(instance, "contestant", manifest["environment"]["image_id"], output / "solver")
                ev.write(output / "records" / f"{index:03d}-{repetition}.json",
                         {"run_id": manifest["id"], "case_index": index,
                          "repetition": repetition, "result": result})
                outputs.append(result)
            rows.append(ev.aggregate(case, "contestant", outputs))
        ev.write(output / "aggregates.json", rows)
        ev.write(output / "summary.json", ev.summary(manifest, rows))
        ev.audit_run(output, self.epoch, check_complete=False)
        ev.seal(output)
        manifest, rows = ev.audit_run(output, self.epoch)
        summary = ev.summary(manifest, rows, self.reference)
        checkpoint()
        return sign_envelope({**identity, "verified": summary["eligible"],
                              "score": summary.get("score"), "diagnostics": summary,
                              "failure_class": None if summary["eligible"] else "invalid_answer"}, key)


def solver_directory(checkout: Path, relative: str = "src/mldsafail/solver") -> Path:
    # Same approved Python source contract as the local contestant interface.
    source = checkout / relative
    if not (source / "solver.py").is_file():
        raise DomainError("eligible_source_missing", "MLWE requires solver.py in the selected solver directory.")
    return source
