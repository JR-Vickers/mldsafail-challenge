# Failure acceptance preparation — 2026-10-01

The runner and reviewed fixtures are implemented and locally validated. **Native
failure and rollback acceptance has not run.** On 2026-10-02 the owner-published
[fixture repository](https://github.com/JR-Vickers/mldsafail-failure-fixtures) was fetched with
the credential helper disabled, and all four tracked Python files matched the
reviewed local sources byte for byte. The fixture publication gate is complete. Staging services, accounts,
tokens, epoch, evidence, and results have not been changed by this preparation.
The owner published the fixtures; no commits were pushed by the agent.

[The sanitized report](report.json) records completed local checks, frozen
image identities, and every pending native gate. [The operator guide](../../HOSTED_FAILURE_ACCEPTANCE.md)
explains publication, invocation, recovery, deadlines, and rollback.

The standalone fixture repository is `/Users/jarrett/dev/mldsafail-failure-fixtures`,
published commit `e547caffb06ced2e82f28cf1c130c8131613384d`. Keep this full SHA pinned.
It contains only the four approved Python solver files.

Frozen application source: `f17be45c9e53f7d63cae656607c50bbe967fb0d3`.
Known-good retained rollback: `b4d212da3109b7716eb41553986848e377fb5b3d`.
Immutable manifests were recorded outside the repository in
`/Users/jarrett/dev/mldsafail-releases/f17be45-failure-acceptance.json` and
`/Users/jarrett/dev/mldsafail-releases/b4d212d-rollback.json`. Local Docker tags
`mldsafail-{web,coordinator}:failure-acceptance` and
`mldsafail-{web,coordinator}:rollback-b4d212d` retain the corresponding images;
use the manifest image IDs for deployment and rollback.

Both application builds are Linux amd64. The web image's live-health smoke
passed. Packaged evaluator Python source digests match the rollback image
exactly; worker identity, dependency locks, Compose configuration hash, and
historical/MLWE trusted fingerprints match both manifests. This establishes
local compatibility, not native epoch acceptance.

Focused runner tests: 22 passed. Final `make check`: 299 passed, 8 Docker tests
skipped; the historical small score remains 3901. Docker skips are not counted
as native failure-handling acceptance.

Deployment and integrated native execution remain pending saved token/deployment
inputs. Fixture publication and content verification are complete. Automated off-host backups and overall migration
acceptance remain separate requirements. Public launch is not authorized by
this preparation or by this suite alone.
