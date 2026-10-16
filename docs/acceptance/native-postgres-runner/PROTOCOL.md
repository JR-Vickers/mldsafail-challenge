# Disposable native PostgreSQL runner

The sole native host operator uses clean retained source, a preloaded immutable
native-architecture PostgreSQL image, and a new output directory inside a private
0700 evidence parent. No staging URL, volumes, secrets or database enter the run:

```sh
python scripts/native_postgres_acceptance.py --image sha256:IMAGE_ID --output NEW_PRIVATE_OUTPUT
```

Docker must be rootless. The runner records image/Python/kernel/Docker/source
identities, creates a uniquely named loopback-only PostgreSQL container with tmpfs
storage and a synthetic password, and runs only the three explicit disposable
admission/ownership tests. Startup probes and the test process are bounded.
Image-declared storage volumes outside the tmpfs path are rejected.

Creation intent and owned CLI/test process identities are fsynced before proceeding.
An interrupted run is fenced by its existing output directory. Recovery uses the
same sibling lock as execution; it stops only same-boot, PID/startticks/UID/cmdline-
verified owned clients through pidfd, removes only containers whose exact label,
name, image and ID match the receipt, and proves repeated empty inventories:

```sh
python scripts/native_postgres_acceptance.py --cleanup --output EXISTING_PRIVATE_OUTPUT
```

Each cleanup attempt and the earlier report remain retained. A daemon failure,
ownership mismatch or leftover container keeps cleanup incomplete; retry after
repair before another native operation. Success requires all tests and cleanup;
local mocked tests cannot pass native PostgreSQL gates. Raw logs/receipts stay
protected and never enter the public launch ledger.
