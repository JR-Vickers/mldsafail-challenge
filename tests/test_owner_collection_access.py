"""Inspect the privileged artifact without granting privileges or running inventory."""
import hashlib
import zipfile
from pathlib import Path
import pytest
from scripts.prepare_owner_collection_access import build,ROOT,COMMAND,SUDOERS


def test_artifact_is_deterministic_and_has_closed_source_inventory(tmp_path):
    source=Path(__file__).resolve().parents[1]
    first=build(source,tmp_path/'first.pyz');second=build(source,tmp_path/'second.pyz')
    assert first['sha256']==second['sha256']
    with zipfile.ZipFile(first['artifact']) as archive:
        assert set(archive.namelist())==set(first['sources'])|{'__main__.py'}
        for name,expected in first['sources'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==expected
        code=archive.read('__main__.py').decode();compile(code,'__main__.py','exec')
    assert COMMAND=='/usr/bin/python3 -I -B '+ROOT+'/collector.pyz'
    assert SUDOERS=='mldsafail ALL=(root) NOPASSWD: '+COMMAND+'\n'
    assert 'ALL=(ALL)' not in SUDOERS and '*' not in SUDOERS
    with pytest.raises(FileExistsError):build(source,tmp_path/'first.pyz')


def namespace(tmp_path):
    packet=build(Path(__file__).resolve().parents[1],tmp_path/'collector.pyz')
    with zipfile.ZipFile(packet['artifact']) as archive:code=archive.read('__main__.py')
    scope={'__name__':'fixture'};exec(compile(code,'fixture','exec'),scope)
    return scope


def test_collector_refuses_arbitrary_arguments_and_nonroot_execution(tmp_path,monkeypatch):
    scope=namespace(tmp_path)
    monkeypatch.setattr(scope['os'],'getuid',lambda:1000)
    with pytest.raises(ValueError,match='root_required'):scope['main']()


def test_raw_output_cap_preserves_preceding_evidence(tmp_path):
    import io
    scope=namespace(tmp_path);stream=io.BytesIO();bounded=scope['BoundedRaw'](stream)
    bounded.write(b'kept');bounded.bytes=32*1024**2
    with pytest.raises(ValueError,match='raw_output_bound'):bounded.write(b'overflow')
    assert stream.getvalue()==b'kept'


def test_existing_sudoers_rule_is_preserved(tmp_path):
    scope=namespace(tmp_path);path=tmp_path/'rule';path.write_bytes(b'unknown')
    scope['RULE']=path;scope['trusted']=lambda path:path
    with pytest.raises(ValueError,match='existing_sudoers_resource_preserved'):scope['install_rule']()
    assert path.read_bytes()==b'unknown'
