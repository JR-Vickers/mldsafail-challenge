import copy

import pytest

from research.primitive_selection.decision import CHALLENGE_CELLS, case_cost, eligibility, ranking, ranked_groups, tied
from research.primitive_selection.runner import _aggregate_repetitions


def record(profile, eta, solver, cpu, statuses=("success",)*3):
    reps = []
    for status in statuses:
        rep = {"cpu_seconds": cpu, "evaluator_wall_seconds": cpu,
               "candidate": {"tag": "recovered_secret"}, "verification": {"verified": status == "success"},
               "status": status}
        if status == "applicability_cap":
            rep.update(candidate=None, diagnostic_counters={"search_space_skipped": 10**30})
        if status == "timeout":
            rep.update(timeout=True)
        reps.append(rep)
    return {"track": "mlwe", "profile": profile, "eta": eta, "seed": 0, "solver": solver,
            **_aggregate_repetitions(reps)}


def test_actual_aggregates_drive_failure_penalties_and_invalid_disqualification():
    r = record("small", 1, "primal-lll", .01, ("success", "timeout", "success"))
    assert not r["verification_result"] and case_cost(r) == 60
    r = record("small", 1, "primal-lll", .01, ("success", "invalid_answer", "success"))
    with pytest.raises(ValueError, match="ineligible"):
        case_cost(r)


def test_ranking_pairs_all_predeclared_cells_and_refuses_duplicates():
    records = [record(p,e,s,.01 if s == "primal-lll" else .005)
               for p,e in CHALLENGE_CELLS for s in ("primal-lll", "hybrid-bdd")]
    assert ranking(records, "primal-lll") == 1
    assert ranking(records, "hybrid-bdd") == pytest.approx(.5)
    with pytest.raises(ValueError, match="complete paired"):
        ranking(records[:-1], "hybrid-bdd")
    with pytest.raises(ValueError, match="duplicate"):
        ranking(records + [records[0]], "primal-lll")
    assert tied(1,1.005) and not tied(1,1.02)
    groups = ranked_groups({"a": 1.0, "b": 1.009, "c": 1.018})
    assert [row["rank"] for row in groups] == [1,1,3]


def test_eligibility_uses_real_cap_status_and_checks_mixed_invalid():
    records = []
    for p,e in CHALLENGE_CELLS:
        for solver in ("primal-lll", "hybrid-bdd", "exhaustive"):
            statuses = ("applicability_cap",)*3 if p == "medium" and solver == "exhaustive" else ("success",)*3
            records.append(record(p,e,solver,.01 if p == "small" else .1,statuses))
        direct = record(p,e,"direct-linear",.01,("applicability_cap",)*3)
        for rep in direct["repetitions"]:
            rep["diagnostic_counters"] = {}
            rep["status"] = "no_candidate"
        records.append({**direct, **_aggregate_repetitions(direct["repetitions"])})
    assert eligibility(records)["numeric_eligibility"]
    bad = copy.deepcopy(records)
    bad[0] = record("small", 1, "primal-lll", .01, ("success", "invalid_answer", "success"))
    assert not eligibility(bad)["numeric_eligibility"]
    assert eligibility(bad)["invalid_answers"] == 1
