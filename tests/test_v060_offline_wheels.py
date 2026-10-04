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
    monkeypatch.setattr(build,'frozen_wheel_pins',lambda:pins)
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
