import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import native_image_export as export
from deploy import owned_daemon

IMAGE='sha256:'+'a'*64


def configuration():
    return dict(schema=export.SCHEMA,source_commit='b'*40,script_sha256='c'*64,
        docker_host='unix:///run/user/1000/docker.sock',expected_architecture='amd64',images=[IMAGE],minimum_free_bytes=1)


def test_mutable_tags_and_duplicate_ids_rejected_before_native_access(tmp_path):
    for images in (['postgres:16'],[IMAGE,IMAGE],['sha256:'+'g'*64]):
        config=configuration();config['images']=images
        with pytest.raises(ValueError,match='immutable image'):export.validate(config,tmp_path)


def test_only_readonly_pinned_image_commands_allowed(tmp_path,monkeypatch):
    operation=export.Export(tmp_path,dict(clients=[]))
    monkeypatch.setattr(export.owned_client,'run',lambda *a,**kw:pytest.fail('mutation cannot reach Docker'))
    for argv in (['docker','create',IMAGE],['docker','image','rm',IMAGE],['docker','image','inspect','latest'],['docker','image','save','--output','/foreign/archive',IMAGE]):
        with pytest.raises(ValueError,match='Read-only'):operation.command(argv)


def test_actual_seal_binds_identity_hash_and_immutable_mode(tmp_path):
    partial=tmp_path/'partial';partial.write_bytes(b'actual retained bytes');partial.chmod(0o600)
    final=tmp_path/'image.tar';identity=export.file_identity(partial)
    result=export.seal(partial,identity,final)
    assert result['image_archive_sha256']==hashlib.sha256(final.read_bytes()).hexdigest()
    assert final.stat().st_mode & 0o777==0o400 and not partial.exists()
    foreign=tmp_path/'foreign';foreign.write_bytes(b'foreign');foreign.chmod(0o600)
    link=tmp_path/'link';link.symlink_to(foreign)
    with pytest.raises(OSError):export.seal(link,identity,tmp_path/'wrong')
    assert foreign.read_bytes()==b'foreign'


def test_failed_save_retains_partial_and_independently_retries_cleanup(tmp_path,monkeypatch):
    config=configuration();root=tmp_path/'output'
    monkeypatch.setattr(export,'validate',lambda *a:None)
    original=RuntimeError('native image save interrupted')
    calls=[]
    def command(self,argv,**kw):
        if argv[2]=='inspect':return SimpleNamespace(stdout=json.dumps([dict(Id=IMAGE,Architecture='amd64',RepoDigests=[],Size=1)]))
        Path(argv[4]).write_bytes(b'partial archive')
        self.data['clients'].extend([dict(id='failed'),dict(id='known')]);self.save()
        raise original
    monkeypatch.setattr(export.Export,'command',command)
    def stop(row):
        calls.append(row['id'])
        if row['id']=='failed':raise RuntimeError('first cleanup failed')
    monkeypatch.setattr(export.owned_client,'stop',stop)
    with pytest.raises(RuntimeError) as caught:export.execute(root,config,tmp_path)
    assert caught.value is original and calls==['failed','known']
    data=json.loads((root/'journal.json').read_text())
    assert data['passed'] is False and data['cleanup_complete'] is False
    assert (root/('a'*64+'.partial.tar')).read_bytes()==b'partial archive'
    monkeypatch.setattr(export.owned_client,'stop',lambda row:calls.append('retry-'+row['id']))
    assert export.run(root,cleanup_only=True)==dict(cleanup_complete=True,passed=False)
    assert calls[-1]=='retry-failed'
    assert export.run(root,cleanup_only=True)==dict(cleanup_complete=True,passed=False)


def test_final_publication_failure_preserves_negative_outcome(tmp_path,monkeypatch):
    root=tmp_path/'output';monkeypatch.setattr(export,'validate',lambda *a:None)
    def command(self,argv,**kw):
        if argv[2]=='inspect':return SimpleNamespace(stdout=json.dumps([dict(Id=IMAGE,Architecture='amd64',RepoDigests=[],Size=1)]))
        Path(argv[4]).write_bytes(b'complete archive');return SimpleNamespace(stdout=b'')
    monkeypatch.setattr(export.Export,'command',command)
    actual=export.atomic_json;failed=[]
    def publish(path,data):
        actual(path,data)
        if data.get('passed') is True and not failed:
            failed.append(True);raise OSError('directory synchronization failed')
    monkeypatch.setattr(export,'atomic_json',publish)
    with pytest.raises(OSError,match='synchronization'):export.execute(root,configuration(),tmp_path)
    result=json.loads((root/'journal.json').read_text())
    assert result['passed'] is False and result['cleanup_complete'] is True
    assert result['images'][0]['state']=='retained'


def test_cleanup_never_preserves_pass_for_corrupt_archive(tmp_path,monkeypatch):
    root=tmp_path/'output';monkeypatch.setattr(export,'validate',lambda *a:None)
    def command(self,argv,**kw):
        if argv[2]=='inspect':return SimpleNamespace(stdout=json.dumps([dict(Id=IMAGE,Architecture='amd64',RepoDigests=[],Size=1)]))
        Path(argv[4]).write_bytes(b'complete archive');return SimpleNamespace(stdout=b'')
    monkeypatch.setattr(export.Export,'command',command)
    assert export.execute(root,configuration(),tmp_path)['passed'] is True
    archive=root/('a'*64+'.tar');archive.chmod(0o600);archive.write_bytes(b'corrupt');archive.chmod(0o400)
    with pytest.raises(ValueError):export.run(root,cleanup_only=True)
    receipt=json.loads((root/'journal.json').read_text())
    assert receipt['passed'] is False and receipt['cleanup_complete'] is True


def test_successful_docker_save_atomic_replacement_binds_produced_inode(tmp_path,monkeypatch):
    root=tmp_path/'output';monkeypatch.setattr(export,'validate',lambda *a:None)
    def command(self,argv,**kw):
        if argv[2]=='inspect':return SimpleNamespace(stdout=json.dumps([dict(Id=IMAGE,Architecture='amd64',RepoDigests=[],Size=1)]))
        replacement=root/'docker-output';replacement.write_bytes(b'actual atomic Docker archive');replacement.chmod(0o600)
        os.replace(replacement,argv[4]);return SimpleNamespace(stdout=b'')
    monkeypatch.setattr(export.Export,'command',command)
    result=export.execute(root,configuration(),tmp_path)
    row=result['images'][0]
    assert result['passed'] is True and row['save_acknowledged'] is True
    assert row['file_identity']!=row['produced_file_identity']
    assert Path(row['image_archive']).stat().st_ino==row['produced_file_identity']['inode']
    assert export.run(root,cleanup_only=True)['passed'] is True
