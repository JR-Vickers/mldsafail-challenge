"""Measurement adversarial tests: executable child deadlines and forged cohort records."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from research.primitive_selection import runner
from research.primitive_selection.audit import audit
from research.primitive_selection.generator import generate_mlwe
from research.primitive_selection.models import RecoveredSecret, ReducedBasis, digest
from research.primitive_selection.worker import classify_result, verify_candidate


def _fake_result(instance, solver, parameters=None):
    candidate = None
    if instance.track == "mlwe":
        generated = generate_mlwe("small", 0, 1)
        candidate = RecoveredSecret(generated.planted_s1, generated.planted_s2).to_dict()
    elif instance.track == "bkz":
        d = len(instance.basis)
        identity = tuple(tuple(int(i == j) for j in range(d)) for i in range(d))
        candidate = ReducedBasis(instance.basis, identity).to_dict()
    candidate = json.loads(json.dumps(candidate))
    params = dict(runner.DEFAULT_PARAMETERS[solver])
    if instance.track == "bkz" and solver == "progressive-bkz":
        params["max_basis_dimension"] = 160
    result = {"candidate": candidate, "verification": verify_candidate(instance, candidate),
              "solver_parameters": params, "diagnostic_counters": {},
              "phase_cpu_seconds": {"reduction": .01}, "solver_cpu_seconds": .02,
              "verification_cpu_seconds": .005, "cpu_seconds": .03,
              "wall_seconds": .04, "evaluator_wall_seconds": .05,
              "peak_rss_bytes": 10 * 1024**2, "timeout": False, "memory_limit": False,
              "limits": {"rlimits_applied": ["RLIMIT_AS"], "cpu_affinity": 0}}
    result["status"] = classify_result(result)
    return json.loads(json.dumps(result))


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_invoke", _fake_result)
    revision, _ = runner._git_revision()
    monkeypatch.setattr(runner, "_git_revision", lambda: (revision, True))
    actual_deps = runner.dependency_provenance()
    for version in actual_deps["packages"].values():
        version["installed"] = version["required"]
    monkeypatch.setattr(runner, "dependency_provenance", lambda: actual_deps)
    path = runner.run("development", output=tmp_path / "smoke.jsonl", smoke=True)
    return path


def _rewrite(path, records=None, manifest_edit=None):
    if records is not None:
        path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
    manifest = json.loads(runner.manifest_path(path).read_text())
    manifest["records_sha256"] = runner.file_digest(path)
    if manifest_edit:
        manifest_edit(manifest)
    runner.manifest_path(path).write_text(json.dumps(manifest))


def _records(path):
    return list(map(json.loads, path.read_text().splitlines()))


def test_complete_cohort_audits_warmups_and_refuses_overwrite(cohort):
    records = _records(cohort)
    assert audit([cohort])["records"] == len(runner.cases_for("development", smoke=True))
    assert all(len(r["warmups"]) == 1 and len(r["repetitions"]) == 3 for r in records)
    before = cohort.read_bytes()
    with pytest.raises(FileExistsError, match="overwrite"):
        runner.run("development", output=cohort, smoke=True)
    assert cohort.read_bytes() == before
    with pytest.raises(ValueError, match="duplicate run"):
        audit([cohort, cohort])


@pytest.mark.parametrize("change,match", [
    (lambda r: r.pop(), "missing"),
    (lambda r: r.append(copy.deepcopy(r[0])), "duplicate cases"),
    (lambda r: r[0].update(seed=999999), "grid mismatch"),
    (lambda r: r[0].update(solver="invented"), "grid mismatch"),
    (lambda r: r[0].update(profile="invented"), "grid mismatch"),
    (lambda r: r[0].update(git_revision="b" * 40), "git_revision"),
    (lambda r: r[0].update(input_digest="0" * 64), "input digest"),
    (lambda r: r[0].update(output_digest="0" * 64), "output digest"),
    (lambda r: r[0].update(median_cpu_seconds=123), "aggregate median_cpu_seconds"),
    (lambda r: r[0].update(peak_rss_bytes=1), "aggregate peak_rss_bytes"),
    (lambda r: r[0].update(configuration_digest="0" * 64), "configuration_digest"),
    (lambda r: r[0].pop("failure_reason"), "missing fields"),
    (lambda r: r[0].update(warmups=[]), "warmup count"),
])
def test_audit_rejects_case_or_aggregate_tampering(cohort, change, match):
    records = _records(cohort)
    change(records)
    _rewrite(cohort, records)
    with pytest.raises(ValueError, match=match):
        audit([cohort])


def test_audit_rejects_configuration_and_partial_runs(cohort):
    _rewrite(cohort, manifest_edit=lambda m: m["configuration"]["limits"].update(wall_seconds=61))
    with pytest.raises(ValueError, match="configuration"):
        audit([cohort])
    _rewrite(cohort, manifest_edit=lambda m: m.update(state="partial"))
    with pytest.raises(ValueError, match="partial"):
        audit([cohort])


def test_audit_reverifies_candidate_instead_of_trusting_success(cohort):
    records = _records(cohort)
    target = next(r for r in records if r["track"] == "mlwe")
    for repetition in target["repetitions"]:
        repetition["candidate"]["s1"][0][0] = 99
    target["output_digest"] = digest([r["candidate"] for r in target["repetitions"]])
    _rewrite(cohort, records)
    with pytest.raises(ValueError, match="independent candidate verification"):
        audit([cohort])


def test_audit_reverifies_quality_and_warmups(cohort):
    records = _records(cohort)
    target = next(r for r in records if r["track"] == "mlwe")
    target["warmups"][0]["verification"]["norm_squared"] = -1
    _rewrite(cohort, records)
    with pytest.raises(ValueError, match="independent candidate verification"):
        audit([cohort])


def test_audit_rejects_forged_cap_status_and_excess_timings(cohort):
    records = _records(cohort)
    records[0]["repetitions"][0]["status"] = "applicability_cap"
    _rewrite(cohort, records)
    with pytest.raises(ValueError, match="repetition status"):
        audit([cohort])
    records[0]["repetitions"][0]["evaluator_wall_seconds"] = 61
    _rewrite(cohort, records)
    with pytest.raises(ValueError, match="wall deadline"):
        audit([cohort])


def test_empty_dependency_evidence_rejected(cohort):
    def edit(manifest):
        manifest["dependency_provenance"]["packages"] = {}
        manifest["dependency_digest"] = digest(manifest["dependency_provenance"])
    _rewrite(cohort, manifest_edit=edit)
    with pytest.raises(ValueError, match="dependency package set"):
        audit([cohort])


def test_interrupt_retains_partial_evidence(tmp_path, monkeypatch):
    path = tmp_path / "interrupted.jsonl"
    calls = 0
    def interrupted(instance, solver, parameters=None):
        nonlocal calls
        calls += 1
        if calls == 6:
            raise KeyboardInterrupt()
        return _fake_result(instance, solver, parameters)
    monkeypatch.setattr(runner, "_invoke", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.run("development", output=path, smoke=True)
    assert not path.exists()
    assert len(path.with_suffix(".jsonl.partial").read_text().splitlines()) == 1
    manifest = json.loads(runner.manifest_path(path).read_text())
    assert manifest["state"] == "partial" and manifest["completed_case_count"] == 1
    assert manifest["interruption"] == "KeyboardInterrupt"
    with pytest.raises(FileExistsError):
        runner.run("development", output=path, smoke=True)


def test_parent_deadline_kills_a_real_sleeping_child(monkeypatch):
    actual_run = subprocess.run
    def sleepy(_args, **kwargs):
        return actual_run([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)
    monkeypatch.setattr(runner.subprocess, "run", sleepy)
    monkeypatch.setattr(runner, "WALL_LIMIT_SECONDS", .1)
    result = runner._invoke(generate_mlwe("small", 0, 1).public, "primal-lll")
    assert result["status"] == "timeout" and result["timeout"]
    assert .09 <= result["evaluator_wall_seconds"] < 2


@pytest.mark.parametrize("returncode,stdout,status", [(-9, b"", "crash"), (-11, b"", "crash"),
                                                         (0, b"[]", "crash"), (0, b"not json", "crash")])
def test_worker_failures_are_reported_without_guessing_oom(monkeypatch, returncode, stdout, status):
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], returncode, stdout, b"error"))
    result = runner._invoke(generate_mlwe("small", 0, 1).public, "primal-lll")
    assert result["status"] == status and not result["memory_limit"]


def test_failure_categories_and_protocol():
    assert classify_result({"memory_limit": True}) == "memory_failure"
    assert classify_result({"candidate": None, "diagnostic_counters": {"dimension_cap_exceeded": 300}}) == "applicability_cap"
    assert classify_result({"candidate": {"tag": "bad"}, "verification": {"verified": False}}) == "invalid_answer"
    assert classify_result({"candidate": None}) == "no_candidate"
    with pytest.raises(ValueError, match="three"):
        runner.run("development", smoke=True, repetitions=1)
    with pytest.raises(ValueError, match="committed freeze"):
        runner.run("validation", nonce="a fresh reviewer nonce")


def test_post_freeze_nonce_checks_exact_rules_and_creation_time(tmp_path, monkeypatch):
    from research.primitive_selection.decision import RANKING_RULE, SELECTION_CRITERIA
    freeze = tmp_path / "freeze.json"
    nonce_path = tmp_path / "nonce.json"
    nonce = "review-agent-fresh-nonce-12345"
    frozen = {"created_at": "2026-09-07T01:00:00+00:00", "source_digest": "c" * 64,
              "configuration": runner.configuration(), "dependency_provenance": runner.dependency_provenance(),
              "selection_criteria": SELECTION_CRITERIA, "ranking_rule": RANKING_RULE,
              "expected_case_counts": {"development": len(runner.cases_for("development")),
                                       "validation": len(runner.cases_for("validation", nonce))}}
    freeze.write_text(json.dumps(frozen))
    reviewer = {"nonce": nonce, "freeze_sha256": runner.file_digest(freeze), "freeze_commit": "a" * 40,
                "created_at": "2026-09-07T01:01:00+00:00", "reviewer_model": "test-reviewer",
                "reviewer_session": "test-session"}
    nonce_path.write_text(json.dumps(reviewer))
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "_source_digest", lambda: "c" * 64)
    monkeypatch.setattr(runner, "_git_revision", lambda: ("a" * 40, False))
    checked = runner.check_freeze(freeze, nonce_path, nonce)
    assert checked["freeze_file_text"] == freeze.read_text()
    reviewer["created_at"] = frozen["created_at"]
    nonce_path.write_text(json.dumps(reviewer))
    with pytest.raises(ValueError, match="after freeze"):
        runner.check_freeze(freeze, nonce_path, nonce)
    frozen["ranking_rule"] = {"arbitrary": "changed"}
    freeze.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="selection criteria and ranking"):
        runner.check_freeze(freeze, nonce_path, nonce)


def test_report_success_uncertainty_does_not_treat_repetitions_as_seeds(cohort):
    from research.primitive_selection.report import _success_interval, render, summarize
    records = _records(cohort)
    rows = summarize(records, ("track", "source_track", "solver", "profile", "eta"))
    assert all(row["seed_clusters"] == 1 for row in rows)
    low, high = _success_interval([1] * 20)
    assert .8 < low < 1 and high == 1
    text = render(records, "smoke")
    assert "Wilson" in text and "runtime consumption only" in text
    assert "No recommendation is frozen" not in text


def test_worker_memoryerror_is_explicit_failure_evidence(monkeypatch):
    actual_run = subprocess.run
    code = (
        "from research.primitive_selection import worker\n"
        "def fail(*args):\n    raise MemoryError('test allocation failure')\n"
        "worker.run_solver = fail\n"
        "raise SystemExit(worker.main())\n"
    )
    def memory_worker(_args, **kwargs):
        return actual_run([sys.executable, "-c", code], **kwargs)
    monkeypatch.setattr(runner.subprocess, "run", memory_worker)
    result = runner._invoke(generate_mlwe("small", 0, 1).public, "primal-lll")
    assert result["status"] == "memory_failure" and result["memory_limit"]
    assert result["error"] == "memory limit exceeded"


def test_dependency_binary_tampering_rejected(cohort):
    def edit(manifest):
        artifacts = manifest["dependency_provenance"]["binary_artifacts"]["fpylll"]
        artifacts[next(iter(artifacts))] = "0" * 64
        manifest["dependency_digest"] = digest(manifest["dependency_provenance"])
    _rewrite(cohort, manifest_edit=edit)
    with pytest.raises(ValueError, match="installed binary_artifacts"):
        audit([cohort])


def test_sigkill_retains_fsynced_partial_case_and_manifest(tmp_path):
    path = tmp_path / "killed.jsonl"
    code = (
        "import os, signal, sys\n"
        "from pathlib import Path\n"
        "from research.primitive_selection import runner\n"
        "calls = 0\n"
        "def invoke(*args):\n"
        "    global calls\n"
        "    calls += 1\n"
        "    if calls == 5:\n"
        "        os.kill(os.getpid(), signal.SIGKILL)\n"
        "    return {'timeout': True, 'status': 'timeout', 'error': 'test timeout', 'evaluator_wall_seconds': 60}\n"
        "runner._invoke = invoke\n"
        "runner.run('development', output=Path(sys.argv[1]), smoke=True)\n"
    )
    completed = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, timeout=15)
    assert completed.returncode == -9
    assert not path.exists()
    partial = path.with_suffix(".jsonl.partial")
    assert len(partial.read_text().splitlines()) == 1
    manifest = json.loads(runner.manifest_path(path).read_text())
    assert manifest["state"] == "partial" and manifest["completed_case_count"] == 1
    with pytest.raises(ValueError, match="partial"):
        audit([partial])


def test_mid_run_source_change_remains_partial(tmp_path, monkeypatch):
    path = tmp_path / "changed.jsonl"
    def changed(instance, solver, parameters=None):
        monkeypatch.setattr(runner, "_source_digest", lambda: "0" * 64)
        return _fake_result(instance, solver, parameters)
    monkeypatch.setattr(runner, "_invoke", changed)
    with pytest.raises(RuntimeError, match="changed during run"):
        runner.run("development", output=path, smoke=True)
    assert not path.exists()
    manifest = json.loads(runner.manifest_path(path).read_text())
    assert manifest["state"] == "partial" and manifest["interruption"] == "RuntimeError"
    assert path.with_suffix(".jsonl.partial").exists()
