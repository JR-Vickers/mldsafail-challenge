import hashlib
from pathlib import Path
import pytest
from mldsafail.benchmark_v060 import build


def inventory(monkeypatch,tmp_path):
    directory=tmp_path/'approved';directory.mkdir(mode=0o700)
    pins={};hashes={}
    for package,version in [('cysignals','1.12.5'),('fpylll','0.6.4')]:
        name=f'{package}-{version}-cp312-cp312-manylinux2014_x86_64.whl'
        content=('approved fixture '+package).encode()
        (directory/name).write_bytes(content)
        digest=hashlib.sha256(content).hexdigest();pins[package]=(version,digest);hashes[name]=digest
    monkeypatch.setattr(build,'native_wheel_pins',lambda:pins)
    return directory,hashes


def test_identical_offline_inventory_binds_both_contexts(monkeypatch,tmp_path):
    directory,hashes=inventory(monkeypatch,tmp_path)
    options=dict(wheel_directory=directory,wheel_inventory=hashes,command=lambda argv:b'a'*40 if argv[-1]=='HEAD' else b'')
    first=build.prepare_context(tmp_path/'build-context',**options)
    second=build.prepare_context(tmp_path/'acceptance-context',**options)
    assert first['source_sha256']==second['source_sha256']
    assert all(first['files']['wheels/'+name]==digest for name,digest in hashes.items())
    empty=build.prepare_context(tmp_path/'online-context',command=options['command'])
    assert empty['source_sha256']!=first['source_sha256']


@pytest.mark.parametrize('damage',['missing','extra','tampered','symlink','wrong_hash','wrong_version','fifo'])
def test_unapproved_wheels_fail_before_context_creation(monkeypatch,tmp_path,damage):
    directory,hashes=inventory(monkeypatch,tmp_path);name=next(iter(hashes));path=directory/name
    if damage=='missing':path.unlink()
    if damage=='extra':(directory/'extra.whl').write_bytes(b'extra')
    if damage=='tampered':path.write_bytes(b'new PyPI bytes')
    if damage=='symlink':path.unlink();path.symlink_to(tmp_path/'target')
    if damage=='wrong_hash':hashes[name]='f'*64
    if damage=='wrong_version':new=name.replace('1.12.5','1.12.6');path.rename(directory/new);hashes[new]=hashes.pop(name)
    if damage=='fifo':
        import os
        path.unlink();os.mkfifo(path)
    with pytest.raises((ValueError,OSError)):build.prepare_context(tmp_path/'context',wheel_directory=directory,wheel_inventory=hashes)
    assert not (tmp_path/'context').exists()


def test_actual_frozen_dependency_hashes_are_unchanged():
    pins=build.frozen_wheel_pins()
    assert pins['cysignals']==('1.12.5','9c8011f72efc59fda3cf72096e7cdfc00f415629252c161c29eb721427a666a8')
    assert pins['fpylll']==('0.6.4','ed5b1ddbab1605b8c8ea4797609a74655244820ab01273e12bafa371f3e9df96')


def test_proposed_amd64_lock_is_separate_and_matches_approved_native_lock():
    import hashlib
    lock=Path(build.__file__).parent/'requirements.amd64.lock'
    assert hashlib.sha256(lock.read_bytes()).hexdigest()=='35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0'
    assert build.native_wheel_pins()=={
        'cysignals':('1.12.5','eccbcfd762de37daf4a01a0a77ef653561a153c48c2db9104916d36ebbd3cf24'),
        'fpylll':('0.6.4','05f43362f2803207a8a6dfe5bad41c64df2479cded1338490bad773ca78b5ba1')}
    assert build.native_wheel_pins()!=build.frozen_wheel_pins()


def test_private_protocol_binds_actual_retained_native_provenance(monkeypatch,tmp_path):
    from deploy import owned_daemon
    directory,hashes=inventory(monkeypatch,tmp_path)
    provenance=dict(schema='mldsafail.v060-offline-wheel-provenance.v1',source_image='sha256:6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe',architecture='linux/amd64',wheel_sha256=hashes,artifacts_sha256='0aaec49378c4b61c93fb5edf475fb619f5b7b7950406628283773ea6470eb01c')
    receipt=tmp_path/'provenance.json';owned_daemon.publish(receipt,provenance)
    protocol=dict(schema='mldsafail.v060-worker-protocol.v1',approved_wheel_directory=str(directory),approved_wheel_sha256=hashes,provenance_receipt=str(receipt))
    owned_daemon.publish(tmp_path/'v060-worker-protocol.json',protocol)
    assert build.wheel_protocol({'state_root':str(tmp_path/'fresh')})['wheel_provenance']==provenance
    for field in ('source_image','artifacts_sha256','architecture'):
        owned_daemon.publish(receipt,dict(provenance,**{field:'unrelated'}))
        with pytest.raises(ValueError):build.wheel_protocol({'state_root':str(tmp_path/'fresh')})


@pytest.mark.parametrize('entrypoint',['build','acceptance'])
def test_invalid_offline_protocol_rejects_before_driver_mutation(tmp_path,monkeypatch,entrypoint):
    import sys
    from deploy import owned_daemon
    from scripts import native_v060_worker_preparation
    from research.mlwe_v060_preparation import native_acceptance
    module=native_v060_worker_preparation if entrypoint=='build' else native_acceptance
    config=tmp_path/'config.json';owned_daemon.publish(config,dict(state_root=str(tmp_path/'new-state')))
    owned_daemon.publish(tmp_path/'v060-worker-protocol.json',dict(schema='invalid'))
    called=[]
    monkeypatch.setattr(module.native_driver,'execute',lambda *a,**kw:called.append(True))
    monkeypatch.setattr(sys,'argv',['operator','--config',str(config)])
    with pytest.raises(ValueError):module.main()
    assert called==[]
