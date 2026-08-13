"""Acquire an immutable commit and extract only the eligible source surface."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from mldsafail.web.services import DomainError, valid_repository_url

ELIGIBLE_ROOTS = (PurePosixPath("src/mldsafail/solver"), PurePosixPath("src/mldsafail/math"))


@dataclass(frozen=True)
class SourcePolicy:
    max_repository_bytes: int = 50 * 1024 * 1024
    max_file_bytes: int = 256 * 1024
    max_eligible_bytes: int = 2 * 1024 * 1024
    fetch_seconds: int = 30


@dataclass(frozen=True)
class EligibleSource:
    root: Path
    files: tuple[PurePosixPath, ...]
    digest: str


def _git_environment() -> dict[str, str]:
    allowed = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    return allowed | {
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_ASKPASS": "/bin/false", "HOME": "/nonexistent",
    }


def acquire_commit(repository_url: str, commit_sha: str, destination: Path, policy: SourcePolicy = SourcePolicy()) -> Path:
    repository_url = valid_repository_url(repository_url)
    if destination.exists() and any(destination.iterdir()):
        raise DomainError("source_destination_not_empty", "Controlled source destination is not empty.")
    destination.mkdir(parents=True, exist_ok=True)
    command = ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never"]
    try:
        subprocess.run([*command, "init", "--quiet", str(destination)], check=True, env=_git_environment(), timeout=10)
        subprocess.run(
            [*command, "-C", str(destination), "fetch", "--quiet", "--no-tags", "--depth=1", repository_url, commit_sha],
            check=True, env=_git_environment(), timeout=policy.fetch_seconds, capture_output=True,
        )
        resolved = subprocess.run([*command, "-C", str(destination), "rev-parse", "FETCH_HEAD"], check=True, text=True, capture_output=True, env=_git_environment()).stdout.strip()
        if resolved.lower() != commit_sha.lower():
            raise DomainError("commit_mismatch", "Fetched commit does not match the requested SHA.")
        subprocess.run([*command, "-C", str(destination), "checkout", "--quiet", "--detach", resolved], check=True, env=_git_environment(), timeout=10)
    except subprocess.TimeoutExpired:
        raise DomainError("source_timeout", "Repository acquisition exceeded its time limit.") from None
    except subprocess.CalledProcessError:
        raise DomainError("commit_inaccessible", "The public repository or exact commit is inaccessible.") from None
    size = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    if size > policy.max_repository_bytes:
        raise DomainError("repository_too_large", "Repository exceeds the acquisition size limit.")
    return destination


def validate_eligible_source(root: Path, policy: SourcePolicy = SourcePolicy()) -> EligibleSource:
    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD"], check=True, capture_output=True,
            timeout=10, env=_git_environment(),
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise DomainError("invalid_git_tree", "Unable to inspect the submitted Git tree.") from None
    files: list[PurePosixPath] = []
    total = 0
    digest = hashlib.sha256()
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b"\t", 1)
        mode, kind, _object_id = metadata.decode("ascii").split()
        path_text = encoded_path.decode("utf-8")
        path = PurePosixPath(path_text)
        if path.is_absolute() or ".." in path.parts:
            raise DomainError("unsafe_path", "Submitted Git tree contains an unsafe path.")
        if mode == "160000" or kind == "commit":
            raise DomainError("submodules_forbidden", "Git submodules are not accepted.")
        if mode == "120000":
            raise DomainError("symlinks_forbidden", "Symbolic links are not accepted.")
        if path.name == ".gitmodules":
            raise DomainError("submodules_forbidden", "Git submodule configuration is not accepted.")
        disk_path = root.joinpath(*path.parts)
        if path.name == ".gitattributes" and disk_path.is_file() and b"filter=lfs" in disk_path.read_bytes():
            raise DomainError("git_lfs_forbidden", "Git LFS configuration is not accepted.")
        eligible = any(path == base or base in path.parents for base in ELIGIBLE_ROOTS)
        if not eligible:
            continue
        if kind != "blob" or path.suffix != ".py":
            raise DomainError("unsupported_file", "Eligible directories may contain Python source files only.")
        if not disk_path.is_file() or disk_path.is_symlink():
            raise DomainError("unsafe_file", "Eligible source did not resolve to a regular file.")
        content = disk_path.read_bytes()
        if len(content) > policy.max_file_bytes:
            raise DomainError("file_too_large", "An eligible source file exceeds the size limit.")
        if content.startswith(b"version https://git-lfs.github.com/spec/"):
            raise DomainError("git_lfs_forbidden", "Git LFS content is not accepted.")
        total += len(content)
        if total > policy.max_eligible_bytes:
            raise DomainError("eligible_source_too_large", "Eligible source exceeds the total size limit.")
        files.append(path)
        digest.update(len(path_text.encode()).to_bytes(4, "big")); digest.update(path_text.encode())
        digest.update(len(content).to_bytes(8, "big")); digest.update(content)
    if not files:
        raise DomainError("eligible_source_missing", "Commit contains no eligible solver or math source.")
    return EligibleSource(root=root, files=tuple(sorted(files, key=str)), digest=digest.hexdigest())


def assemble_harness(trusted_checkout: Path, source: EligibleSource, destination: Path) -> None:
    if destination.exists():
        raise DomainError("assembly_destination_exists", "Clean assembly destination already exists.")
    shutil.copytree(trusted_checkout, destination, symlinks=False, ignore=shutil.ignore_patterns(".git", ".venv", "results", "__pycache__"))
    for relative in source.files:
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source.root.joinpath(*relative.parts), target)
