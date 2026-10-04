import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import native_v060_worker_preparation as preparation


def setup(monkeypatch,tmp_path,*,wrong_image=False,fail_export=False):
    image='sha256:'+'a'*64;calls=[]
    context=dict(source_tree_clean=True,source_commit='b'*40,source_sha256='c'*64,files={})
    monkeypatch.setattr(preparation,'prepare_context',lambda path,**kwargs:context)
    class Journal:
        path=tmp_path/'driver.json'
        def command(self,args,**kwargs):
            calls.append((args,kwargs))
            if args[1]=='build':Path(args[args.index('--iidfile')+1]).write_text(image)
            if args[1:3]==['image','inspect']:
                config=dict(Labels={'org.mldsafail.benchmark.version':'0.6.0','org.mldsafail.measurement':'cgroup-v2-usage-usec'},Entrypoint=['python','-m','mldsafail.benchmark_v060.worker'],User='65534:65534')
                return SimpleNamespace(stdout=json.dumps([dict(Id=('sha256:'+'d'*64) if wrong_image else image,Config=config)]))
            if args[1:3]==['image','save']:
                if fail_export:raise RuntimeError('export failure')
                Path(args[args.index('--output')+1]).write_bytes(b'immutable exported image')
            return SimpleNamespace(stdout='')
    config=dict(source_commit='b'*40,supervisor_source_sha256='e'*64,acceptance_source_sha256='f'*64)
    return Journal(),config,calls


def test_build_only_preparation_retains_exact_archive_without_native_gate_claim(monkeypatch,tmp_path):
    journal,config,calls=setup(monkeypatch,tmp_path)
    result=preparation.callback(journal,config,{})
    artifact=json.loads((tmp_path/'v060-worker/artifact.json').read_text())
    archive=Path(artifact['image_archive'])
    assert result['passed'] and artifact['passed']
    assert artifact['image_archive_sha256']==hashlib.sha256(archive.read_bytes()).hexdigest()
    assert archive.stat().st_mode&0o777==0o400
    assert not any(artifact[key] for key in ('contract_adopted','epoch_created','reference_created','native_faults_passed','native_pairs_passed','default_changed'))
    assert artifact['outer_cleanup_required'] is True
    assert [row[0][1] for row in calls]==['build','image','image']
    assert all(row[1]['timeout']<=600 for row in calls)


@pytest.mark.parametrize('failure',['wrong_image','fail_export'])
def test_inspection_or_export_failure_never_publishes_positive_artifact(monkeypatch,tmp_path,failure):
    journal,config,_=setup(monkeypatch,tmp_path,**{failure:True})
    with pytest.raises(RuntimeError):preparation.callback(journal,config,{})
    assert not (tmp_path/'v060-worker/artifact.json').exists()


def test_archive_sealing_refuses_symlink_and_preserves_target(tmp_path):
    target=tmp_path/'target';target.write_bytes(b'image');target.chmod(0o600)
    alias=tmp_path/'alias';alias.symlink_to(target)
    with pytest.raises(OSError):preparation.retain_archive(alias)
    assert target.stat().st_mode&0o777==0o600


def test_archive_mode_metadata_is_synced_after_sealing(tmp_path,monkeypatch):
    import os,stat
    archive=tmp_path/'image.tar';archive.write_bytes(b'exported image')
    actual=os.fsync;file_modes=[]
    def fsync(descriptor):
        info=os.fstat(descriptor)
        if stat.S_ISREG(info.st_mode):file_modes.append(info.st_mode&0o777)
        actual(descriptor)
    monkeypatch.setattr(preparation.os,'fsync',fsync)
    preparation.retain_archive(archive)
    assert file_modes[-1]==0o400
