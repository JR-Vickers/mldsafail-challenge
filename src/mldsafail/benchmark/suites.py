"""Loading of repository-controlled benchmark seed suites."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
SUITE_FILES = {
    "public": DATA_DIR / "public_seeds.json",
    "hidden": DATA_DIR / "hidden_seeds.json",
}


class SuiteError(ValueError):
    """A requested benchmark suite or profile is not configured."""


def load_seed_suite(name: str, profile: str | None = None) -> dict[str, tuple[int, ...]]:
    """Return a validated seed mapping for ``public`` or ``hidden``."""

    if name not in SUITE_FILES:
        raise SuiteError(f"unknown seed suite: {name}")
    with SUITE_FILES[name].open(encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise SuiteError(f"{name} suite must contain a profile mapping")
    suites: dict[str, tuple[int, ...]] = {}
    for key, seeds in raw.items():
        if not isinstance(key, str) or not isinstance(seeds, list) or not all(
            isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds
        ):
            raise SuiteError(f"invalid seeds for profile {key!r}")
        suites[key] = tuple(seeds)
    if profile is not None:
        if profile not in suites:
            raise SuiteError(f"unknown profile: {profile}")
        return {profile: suites[profile]}
    return suites


def selected_suites(name: str) -> tuple[str, ...]:
    """Expand CLI suite semantics; ``full`` means public followed by hidden."""

    if name == "full":
        return ("public", "hidden")
    if name in SUITE_FILES:
        return (name,)
    raise SuiteError(f"unknown suite: {name}")
