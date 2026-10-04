from pathlib import Path
import os
import pytest
from deploy import owned_daemon, owned_client


def test_default_staging_unit_is_ineligible_before_any_control(monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError('No shared daemon control permitted')
    monkeypatch.setattr(owned_daemon.subprocess,'check_output',forbidden)
    with pytest.raises(RuntimeError,match='dedicated'): owned_daemon._unit('docker.service')


def test_provision_requires_fresh_private_disjoint_roots(monkeypatch,tmp_path):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    tmp_path.chmod(0o700)
    protected=tmp_path/'staging';protected.mkdir(mode=0o700)
    with pytest.raises(RuntimeError,match='overlap'):
        owned_daemon.provision(protected/'nested',unit='mldsafail-owned-daemon-test.service',protected_roots=[protected])
    receipt=owned_daemon.provision(tmp_path/'fresh',unit='mldsafail-owned-daemon-test.service',protected_roots=[protected])
    assert set(receipt['roots'])=={'root_dir','exec_root','rootless_state'}
    assert (tmp_path/'fresh/provision.json').stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):
        owned_daemon.provision(tmp_path/'fresh',unit=receipt['unit'],protected_roots=[protected])
    root=Path(receipt['roots']['root_dir']['path'])
    root.rmdir();root.mkdir(mode=0o700)
    with pytest.raises(RuntimeError,match='fresh provisioning'):
        owned_daemon._provisioning(receipt,receipt['unit'],{name:owned_daemon._private_directory(value['path']) for name,value in receipt['roots'].items()})


def fixture_manifest(tmp_path,monkeypatch):
    monkeypatch.setattr(owned_client,'boot_id',lambda:'boot')
    domains=[]
    for name in ('daemon','worker'):
        path=tmp_path/name;path.mkdir()
        for control,value in [('cgroup.events','populated 0\n'),('cgroup.kill','')]: (path/control).write_text(value)
        domains.append(owned_client.domain_identity(path))
    return dict(schema=owned_daemon.SCHEMA,epoch='a'*32,unit='mldsafail-owned-daemon-test.service',
                unit_fragment_sha256='b'*64,domain=domains[0],worker_domain=domains[1],
                leader={'pid':123},roots={})


def test_barrier_kills_entire_registered_worker_parent_and_preserves_identity_failures(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:{'ActiveState':'inactive','unit_fragment_sha256':'b'*64})
    monkeypatch.setattr(owned_client,'stop',lambda entry:None)
    result=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert result['shutdown_proven'] is True
    assert (tmp_path/'worker/cgroup.kill').read_text()=='1'
    assert (tmp_path/result['receipt_file']).exists()
    manifest['worker_domain']=dict(manifest['worker_domain'],inode=-1)
    result=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert result['shutdown_proven'] is False
    assert any(item['step']=='dedicated_worker_domain_stop' for item in result['errors'])


def test_wrong_unit_epoch_prevents_daemon_kill_but_worker_cleanup_is_independent(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    monkeypatch.setattr(owned_daemon,'_unit',lambda unit:{'ActiveState':'active','MainPID':'456',
                    'domain_path':manifest['domain']['path'],'unit_fragment_sha256':'b'*64})
    killed=[]
    monkeypatch.setattr(owned_client,'stop',lambda entry:killed.append(entry))
    receipt=owned_daemon.shutdown_barrier(manifest,evidence_directory=tmp_path,attempt_id='attempt')
    assert not receipt['shutdown_proven'] and killed==[]
    assert (tmp_path/'worker/cgroup.kill').read_text()=='1'


def test_restart_rejects_unproved_shutdown_before_any_start(tmp_path,monkeypatch):
    manifest=fixture_manifest(tmp_path,monkeypatch)
    with pytest.raises(RuntimeError,match='Positive exact'):
        owned_daemon.restart_and_refresh(manifest,{'shutdown_proven':False},manifest_path=tmp_path/'manifest',
                evidence_directory=tmp_path,attempt_id='attempt')
