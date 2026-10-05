# Private proposed 0.6.0 native participant installation

This source tooling prepares a private Linux amd64 installation gate. It does
not establish native acceptance by itself, adopt the contract, publish the
archive, activate a default, or reproduce a private accounting/reference run.
The latter remains dependent on the unchanged native accounting fault and
30-pair performance gates. Installation is independently executable.

Run `scripts/native_participant_v060_install.py --config PRIVATE_CONFIG` through
the reviewed same-process owned native driver. Bind that exact callback file
SHA256 and committed operator source in the driver configuration/review packet.
Use the existing owned-driver resource/cleanup protocol; no VPS staging services
or existing participant HOME are used. Private native host evidence must include
both the install artifact and its matching successfully completed driver journal
with whole-resource cleanup complete. A positive install artifact alone is
insufficient. Preserve failed attempts and retained inputs; cleanup never removes
those historical files.

Beside the driver journal, provide a private `participant-install-protocol.json`:

```json
{
  "schema": "mldsafail.participant-native-install-protocol.v1",
  "participant_source": "/private/retained-candidate-source",
  "participant_source_commit": "b0421cdcda842e4dd6c4b43fafd90541a7ae0cd2",
  "manifest": "/private/candidate/manifest.json",
  "review": "/private/candidate/independent-review.json",
  "archive": "/private/candidate/participant-v060-unapproved-candidate.tar.gz",
  "wheel": "/private/candidate/mldsafail_challenge-0.5.1-py3-none-any.whl",
  "python": "/private/installed-linux-python/bin/python3",
  "dependency_wheels": [
    {"path": "/private/dependencies/EXACT_DEPENDENCY.whl", "sha256": "EXACT_SHA256"}
  ]
}
```

Paths above are illustrative private inputs, not infrastructure configuration.
Use every actual dependency wheel from a separately retained offline wheelhouse,
with its exact SHA256, compatible with the chosen native Python. Dependencies
are installed into a fresh venv without system-site packages; no online resolver
or package purchase is needed. Missing offline dependencies fail the install and
must be supplied as engineering prerequisites. Keep the native Python/uv runtime
identity in the matching driver evidence and retain its installation provenance.

The already independently reviewed participant archive has SHA256
`c67bf7ada203a15196a25e9bd5e1638299f08c94b954e609785933e5b77a0883`;
its wheel has SHA256
`570386753f38982f5a637280ba6218e0a930313c75ffc45ee2c7b1ad697985e7`.
Package version remains `0.5.1`; the explicitly selected proposed benchmark
protocol is `0.6.0`. Retain the exact clean b042 source tree separately on the
native host before execution. Copying the wheel/archive without that source is
insufficient; never relabel the current operator source as b042. Retain the
original manifest and `v060-candidate-c67-independent-review.json` as private
inputs with original source/wheel/archive bindings. No rebuild is required.

Admission verifies sealed owned bounded regular archive/wheel/dependency files,
review bindings, exact archive member inventory and checksums, and exact clean
participant source. The driver executes an offline fresh-home install, installed
CLI help, explicit candidate clone and byte-identical public starter, historical
0.4 clone/run (score 3901), and installed-package identity proof. The installed
interpreter runs the two repository-generated small public fixtures through the
starter and independent public verifier. This is an ordinary public correctness
smoke, never an official score or accounting acceptance.

A disposable loopback server advertises only 0.5.0. The actual installed CLI
must reject explicit 0.6.0 before any POST or submission intent. It uses a private
dummy token and null keyring; no owner credentials are read. The probe shuts down
and joins its server thread in all exits. All subprocesses belong to the durable
owned-driver client lifecycle; timeout/interruption requires its independent
cleanup before a passed handoff. No real submission, login, external server,
reference, epoch or Docker control is supplied to participant code.

Commit only sanitized native outcomes, hashes and protected evidence references.
The private install directory and driver journal remain protected on the native
host. Full native reproduction and public release approval remain false in the
install proof regardless of this gate's result.
