# Research v2 challenge specification

Status: proposed MLWE bounded recovery, pending freeze and held-out agent approval. This specifies the scientific choices for the next benchmark. Benchmark 0.4.0 remains unchanged.

## Mathematical task

Let R_q = Z_q[x]/(x^n+1), represented by n coefficients in ascending degree. Given A in R_q^(k x l), t in R_q^k, and eta, return (s1,s2), respectively l and k integer polynomials of degree below n, satisfying A*s1+s2=t modulo q. Every coefficient must be an integer in [-eta,eta]. Any pair satisfying the full equation and bounds is accepted; the particular planted pair is not required. This is feasibility, with norms recorded as diagnostics.

The motivation is ML-DSA's module/ring structure and short secret/error relation. These tiny profiles are structural analogues, not standardized ML-DSA parameter sets or a distribution carrying a claimed production hardness reduction. FIPS 204 uses degree 256 and modulus 8380417. The explicit tiny-instance research scope takes precedence over the contradictory older AGENTS sentence about standardized parameters. [NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final), [Langlois–Stehlé module-lattice definitions](https://eprint.iacr.org/2012/090).

Only repository-generated synthetic instances are executable inputs. No external keys, signatures, targets, practical parameters, or signature forging are accepted. Immutable ceilings remain n<=32, q<=257, module rank<=5, matrix coefficient count<=800, serialized JSON<=2,000,000 bytes, and derived basis dimension<=384.

## Generator and profiles

| Profile | n | q | MLWE k,l | MSIS comparator rows,columns | eta | Ranking role |
|---|---:|---:|---|---|---|---|
| small | 4 | 97 | 2,1 | 2,3 | 1 and 2 | challenge |
| medium | 8 | 97 | 2,2 | 2,3 | 1 and 2 | challenge |
| large | 16 | 193 | 3,2 | 3,4 | 1 and 2 | eta=1 challenge; eta=2 stress |

Primitive-selection-v2 is an incompatible generator, payload, and measurement version. A is coefficient-wise uniform in [0,q); s1 and s2 are independently coefficient-wise uniform in [-eta,eta]; t is their exact negacyclic matrix product and modular sum. Generation does not reject cases on difficulty, solver success, norm, or matrix rank. Development uses all seeds 0 through 9. Python 3.12.10 random.Random and randrange are part of the sampler.

Each stream initializes random.Random with the big-endian integer value of SHA-256 over the UTF-8 string joining version, track, profile, eta, seed, and purpose with NUL bytes. Integers use decimal spelling. Purposes are matrix, secret-s1, secret-s2, and comparator-only relation. Eta is newly domain-separated in v2. An instance ID hashes the canonical public JSON without instance_id: sorted keys, compact separators, ASCII encoding. The input digest also includes instance_id.

The reviewer generates 32 random bytes as 64 hexadecimal characters only after the freeze commit. Its record binds nonce, UTC creation time, freeze-file SHA-256, freeze commit, and reviewer model/session. For each profile, validation hashes version, validation, profile, nonce, and counter (NUL-separated), takes the first eight bytes as a big-endian integer, and increments counter from zero until 20 distinct seeds are obtained. The per-profile seed pairs eta, solver, and track observations; sampler labels separate their streams. No seed or outcome selection is permitted. Repairs require a new version, freeze, and nonce while retaining earlier evidence.

## Public contract and verification

The public MLWE object contains exactly schema_version, study_version, track, profile, ring, dimensions, eta, A, t, and instance_id. Ring contains modulus, degree, polynomial; dimensions contains rows, columns. No generation seed, nonce, run identity, source path, witness, or evaluator diagnostic crosses this interface. Only the fixed profiles pass the public decoder. The evaluator retains generation seeds and provenance in result records.

The output contains exactly tag=recovered_secret, s1, and s2, with both complete polynomial vectors. The structural schemas are research/primitive_selection/schemas/instance-v2.schema.json and candidate-v2.schema.json; models.py and verify.py additionally enforce shapes, integer types (including boolean rejection), caps, canonical IDs, bounds, and every ring equation. Stored candidates are independently reverified against regenerated evaluator instances. Solver success flags and claimed quality are not trusted. Zero MLWE output is valid only when it satisfies the full task; a zero MSIS relation is always rejected.

