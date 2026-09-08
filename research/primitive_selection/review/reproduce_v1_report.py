"""Reproduce the preserved report using its reviewed renderer, without rewriting evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    source = Path(__file__).with_name("report_at_review_v1.py")
    spec = importlib.util.spec_from_file_location(
        "research.primitive_selection.legacy_v1.reviewed_report", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = root / "results/development.jsonl"
    records = [json.loads(line) for line in raw.read_text().splitlines()]
    rendered = module.render(records, "development").encode()
    committed = root / "results/REPORT.md"
    if rendered != committed.read_bytes():
        raise SystemExit("historical report reproduction failed")
    print(json.dumps({"status": "passed", "records": len(records),
        "measurement_revision": "b33f229338695fcccfba415245058deb772a5a8f",
        "renderer_revision": "c60e1d069b97006aa22793921e9a2c5a64100edf",
        "renderer_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(rendered).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
