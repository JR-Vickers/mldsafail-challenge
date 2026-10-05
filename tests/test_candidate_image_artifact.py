import json
from types import SimpleNamespace
import pytest
from candidate_runtime import image_artifact


def test_private_image_requires_exact_inert_rootless_configuration(monkeypatch):
    proof=dict(schema='mldsafail.private-candidate-image-build.v1',passed=True,native_executed=True,candidate_only=True,
        production_adopted=False,default_changed=False,source_commit='a'*40,image='sha256:'+'b'*64,context_sha256='c'*64)
    monkeypatch.setattr(image_artifact.owned_daemon,'read_private_json',lambda *args,**kwargs:proof)
    image=dict(Id=proof['image'],Architecture='amd64',Config=dict(User='0:0',Entrypoint=['/app/.venv/bin/python','-m','candidate_runtime'],Labels={'org.mldsafail.candidate':'private-unapproved','org.mldsafail.protocol':'0.6.0','org.mldsafail.default':'0.5.0'}))
    journal=SimpleNamespace(command=lambda *args,**kwargs:SimpleNamespace(stdout=json.dumps([image])))
    assert image_artifact.require_image(journal,'private',expected_source='a'*40,loaded_images=[proof['image']])==proof
    image['Config']['User']='10001:10001'
    with pytest.raises(ValueError,match='Rootless UID0'):image_artifact.require_image(journal,'private',expected_source='a'*40,loaded_images=[proof['image']])
