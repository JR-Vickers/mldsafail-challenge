# Container reproduction record

- Date: 2026-09-06 (Asia/Kuala_Lumpur)
- Command: `research/primitive_selection/rebuild-check.sh`
- Base image: `python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db`
- First clean-build image ID: `sha256:c4c27e9048d11519b32bf01717201c666f29ad7a2d90b6e9c2e94e8927ee106d`
- Second clean-build image ID: `sha256:2e9c5d246c0a3da9a8c703bcf6e8dcf23c51852485378a4696de5f242ae5844e`
- Fixture-output SHA-256 from both images: `31b531d875d8aed905fd4206e165e3a8a4aeba4cc0e33552c37be9c05faca592`
- Normalized smoke outputs: identical
- Smoke result schemas: valid in both images

The image IDs differ because clean BuildKit invocations emit distinct build
attestations. The reproducibility assertion concerns the pinned inputs,
deterministic fixture IDs, candidate digests, verification results, and schemas;
host/timing metadata is intentionally not expected to be byte-identical.
