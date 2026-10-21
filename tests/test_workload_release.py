"""V3 offline bundle identity tests; these do not certify installed controls."""
from copy import deepcopy
from pathlib import Path

import pytest

from deploy.workload_release import freeze, verify
from mldsafail.evaluator.workload import WorkloadBlocked


def bundle(tmp_path):
    source = tmp_path/'source'; source.mkdir()
    (source/'runtime.py').write_text('print("inert")\n')
    wheel = tmp_path/'fixture-1.0-py3-none-any.whl'
    import base64
    import csv
    import hashlib
    import io
    import zipfile
    contents = {'fixture.py': b'value = 1\n',
                'fixture-1.0.dist-info/METADATA': b'Metadata-Version: 2.1\nName: fixture\nVersion: 1.0\n',
                'fixture-1.0.dist-info/WHEEL': b'Wheel-Version: 1.0\nTag: py3-none-any\n'}
    rows = [[name, 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(), str(len(data))]
            for name, data in contents.items()]
    stream = io.StringIO()
    csv.writer(stream).writerows(rows+[['fixture-1.0.dist-info/RECORD', '', '']])
    contents['fixture-1.0.dist-info/RECORD'] = stream.getvalue().encode()
    with zipfile.ZipFile(wheel, 'w') as archive:
        for name, data in contents.items(): archive.writestr(name, data)
    bindings = dict(interpreter=dict(implementation='cpython', version='3.12', platform='linux', architecture='x86_64'),
                    worker_environment=dict(image_id='sha256:'+'a'*64, trusted_fingerprint='b'*64, artifacts={}, host={}),
                    evaluator_fingerprint='c'*64, coordinator_image='sha256:'+'d'*64,
                    configurations={role: dict(path='/private/'+role+'.json', sha256='e'*64)
                                    for role in ('supervisor', 'native', 'controller')})
    destination = tmp_path/'release'
    manifest = freeze(source, destination, source_names=['runtime.py'],
                      generated_units={'fixture.service': '[Service]\n'}, wheels=[wheel], bindings=bindings)
    return source, destination, manifest


def test_complete_offline_bundle_survives_checkout_drift(tmp_path):
    source, destination, manifest = bundle(tmp_path)
    original = verify(destination, manifest)
    (source/'runtime.py').write_text('changed checkout')
    assert verify(destination, manifest) == original
    assert not list(destination.rglob('supervisor.json'))


@pytest.mark.parametrize('name', ['runtime.py', 'generated/fixture.service', 'offline/fixture-1.0-py3-none-any.whl', 'manifest.json'])
def test_content_tampering_rejected(tmp_path, name):
    _, destination, manifest = bundle(tmp_path)
    (destination/name).write_bytes(b'changed')
    with pytest.raises(WorkloadBlocked): verify(destination, manifest)


@pytest.mark.parametrize('mutation', ['extra', 'partial', 'symlink', 'hardlink', 'mode'])
def test_replaced_or_partial_bundles_rejected(tmp_path, mutation):
    _, destination, manifest = bundle(tmp_path)
    target = destination/'runtime.py'
    if mutation == 'extra': (destination/'unexpected').write_text('extra')
    elif mutation == 'partial': target.unlink()
    elif mutation == 'mode': target.chmod(0o644)
    else:
        saved = tmp_path/'saved'; target.rename(saved)
        if mutation == 'symlink': target.symlink_to(saved)
        else:
            import os
            os.link(saved, target)
    with pytest.raises(WorkloadBlocked): verify(destination, manifest)


def test_manifest_drift_rejected(tmp_path):
    _, destination, manifest = bundle(tmp_path)
    changed = deepcopy(manifest)
    changed['coordinator_image'] = 'sha256:'+'f'*64
    with pytest.raises(WorkloadBlocked): verify(destination, changed)


def test_existing_destination_never_overwritten(tmp_path):
    source, destination, manifest = bundle(tmp_path)
    with pytest.raises(WorkloadBlocked):
        freeze(source, destination, source_names=[], generated_units={}, wheels=[], bindings={})
    assert verify(destination, manifest)


def test_runtime_inclusion_is_complete_and_excludes_private_configurations():
    from deploy.workload_release import runtime_sources
    source = Path(__file__).resolve().parents[1]
    names = runtime_sources(source)
    assert 'src/mldsafail/evaluator/workload_service.py' in names
    assert 'src/mldsafail/web/static/quantus_q_logo.png' in names
    assert 'deploy/workload_wheels.py' in names
    assert 'deploy/dev.env' not in names
    assert 'deploy/production.env.example' not in names
    assert 'uv.lock' in names
    assert any(name.startswith('migrations/versions/') for name in names)


@pytest.mark.parametrize('tracked', [False, True])
def test_runtime_inventory_does_not_silently_bundle_private_data(tmp_path, tracked):
    import subprocess
    from deploy.workload_release import runtime_sources
    source = tmp_path/'checkout'; source.mkdir()
    names = ['pyproject.toml', 'uv.lock', 'README.md', 'alembic.ini', '.dockerignore',
             'config/profiles.toml', 'config/benchmark.toml',
             'compose.production.yaml', 'Dockerfile.coordinator',
             'deploy/worker-linux-amd64.requirements.txt', 'examples/mlwe/primal-lll/solver.py',
             'src/mldsafail/evaluator/workload_service.py', 'src/mldsafail/other.py', 'scripts/prepare_workload_packet.py',
             'migrations/versions/fixture.py']
    for name in names:
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture')
    subprocess.run(['git', 'init', '-q', str(source)], check=True)
    subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
    private = source/'src/mldsafail/owner.secret'; private.write_text('private fixture')
    if tracked:
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        with pytest.raises(WorkloadBlocked, match='release_unclassified_package_data'):
            runtime_sources(source)
    else:
        assert 'src/mldsafail/owner.secret' not in runtime_sources(source)
        (source/'src/mldsafail/other.py').unlink()
        with pytest.raises(WorkloadBlocked, match='release_missing_file:src/mldsafail/other.py'):
            runtime_sources(source)
