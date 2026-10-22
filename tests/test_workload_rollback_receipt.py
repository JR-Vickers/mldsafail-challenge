import pytest

from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked


def test_hashed_receipt_alone_does_not_prove_rollback_compatibility(tmp_path,monkeypatch):
    import deploy.workload_installed as installed
    receipt=tmp_path/'compatibility.json';receipt.write_bytes(canonical({'verified':True}))
    source=dict(rollback=dict(compatibility_receipt_path=str(receipt),
        compatibility_receipt_sha256=digest(receipt.read_bytes())))
    expected=dict(schema='mldsafail.workload-rollback-compatibility.v3',manifest_sha256='a'*64,
                  compatibility='unchanged_schema_and_inhibited_release_selection',coordinator_start_authorized=False)
    monkeypatch.setattr(installed,'observe_rollback',lambda value:expected)
    with pytest.raises(WorkloadBlocked,match='compatibility_binding_changed'):installed.verify_rollback(source)
    receipt.write_bytes(canonical(expected));source['rollback']['compatibility_receipt_sha256']=digest(receipt.read_bytes())
    assert installed.verify_rollback(source)
    changed=dict(expected,manifest_sha256='b'*64);receipt.write_bytes(canonical(changed))
    source['rollback']['compatibility_receipt_sha256']=digest(receipt.read_bytes())
    with pytest.raises(WorkloadBlocked,match='compatibility_binding_changed'):installed.verify_rollback(source)


@pytest.mark.parametrize('name',['native','supervisor','controller','signing.key'])
def test_rollback_private_permissions_are_verified_even_when_bytes_match(tmp_path,name):
    from deploy.workload_installed import rollback_private_files
    key=tmp_path/'signing.key';key.write_bytes(b'x'*32);key.chmod(0o600)
    paths={};hashes={}
    for role in ('native','supervisor','controller'):
        path=tmp_path/role;data=canonical(dict(signing_key=str(key)))
        path.write_bytes(data);path.chmod(0o600)
        paths[role]=dict(path=str(path));hashes[role]=digest(data)
    rollback=dict(manifest=dict(configurations=paths,private_artifacts=dict(signing_key=dict(sha256=digest(key.read_bytes()),bytes=32))),configuration_hashes=hashes)
    before=rollback_private_files(rollback)
    (tmp_path/name).chmod(0o644)
    with pytest.raises(WorkloadBlocked,match='rollback_'):rollback_private_files(rollback)
    (tmp_path/name).chmod(0o600)
    assert rollback_private_files(rollback)==before
