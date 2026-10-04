import hashlib
from pathlib import Path
import pytest
from scripts.native_baseline_acceptance import build_context


def test_frozen_build_context_is_minimal_and_preserves_scientific_bytes(tmp_path):
    from mldsafail.benchmark_v050 import execution
    wheels=tmp_path/'input';wheels.mkdir();wheel=wheels/'fixture.whl';wheel.write_bytes(b'public dependency fixture')
    checksum={wheel.name:hashlib.sha256(wheel.read_bytes()).hexdigest()}
    context=tmp_path/'context';files=build_context(context,wheels,checksum,'sha256:'+'a'*64)
    source=Path(execution.__file__).parent
    assert set(path.name for path in (context/'mldsafail/benchmark_v050').iterdir())==set(execution.WORKER_FILES)
    for name in execution.WORKER_FILES:assert (context/'mldsafail/benchmark_v050'/name).read_bytes()==(source/name).read_bytes()
    assert not any('generator' in name or 'evidence' in name or '.venv' in name for name in files)
    assert (context/'Dockerfile').read_text().split('\n',1)[1]==(source/'Dockerfile').read_text().split('\n',1)[1]


def test_changed_dependency_inventory_is_rejected(tmp_path):
    wheels=tmp_path/'input';wheels.mkdir();(wheels/'unexpected.whl').write_bytes(b'changed')
    with pytest.raises(ValueError,match='offline wheel inventory'):
        build_context(tmp_path/'context',wheels,{'expected.whl':'b'*64},'sha256:'+'a'*64)
