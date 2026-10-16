import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from scripts import participant_v060_candidate as candidate


def wheel(tmp_path,version='0.5.1'):
    path=tmp_path/'mldsafail_challenge-0.5.1-py3-none-any.whl'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('mldsafail/benchmark_v060/backend.py','public candidate source')
        archive.writestr('mldsafail_challenge-0.5.1.dist-info/METADATA','Name: mldsafail-challenge\nVersion: '+version+'\n')
    return path


def test_archive_keeps_unapproved_protocol_distinct_from_package(tmp_path,monkeypatch):
    monkeypatch.setattr(candidate,'git',lambda source,*args:b'public approved source\n')
    identity={'package_version':'0.5.1','benchmark_protocol':'0.6.0','publication_approved':False}
    files,checks=candidate.public_files(tmp_path,wheel(tmp_path),identity)
    retained=json.loads(files['SOURCE.json'])
    assert retained['benchmark_protocol']=='0.6.0' and retained['package_version']=='0.5.1'
    assert retained['publication_approved'] is False
    assert len(json.loads(files['public-fixtures.json']))==6
    assert all(hashlib.sha256(files[name]).hexdigest()==checksum for name,checksum in checks.items())
    assert b'NEW_INSTALL_DIRECTORY/bin/mldsafail' in files['README.md']


def test_symlink_wheel_rejected_before_read(tmp_path):
    original=wheel(tmp_path);link=tmp_path/'link.whl';link.symlink_to(original)
    with pytest.raises(ValueError,match='regular candidate'):candidate.public_files(tmp_path,link,{})


def test_package_relabel_does_not_impersonate_protocol_version(tmp_path):
    with pytest.raises(ValueError,match='Package version'):candidate.public_files(tmp_path,wheel(tmp_path,'0.6.0'),{})


def test_archive_wheel_traversal_rejected(tmp_path):
    path=wheel(tmp_path)
    with zipfile.ZipFile(path,'a') as archive:archive.writestr('../private.env','forbidden')
    with pytest.raises(ValueError,match='Unsafe'):candidate.public_files(tmp_path,path,{})
