"""Read-only final evidence reproduction; run in the frozen dependency image."""
from pathlib import Path
import hashlib
import json

from research.primitive_selection.audit import _audit_file
from research.primitive_selection.conclusion import analyze
from research.primitive_selection.report import render


def main():
    root = Path(__file__).resolve().parents[1] / "results"
    combined = []
    proofs = []
    for folder, cohort in (("v2-development-20260908", "development"),
                           ("v2-validation-20260908", "validation")):
        path = root / folder / f"{cohort}.jsonl"
        _, records, counts = _audit_file(path)
        proofs.append({"status": "passed", "run_id": records[0]["run_id"],
                       "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "counts": counts})
        # Exact candidates were verified above. Reporting only needs their presence.
        # Projection is in memory; immutable raw evidence is never rewritten.
        for record in records:
            for repetition in [*record["warmups"], *record["repetitions"]]:
                if repetition.get("candidate") is not None:
                    repetition["candidate"] = {}
        combined.extend(records)
    packet = root / "v2-final"
    assert {"status": "passed", "cohorts": proofs} == json.loads((packet / "AUDIT.json").read_text())
    report = render(combined, "development+validation")
    assert report.encode() == (packet / "REPORT.md").read_bytes()
    assert json.loads(json.dumps(analyze(combined))) == json.loads((packet / "CONCLUSION.json").read_text())
    print(json.dumps({"status": "passed", "records": len(combined),
                      "report_sha256": hashlib.sha256(report.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
