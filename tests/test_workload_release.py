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
    wheel.write_bytes(b'offline fixture; never installed')
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
