# Local MLWE benchmark 0.5.0

This opt-in benchmark implements the [frozen MLWE contract](PRIMITIVE_SELECTION_SPEC.md). The package version, `mldsafail` commands, historical scores/fingerprints, and hosted service remain 0.4.0. There is no hosted leaderboard integration.

Use evaluator Python **3.12.10** and Docker with a Linux **ARM64** worker. This initial artifact lock contains the reviewed ARM64 CPython wheels, their SHA-256 hashes, the pinned Python base-image digest, and exact GMP/MPFR package versions. Other architectures require a separately reviewed artifact lock and new epoch. Native library, wheel, interpreter, image, trusted-code and Docker-host identities are retained in each epoch. Run evaluations sequentially on a common idle host; timings are host-specific.

```sh
source .venv/bin/activate
uv sync
python -m mldsafail.benchmark_v050.build
mldsafail-mlwe smoke --output /tmp/mlwe-smoke-new

# Choose a new private directory outside any solver checkout.
export MLWE_EVIDENCE="$HOME/mlwe-private-new"
mkdir -m 700 "$MLWE_EVIDENCE"
mldsafail-mlwe epoch create --output "$MLWE_EVIDENCE/epoch"
mldsafail-mlwe run --epoch "$MLWE_EVIDENCE/epoch" \
  --solver-dir examples/mlwe/primal-lll --output "$MLWE_EVIDENCE/reference-run"
mldsafail-mlwe run --epoch "$MLWE_EVIDENCE/epoch" \
  --solver-dir examples/mlwe/hybrid-bdd --output "$MLWE_EVIDENCE/hybrid-run"
mldsafail-mlwe audit --epoch "$MLWE_EVIDENCE/epoch" \
  --run "$MLWE_EVIDENCE/reference-run" --run "$MLWE_EVIDENCE/hybrid-run"
mldsafail-mlwe rank --epoch "$MLWE_EVIDENCE/epoch" \
  --run "$MLWE_EVIDENCE/epoch/primal-lll" \
  --run "$MLWE_EVIDENCE/reference-run" --run "$MLWE_EVIDENCE/hybrid-run"
```

Every output directory must be new. Epoch creation samples a fresh private nonce, derives 20 seeds per profile and fixes 100 ranked cases. It runs primal-LLL, exhaustive, and direct-linear with one warmup and three measured executions each, checking the frozen reference-success, second-family, runtime-separation, exhaustive-headroom, and direct-shortcut gates. A failed gate preserves the epoch and returns nonzero; it never selects replacement seeds. The frozen reference table ranked against itself scores exactly 1. A separate reference contestant run has new timings and need not score exactly 1.

A contestant directory contains only Python source, at most 2 MB in total, with `solver.py` exporting:

```python
def solve(public_instance):
    # Read A, t, ring, dimensions, eta and the public instance ID.
    # Return complete bounded vectors, or None if no answer was found.
    return {"tag": "recovered_secret", "s1": s1, "s2": s2}
```

`None` and exceptions are recorded failures. The exhaustive, primal-LLL and hybrid-BDD examples provide working starters. The trusted arithmetic and solver modules are available inside the image; the evaluator generator and evidence modules are absent. No MSIS or BKZ challenge input is accepted. Large/eta2 is supported by the fixed public decoder for public reproduction, but is outside this 100-case ranking.

Each execution gets a fresh disposable container with public input on stdin and a read-only snapshot of approved contestant files. Containers have no network, repository, epoch, credentials, research evidence, prior results, or Docker socket mounts. They run as UID 65534 with a read-only root, dropped capabilities, one CPU, 2-GiB memory/address-space limits, 64-MiB temporary storage and a bounded output stream. The parent terminates executions at 60 seconds and independently verifies candidates. A kill signal alone is a crash, not evidence of OOM; address-space allocation failures and Docker OOM reports are recorded separately.

This is a cooperative local research interface. Contestants must not tamper with the trusted in-container timing adapter, enumerate published development seeds, cache answers, inspect evaluator data, or communicate externally. Protection against malicious timing manipulation is outside scope. Complete worker CPU includes parsing, contestant loading, lazy mathematical imports, solving and verification; it excludes trusted adapter imports before the clock and final serialization. Parent wall time includes Docker startup.

Private evidence contains the nonce, derived seeds, public cases, raw streams/candidates, measurements, verification/quality, source snapshots and provenance. Directories use mode 0700 and evidence files 0600. `manifest.json` fixes identity/settings/cases; `COMPLETE.json` is the atomic completion manifest binding every evidence file, including the frozen reference-cost table and child runs. Missing completion markers remain partial diagnostics and cannot rank. Audit regenerates instances and rechecks every stored candidate, digest, identity, setting, aggregate and reference table. Partial-run audit reports available verified records and missing work, then returns nonzero. There is no resume or overwrite operation.

Each run retains `summary.json` as a shareable non-ranking diagnostic. `audit` and `rank` regenerate ranking summaries on stdout, using the private frozen reference. These summaries omit seeds, nonce, witnesses, candidates and secret filesystem paths. Keep complete evidence private; redirect only the CLI's JSON stdout when sharing results. Any invalid ranked candidate makes a run ineligible; ordinary recorded timeouts, caps, crashes and no-answer results remain complete evidence with a 60-second case penalty.

Scoring uses median complete-worker CPU when all three measurements succeed, with a one-microsecond floor, divided by the same-instance frozen reference cost. Five cell geometric means receive equal weight. Competitive ranks use anchored 1% ties, and uncertainty uses the frozen 2,000-draw profile/seed-cluster bootstrap. Warmups, stress cases, norms and RSS do not enter the score.

Verification commands:

```sh
make check
MLWE_DOCKER_TESTS=1 pytest tests/test_mlwe_v050_docker.py
python -m mldsafail.benchmark_v050.build --no-cache --tag mldsafail-mlwe:rebuild-a
python -m mldsafail.benchmark_v050.build --no-cache --tag mldsafail-mlwe:rebuild-b
python scripts/mlwe_reproduce.py --image-a mldsafail-mlwe:rebuild-a \
  --image-b mldsafail-mlwe:rebuild-b --output /tmp/mlwe-reproduction-new
```

The reproduction comparison additionally needs the reviewed `mldsafail-primitive-study:validation-v2` image. It compares public fixtures and normalized outputs against both clean builds and the reviewed worker; timing equality is not required. See [specification mapping](MLWE_SPEC_MAPPING.md) and [acceptance evidence](acceptance/mlwe-v050/README.md).
