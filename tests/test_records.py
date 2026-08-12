from __future__ import annotations

import json

import pytest

from mldsafail.benchmark import records as records_module
from mldsafail.benchmark.records import (
    RecordValidationError,
    append_record,
    new_experiment_record,
    read_records,
    validate_record,
)


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
    assert record["schema_version"] == "2"
    assert record["solver"] == "lazy"
    assert record["score"] is None
    assert record["cost_model_version"] == "2"
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


def test_schema_and_benchmark_versions_are_validated(tmp_path):
    wrong_schema = sample_record() | {"schema_version": "999"}
    with pytest.raises(RecordValidationError, match="schema version"):
        validate_record(wrong_schema)
    with pytest.raises(RecordValidationError, match="does not match"):
        validate_record(sample_record(), expected_benchmark_version="9.0.0")

    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps(wrong_schema) + "\n" + json.dumps(sample_record()) + "\n")
    assert len(read_records(path)) == 1
    with pytest.raises(RecordValidationError, match="line 1"):
        read_records(path, strict=True)


def test_invalid_append_does_not_modify_existing_file(tmp_path):
    path = tmp_path / "records.jsonl"
    append_record(sample_record(), path)
    original = path.read_bytes()
    with pytest.raises(RecordValidationError, match="missing"):
        append_record({"schema_version": "1"}, path)
    assert path.read_bytes() == original


def test_version_two_score_is_required_and_consistent():
    valid = new_experiment_record(
        benchmark_version="0.2.0", suites={}, profiles={},
        aggregate={"score": 7}, correct=True, score=7,
    )
    validate_record(valid)
    with pytest.raises(RecordValidationError, match="must have a score"):
        validate_record(valid | {"score": None, "aggregate": {"score": None}})
    with pytest.raises(RecordValidationError, match="must not have a score"):
        validate_record(sample_record() | {"score": 1, "aggregate": {"score": 1}})


def test_early_schema_one_records_remain_readable():
    legacy = sample_record()
    legacy["schema_version"] = "1"
    legacy.pop("score")
    legacy.pop("cost_model_version")
    legacy.pop("resource_limits")
    legacy.pop("integrity")
    validate_record(legacy)


def test_dirty_git_state_is_recorded(monkeypatch):
    def fake_git(*args):
        return " M src/example.py" if args == ("status", "--porcelain") else "abc123"

    monkeypatch.setattr(records_module, "_git", fake_git)
    environment = records_module.reproducibility_metadata(["bench"])
    assert environment["git_dirty"] is True
    assert environment["git_commit"] == "abc123"
