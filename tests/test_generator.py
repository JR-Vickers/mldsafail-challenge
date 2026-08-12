from dataclasses import asdict
from pathlib import Path

import pytest

from mldsafail.math.lattice import is_invertible
from mldsafail.models import DiagnosticMetadata, ToyInstance
from mldsafail.trusted.generator import (
    MAX_DIMENSION,
    generate_instance,
    generate_instance_with_diagnostics,
    load_profiles,
)


def test_same_seed_and_profile_are_deterministic() -> None:
    first = generate_instance(12345, "toy-medium")
    second = generate_instance(12345, "toy-medium")
    assert first == second
    assert asdict(first) == asdict(second)


def test_different_seeds_produce_different_public_instances() -> None:
    first = generate_instance(1, "toy-small")
    second = generate_instance(2, "toy-small")
    assert first.instance_id != second.instance_id
    assert first.matrix != second.matrix


@pytest.mark.parametrize("profile", ["toy-small", "toy-medium", "toy-large"])
def test_profiles_are_bounded_and_matrices_are_invertible(profile: str) -> None:
    instance = generate_instance(7, profile)
    assert instance.dimension <= MAX_DIMENSION
    assert len(instance.matrix) == instance.dimension
    assert is_invertible(instance.matrix, instance.modulus)


def test_unknown_profile_and_invalid_seed_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown toy profile"):
        generate_instance(1, "ML-DSA-87")
    with pytest.raises(ValueError, match="non-negative"):
        generate_instance(-1, "toy-small")
    with pytest.raises(ValueError, match="non-negative"):
        generate_instance(True, "toy-small")


def test_public_and_diagnostic_data_are_separate() -> None:
    public = generate_instance(99, "toy-small")
    paired_public, diagnostic = generate_instance_with_diagnostics(99, "toy-small")
    assert isinstance(public, ToyInstance)
    assert isinstance(diagnostic, DiagnosticMetadata)
    assert public == paired_public
    assert public.instance_id == diagnostic.instance_id
    assert "planted_solution" not in asdict(public)
    assert "matrix" not in asdict(diagnostic)


def test_profile_loader_uses_repo_root_from_any_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert load_profiles()["toy-small"].dimension == 8


def test_profile_loader_rejects_oversized_or_malformed_profiles(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.toml"
    oversized.write_text(
        f"""
[toy-small]
dimension = {MAX_DIMENSION + 1}
modulus = 97
eta = 2
public_seeds = 1
hidden_seeds = 1
[toy-medium]
dimension = 16
modulus = 257
eta = 3
public_seeds = 1
hidden_seeds = 1
[toy-large]
dimension = 24
modulus = 769
eta = 4
public_seeds = 1
hidden_seeds = 1
"""
    )
    with pytest.raises(ValueError, match="dimension cap"):
        load_profiles(oversized)

    malformed = tmp_path / "malformed.toml"
    malformed.write_text("[toy-small]\ndimension = 8\n")
    with pytest.raises(ValueError, match="exactly"):
        load_profiles(malformed)
