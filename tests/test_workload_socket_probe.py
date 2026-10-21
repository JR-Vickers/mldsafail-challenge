import os
import pytest
from deploy.workload_socket_probe import peer_uids
from mldsafail.evaluator.workload import WorkloadBlocked


def test_wrong_peer_uses_existing_mapping():
    assert peer_uids(dict(coordinator_container_uid=0,uid_map=[[0,os.getuid(),1],[100,100000,10]]))==(0,100)


def test_single_owner_mapping_is_an_explicit_blocker():
    with pytest.raises(WorkloadBlocked,match='distinct_mapped_uid'):
        peer_uids(dict(coordinator_container_uid=0,uid_map=[[0,os.getuid(),1]]))


def test_owner_mapping_mismatch_precedes_probe_mutations():
    with pytest.raises(WorkloadBlocked,match='owner_mapping'):
        peer_uids(dict(coordinator_container_uid=0,uid_map=[[0,os.getuid()+1,1]]))
