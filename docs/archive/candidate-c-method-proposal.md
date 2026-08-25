# Candidate C — Method Proposal: Guessing + Reduced Solve

## 1. What the method does

The method exploits the bounded coefficient structure (`|c_i| ≤ η`) by combining **targeted enumeration** of a subset of coefficients with **algebraic solving** for the remainder.

**Algorithm:**
1. Choose `k` coefficients to guess (enumeration set). The remaining `n−k` coefficients are solved algebraically.
2. Enumerate all `(2η+1)^k` possible assignments to the `k` guessed coefficients (each in `[−η, η]`).
3. For each assignment:
   - Substitute the guessed values into the linear system `A c ≡ t (mod q)`, reducing it to an `(n−k) × (n−k)` system in the remaining unknowns.
   - Solve the reduced system via Gaussian elimination over the prime field `ℤ_q`.
   - Check whether all solved coefficients lie in `[−η, η]`. If yes, verify `A c ≡ t (mod q)` and return.
4. If no valid assignment is found after full enumeration, report failure.

**What it exploits:** The small `η` bound makes the enumeration space `(2η+1)^k` manageable when `k` is chosen appropriately for the dimension. The structure exploited is the **decoupling** of the coefficient vector into a small enumerable prefix and an algebraically solvable suffix — a different axis from the geometric (Candidate B) or optimization-based (Candidate A) approaches.

## 2. Why it is different from A and B

- **Candidate A (direct bounded recovery):** Solves the system directly (Gaussian elimination) and then checks/clips the result against the bound. It does not enumerate any coefficients. It treats the bound as a post-hoc constraint.
- **Candidate B (lattice reduction + extraction):** Constructs a lattice, runs LLL/BKZ, extracts a short vector. The algorithmic axis is geometric reduction in an `(n+1)`-dimensional lattice. No enumeration, no substitution.
- **Candidate C (guessing + reduced solve):** Uses **combinatorial enumeration** of a subset of coefficients (exploiting small η) combined with **algebraic elimination** for the rest. The axis is: *enumerate a small sub-space, solve the complement exactly*. This is a hybrid that neither A (pure solve) nor B (pure lattice geometry) uses. The bounded structure is exploited through the enumeration size `(2η+1)^k` rather than through geometric shortness or constrained optimization.

## 3. How it produces a valid c

The method directly produces the full coefficient vector `c` as the concatenation of guessed coefficients and solved coefficients. No separate extraction step is needed — the enumeration produces candidate vectors, and the first one satisfying both the bound and the modular relation is the output. The extraction method is **"guessing + reduced Gaussian solve"**.

## 4. How the shared cost is instrumented

Every operation in the pipeline is counted through the shared `OperationMeter`:

- **Enumeration loop:** Each iteration counts as a memory access pattern (memory_reads for loop control, memory_writes for storing the current guess tuple).
- **Substitution step:** For each guessed coefficient substituted into the reduced system, count multiplications (scaling the column) and additions (updating the RHS), plus modular_reductions.
- **Gaussian elimination on the reduced system:** Count exactly as in `baseline.py` — additions, multiplications, modular_reductions, basis_updates (row swaps), memory_reads, memory_writes.
- **Bound check:** memory_reads for inspecting each solved coefficient.
- **Final verification (if candidate found):** mat_vec_mul: n multiplications + n additions + n modular_reductions per row, plus memory reads/writes.
- **Failure path:** If enumeration exhausts without success, all accumulated costs are flushed to the meter in a `finally` block (following `baseline.py` pattern).

The cost meter is used as a single shared instance across the entire pipeline — no private cost model.

## 5. Diagnostics reported

Candidate-specific diagnostics in `candidate_diagnostics`:
- `k_guessed`: number of coefficients enumerated.
- `enumeration_space_size`: `(2η+1)^k`, the total number of guesses.
- `guesses_tried`: how many guesses were actually tried before finding a solution (or the full space on failure).
- `reduced_dimension`: `n − k`, the size of the algebraically solved subsystem.
- `first_guess_hit_index`: the index (0-based) of the first successful guess, or null if none found.
- `gaussian_elim_solves`: number of times the reduced system was solved (equals guesses tried).
- `substitution_cost_estimate`: rough count of operations spent in substitution across all guesses.

These explain where the budget went: enumeration overhead, substitution cost, and the Gaussian solve cost per guess.

## 6. Plausibility check on the reduced-scale instances

The method is designed to work on all three profiles by choosing `k` adaptively:

| Profile | n | η | (2η+1) | k chosen | Enumeration size | Reduced n−k | Gaussian ops per solve (approx) | Total ops estimate |
|---------|---|---|--------|-----------|------------------|-------------|----------------------------------|---------------------|
| small   | 8 | 2 | 5      | 4         | 5⁴ = 625         | 4           | ~4³ = 64                         | ~40,000            |
| medium  | 16| 3 | 7      | 6         | 7⁶ = 117,649    | 10          | ~10³ = 1,000                     | ~117 million       |
| large   | 24| 4 | 9      | 6         | 9⁶ = 531,441    | 18          | ~18³ = 5,832                     | ~3.1 billion       |

- **Small (n=8, η=2):** Trivial. 625 guesses, each solving a 4×4 system. Should complete in well under a second with low cost.
- **Medium (n=16, η=3):** 117K guesses with 10×10 solves. ~117M total operations. Feasible within minutes. If the planted solution happens to be found early in the enumeration order, cost is much lower.
- **Large (n=24, η=4):** 531K guesses with 18×18 solves. ~3.1B operations. This is the most expensive case. If this proves too slow, the method can fall back to `k=5` (59K guesses × 19×19 solve ≈ 405M ops) or `k=4` (6,561 guesses × 20×20 solve ≈ 52M ops). The enumeration order can also be randomized to avoid worst-case positioning of the planted solution.

**Why it could work:** The method always eventually finds the planted solution if it exhausts the full enumeration space, because the planted solution is one of the `(2η+1)^n` possible coefficient vectors, and we enumerate a cross-product of subsets that covers the full space when k=n (worst case) or hits it probabilistically when k < n. For the reduced-scale instances, the planted solution exists and is unique (the matrix is invertible), so any complete search over a covering set will find it. The practical concern is only runtime/cost, not correctness.

**Note on enumeration order:** Guesses are enumerated in lexicographic order over `[-η, η]^k`. The planted solution's position in this order is effectively random (since the generator picks coefficients uniformly). Expected position is half the enumeration space. For small and medium this is fine; for large, expected cost is ~1.5B ops, which is acceptable for a one-off benchmark run with no resource limits.
