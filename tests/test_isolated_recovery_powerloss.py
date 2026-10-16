import hashlib
import json
import pytest
from deploy import native_recovery_powerloss as gate


def boundary():
    return {'schema':'mldsafail.synthetic-powerloss-boundary.v1','synthetic_only':True,'boot_id':'old',
            'daemon_manifest':{'unit':'owned','unit_fragment_sha256':'sha','leader':{'boot_id':'old'}}}


def test_real_changed_boot_required_before_old_unit_inspection(monkeypatch):
    monkeypatch.setattr(gate.owned_client,'boot_id',lambda:'old')
    monkeypatch.setattr(gate.owned_daemon,'_unit',lambda unit:pytest.fail('same boot cannot claim power loss'))
    with pytest.raises(ValueError,match='changed guest boot'):gate.validate_reboot(boundary())


def test_old_active_or_reconfigured_daemon_cannot_authorize_recovery(monkeypatch):
    monkeypatch.setattr(gate.owned_client,'boot_id',lambda:'new')
    for state in [{'unit_fragment_sha256':'sha','ActiveState':'active'},
                  {'unit_fragment_sha256':'different','ActiveState':'inactive'}]:
        monkeypatch.setattr(gate.owned_daemon,'_unit',lambda unit:state)
        with pytest.raises(ValueError,match='old dedicated unit'):gate.validate_reboot(boundary())


def test_synthetic_payload_contains_public_tiny_instance_only():
    row=json.loads(gate.payload())
    assert row['scope']=='synthetic-recovery-only'
    public=row['public_instance']
    assert public['profile']=='small'
    assert set(public)=={'A','dimensions','eta','instance_id','profile','ring','schema_version','study_version','t','track'}


def test_prepare_failure_attempts_cleanup_without_masking_original(tmp_path,monkeypatch):
    original=ValueError('synthetic SQL failure')
    attempted=[]
    class Journal:
        def __init__(self,*args):pass
        def cleanup(self):attempted.append('cleanup');raise RuntimeError('cleanup failed')
    monkeypatch.setattr(gate,'Journal',Journal)
    def database(*args):raise original
    monkeypatch.setattr(gate,'database',database)
    with pytest.raises(ValueError) as caught:
        gate.prepare_callback(None,{'state_root':str(tmp_path/'pre-driver')},{'id':'owned'})
    assert caught.value is original and attempted==['cleanup']
    assert original.__notes__==['Independent preparation cleanup failed: RuntimeError']


def test_vm_inherited_extra_writable_drive_is_rejected_before_provision():
    from pathlib import Path
    from deploy.qemu_isolated_recovery_powerloss import isolated_argv
    with pytest.raises(ValueError,match='allowlist'):
        isolated_argv(Path('/base'),Path('/new'),['qemu-system-aarch64','-drive','file=/foreign'],2222)


def test_vm_base_open_file_or_failed_probe_refuses_boot(monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from deploy import qemu_isolated_recovery_powerloss as host
    for result in (SimpleNamespace(returncode=0,stdout=b'123',stderr=b''),SimpleNamespace(returncode=2,stdout=b'',stderr=b''),SimpleNamespace(returncode=1,stdout=b'',stderr=b'inspection failure')):
        monkeypatch.setattr(host.subprocess,'run',lambda *args,**kwargs:result)
        with pytest.raises(RuntimeError,match='quiescence unproved'):host.require_base_quiescent(Path('/base'))


def test_disposable_guest_inherited_groupwrite_is_secured_before_driver(tmp_path):
    import os
    home=tmp_path/'home';home.mkdir(mode=0o775)
    (home/'.config').mkdir(mode=0o775)
    os.chmod(home,0o775);os.chmod(home/'.config',0o775)
    gate.secure_guest_configuration(home)
    assert all(path.stat().st_mode & 0o777==0o700 for path in (home,home/'.config',home/'.config/systemd',home/'.config/systemd/user'))


def test_disposable_guest_config_symlink_cannot_chmod_foreign_target(tmp_path):
    home=tmp_path/'home';home.mkdir()
    target=tmp_path/'target';target.mkdir(mode=0o755)
    before=target.stat().st_mode
    (home/'.config').symlink_to(target,target_is_directory=True)
    with pytest.raises(OSError):gate.secure_guest_configuration(home)
    assert target.stat().st_mode==before


def test_retained_bootstrap_archive_checksum_binds_offline_image(tmp_path):
    from deploy import owned_daemon
    from deploy.qemu_isolated_recovery_powerloss import verified_bootstrap_artifact
    image=tmp_path/'image.tar';image.write_bytes(b'retained official synthetic image');image.chmod(0o600)
    manifest=tmp_path/'manifest.json'
    value=dict(schema='mldsafail.synthetic-image-cache.v1',image='sha256:'+'a'*64,image_archive=str(image),image_archive_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),provenance='retained native official image receipt')
    owned_daemon.publish(manifest,value)
    assert verified_bootstrap_artifact(manifest)==value
    image.write_bytes(b'corruption')
    with pytest.raises(ValueError,match='checksum mismatch'):verified_bootstrap_artifact(manifest)


def test_evidence_export_retains_operator_proofs_but_not_opaque_runtime_graph(tmp_path):
    from deploy.qemu_isolated_recovery_powerloss import evidence_tar_command
    command=evidence_tar_command()
    for name in ('root_dir','exec_root','rootless_state','docker.sock','dockerd.pid'):
        assert "--exclude='powerloss-evidence/*-driver/daemon/"+name+"'" in command
    assert 'powerloss-evidence powerloss-artifacts' in command
    assert 'daemon-provision' not in command and 'driver.json' not in command


def test_actual_tar_export_omits_unreadable_graph_and_preserves_proof_files(tmp_path):
    import io,shlex,subprocess,tarfile
    from deploy.qemu_isolated_recovery_powerloss import evidence_tar_command
    graph=tmp_path/'powerloss-evidence/prepare-driver/daemon/root_dir/work'
    graph.mkdir(parents=True)
    blocked=graph/'opaque';blocked.write_bytes(b'opaque graph');blocked.chmod(0)
    proof=tmp_path/'powerloss-evidence/prepare-driver/driver.json';proof.write_text('{}')
    dump=tmp_path/'powerloss-evidence/immutable-synthetic.dump';dump.write_bytes(b'logical')
    artifacts=tmp_path/'powerloss-artifacts';artifacts.mkdir();(artifacts/'postgres.tar').write_bytes(b'pinned')
    argv=shlex.split(evidence_tar_command());argv[argv.index('-C')+1]=str(tmp_path)
    try:
        result=subprocess.run(argv,capture_output=True,check=True,timeout=10)
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:names=archive.getnames()
        assert not any('/root_dir' in name for name in names)
        assert 'powerloss-evidence/prepare-driver/driver.json' in names
        assert 'powerloss-evidence/immutable-synthetic.dump' in names
        assert 'powerloss-artifacts/postgres.tar' in names
    finally:blocked.chmod(0o600)
