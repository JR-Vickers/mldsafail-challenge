from copy import deepcopy
import pytest
from candidate_runtime import worker_artifact


def artifact():
    return dict(schema='mldsafail.v060-worker-preparation.v1',passed=True,native_executed=True,
        benchmark_version='0.6.0',measurement_method='cgroup-v2-usage-usec',architecture='linux/amd64',
        image='sha256:'+'a'*64,contract_adopted=False,default_changed=False,image_archive_sha256='b'*64,
        source_context_sha256='c'*64,source_commit='d'*40,source_manifest=dict(source_commit='d'*40,source_sha256='c'*64,source_tree_clean=True))


def test_worker_source_remains_separate_from_app_source(monkeypatch):
    value=artifact();calls=[]
    monkeypatch.setattr(worker_artifact.owned_daemon,'read_private_json',lambda *args,**kwargs:value)
    monkeypatch.setattr(worker_artifact,'require_prerequisites',lambda path,**kwargs:calls.append(kwargs))
    result=worker_artifact.accepted_worker('/artifact','/prerequisites',expected_image=value['image'],expected_archive_sha256='b'*64,supervisor_source_sha256='e'*64,loaded_images=[value['image']])
    assert result['source_commit']=='d'*40 and calls[0]['worker_source_commit']=='d'*40


@pytest.mark.parametrize('field,value',[('passed',False),('image','sha256:'+'f'*64),('source_commit','bad'),('default_changed',True),('image_archive_sha256','f'*64),('source_manifest',{})])
def test_wrong_artifact_cannot_reuse_native_gates(monkeypatch,field,value):
    retained=artifact();retained[field]=value
    monkeypatch.setattr(worker_artifact.owned_daemon,'read_private_json',lambda *args,**kwargs:retained)
    monkeypatch.setattr(worker_artifact,'require_prerequisites',lambda *args,**kwargs:pytest.fail('unbound artifact admitted'))
    with pytest.raises(ValueError):worker_artifact.accepted_worker('/artifact','/prerequisites',expected_image='sha256:'+'a'*64,expected_archive_sha256='b'*64,supervisor_source_sha256='e'*64,loaded_images=['sha256:'+'a'*64])
