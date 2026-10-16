import json
from types import SimpleNamespace
import pytest
from candidate_runtime import image_artifact


def test_private_image_requires_exact_inert_rootless_configuration(monkeypatch):
    proof=dict(schema='mldsafail.private-candidate-image-build.v1',passed=True,native_executed=True,candidate_only=True,
        production_adopted=False,default_changed=False,source_commit='a'*40,image='sha256:'+'b'*64,context_sha256='c'*64)
    proof.update(outer_cleanup_required=True,owned_driver_journal='driver',owned_driver_id='d'*32,operator_source_commit='e'*40,acceptance_source_sha256='f'*64,artifact_path='private',wheel_source_commit='e'*40,wheel_sha256='0'*64)
    driver=dict(schema='mldsafail.cpu-native-driver-state.v1',id=proof['owned_driver_id'],native_acceptance_passed=True,cleanup={'cleanup_complete':True},
        config={'source_commit':proof['operator_source_commit'],'acceptance_source_sha256':proof['acceptance_source_sha256']},
        operator_acceptance={'passed':True,'source_sha256':proof['acceptance_source_sha256'],'evidence_refs':['private']})
    monkeypatch.setattr(image_artifact.owned_daemon,'read_private_json',lambda path,**kwargs:driver if path=='driver' else proof)
    image=dict(Id=proof['image'],Architecture='amd64',Config=dict(User='0:0',Entrypoint=['/app/.venv/bin/python','-m','candidate_runtime'],Labels={'org.mldsafail.candidate':'private-unapproved','org.mldsafail.protocol':'0.6.0','org.mldsafail.default':'0.5.0','org.mldsafail.candidate.source_commit':proof['source_commit'],'org.mldsafail.candidate.wheel_source_commit':proof['wheel_source_commit'],'org.mldsafail.candidate.wheel_sha256':proof['wheel_sha256']}))
    journal=SimpleNamespace(command=lambda *args,**kwargs:SimpleNamespace(stdout=json.dumps([image])))
    assert image_artifact.require_image(journal,'private',expected_source='a'*40,loaded_images=[proof['image']])==proof
    driver['cleanup']['cleanup_complete']=False
    with pytest.raises(ValueError,match='whole-owner cleanup'):image_artifact.require_image(journal,'private',expected_source='a'*40,loaded_images=[proof['image']])
    driver['cleanup']['cleanup_complete']=True
    image['Config']['User']='10001:10001'
    with pytest.raises(ValueError,match='Rootless UID0'):image_artifact.require_image(journal,'private',expected_source='a'*40,loaded_images=[proof['image']])
