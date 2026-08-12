"""Trusted, versioned abstract operation accounting.

Solvers receive an opaque meter with validated counting methods.  They cannot
replace counters or write negative values through the supported interface.
The meter is an audit boundary for cooperative research code, not a hostile
Python sandbox.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

COST_MODEL_VERSION = "2"
CATEGORIES = (
    "additions",
    "multiplications",
    "modular_reductions",
    "basis_updates",
    "memory_reads",
    "memory_writes",
)
# Version 2 deliberately starts with transparent unit weights. Changing any
# weight requires a new cost-model and benchmark version.
WEIGHTS = MappingProxyType({category: 1 for category in CATEGORIES})


def _validate_count(value: int, category: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{category} count must be a non-negative integer")
    return value


@dataclass(frozen=True)
class CostSnapshot:
    version: str
    additions: int
    multiplications: int
    modular_reductions: int
    basis_updates: int
    memory_reads: int
    memory_writes: int

    def __post_init__(self) -> None:
        if self.version != COST_MODEL_VERSION:
            raise ValueError(f"unsupported cost model version: {self.version!r}")
        for category in CATEGORIES:
            _validate_count(getattr(self, category), category)

    @property
    def raw_total(self) -> int:
        return sum(getattr(self, category) for category in CATEGORIES)

    @property
    def weighted_total(self) -> int:
        return sum(getattr(self, category) * WEIGHTS[category] for category in CATEGORIES)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {
            "raw_total": self.raw_total,
            "total": self.weighted_total,
            "weights": dict(WEIGHTS),
        }


class OperationMeter:
    """Validated write-only operation counter passed to editable solvers."""

    __slots__ = ("__counts",)

    def __init__(self) -> None:
        self.__counts = [0] * len(CATEGORIES)

    def _count(self, category: str, amount: int) -> None:
        value = _validate_count(amount, category)
        self.__counts[CATEGORIES.index(category)] += value

    def additions(self, amount: int = 1) -> None:
        self._count("additions", amount)

    def multiplications(self, amount: int = 1) -> None:
        self._count("multiplications", amount)

    def modular_reductions(self, amount: int = 1) -> None:
        self._count("modular_reductions", amount)

    def basis_updates(self, amount: int = 1) -> None:
        self._count("basis_updates", amount)

    def memory_reads(self, amount: int = 1) -> None:
        self._count("memory_reads", amount)

    def memory_writes(self, amount: int = 1) -> None:
        self._count("memory_writes", amount)

    def snapshot(self) -> CostSnapshot:
        return CostSnapshot(COST_MODEL_VERSION, *self.__counts)
