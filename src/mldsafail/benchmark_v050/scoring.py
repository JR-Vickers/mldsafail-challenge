"""Prevalidation eligibility and ranking rules; independent of historical scores."""

from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict

CHALLENGE_CELLS = (("small", 1), ("small", 2), ("medium", 1), ("medium", 2), ("large", 1))
REFERENCE_SOLVER = "primal-lll"
SELECTION_CRITERIA = {
    "candidate": "mlwe",
    "challenge_cells": [list(c) for c in CHALLENGE_CELLS],
    "stress_cells": [["large", 2]],
    "minimum_distinct_degrees": 2,
    "reference_solver": REFERENCE_SOLVER,
    "reference_success_per_challenge_cell": 0.90,
    "second_family_success_on_at_least_one_cell": 0.80,
    "second_families": ["exhaustive", "hybrid-bdd"],
    "minimum_level_median_cpu_ratio": 2.0,
    "level_cpu_ratio_profiles": ["large", "small"],
    "direct_modular_disqualification_success_every_cell": 0.90,
    "harder_than_exhaustive": "at least one challenge level exceeds the fixed exhaustive applicability cap",
    "invalid_answers_allowed": 0,
    "bkz_kernel_share": 0.70,
    "bkz_materially_different_end_to_end_families": 2,
    "bkz_complete_solver_gain": 0.20,
    "bkz_gain_distinct_sizes": 2,
    "bkz_share_denominator": "complete worker CPU including verification; median repetition fraction per case, mean eta fractions per profile/seed, median over seed clusters",
    "bkz_gain_pairing": "same track/profile/eta/seed, both verified, same surrounding solver",
    "bkz_gain_statistic": "per profile: median over seeds of mean fractional CPU gain across jointly successful eta cases; two distinct profiles required",
    "fallback_weights": {"relevance": 30, "diversity": 20, "headroom": 15,
                         "verification": 15, "measurement": 10, "safety": 10},
    "fallback_tie_band_points": 5,
    "fallback_tie_preference": "msis, only if eligible",
    "msis_disposition": "disqualified: square planted prefix admits modular recovery",
    "bkz_structural_limitation": "MLWE-derived embedding contains trivial norm-squared-2 rows",
    "validation_problem_seeds_per_profile": 20,
    "uncertainty": "95% seed-cluster bootstrap intervals; Wilson intervals for per-cell success",
    "approval": "dedicated reviewer must accept all blocking dispositions and validation evidence",
}

RANKING_RULE = {
    "track": "mlwe",
    "objective": "minimize equally-cell-weighted geometric mean of case CPU/reference CPU ratios",
    "correctness": "exact complete A*s1+s2=t mod q; integral coefficients in [-eta,eta]",
    "case_success": "all three measured repetitions independently verified and within limits",
    "successful_case_cost": "max(1e-6, median complete worker CPU across three repetitions)",
    "failed_case_cost_seconds": 60.0,
    "failure_treatment": "any cap, timeout, memory failure, crash or no candidate makes entire case cost 60 seconds",
    "invalid_treatment": "any malformed or mathematically invalid candidate makes submission ineligible",
    "reference_solver": REFERENCE_SOLVER,
    "challenge_cells": [list(c) for c in CHALLENGE_CELLS],
    "tie": "sort raw scores ascending; each group's minimum anchors scores at most 1.01 times that minimum; competitive ranks, display ties by submission ID; no quality tie-break",
    "comparison_scope": "same frozen version, cases, pinned dependencies, and dedicated host; never cross tracks",
    "measurement_assumptions": "one warmup and three fresh worker subprocesses; one CPU, 60s wall, 2GiB; cooperative solver code",
    "score_uncertainty": "95% percentile interval from 2000 paired profile-seed cluster bootstrap draws; keep eta and solver pairs together; RNG label primitive-ranking-v2",
}


def _case_key(r):
    return r["profile"], r["eta"], r["seed"]


def case_cost(record):
    if any(r.get("status") == "invalid_answer" for r in record.get("repetitions", [])):
        raise ValueError("invalid candidate makes submission ineligible")
    if not record["verification_result"]:
        return 60.0
    cpu = record["median_cpu_seconds"]
    if cpu is None or not math.isfinite(cpu) or cpu < 0:
        raise ValueError("invalid CPU measurement")
    return max(1e-6, cpu)


def ranking(records, solver):
    """Rank complete, previously audited cohorts only; refuse unmatched cases."""
    relevant = [r for r in records if r["track"] == "mlwe"
                and (r["profile"], r["eta"]) in CHALLENGE_CELLS]
    def index(name):
        rows = [r for r in relevant if r["solver"] == name]
        result = {_case_key(r): r for r in rows}
        if len(result) != len(rows):
            raise ValueError("duplicate ranking case")
        return result
    reference, candidate = index(REFERENCE_SOLVER), index(solver)
    if not reference or reference.keys() != candidate.keys():
        raise ValueError("ranking requires complete paired reference cases")
    cells = defaultdict(list)
    for key, r in candidate.items():
        cells[key[:2]].append(math.log(case_cost(r) / case_cost(reference[key])))
    if set(cells) != set(CHALLENGE_CELLS):
        raise ValueError("ranking is missing a challenge cell")
    return math.exp(statistics.mean(statistics.mean(v) for v in cells.values()))


