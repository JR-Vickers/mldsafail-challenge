import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts import mlwe_pilot as pilot


def record(name, score, *, role="candidate", eligible=True, complete=True):
    return {"experiment_id": name, "diagnostic_score": score, "role": role,
            "eligible": eligible, "complete": complete, "source_digest": name}


def test_public_grid_and_execution_count():
    grid = pilot.public_cases()
    assert len(grid) == pilot.PUBLIC_CASES == 50
    assert pilot.PUBLIC_EXECUTIONS == 200
    assert len({row["instance_id"] for row in grid}) == 50
    assert {(r["profile"], r["eta"]) for r in grid} == set(pilot.CHALLENGE_CELLS)
    assert all(sum((r["profile"], r["eta"]) == cell for r in grid) == 10
               for cell in pilot.CHALLENGE_CELLS)


def test_baseline_normalization_and_candidate_selection():
    rows = []
    faster = []
    for profile, eta in pilot.CHALLENGE_CELLS:
        for seed in range(10):
            base = {"track": "mlwe", "profile": profile, "eta": eta, "seed": seed,
                    "verification_result": True, "median_cpu_seconds": 2.0,
                    "repetitions": [{"status": "success"}] * 3}
            rows.append(base)
            faster.append({**base, "median_cpu_seconds": 1.0})
    score, cells = pilot.diagnostic_scores(rows, faster, "candidate")
    assert score == pytest.approx(.5)
    assert set(cells.values()) == {.5}
    baseline = record("baseline", 1.0, role="baseline")
    first = record("first", .8)
    tied_later = record("later", .8)
    invalid = record("invalid", .1, eligible=False)
    partial = record("partial", .01, complete=False)
    assert pilot.select_candidate([baseline, first, tied_later, invalid, partial]) == first


def test_hypothesis_and_time_budget_enforcement():
    now = datetime.now(timezone.utc)
    baseline = {**record("baseline", 1.0, role="baseline"), "finished_utc": now.isoformat()}
    pilot.enforce_budget([baseline] + [record(str(i), .9) for i in range(5)], now)
    with pytest.raises(ValueError, match="six-hypothesis"):
        pilot.enforce_budget([baseline] + [record(str(i), .9) for i in range(6)], now)
    old = {**baseline, "finished_utc": (now - timedelta(hours=4)).isoformat()}
    with pytest.raises(ValueError, match="four-hour"):
        pilot.enforce_budget([old], now)


def develop_args(tmp_path, output):
    solver = tmp_path / "solver"
    solver.mkdir(exist_ok=True)
    (solver / "solver.py").write_text("def solve(x): return None\n")
    return argparse.Namespace(output=output, solver_dir=solver, baseline_run=None,
                              ledger=tmp_path / "ledger.jsonl", hypothesis="fails",
                              mechanism="sentinel", parent_revision="abc", agent="codex",
                              model="test", expected_source_digest=None)


