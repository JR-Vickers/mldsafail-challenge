import json
from types import SimpleNamespace
import pytest
from scripts import native_recovery_service_verification as verifier


def test_archive_loaded_image_without_repodigests_is_accepted(tmp_path,monkeypatch):
    image='sha256:'+'a'*64
    journal=SimpleNamespace(path=tmp_path/'driver.json',command=lambda *a,**kw:SimpleNamespace(stdout=json.dumps([dict(Id=image,RepoDigests=[])])))
    admitted=[]
    monkeypatch.setattr(verifier.native_recovery_acceptance,'run',lambda args:admitted.append(args.image))
    monkeypatch.setattr(verifier.owned_daemon,'read_private_json',lambda *a:dict(native_service_suite_passed=True,cleanup_complete=True))
    result=verifier.callback(journal,dict(image=image,acceptance_source_sha256='bound'),{})
    assert admitted==[image] and result['passed'] is True


def test_callback_requires_both_native_behavior_and_cleanup(tmp_path,monkeypatch):
    image='sha256:'+'a'*64
    journal=SimpleNamespace(path=tmp_path/'driver.json',command=lambda *a,**kw:SimpleNamespace(stdout=json.dumps([dict(Id=image,RepoDigests=['alpine@sha256:'+'b'*64])])))
    monkeypatch.setattr(verifier.native_recovery_acceptance,'run',lambda *a:None)
    monkeypatch.setattr(verifier.owned_daemon,'read_private_json',lambda *a:dict(native_service_suite_passed=True,cleanup_complete=False))
    with pytest.raises(RuntimeError,match='both pass'):verifier.callback(journal,dict(image=image),{})


def test_fixture_image_admission_accepts_sha_rejects_options_tags(tmp_path,monkeypatch):
    fixture=verifier.native_recovery_acceptance
    monkeypatch.setattr(fixture.sys,'platform','darwin')
    with pytest.raises(ValueError,match='Native Linux'):
        fixture.run(SimpleNamespace(output=tmp_path/'new',image='sha256:'+'a'*64,cleanup=False))
    for image in ['alpine:latest','--foreign@sha256:'+'a'*64,'sha256:'+'g'*64]:
        with pytest.raises(ValueError,match='immutable'):
            fixture.run(SimpleNamespace(output=tmp_path/'new',image=image,cleanup=False))
