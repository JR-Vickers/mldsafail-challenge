"""Deterministic integrity manifests for benchmark-defining files.

The manifest deliberately excludes solver and result files: solver changes are
the subject of experiments, while the trusted generator, verifier, profiles,
hidden suite, and scoring harness define what an experiment means.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_TRUSTED_PATHS = (
    Path("config"),
    Path("data/hidden_seeds.json"),
    Path("src/mldsafail/trusted"),
    Path("src/mldsafail/benchmark"),
)
_IGNORED_DIRECTORY_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache"})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass(frozen=True)
class IntegrityDiff:
    """Path-level differences between an expected and current manifest."""

    added: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def matches(self) -> bool:
        return not (self.added or self.missing or self.changed)

    def describe(self) -> str:
        if self.matches:
            return "trusted benchmark files match"
        parts = []
        if self.added:
            parts.append("added: " + ", ".join(self.added))
        if self.missing:
            parts.append("missing: " + ", ".join(self.missing))
        if self.changed:
            parts.append("changed: " + ", ".join(self.changed))
        return "; ".join(parts)


class IntegrityError(RuntimeError):
    """Raised when trusted benchmark files differ from an expected manifest."""

    def __init__(self, difference: IntegrityDiff):
        self.difference = difference
        super().__init__(difference.describe())


def _included_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in _TRUSTED_PATHS:
        target = root / relative
        candidates = target.rglob("*") if target.is_dir() else (target,)
        for candidate in candidates:
            if (
                candidate.is_file()
                and not any(part in _IGNORED_DIRECTORY_NAMES for part in candidate.parts)
                and candidate.suffix not in _IGNORED_SUFFIXES
            ):
                files.append(candidate)
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def build_trusted_manifest(root: str | Path | None = None) -> dict[str, str]:
    """Return ``relative path -> SHA-256`` for benchmark-defining files."""
    repository_root = Path(root).resolve() if root is not None else _REPOSITORY_ROOT
    manifest: dict[str, str] = {}
    for path in _included_files(repository_root):
        relative = path.relative_to(repository_root).as_posix()
        manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def fingerprint_manifest(manifest: Mapping[str, str]) -> str:
    """Hash a manifest canonically, independent of mapping insertion order."""
    encoded = json.dumps(
        dict(manifest), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def compute_trusted_fingerprint(root: str | Path | None = None) -> str:
    """Return the current trusted benchmark fingerprint."""
    return fingerprint_manifest(build_trusted_manifest(root))


def compare_trusted_manifest(
    expected: Mapping[str, str], root: str | Path | None = None
) -> IntegrityDiff:
    """Compare an expected manifest with the current trusted file tree."""
    current = build_trusted_manifest(root)
    expected_paths = set(expected)
    current_paths = set(current)
    return IntegrityDiff(
        added=tuple(sorted(current_paths - expected_paths)),
        missing=tuple(sorted(expected_paths - current_paths)),
        changed=tuple(
            sorted(
                path
                for path in expected_paths & current_paths
                if expected[path] != current[path]
            )
        ),
    )


def assert_trusted_manifest(
    expected: Mapping[str, str], root: str | Path | None = None
) -> None:
    """Raise :class:`IntegrityError` unless trusted files match exactly."""
    difference = compare_trusted_manifest(expected, root)
    if not difference.matches:
        raise IntegrityError(difference)