MSIS remains a disqualified comparator. A=[B|-Bw] with final witness polynomial one permits modular recovery; the planted target norm does not guarantee difficulty. V2 enforces both public norm bounds and nonzero relations; historical v1 success retains its weaker original meaning. BKZ comparators require exact B'=UB, exact |det(U)|=1 using Bareiss determinants, and regenerated source-basis provenance. Their quality is separate from MLWE. MLWE-derived BKZ bases have trivial norm-squared-two vectors and cannot organize a short-vector challenge on that objective.

This is a cooperative research-code interface. Solvers must not access evaluator generators, seeds, nonces, files, environment, results, answer tables, or diagnostics; enumerate known development seeds; cache answers between subprocesses; communicate externally; or modify measurement or verification. Published development records allow reconstruction outside evaluation. The shared Python/filesystem environment is not a hostile-code sandbox. Production integration must enforce evaluator/solver isolation rather than infer secrecy from omitted field names.

## Portfolio and measurement

The fixed portfolio has sixteen combinations per profile/eta/seed:

- MLWE: exhaustive, primal-lll, primal-bkz, hybrid-bdd, direct-linear.
- MSIS: lll-short-vector, progressive-bkz, restart-bkz, direct-linear, sparse-relation.
- BKZ: lll-only, fixed-bkz, progressive-bkz, each on MLWE- and MSIS-derived bases.

The original thirteen-combination subset contributes 780 development / 1,560 validation records. The three added simple comparators contribute 180 / 360, giving exact totals 960 / 1,920. All combinations and outcomes remain in the final cohort.

Primal-lll is the reference: q-ary primal basis, LLL delta=.99, fast fpylll CVP. Primal-bkz replaces reduction with block 12 and two requested tours. Hybrid-bdd guesses one secret coefficient, reduces a shared residual basis once with block 12 / one requested tour, and applies Babai nearest-plane to each guess. Exhaustive enumerates only s1 and derives centered residual s2, capped at one million possible s1 assignments. Direct-linear solves the modular system without optimizing shortness and returns no candidate if bounds fail. MSIS direct solving includes bounded free-variable search capped at one million; sparse search covers support one or two with +/-1 coefficients. All adapter settings, uniform applicability caps, and per-track overrides are frozen through configuration and source digests.

Each case has one warmup and three measured executions in fresh subprocesses. A deterministic cohort/nonce-separated shuffle randomizes case order. The parent enforces 60 seconds wall time; Linux workers apply a 2-GiB address-space limit and one CPU affinity, and the container has one CPU and 2-GiB memory. Complete measured worker CPU includes parsing, solver work, verification, and lazy imports during solving; it excludes interpreter/import work before the worker clock starts and final output serialization. Parent wall time includes startup. These conventions, exact dependency pins, and a common idle host define comparisons; timings are not hardware-independent operation costs. Peak RSS includes interpreter/library residency.

Records retain every warmup/repetition output, status, timing, quality, limits, settings, input/output hashes, host, image, and source/configuration/dependency provenance. Statuses distinguish success, applicability_cap, timeout, memory_failure, crash, invalid_answer, no_candidate, and mixed. Signals alone do not establish OOM. Caps are unsolved observations, not measured algorithm failures. Unique exclusive manifests fix the shuffled case grid; interrupted evidence stays partial and is excluded from final reports. Auditing checks completeness, uniqueness, provenance, derivation, settings, aggregates, digests, and independently recomputed correctness and quality.

## Selection and ranking

Eligibility precedes fallback scoring. MLWE must retain all four small/medium eta cells plus large/eta=1, at least two distinct degrees, reference success >=90% of all seeds per cell, a different exhaustive or hybrid method with >=80% success on at least one challenge cell, large/eta=1 versus small median reference CPU ratio >=2, and a challenge level exceeding exhaustive applicability. Direct modular recovery >=90% in every challenge cell disqualifies the formulation. No invalid submitted answer is allowed. The same thresholds apply unchanged to validation. Large/eta=2 stress outcomes remain visible. Per-cell success uses 95% Wilson intervals; CPU, quality, reduction shares, and paired gains use seed-level bootstrap intervals. These are minimum viability criteria, not hardness claims.

