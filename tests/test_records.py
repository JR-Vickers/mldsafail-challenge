from __future__ import annotations

import json

import pytest

from mldsafail.benchmark.records import append_record, new_experiment_record, read_records


def sample_record():
    return new_experiment_record(
        benchmark_version="0.1.0", suites={}, profiles={}, aggregate={}, correct=False,
        agent="test", model="test", hypothesis="exercise recording", command=["pytest"],
    )


def test_append_is_jsonl_and_does_not_replace(tmp_path):
    path = tmp_path / "nested" / "experiments.jsonl"
    first, second = sample_record(), sample_record()
    append_record(first, path)
    append_record(second, path)
    assert read_records(path) == [first, second]
    assert len(path.read_text().splitlines()) == 2


def test_records_include_reproducibility_metadata():
    record = sample_record()
    assert record["schema_version"] == "1"
    assert record["environment"]["architecture"]
    assert record["environment"]["python_version"]
    assert record["environment"]["command"] == ["pytest"]
    assert record["environment"]["dependency_lock_sha256"]


def test_reader_tolerates_corrupt_tail_or_can_be_strict(tmp_path):
    path = tmp_path / "experiments.jsonl"
    path.write_text(json.dumps(sample_record()) + "\n{interrupted")
    assert len(read_records(path)) == 1
    with pytest.raises(ValueError, match="line 2"):
        read_records(path, strict=True)
