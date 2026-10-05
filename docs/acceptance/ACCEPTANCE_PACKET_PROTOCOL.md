# Sanitized acceptance snapshots

The packet tool consumes the authoritative launch ledger; it never updates that
ledger, controls services, provisions accounts, sends messages or grants approval.
Run it from the retained source containing the same `scripts/launch_ledger.py`
validator as the selected repository:

```sh
python -m scripts.launch_acceptance_packet \
  docs/acceptance/public-launch/report.json --root . \
  --output /protected/new-draft-snapshot.json
```

The output path must be new. Previous and partial snapshots are preserved. The
snapshot deterministically binds the ledger's exact bytes, full repository commit,
generator and validator SHA256s. No generation timestamp is added. A draft can be
produced while owner inputs or native gates remain incomplete. It is an operator
snapshot, not a native test or a final acceptance pass.

Completed gates retain sanitized evidence references and source/artifact identities.
`native_attested` requires an explicit positive `native_executed` flag in the
referenced JSON scope. An environment named "native" never establishes execution.
Source/local evidence is classified separately; evidence without enough metadata
remains `unclassified`. All attempt history is retained, with failed/partial
attempts additionally indexed. Raw hidden epoch IDs, private filesystem paths,
network addresses and endpoint URLs are omitted or redacted. Credentials rejected
by the ledger validator cause generation to fail before a snapshot is emitted.
Raw private evidence must stay in protected operator storage.

Every external blocker includes the exact sanitized missing input, supplying owner,
requested action and affected descendants. An external decision does not hide
unfinished implementation prerequisites. Pending or waiting leaves with no
unfinished prerequisites still count as executable work, even if their `ready`
label is stale. Running and failed tasks must be reconciled. There is no implicit
exception for the packet task itself; record its declared prerequisites and status
accurately in the ledger.

`agent_work_complete` means no internal unfinished dependency roots remain. It may
be true while external blockers remain. `final_ready` additionally requires an
available original checklist with exactly 78 unique numbered mappings, a source
tree observed clean before writing the snapshot, and a native handoff-state record.
The packet always leaves `public_launch_approved` and
`production_activation_attested` false: owner approval and production activation
cannot be inferred from completed engineering, local tests, a draft or readiness.

For a final readiness check, add `--final --state-evidence docs/PATH.json`.
Incomplete final readiness emits a rejected snapshot and exits with status 2.
The state document must be a sanitized JSON record with schema
`mldsafail.launch-handoff-state.v1`, positive `native_executed`, `passed`,
`maintenance_reconciled` and `live_state_verified` fields, and nonempty
`evidence_refs` resolving to positive, explicitly native-attested JSON evidence
in the referenced scope. A positive source-review pointer or a contradictory
`native_executed: false` ancestor cannot support this handoff attestation. Those fields must come from
actual source-bound operator checks, including intended live service states and
absence of unaccounted owned processes, attempts and incomplete cleanup. Source
fixtures or configuration parsing never provide these attestations. The packet
retains only the state reference and byte SHA256, not private telemetry.

Freeze ledger and evidence while generating the final snapshot. Retain its source
identity and commit the sanitized artifact at a validated checkpoint. Source
cleanliness is observed before the output file is created; a newly created packet
must still be committed or moved into protected retention before final handoff.
A subsequent ledger or source change requires a new snapshot. Keep historical
failed and rejected snapshots. Never push, publish or activate based on this tool.
