"""Reproduce quantitative selection gates from previously audited raw evidence."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .audit import audited_records
from .decision import eligibility, ranked_groups, ranking, ranking_interval
from .report import reduction_share, _bootstrap


def kernel_gates(records):
    families = {}
    for track, solver, family in (("mlwe", "primal-bkz", "primal-cvp"),
                                  ("mlwe", "hybrid-bdd", "guess-babai"),
                                  ("msis", "progressive-bkz", "relation-enumeration"),
                                  ("msis", "restart-bkz", "relation-enumeration")):
        clusters = defaultdict(list)
        for r in records:
            if r["track"] == track and r["solver"] == solver and r["verification_result"]:
                clusters[(r["profile"], r["seed"])].append(reduction_share(r))
        values = [statistics.mean(v) for _,v in sorted(clusters.items())]
        families[f"{track}/{solver}"] = {"family": family, "seed_clusters": len(values),
            "median_share": statistics.median(values) if values else None,
            "interval95": _bootstrap(values, statistics.median)}
    qualifying = {v["family"] for v in families.values() if v["median_share"] is not None and v["median_share"] >= .70}
    comparisons = {}
    for track, old, new in (("mlwe", "primal-lll", "primal-bkz"),
                            ("msis", "lll-short-vector", "progressive-bkz")):
        def index(solver):
            return {(r["profile"], r["eta"], r["seed"]): r for r in records
                    if r["track"] == track and r["solver"] == solver}
        left, right = index(old), index(new)
        clusters, totals, successes = defaultdict(lambda: defaultdict(list)), defaultdict(int), defaultdict(int)
        for key in sorted(left.keys() | right.keys()):
            p, _, seed = key
            totals[p] += 1
            a,b = left.get(key), right.get(key)
            if a and b and a["verification_result"] and b["verification_result"]:
                clusters[p][seed].append(1-b["median_cpu_seconds"]/a["median_cpu_seconds"])
                successes[p] += 1
        comparisons[track] = {}
        for p in sorted(totals):
            gains = [statistics.mean(v) for _,v in sorted(clusters[p].items())]
            comparisons[track][p] = {"all_pairs": totals[p], "joint_successes": successes[p],
                "median_seed_gain": statistics.median(gains) if gains else None,
                "interval95": _bootstrap(gains, statistics.median)}
    gain_gate = any(sum(row["median_seed_gain"] is not None and row["median_seed_gain"] >= .20
                        for row in profiles.values()) >= 2 for profiles in comparisons.values())
    return {"shares": families, "distinct_dominant_families": len(qualifying),
            "dominance_gate": len(qualifying) >= 2, "paired_gains": comparisons,
            "gain_at_two_sizes_gate": gain_gate,
            "eligible": False,
            "structural_disqualification": "MLWE-derived objective has trivial norm-squared-two vectors; MSIS source distribution is shortcut-prone",
            "interpretation": "runtime consumption alone is not evidence of improvement; unsuccessful pairs are retained in all-pair counts"}


def analyze(records):
    groups = defaultdict(list)
    for r in records:
        groups[(r["study_version"], r["cohort"], r.get("run_id", "legacy"))].append(r)
    results = []
    for (version, cohort, identity), rows in sorted(groups.items()):
        if version != "primitive-selection-v2":
            continue
        scores, ineligible = {}, {}
        for solver in sorted({r["solver"] for r in rows if r["track"] == "mlwe"}):
            try:
                scores[solver] = ranking(rows, solver)
            except ValueError as exc:
                ineligible[solver] = str(exc)
        results.append({"study_version": version, "cohort": cohort, "run_id": identity,
                        "records": len(rows), "mlwe": eligibility(rows), "bkz": kernel_gates(rows),
                        "ranking": [{**row, "interval95": ranking_interval(rows, row["submission"])}
                                    for row in ranked_groups(scores)], "ineligible_submissions": ineligible,
                        "msis": {"eligible": False, "reason": "direct modular planted-answer recovery"}})
    return {"cohorts": results, "decision_status": "numeric evidence only; dedicated reviewer approval is a separate mandatory gate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(audited_records(args.input))
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(args.output)


if __name__ == "__main__":
    main()