The initial two-level proposal failed the 2x runtime-separation gate in development calibration (small 0.02625s; medium 0.03291s, about 1.25x). Large/eta=1 measured 0.32558s, about 12.4x small, and was added before the final development cohort and before validation. This repairs the proposed challenge by adding a measured difficulty level; it does not waive the failed gate or erase the calibration. The complete development and validation cohorts must independently meet the revised five-cell criteria.

BKZ retains both original gates: >=70% of complete CPU in reduction in at least two materially different end-to-end families, and >=20% paired complete-solver gain at two sizes, reproduced on validation. Runtime consumption alone proves no gain. Eligible fallback candidates receive weights relevance 30, diversity 20, headroom 15, verification 15, measurement 10, safety 10. The historical five-point tie band prefers MSIS only if eligible. Disqualified candidates cannot gain eligibility through points. A dedicated agent must approve all blocking dispositions and held-out evidence.

The future MLWE ranking is fully specified by decision.py. Any invalid candidate on a ranked case makes the submission ineligible. A case succeeds only if all three measured repetitions verify and stay within limits. Its cost is max(one microsecond, median complete CPU); any cap, timeout, memory failure, crash, or no candidate in any repetition charges 60 seconds for the entire case. Warmups do not score. Pair each case with the frozen primal-lll reference on that same instance; compute its cost ratio, average log ratios within each challenge cell, average those five cell means equally, then exponentiate. Lower is better. Stress cells, other tracks, norms, RSS, and operation counters never enter this score.

Sort raw scores ascending. Each tie group's minimum a anchors all following scores <=1.01*a; give the group the same competitive rank and display by submission ID. Start the next group beyond that boundary. Missing or duplicate ranked cases cannot be ranked. Reference costs, cases, environment, and version must match. Uncertainty accompanies the ranking without an unrecorded tie-break.

Score uncertainty uses a 95% percentile interval from 2,000 bootstrap draws with RNG label primitive-ranking-v2. Within each profile, resample seed clusters with replacement, keeping eta and reference/contender pairs together, and recompute the equally weighted five-cell score. Report the sorted draw values at indices 49 and 1949. Repeated timings are never independent problem instances.

## Migration to the next benchmark

Production must create a new benchmark version and trusted fingerprint, port this exact sampler/seed protocol and strict tagged contracts, isolate evaluator state from contestant code, port the reference solver/settings, enforce limits and fresh subprocesses, and implement the five-cell normalized ranking including penalties and anchored ties. It must persist raw candidate evidence and complete/partial run identities, independently verify answers, and expose every failure category. Changed distributions, settings, or score meaning require versioning.

Storage and APIs must namespace results and reference costs by benchmark version, accept the MLWE output only for the new version, retain all historical 0.4.0 score computation/rendering, and reject cross-version comparisons. Hosted workers need public-input-only isolation and bounded JSON/process resources. Migration tests must replay unchanged 0.4.0 fixtures, frozen research fixtures and normalized reference outputs, verifier rejection cases, resource failures, and ranking/penalty/tie examples. Production deployment, hidden-seed setup, database migrations, and UI activation are later implementation work, not part of this research change.

Each new benchmark evaluation epoch uses 20 seeds per profile: 100 ranked MLWE cases across the five cells. Its evaluator creates a fresh private 32-byte root nonce and derives seeds by the specified validation protocol; the published research-validation nonce must never serve as a production secret. Before accepting submissions for an epoch, execute the frozen reference with the same one-warmup/three-measurement protocol on every ranked case and the common evaluation host, then freeze its reference-cost table and manifest. Keep cases and reference costs fixed for that epoch. Changing the case set, dependency artifacts, or host starts a new epoch and reference table; cross-epoch scores are not directly ranked together.
