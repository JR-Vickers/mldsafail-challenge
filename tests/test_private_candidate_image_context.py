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


def test_prior_runtime_is_copied_from_exact_retained_source_not_current_operator(tmp_path):
    package=tmp_path/'package';runtime=tmp_path/'prior-runtime';package.mkdir();runtime.mkdir()
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:archive.writestr('mldsafail/__init__.py','')
    wheel=tmp_path/'candidate.whl';wheel.write_bytes(stream.getvalue())
    manifest=dict(source_commit='a'*40,benchmark_protocol='0.6.0',package_version='0.5.1',publication_approved=False,
        wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
    base=dict(source_commit=context.SOURCE,images={'web':{'id':'sha256:'+'c'*64}})
    def command(argv):
        directory=argv[2]
        if 'status' in argv:return b''
        if 'rev-parse' in argv:return ('b'*40 if directory==str(runtime) else 'a'*40).encode()+b'\n'
        assert directory==str(runtime)
        return ('# exact prior runtime '+argv[-1]+'\n').encode()
    result=context.context(tmp_path/'out',source=package,wheel=wheel,wheel_manifest=manifest,base_manifest=base,
        runtime_source=runtime,runtime_source_commit='b'*40,command=command)
    assert result['runtime_source_commit']=='b'*40 and result['wheel_source_commit']=='a'*40
    assert (tmp_path/'out/candidate_runtime/config.py').read_text().startswith('# exact prior runtime HEAD:')
    assert 'org.mldsafail.candidate.source_commit='+'b'*40 in (tmp_path/'out/Dockerfile').read_text()
    with pytest.raises(ValueError,match='Exact retained'):
        context.context(tmp_path/'wrong',source=package,wheel=wheel,wheel_manifest=manifest,base_manifest=base,
            runtime_source=runtime,runtime_source_commit='d'*40,command=command)
    assert not (tmp_path/'wrong').exists()