def tied(a, b):
    return abs(a-b) <= 0.01*min(a, b)


def ranked_groups(scores):
    """Anchored tie groups avoid the nontransitivity of pairwise tolerance."""
    ordered = sorted(scores.items(), key=lambda item: (item[1], item[0]))
    if any(not math.isfinite(v) or v <= 0 for _,v in ordered):
        raise ValueError("ranking scores must be finite and positive")
    result = []
    while ordered:
        anchor = ordered[0][1]
        group = [(name, value) for name,value in ordered if value <= 1.01*anchor]
        rank = len(result)+1
        result.extend({"submission": name, "score": value, "rank": rank} for name,value in sorted(group))
        ordered = ordered[len(group):]
    return result


def ranking_interval(records, solver):
    ranking(records, solver)  # Require the same completeness and correctness gates.
    indices = {s: {(r["profile"], r["eta"], r["seed"]): r for r in records
                   if r["track"] == "mlwe" and r["solver"] == s
                   and (r["profile"], r["eta"]) in CHALLENGE_CELLS}
               for s in {REFERENCE_SOLVER, solver}}
    reference, candidate = indices[REFERENCE_SOLVER], indices[solver]
    ratios = {key: math.log(case_cost(r)/case_cost(reference[key])) for key,r in candidate.items()}
    seeds = {p: sorted({seed for profile,_,seed in reference if profile == p})
             for p,_ in CHALLENGE_CELLS}
    if min(map(len, seeds.values())) < 2:
        return None
    rng = random.Random("primitive-ranking-v2")
    scores = []
    for _ in range(2000):
        draw = {p: rng.choices(values, k=len(values)) for p,values in sorted(seeds.items())}
        scores.append(math.exp(statistics.mean(statistics.mean(ratios[(p,e,s)] for s in draw[p])
                                               for p,e in CHALLENGE_CELLS)))
    scores.sort()
    return scores[49], scores[1949]


def eligibility(records):
    """Numeric viability gates; review and simple-baseline gates remain explicit."""
    mlwe = [r for r in records if r["track"] == "mlwe"]
    rates = {}
    for cell in CHALLENGE_CELLS:
        for solver in (REFERENCE_SOLVER, "exhaustive", "hybrid-bdd"):
            rows = [r for r in mlwe if (r["profile"], r["eta"]) == cell and r["solver"] == solver]
            rates[f"{cell[0]}/eta{cell[1]}/{solver}"] = (sum(r["verification_result"] for r in rows)/len(rows) if rows else None)
    baseline = all(rates[f"{p}/eta{e}/{REFERENCE_SOLVER}"] is not None and
                   rates[f"{p}/eta{e}/{REFERENCE_SOLVER}"] >= .9 for p,e in CHALLENGE_CELLS)
    second = any((rates[f"{p}/eta{e}/{s}"] or 0) >= .8
                 for p,e in CHALLENGE_CELLS for s in ("exhaustive", "hybrid-bdd"))
    times = {}
    for profile in ("small", "large"):
        values = [r["median_cpu_seconds"] for r in mlwe if r["profile"] == profile
                  and (r["profile"], r["eta"]) in CHALLENGE_CELLS
                  and r["solver"] == REFERENCE_SOLVER and r["verification_result"]]
        times[profile] = statistics.median(values) if values else None
    ratio = times["large"]/times["small"] if times["small"] and times["large"] else None
    harder = any(r.get("status") == "applicability_cap" for r in mlwe
                 if r["profile"] == "medium" and r["solver"] == "exhaustive")
    invalid = sum(any(rep.get("status") == "invalid_answer" for rep in r["repetitions"]) for r in mlwe
                  if (r["profile"],r["eta"]) in CHALLENGE_CELLS)
    direct_rates = {}
    for profile, eta in CHALLENGE_CELLS:
        rows = [r for r in mlwe if r["profile"] == profile and r["eta"] == eta
                and r["solver"] == "direct-linear"]
        direct_rates[f"{profile}/eta{eta}"] = sum(r["verification_result"] for r in rows)/len(rows) if rows else None
    direct_gate = all(v is not None for v in direct_rates.values()) and any(
        v < .90 for v in direct_rates.values() if v is not None)
    return {"rates": rates, "baseline_gate": baseline, "second_family_gate": second,
            "level_cpu_ratio": ratio, "difficulty_gate": ratio is not None and ratio >= 2,
            "exhaustive_headroom_gate": harder, "invalid_answers": invalid,
            "direct_linear_rates": direct_rates, "direct_shortcut_gate": direct_gate,
            "numeric_eligibility": baseline and second and ratio is not None and ratio >= 2 and harder and not invalid and direct_gate,
            "separate_required_gates": ["reviewer approval", "audited held-out evidence"]}
