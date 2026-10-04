import hashlib
import io
import os
import zipfile
import pytest
from scripts import private_candidate_image_context as context


def setup(monkeypatch,tmp_path):
    monkeypatch.setattr(context.subprocess,'check_output',lambda argv,**kw:b'' if 'status' in argv else b'a'*40+b'\n')
    manifest=dict(source_commit='a'*40,benchmark_protocol='0.6.0',package_version='0.5.1',publication_approved=False)
    base=dict(source_commit=context.SOURCE,images={'web':{'id':'sha256:'+'b'*64}})
    return manifest,base


def test_fifo_wheel_rejected_without_blocking(monkeypatch,tmp_path):
    manifest,base=setup(monkeypatch,tmp_path)
    wheel=tmp_path/'candidate.whl';os.mkfifo(wheel)
    with pytest.raises(ValueError,match='regular wheel'):context.context(tmp_path/'out',source=tmp_path,wheel=wheel,wheel_manifest=manifest,base_manifest=base)
    assert not (tmp_path/'out').exists()


def test_linked_zip_member_rejected_before_context(monkeypatch,tmp_path):
    manifest,base=setup(monkeypatch,tmp_path)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        entry=zipfile.ZipInfo('mldsafail/escape');entry.external_attr=0o120777<<16;archive.writestr(entry,'/private')
    wheel=tmp_path/'candidate.whl';wheel.write_bytes(stream.getvalue());manifest['wheel_sha256']=hashlib.sha256(wheel.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='links forbidden'):context.context(tmp_path/'out',source=tmp_path,wheel=wheel,wheel_manifest=manifest,base_manifest=base)
    assert not (tmp_path/'out').exists()
