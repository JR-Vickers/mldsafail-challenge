from copy import deepcopy
import pytest
from deploy.workload_acceptance_packet import reference,validate,execute
from deploy.workload_release import canonical
from deploy.workload_v3 import bootstrap
from deploy.workload_v3_fixture import inspection,installed
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_watchdog import protocol


def fixture(tmp_path):
    proposal=bootstrap(inspection(),now=1100)
    path=tmp_path/'proposal';path.write_bytes(canonical(proposal));path.chmod(0o600)
    observation=tmp_path/'installed';observation.write_bytes(canonical(installed(proposal)));observation.chmod(0o600)
    packet=dict(schema='mldsafail.workload-control-packet.v3',stage='installed',
                proposal=reference(path),inspection=reference(observation),protocol=protocol())
    source=proposal['identities'];plan=packet['protocol']
    plan['fixture_cgroup']=source['installation']['heavy_path']+'/acceptance'
    plan['identities']['retained_services']=source['retained_services']
    plan['identities']['installation']=dict(proposal=packet['proposal'],inspection=packet['inspection'],
        release_sha256=proposal['manifest_sha256'],hostname=source['host']['hostname'],
        uid=source['host']['uid'],boot_id=source['host']['boot_id'])
    return packet,path,observation


def test_installed_packet_uses_frozen_private_references(tmp_path):
    packet,path,_=fixture(tmp_path)
    assert validate(packet,now=1100)==packet
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(WorkloadBlocked,match='reference_changed'):validate(packet,now=1100)


@pytest.mark.parametrize('change',[
    lambda p:p['protocol'].update(origin='installed_native'),
    lambda p:p['protocol'].update(fixture_cgroup='/sys/fs/cgroup/unowned'),
    lambda p:p['protocol']['identities']['installation'].update(release_sha256='f'*64),
    lambda p:p['protocol']['identities'].update(retained_services={}),
])
def test_packet_cannot_relabel_or_substitute_installation(tmp_path,change):
    packet,_,_=fixture(tmp_path);change(packet)
    with pytest.raises(WorkloadBlocked):validate(packet,now=1100)


def test_expired_installed_observation_is_not_execution_evidence(tmp_path):
    packet,_,_=fixture(tmp_path)
    with pytest.raises(WorkloadBlocked,match='expired'):validate(packet,now=2000)


def test_bootstrap_is_reviewable_but_not_executable(tmp_path):
    packet,_,_=fixture(tmp_path);packet.update(stage='bootstrap',inspection=None)
    packet['protocol']['identities']['installation']['inspection']=None
    assert validate(packet,now=1100)
    path=tmp_path/'packet';path.write_bytes(canonical(packet));path.chmod(0o600)
    with pytest.raises(WorkloadBlocked,match='installed_packet_required'):execute(path,tmp_path/'run')
    assert not (tmp_path/'run').exists()