def test_exclusive_output_and_interrupted_retention(tmp_path, monkeypatch):
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        pilot.develop(develop_args(tmp_path, existing))
    monkeypatch.setattr(pilot, "environment", lambda: {"trusted_fingerprint": "f"})
    monkeypatch.setattr(pilot.frozen_cli, "evaluate",
                        lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    output = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        pilot.develop(develop_args(tmp_path, output))
    incomplete = json.loads((output / "experiment-incomplete.json").read_text())
    ledger = pilot.read_jsonl(tmp_path / "ledger.jsonl")
    assert incomplete["decision"] == "retain_incomplete"
    assert ledger == [incomplete]
    assert not (output / "run" / "COMPLETE.json").exists()


def test_source_identity_rejects_non_python_and_changes(tmp_path):
    solver = tmp_path / "solver"
    solver.mkdir()
    (solver / "solver.py").write_text("def solve(x): return None\n")
    first = pilot.source_digest(solver)
    (solver / "solver.py").write_text("def solve(x): return {}\n")
    assert pilot.source_digest(solver) != first
    (solver / "data.txt").write_text("forbidden")
    with pytest.raises(ValueError, match="only Python"):
        pilot.source_digest(solver)


def test_final_enforces_identity_and_prescribed_order(tmp_path, monkeypatch):
    reference = tmp_path / "reference"
    candidate = tmp_path / "candidate"
    for folder, body in ((reference, "def solve(x): return None\n"),
                         (candidate, "def solve(x): return {}\n")):
        folder.mkdir(); (folder / "solver.py").write_text(body)
    ref_digest, cand_digest = pilot.source_digest(reference), pilot.source_digest(candidate)
    args = argparse.Namespace(reference_dir=reference, candidate_dir=candidate,
                              reference_digest=ref_digest, candidate_digest=cand_digest,
                              private_root=tmp_path / "private", public_summary=tmp_path / "public.json")
    env = {"trusted_fingerprint": "f"}
    monkeypatch.setattr(pilot.frozen_cli, "create_epoch", lambda path: path.mkdir())
    monkeypatch.setattr(pilot.ev, "audit_epoch", lambda path: ({"environment": env, "cases": [], "id": "epoch"}, []))
    monkeypatch.setattr(pilot, "environment", lambda: env)
    calls = []
    def fake_evaluate(path, grid, actual_env, solver, epoch, solver_dir):
        calls.append((path.name, "reference" if solver_dir == reference else "candidate"))
    monkeypatch.setattr(pilot.frozen_cli, "evaluate", fake_evaluate)
    analysis = {"pilot_version": pilot.PILOT_VERSION, "benchmark_version": "0.5.0",
                "complete": True, "outcome": "tied", "provenance": {}, "runs": [],
                "pairs": [], "reference_score_spread": {}, "interpretation": "x", "adapter_note": "x"}
    monkeypatch.setattr(pilot, "analyze_private", lambda *a: analysis)
    pilot.final(args)
    assert calls == [(f"pair-{pair}-{role}", role) for pair, role in pilot.FINAL_ORDER]
    assert json.loads(args.public_summary.read_text())["outcome"] == "tied"

    bad = argparse.Namespace(**vars(args))
    bad.private_root = tmp_path / "bad-private"
    bad.public_summary = tmp_path / "bad-public.json"
    bad.candidate_digest = "0" * 64
    with pytest.raises(ValueError, match="source identity"):
        pilot.final(bad)
    assert not bad.private_root.exists()


def test_private_summary_recursive_filtering():
    raw = {"pilot_version": pilot.PILOT_VERSION, "benchmark_version": "0.5.0",
           "complete": True, "outcome": "tied",
           "provenance": {"epoch_id": "public-id", "nonce": "secret", "host": {"ID": "secret"}},
           "runs": [{"pair": 1, "role": "reference", "score": 1.0,
                     "cells": {"small/eta1": {"cases": 20, "seed": 7,
                                                "successful_median_cpu_seconds": .1}},
                     "records": [{"candidate": "secret"}]}],
           "pairs": [], "reference_score_spread": {"minimum": 1.0},
           "interpretation": "x", "adapter_note": "x", "private_root": "/secret"}
    clean = pilot.sanitize_private_summary(raw)
    encoded = json.dumps(clean)
    assert "secret" not in encoded and "nonce" not in encoded and "records" not in encoded
    assert clean["runs"][0]["cells"]["small/eta1"]["cases"] == 20


@pytest.mark.parametrize(("scores", "eligible", "complete", "expected"), [
    ([(1, .98)] * 3, True, True, "consistent observed improvement"),
    ([(1, 1.005)] * 3, True, True, "tied"),
    ([(1, 1.02)] * 3, True, True, "regressed"),
    ([(1, .98), (1, 1.0), (1, 1.02)], True, True, "inconsistent"),
    ([(1, .98)] * 3, False, True, "invalid"),
    ([(1, .98)] * 3, True, False, "incomplete"),
])
def test_final_interpretations(scores, eligible, complete, expected):
    assert pilot.classify_outcome(scores, eligible, complete) == expected


def test_report_reproduction_and_incomplete(tmp_path):
    ledger = [record("baseline", 1.0, role="baseline"), record("winner", .9)]
    private = {"pilot_version": pilot.PILOT_VERSION, "benchmark_version": "0.5.0",
               "complete": True, "outcome": "consistent observed improvement",
               "provenance": {}, "runs": [],
               "pairs": [{"pair": i, "candidate_reference_ratio": .9,
                          "candidate_wins_beyond_tie_band": True,
                          "cell_candidate_reference_ratios": {}} for i in range(1, 4)],
               "reference_score_spread": {"minimum": 1, "maximum": 1, "relative_range": 0},
               "interpretation": "x", "adapter_note": "x"}
    assert pilot.render_report(ledger, private) == pilot.render_report(ledger, private)
    assert "winner" in pilot.render_report(ledger, private)
    assert "incomplete" in pilot.render_report(ledger, None).lower()
