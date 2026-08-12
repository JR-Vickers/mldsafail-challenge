"""Shared, stable data contracts for the benchmark."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChallengeProfile:
    name: str
    dimension: int
    modulus: int
    eta: int
    public_seeds: int
    hidden_seeds: int


@dataclass(frozen=True)
class ChallengeInstance:
    instance_id: str
    seed: int
    profile: str
    dimension: int
    modulus: int
    eta: int
    matrix: tuple[tuple[int, ...], ...]
    target: tuple[int, ...]


@dataclass(frozen=True)
class DiagnosticMetadata:
    instance_id: str
    planted_solution: tuple[int, ...]


@dataclass(frozen=True)
class Candidate:
    coefficients: tuple[int, ...]


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: str
    solution_quality: int | None = None


@dataclass
class InstanceMetrics:
    instance_id: str
    correct: bool
    wall_seconds: float
    peak_memory_bytes: int
    solution_quality: int | None
    cost: dict[str, Any]
    failure_reason: str | None = None
    resource_status: str = "within_limits"


@dataclass
class ProfileMetrics:
    profile: str
    instances: list[InstanceMetrics] = field(default_factory=list)
    correct: bool = False
    total_wall_seconds: float = 0.0
    median_instance_seconds: float = 0.0
    peak_memory_bytes: int = 0
    abstract_cost: int = 0
    solution_quality: int | None = None
