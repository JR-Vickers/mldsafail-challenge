import hashlib
import json
import os
from types import SimpleNamespace
import pytest
from scripts import native_private_candidate_image as build


def test_context_changed_bytes_extra_files_and_fifo_are_rejected(tmp_path):
    path=tmp_path/'context';path.mkdir();wheel=path/'candidate.whl';wheel.write_bytes(b'retained')
    inventory={'candidate.whl':hashlib.sha256(b'retained').hexdigest()}
    proof={'files_sha256':inventory,'context_sha256':hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    build.verify_context(path,proof)
    wheel.write_bytes(b'changed')
    with pytest.raises(ValueError,match='inventory changed'):build.verify_context(path,proof)
    wheel.write_bytes(b'retained');extra=path/'extra';extra.write_text('unaccounted')
    with pytest.raises(ValueError,match='inventory changed'):build.verify_context(path,proof)
    extra.unlink();os.mkfifo(extra)
    with pytest.raises(ValueError,match='regular image context'):build.verify_context(path,proof)


def test_image_labels_bind_runtime_and_separately_identified_wheel():
    manifest={'runtime_source_commit':'a'*40,'wheel_source_commit':'b'*40,'wheel_sha256':'c'*64}
    row=dict(Id='sha256:'+'d'*64,Architecture='amd64',Config=dict(User='0:0',Entrypoint=['/app/.venv/bin/python','-m','candidate_runtime'],Labels={
        'org.mldsafail.candidate':'private-unapproved','org.mldsafail.protocol':'0.6.0','org.mldsafail.default':'0.5.0',
        'org.mldsafail.candidate.source_commit':manifest['runtime_source_commit'],'org.mldsafail.candidate.wheel_source_commit':manifest['wheel_source_commit'],
        'org.mldsafail.candidate.wheel_sha256':manifest['wheel_sha256']}))
    journal=SimpleNamespace(command=lambda *args,**kwargs:SimpleNamespace(stdout=json.dumps([row])))
    assert build.inspect_image(journal,row['Id'],manifest)==row
    row['Config']['Labels']['org.mldsafail.candidate.source_commit']='b'*40
    with pytest.raises(ValueError,match='source-bound'):build.inspect_image(journal,row['Id'],manifest)


def test_ambiguous_positive_image_publication_retries_negative(monkeypatch,tmp_path):
    calls=[];path=tmp_path/'artifact.json'
    def publish(target,value):
        calls.append(value);target.write_text(json.dumps(value))
        if len(calls)==1:raise OSError('post-rename directory fsync')
    monkeypatch.setattr(build.owned_daemon,'publish',publish)
    with pytest.raises(OSError):build.publish_artifact(path,{'passed':True})
    assert json.loads(path.read_text())['passed'] is False and len(calls)==2


def test_build_protocol_rejects_incomplete_and_noncommit_sources():
    with pytest.raises(ValueError):build.require_protocol({'schema':'mldsafail.private-candidate-image-protocol-build.v1'})
    protocol=dict(schema='mldsafail.private-candidate-image-protocol-build.v1',package_source='/private/package',wheel='/private/wheel',
        wheel_manifest='/private/wheel.json',base_manifest='/private/base.json',runtime_source='/private/runtime',runtime_source_commit='short',runtime_review='/private/review.json')
    with pytest.raises(ValueError,match='Full retained'):build.require_protocol(protocol)
