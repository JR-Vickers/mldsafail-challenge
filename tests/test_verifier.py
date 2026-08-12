from dataclasses import replace

from mldsafail.models import Candidate
from mldsafail.trusted.generator import generate_instance_with_diagnostics
from mldsafail.trusted.verifier import verify


def test_known_planted_candidate_passes_without_verifier_metadata() -> None:
    instance, diagnostic = generate_instance_with_diagnostics(42, "toy-medium")
    result = verify(instance, Candidate(diagnostic.planted_solution))
    assert result.valid
    assert result.reason == "candidate satisfies the public relation"
    assert result.solution_quality == max(map(abs, diagnostic.planted_solution))


def test_mutated_candidate_fails_public_relation() -> None:
    instance, diagnostic = generate_instance_with_diagnostics(42, "toy-medium")
    changed = list(diagnostic.planted_solution)
    changed[0] = changed[0] + 1 if changed[0] < instance.eta else changed[0] - 1
    result = verify(instance, Candidate(tuple(changed)))
    assert not result.valid
    assert "public relation" in result.reason


def test_malformed_candidates_fail_without_raising() -> None:
    instance, _ = generate_instance_with_diagnostics(3, "toy-small")
    cases = [
        object(),
        Candidate(()),
        Candidate([0] * instance.dimension),  # type: ignore[arg-type]
        Candidate((0,) * (instance.dimension - 1) + ("x",)),  # type: ignore[arg-type]
        Candidate((instance.eta + 1,) + (0,) * (instance.dimension - 1)),
    ]
    for candidate in cases:
        assert not verify(instance, candidate).valid  # type: ignore[arg-type]


def test_malformed_public_instance_fails_without_raising() -> None:
    instance, diagnostic = generate_instance_with_diagnostics(5, "toy-small")
    malformed = replace(instance, matrix=instance.matrix[:-1])
    result = verify(malformed, Candidate(diagnostic.planted_solution))
    assert not result.valid
    assert "instance dimensions" in result.reason


def test_arbitrary_or_mutated_instance_data_is_rejected() -> None:
    instance, diagnostic = generate_instance_with_diagnostics(5, "toy-small")
    candidate = Candidate(diagnostic.planted_solution)
    cases = [
        replace(instance, profile="custom"),
        replace(instance, dimension=instance.dimension + 1),
        replace(instance, modulus=instance.modulus + 2),
        replace(instance, eta=instance.eta + 1),
        replace(instance, seed=-1),
        replace(instance, instance_id="forged"),
        replace(instance, target=(instance.target[0] + 1,) + instance.target[1:]),
        replace(
            instance,
            matrix=((instance.modulus,) + instance.matrix[0][1:],) + instance.matrix[1:],
        ),
    ]
    for malformed in cases:
        assert not verify(malformed, candidate).valid
