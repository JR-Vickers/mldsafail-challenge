import os
from pathlib import Path
import pytest
from deploy.workload_configuration import verify_private_artifacts
from deploy.workload_installation import identity
from mldsafail.evaluator.workload import WorkloadBlocked


def source(path):
    row=identity(path);row['bytes']=path.stat().st_size
    return dict(origin='local_linux',recipe=dict(private_artifacts=dict(signing_key=row)))


def test_private_key_contents_modes_and_birth_are_verified(tmp_path):
    path=tmp_path/'key';path.write_bytes(b'k'*32);path.chmod(0o600);bound=source(path)
    verify_private_artifacts(bound)
    path.write_bytes(b'x'*32)
    with pytest.raises(WorkloadBlocked,match='artifact_changed'):verify_private_artifacts(bound)
    path.write_bytes(b'k'*32);verify_private_artifacts(bound)
    other=tmp_path/'replacement';other.write_bytes(b'k'*32);other.chmod(0o600);os.replace(other,path)
    with pytest.raises(WorkloadBlocked,match='artifact_changed'):verify_private_artifacts(bound)


def test_missing_private_key_is_an_implementation_input_blocker():
    with pytest.raises(WorkloadBlocked,match='artifact_missing'):
        verify_private_artifacts(dict(origin='local_linux',recipe={}))
