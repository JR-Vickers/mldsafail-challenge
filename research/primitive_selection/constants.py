"""Frozen study constants and safety caps."""

STUDY_VERSION = "primitive-selection-v1"
SCHEMA_VERSION = "1"

MAX_N = 32
MAX_Q = 257
MAX_MODULE_RANK = 5
MAX_MATRIX_ENTRIES = 5 * 5 * MAX_N
MAX_SERIALIZED_BYTES = 2_000_000
WALL_LIMIT_SECONDS = 60
MEMORY_LIMIT_BYTES = 2 * 1024**3
WARMUP_RUNS = 1
MEASURED_RUNS = 3

DEVELOPMENT_SEEDS = tuple(range(10))

# The pairs are deliberate: each q is 1 mod 2n, so x^n + 1 splits over Z_q.
PROFILES = {
    "small": {"n": 8, "q": 97, "k": 2, "l": 2, "msis_rows": 2, "msis_cols": 3},
    "medium": {"n": 16, "q": 193, "k": 3, "l": 2, "msis_rows": 3, "msis_cols": 4},
    "large": {"n": 32, "q": 257, "k": 4, "l": 3, "msis_rows": 4, "msis_cols": 5},
}

ETAS = (1, 2)
