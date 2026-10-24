# Control runner engineering and collection handoff

This is local development guidance, not execution authority. The current
[engineering record](acceptance/production-preparation/protected-runtime-engineering-20261024.md)
separates implemented adapters, local results, unimplemented installed adapters,
native acceptance, missing host facts and complete-proposal review.

`deploy/workload_controls.py` remains the 27-scenario inventory.
`deploy/workload_control_registry.py` is the checked registry; coverage comes from
it through `deploy/workload_evidence.py`. Missing, duplicate, substituted or extra
entries fail validation. A runner declaration is never a passing receipt.

The fixed `scripts.workload_control_case` entrypoint accepts an exact private
packet, one control/scenario and an exclusive private output. Its command must
match exactly one case in that packet. It accepts no arbitrary command. An
exclusive intent prevents replay through the same bound output. Synthetic and
local Linux inert-process adapters do not create installed-native authority.
Raw fixture observations remain private, including failed and partial outcomes.
The synthetic dispatcher cases use real application SQL transactions and signed
synthetic results; they do not open an epoch, fetch a repository or run a solver.

Prepare one review document without execution:

```sh
source .venv/bin/activate
python -m scripts.prepare_workload_control_packet \
  --proposal /absolute/private/proposal.json \
  --inspection /absolute/private/installed.json \
  --packet /absolute/private/future-packet.json \
  --case-output /absolute/private/case-intent.json \
  --control explicit_resume --scenario failed_preflight \
  --attempt /absolute/private/existing-attempt.json \
  --output /absolute/private/control-preparation.json
```

This preparation schema is deliberately not the executable acceptance schema.
It binds frozen proposal/inspection references, selected order, source hashes,
configuration hashes and resource identities. Missing facts stay explicit
blockers. It currently cannot produce a ready installed-native execution packet:
generation-owned context, lifecycle cleanup/postflight commands and matching
native adapters still need implementation and review. Do not remove those
blockers because a reviewer or owner field is present.

The fixed envelope is startup 30 seconds, case 90, cleanup 45 and postflight 15,
180 seconds total. A split packet must fit the same original fixture attempt's
remaining work allowance (30 minutes minus its five-minute cleanup reserve).
Splitting packets never creates another attempt. The preparation attempt fields
are bookkeeping, not proof of authority or a replacement for the fixture journal.
Executable installed-native packets still require exact independent review,
fresh owner authorization and a consumed single-use claim. Existing inner
runtime and command deadlines are unchanged.

Protocol-four recovery records bind parent and mutation intents, operation,
resource identity and expected transition. Protocols one through three retain
their original meanings. Separate reconciliation only observes; continuation
requires fresh execution authority. Acknowledged snapshots, configuration files,
bundle files/directories and tool trees may be skipped only after their exact
identities and postconditions pass. Uncertain external effects are preserved and
blocked; there is no generic image, format, mount or service-manager replay rule.
See `deploy/workload_recovery_inventory.py` for operation/effect dispositions and
the [fixture guide](WORKLOAD_INSTALLATION_FIXTURE.md) for the unchanged complete
installation → fresh inspection → rollback path and interruption cases.

The locally reviewed [collector handoff](acceptance/production-preparation/protected-runtime-collection-handoff-20261024.md)
contains deterministic archive hashes, exact administrator installation/revocation
instructions and private output locations. It preserves the original collector.
It has not been transferred or installed. Missing scheduling references, daemon
policies, delegation, UID mapping, storage and rollback facts still block the
complete host-bound proposal. The v4 `unmeasured_capacity` source policy remains
unchanged, awaiting matching acceptance and review; historical validators remain
in force. No VPS change, epoch, purchase, notification or public activation is
part of this development work.
