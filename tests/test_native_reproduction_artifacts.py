import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import native_reproduction_artifacts as artifacts

REPOSITORY=Path(artifacts.__file__).resolve().parents[1]
IMAGE='sha256:'+'a'*64

def test_context_preserves_science_and_all_original_dependencies(tmp_path,monkeypatch):
    wheel=tmp_path/'approved.whl';wheel.write_bytes(b'approved')
    monkeypatch.setattr(artifacts,'approved_wheels',lambda *args:{wheel.name:wheel})
    options=dict(wheel_directory=str(tmp_path),wheel_inventory={wheel.name:hashlib.sha256(b'approved').hexdigest()},wheel_provenance={'approved':True})
    context=tmp_path/'context'
    manifest=artifacts.study_context(context,REPOSITORY,IMAGE,options,'b'*40)
    for name,digest in artifacts.source_files(REPOSITORY).items():
        assert manifest['research/primitive_selection/'+name]==digest
    dockerfile=(context/'Dockerfile').read_text()
    assert dockerfile.startswith('FROM '+IMAGE+'\n')
    assert '--no-index --find-links=/wheels' in dockerfile
    assert 'RUN pip install --no-cache-dir --requirement /tmp/requirements.txt' in dockerfile
    assert 'pytest==8.4.2' in (context/'research/primitive_selection/requirements.txt').read_text()
    receipt=json.loads((tmp_path/'study-context.json').read_text())
    assert receipt['scientific_source_changed'] is False
    assert receipt['native_acceptance_passed'] is False
    assert receipt['context_files_sha256']==manifest

@pytest.mark.parametrize('rows',[None,[],[None],[{'Id':IMAGE,'Architecture':'arm64'}],[{'Id':'mutable','Architecture':'amd64'}]])
def test_inspection_rejects_nonimmutable_or_malformed_native_identity(rows):
    journal=SimpleNamespace(command=lambda *args,**kwargs:SimpleNamespace(stdout=json.dumps(rows)))
    with pytest.raises(RuntimeError):artifacts.inspect_image(journal,IMAGE)

def test_export_seals_exact_bytes_and_uses_owned_bounded_command(tmp_path):
    calls=[]
    def command(argv,**kwargs):
        calls.append((argv,kwargs));Path(argv[4]).write_bytes(b'archive')
    path=tmp_path/'image.tar'
    result=artifacts.export_image(SimpleNamespace(command=command),IMAGE,path)
    assert result==dict(sha256=hashlib.sha256(b'archive').hexdigest(),bytes=7)
    assert path.stat().st_mode&0o777==0o400
    assert calls[0][1]==dict(kind='read',timeout=600)
    with pytest.raises(ValueError):artifacts.export_image(SimpleNamespace(command=command),IMAGE,path)

def test_cli_rejects_missing_approved_offline_protocol_before_driver(monkeypatch,tmp_path):
    monkeypatch.setattr('sys.argv',['artifact','--config',str(tmp_path/'config.json')])
    monkeypatch.setattr(artifacts.owned_daemon,'read_private_json',lambda path:{})
    monkeypatch.setattr(artifacts,'wheel_protocol',lambda config:{})
    monkeypatch.setattr(artifacts.native_driver,'execute',lambda *args,**kwargs:pytest.fail('must not mutate host'))
    with pytest.raises(ValueError,match='offline'):artifacts.main()
