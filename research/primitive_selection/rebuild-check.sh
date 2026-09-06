#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/primitive-study-rebuild.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM
revision=$(git -C "$repo_dir" rev-parse HEAD)

for suffix in a b; do
  image="mldsafail-primitive-study:rebuild-$suffix"
  docker build --no-cache --tag "$image" \
    --build-arg "RESEARCH_GIT_REVISION=$revision" \
    --file "$repo_dir/research/primitive_selection/Dockerfile" "$repo_dir"
  digest=$(docker image inspect --format '{{.Id}}' "$image")
  docker run --rm --cpus=1 --memory=2g \
    --env "PRIMITIVE_STUDY_IMAGE_DIGEST=$digest" \
    --volume "$tmp_dir:/outputs" \
    "$image" smoke --output "/outputs/smoke-$suffix.jsonl"
  docker run --rm --entrypoint python "$image" -c \
    'from research.primitive_selection.constants import ETAS,PROFILES; from research.primitive_selection.generator import generate_mlwe,generate_msis; print("\n".join(f"{p}:{e}:{g(p,0,e).public.instance_id}" for p in PROFILES for e in ETAS for g in (generate_mlwe,generate_msis)))' \
    > "$tmp_dir/fixtures-$suffix.txt"
done

diff -u "$tmp_dir/fixtures-a.txt" "$tmp_dir/fixtures-b.txt"
python - "$tmp_dir" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
def stable(path):
    return sorted((r["track"], r.get("source_track"), r["profile"], r["eta"], r["seed"],
                   r["solver"], r["input_digest"], r["output_digest"], r["verification_result"])
                  for r in map(json.loads, path.read_text().splitlines()))
assert stable(root / "smoke-a.jsonl") == stable(root / "smoke-b.jsonl")
print("two clean builds reproduced fixture and smoke outputs")
PY
