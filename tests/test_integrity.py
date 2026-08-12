from pathlib import Path

import pytest

from mldsafail.benchmark.integrity import (
    IntegrityError,
    assert_trusted_manifest,
    build_trusted_manifest,
    compare_trusted_manifest,
    compute_trusted_fingerprint,
    fingerprint_manifest,
)


def _fixture_tree(root: Path) -> None:
    files = {
        "config/profiles.toml": b"[small]\ndimension=2\n",
        "data/hidden_seeds.json": b"[1, 2]\n",
        "data/public_seeds.json": b"not trusted\n",
        "src/mldsafail/trusted/generator.py": b"GENERATOR = 1\n",
        "src/mldsafail/benchmark/runner.py": b"RUNNER = 1\n",
        "src/mldsafail/solver/baseline.py": b"not trusted\n",
        "src/mldsafail/benchmark/__pycache__/runner.pyc": b"runtime cache\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def test_manifest_and_fingerprint_are_deterministic(tmp_path: Path) -> None:
    _fixture_tree(tmp_path)
    first = build_trusted_manifest(tmp_path)
    second = build_trusted_manifest(tmp_path)
    assert first == second
    assert list(first) == sorted(first)
    assert "data/public_seeds.json" not in first
    assert "src/mldsafail/solver/baseline.py" not in first
    assert not any("__pycache__" in path for path in first)
    assert compute_trusted_fingerprint(tmp_path) == fingerprint_manifest(first)
    assert fingerprint_manifest(dict(reversed(list(first.items())))) == fingerprint_manifest(first)
    assert_trusted_manifest(first, tmp_path)


def test_comparison_reports_added_missing_and_changed(tmp_path: Path) -> None:
    _fixture_tree(tmp_path)
    expected = build_trusted_manifest(tmp_path)
    (tmp_path / "config/profiles.toml").write_text("changed\n")
    (tmp_path / "data/hidden_seeds.json").unlink()
    added = tmp_path / "src/mldsafail/trusted/new_check.py"
    added.write_text("new\n")

    difference = compare_trusted_manifest(expected, tmp_path)
    assert difference.changed == ("config/profiles.toml",)
    assert difference.missing == ("data/hidden_seeds.json",)
    assert difference.added == ("src/mldsafail/trusted/new_check.py",)
    assert not difference.matches
    assert "added:" in difference.describe()
    assert "missing:" in difference.describe()
    assert "changed:" in difference.describe()

    with pytest.raises(IntegrityError) as raised:
        assert_trusted_manifest(expected, tmp_path)
    assert raised.value.difference == difference
