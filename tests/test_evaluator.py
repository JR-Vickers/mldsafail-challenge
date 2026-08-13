from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mldsafail.evaluator.docker import docker_command
from mldsafail.evaluator.envelope import EnvelopeError, sign_envelope, verify_envelope
from mldsafail.evaluator.queue import claim_job, heartbeat
from mldsafail.evaluator.source import assemble_harness, validate_eligible_source
from mldsafail.web.models import Base, EvaluationJob, Submission, SubmissionState, SubmissionTransition, User
from mldsafail.web.services import DomainError


def git_repo(tmp_path, files: dict[str, bytes | str]) -> Path:
    root = tmp_path / "repo"; root.mkdir()
    subprocess.run(["git", "init", "--quiet", root], check=True)
    for name, content in files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes): path.write_bytes(content)
        else: path.write_text(content)
    subprocess.run(["git", "-C", root, "add", "."], check=True)
    subprocess.run(["git", "-C", root, "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "source"], check=True)
    return root


def test_source_validation_digest_and_clean_assembly(tmp_path):
    source_root = git_repo(tmp_path, {
        "src/mldsafail/solver/__init__.py": "answer = 1\n",
        "src/mldsafail/math/ops.py": "def add(a, b): return a + b\n",
        "setup.py": "raise RuntimeError('must never run')\n",
        "src/mldsafail/trusted/verifier.py": "raise RuntimeError('must never copy')\n",
    })
    source = validate_eligible_source(source_root)
    assert len(source.digest) == 64
    assert all(str(path).startswith(("src/mldsafail/solver/", "src/mldsafail/math/")) for path in source.files)
    trusted = tmp_path / "trusted"; (trusted / "src/mldsafail/trusted").mkdir(parents=True)
    (trusted / "src/mldsafail/trusted/verifier.py").write_text("TRUSTED = True\n")
    destination = tmp_path / "assembled"
    assemble_harness(trusted, source, destination)
    assert (destination / "src/mldsafail/solver/__init__.py").read_text() == "answer = 1\n"
    assert (destination / "src/mldsafail/trusted/verifier.py").read_text() == "TRUSTED = True\n"
    assert not (destination / "setup.py").exists()


@pytest.mark.parametrize("name,content,code", [
    ("src/mldsafail/solver/data.txt", "bad", "unsupported_file"),
    ("src/mldsafail/solver/lfs.py", "version https://git-lfs.github.com/spec/v1\n", "git_lfs_forbidden"),
])
def test_source_rejects_unsupported_and_lfs(tmp_path, name, content, code):
    root = git_repo(tmp_path, {name: content})
    with pytest.raises(DomainError) as caught:
        validate_eligible_source(root)
    assert caught.value.code == code


def test_source_rejects_symlinks(tmp_path):
    root = tmp_path / "repo"; root.mkdir(); subprocess.run(["git", "init", "--quiet", root], check=True)
    target = root / "outside.py"; target.write_text("x=1\n")
    link = root / "src/mldsafail/solver/link.py"; link.parent.mkdir(parents=True); link.symlink_to(target)
    subprocess.run(["git", "-C", root, "add", "."], check=True)
    subprocess.run(["git", "-C", root, "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "symlink"], check=True)
    with pytest.raises(DomainError) as caught: validate_eligible_source(root)
    assert caught.value.code == "symlinks_forbidden"


def test_signed_envelope_binds_all_provenance():
    payload = {"source_digest": "a" * 64, "benchmark_version": "0.2.0", "evaluator_fingerprint": "eval",
               "hidden_suite_version": "hidden-1", "worker_class": "worker-1", "verified": True,
               "score": 10, "diagnostics": {}, "failure_class": None}
    envelope = sign_envelope(payload, b"secret")
    expected = {key: payload[key] for key in ("source_digest", "benchmark_version", "evaluator_fingerprint", "hidden_suite_version", "worker_class")}
    assert verify_envelope(envelope, b"secret", expected)["score"] == 10
    envelope["payload"]["score"] = 1
    with pytest.raises(EnvelopeError, match="signature"): verify_envelope(envelope, b"secret", expected)


def test_docker_command_applies_isolation_contract(tmp_path):
    paths = [tmp_path / name for name in ("harness", "hidden.json", "key")]
    paths[0].mkdir(); paths[1].write_text("{}"); paths[2].write_bytes(b"key")
    command = docker_command("worker@sha256:" + "a" * 64, *paths, {"MLDSAFAIL_SOURCE_DIGEST": "b" * 64})
    rendered = " ".join(command)
    for required in ("--network=none", "--read-only", "--cap-drop=ALL", "no-new-privileges", "--pids-limit=64", "readonly"):
        assert required in rendered
    assert "docker.sock" not in rendered and "DATABASE_URL" not in rendered


def test_queue_claim_creates_lease_and_transactional_transition(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'queue.db'}"); Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(display_name="A"); session.add(user); session.flush()
        submission = Submission(user_id=user.id, repository_url="https://github.com/a/b.git", commit_sha="a" * 40,
                                hypothesis="h", benchmark_version="0.2.0")
        session.add(submission); session.flush()
        session.add_all([EvaluationJob(submission_id=submission.id), SubmissionTransition(submission_id=submission.id, from_state=None, to_state="queued")]); session.commit()
        job = claim_job(session, "worker-1", lease_seconds=30)
        assert job.status == "claimed" and job.lease_owner == "worker-1" and job.attempts == 1
        assert session.get(Submission, submission.id).state == SubmissionState.VALIDATING.value
        assert heartbeat(session, job.id, "wrong") is False
        assert heartbeat(session, job.id, "worker-1") is True
