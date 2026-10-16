import hashlib
from pathlib import Path

import pytest

from scripts.native_production_release import ROLLBACK, inspect_context, validate_protocol


def pair(tmp_path, name, commit):
    context = tmp_path / name
    context.mkdir()
    files = {}
    for relative in ('Dockerfile', 'Dockerfile.coordinator', 'uv.lock', 'pyproject.toml', '.dockerignore',
                     'src/mldsafail/benchmark_v050/worker.py', 'src/mldsafail/evaluator/coordinator.py', 'migrations/schema.py',
                     'deploy/worker-linux-amd64.requirements.txt'):
        path = context / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(context=str(context), manifest=dict(source_commit=commit, source_files_sha256=files))


def test_exact_new_context_and_rollback_compatibility(tmp_path):
    protocol = dict(schema='mldsafail.production-release-build.v1', benchmark_version='0.5.0',
                    pairs=dict(candidate=pair(tmp_path, 'candidate', 'a' * 40),
                               rollback=pair(tmp_path, 'rollback', ROLLBACK)))
    assert validate_protocol(protocol) == protocol['pairs']
    protocol['pairs']['rollback']['manifest']['source_commit'] = 'b' * 40
    with pytest.raises(ValueError, match='selected source'):
        validate_protocol(protocol)


@pytest.mark.parametrize('mutation', ['extra', 'changed', 'link'])
def test_context_rejects_unbound_files_or_links(tmp_path, mutation):
    value = pair(tmp_path, 'candidate', 'a' * 40)
    root = Path(value['context'])
    if mutation == 'extra':
        (root / 'untracked.py').write_text('pass')
    elif mutation == 'changed':
        (root / 'Dockerfile').write_text('changed')
    else:
        (root / 'alias').symlink_to(root / 'Dockerfile')
    with pytest.raises(ValueError):
        inspect_context(root, value['manifest'])


def test_incompatible_actual_lock_rejected(tmp_path):
    candidate = pair(tmp_path, 'candidate', 'a' * 40)
    rollback = pair(tmp_path, 'rollback', ROLLBACK)
    path = Path(rollback['context']) / 'uv.lock'
    path.write_text('different lock')
    rollback['manifest']['source_files_sha256']['uv.lock'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='lock incompatibility'):
        validate_protocol(dict(schema='mldsafail.production-release-build.v1', benchmark_version='0.5.0',
                               pairs=dict(candidate=candidate, rollback=rollback)))
