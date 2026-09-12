import argparse
import json

import pytest

from scripts import mlwe_stability as stability


def test_predeclared_shape_and_rotation():
    assert stability.RUNS == 30
    assert stability.EXECUTIONS_PER_RUN == 400
    assert stability.EPOCH_EXECUTIONS == 1200
    assert stability.TOTAL_EXECUTIONS == 13200
    assert [stability.role_order(i) for i in range(1, 5)] == [
        ("native", "adapter", "candidate"),
        ("adapter", "candidate", "native"),
        ("candidate", "native", "adapter"),
        ("native", "adapter", "candidate"),
    ]
    with pytest.raises(ValueError):
        stability.role_order(0)


def test_stability_cohort_is_limited_to_the_predeclared_macbook_host(monkeypatch):
    monkeypatch.setattr(stability.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(stability.platform, "machine", lambda: "arm64")
    stability.validate_execution_host()

    monkeypatch.setattr(stability.platform, "system", lambda: "Linux")
    with pytest.raises(ValueError, match="requires Darwin arm64"):
        stability.validate_execution_host()


def test_ratio_statistics_and_recursive_sanitization():
    assert stability._cell_ratio(
        [{"instance_id": "a", "profile": "small", "eta": 1, "verification_result": True,
          "median_cpu_seconds": 2, "repetitions": []}],
        [{"instance_id": "a", "profile": "small", "eta": 1, "verification_result": True,
          "median_cpu_seconds": 1, "repetitions": []}], "small", 1) == pytest.approx(.5)
    stats = stability._variation([1, 2, 3])
    assert stats["median"] == 2 and stats["coefficient_of_variation"] > 0
    clean = stability.sanitize({"outer": {"nonce": "no", "items": [{"candidate": "no", "score": 1}]}})
    assert json.dumps(clean) == '{"outer": {"items": [{"score": 1}]}}'


def test_run_enforces_source_environment_order_and_retains_interruption(tmp_path, monkeypatch):
    adapter, candidate = tmp_path / "adapter", tmp_path / "candidate"
    for source in (adapter, candidate):
        source.mkdir(); (source / "solver.py").write_text("def solve(x): return None\n")
    digests = {"adapter": stability.source_digest(adapter), "candidate": stability.source_digest(candidate)}
    monkeypatch.setattr(stability, "validate_execution_host", lambda: None)
    env = {"image_id": "image", "trusted_fingerprint": "fingerprint", "artifacts": {}}
    monkeypatch.setattr(stability, "environment", lambda: env)
    monkeypatch.setattr(stability.frozen_cli, "create_epoch", lambda output: output.mkdir())
    monkeypatch.setattr(stability.ev, "audit_epoch", lambda output: ({"id": "epoch", "environment": env, "cases": []}, []))
    calls = []
    def evaluate(output, grid, actual_env, solver, epoch, solver_dir=None):
        calls.append((output.name, solver, solver_dir))
        output.mkdir()
    monkeypatch.setattr(stability.frozen_cli, "evaluate", evaluate)
    monkeypatch.setattr(stability, "analyze_root", lambda *args: {"complete": True})
    args = argparse.Namespace(adapter_dir=adapter, candidate_dir=candidate,
                              adapter_digest=digests["adapter"], candidate_digest=digests["candidate"],
                              private_root=tmp_path / "private")
    assert stability.run(args) == {"complete": True}
    assert [name for name, _, _ in calls] == [stability.run_name(c, role)
                                                for c in range(1, 11)
                                                for role in stability.role_order(c)]
    assert calls[0][1:] == ("primal-lll", None)
    assert (args.private_root / "COMPLETE_STUDY.json").exists()
    with pytest.raises(ValueError, match="never resume"):
        stability.run(args)

    bad = argparse.Namespace(**vars(args)); bad.private_root = tmp_path / "interrupted"
    monkeypatch.setattr(stability.frozen_cli, "create_epoch", lambda output: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        stability.run(bad)
    assert json.loads((bad.private_root / "INCOMPLETE.json").read_text())["complete"] is False


def test_report_is_exclusive_and_descriptive(tmp_path, monkeypatch):
    summary = {"study_version": stability.STUDY_VERSION, "complete": True,
               "provenance": {"runs": 30, "executions": 13200}, "roles": {
                   role: {"score_statistics": {"median": 1., "minimum": .9, "maximum": 1.1,
                                                  "coefficient_of_variation": .01}} for role in stability.ROLES},
               "aggregate_ratios": {"adapter_native": {"median": 1.02}, "candidate_adapter": {"median": .5}},
               "tie_band_percent": 1., "nested": {"host": "secret", "seed": 1}}
    monkeypatch.setattr(stability, "analyze_root", lambda *args: summary)
    args = argparse.Namespace(private_root=tmp_path / "private", adapter_digest="a", candidate_digest="c",
                              summary=tmp_path / "report.json", markdown=tmp_path / "report.md")
    result = stability.report(args)
    assert "host" not in json.dumps(result) and "seed" not in json.dumps(result)
    assert "single-host" in args.markdown.read_text()
    with pytest.raises(ValueError, match="already exist"):
        stability.report(args)
