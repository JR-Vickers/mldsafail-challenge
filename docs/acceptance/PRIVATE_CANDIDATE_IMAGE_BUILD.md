# Private application artifact preparation

Run `python -m scripts.native_private_candidate_image --config PRIVATE_CONFIG`
only inside a reviewed owned operator unit. The generic driver source/review
packet binds this callback's SHA256. This builds an inert prospective application
image, not a worker, benchmark reference, epoch, publication or production default.

Beside the state root, provide protected `candidate-image-build-protocol.json`:

```json
{
  "schema": "mldsafail.private-candidate-image-protocol-build.v1",
  "package_source": "/protected/retained-package-source",
  "wheel": "/protected/participant.whl",
  "wheel_manifest": "/protected/participant-manifest.json",
  "base_manifest": "/protected/frozen-release-manifest.json",
  "runtime_source": "/protected/retained-runtime-source",
  "runtime_source_commit": "FULL_40_CHARACTER_RUNTIME_COMMIT",
  "runtime_review": "/protected/runtime-review.json"
}
```

The wheel manifest must bind its clean package source commit, SHA256,
`package_version: "0.5.1"`, `benchmark_protocol: "0.6.0"`, and
`publication_approved: false`. Runtime review must have schema
`mldsafail.private-candidate-runtime-review.v1`, that exact runtime source commit,
`source_review_passed: true` and nonempty independent `evidence_refs`.
These review claims must come from actual review, not placeholder templates.
The compatible frozen baseline manifest must identify source `6b332cd` by its
full commit and immutable web image. Load its protected retained archive through
the generic native driver before callback admission.

Package and runtime identities are separate: artifact `source_commit` names the
runtime source, while `wheel_source_commit` names the installed participant
package. To prepare a prior candidate artifact, select its actual retained clean
runtime and corresponding retained wheel/package sources. The builder reads
tracked runtime/helper blobs from that tree. It never substitutes the currently
executing operator's runtime or relabels an existing image as the prior source.
Both identities and the wheel checksum appear in image labels and the artifact.

The callback assembles a checksum-bound context, verifies it before and after an
offline native `linux/amd64` build, checks immutable image ID/configuration, and
runs a bounded network-none read-only import smoke. It exports a new image
archive, seals it read-only and binds its SHA256 and size. Ambiguous positive
artifact publication triggers a negative retry and preserves the original error.

A prospective artifact is not reusable merely because its local `passed` field
is true: `candidate_runtime.image_artifact.require_image` additionally requires
its exact owned driver nonce, operator commit and callback SHA256, completed
native acceptance and whole-owner cleanup, and the matching driver evidence
reference. It also checks the loaded immutable image's source/wheel labels.
Native application, rollback, recovery and benchmark gates remain separate.
Keep raw receipts and archives private; commit only sanitized acceptance evidence.
