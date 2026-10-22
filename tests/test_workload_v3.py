from copy import deepcopy
import pytest
from deploy.workload_preparation import bootstrap_commands, installed_commands
from deploy.workload_v3_fixture import inspection, installed
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.prepare_workload_packet import prepare_v3


def test_complete_preparation_and_installed_transitions_are_reachable():
    proposal=bootstrap_commands(inspection(),now=1100)
    assert proposal['commands']['install'] and proposal['commands']['rollback']
    assert not proposal['preparation_blockers'] and proposal['execution_requirements']
    assert proposal['execution_authority'] is False
    assert installed_commands(installed(proposal),proposal,now=1100)['preparation_blockers']==[]
    assert proposal['identities']['resources']['delegation']['state']=='proposed'


@pytest.mark.parametrize('mutation',[
    lambda r:r['resources']['socket'].update(inode=4),
    lambda r:r['resources']['delegation']['ancestors'][0].update(writable=False),
    lambda r:r['inventory'].update(truncations=1),
    lambda r:r['inventory'].update(unknown_owners=1),
    lambda r:r['admission'].update(memory_available=1024),
    lambda r:r['rollback'].update(installed_schema_sha256='a'*64),
    lambda r:r['recipe']['installed_files'].clear(),
    lambda r:r['uid_mapping'].update(uid_map=[[0,1000,1],[0,1001,1]]),
])
def test_incomplete_inputs_have_specific_blockers(mutation):
    data=inspection(); mutation(data)
    with pytest.raises(WorkloadBlocked): bootstrap_commands(data,now=1100)


@pytest.mark.parametrize('mutation',[
    lambda r:r['resources']['socket'].update(state='proposed'),
    lambda r:r['resources']['output'].update(mount_id=0),
    lambda r:r['resources']['activation'].update(target='/srv/unknown'),
    lambda r:r['dependency_files'].clear(),
    lambda r:r['units'].clear(),
    lambda r:r['scheduling'].update(permission_files_absent=False),
    lambda r:r.update(paused=False),
])
def test_installed_drift_and_proposed_identities_fail(mutation):
    proposal=bootstrap_commands(inspection(),now=1100); data=installed(proposal); mutation(data)
    with pytest.raises(WorkloadBlocked): installed_commands(data,proposal,now=1100)


def test_modified_commands_fail_revalidation():
    proposal=bootstrap_commands(inspection(),now=1100); data=installed(proposal)
    proposal['commands']['install'].clear()
    with pytest.raises(WorkloadBlocked): installed_commands(data,proposal,now=1100)


def test_cli_uses_v3_without_historical_permanent_blockers(tmp_path):
    import json,os,subprocess,sys,time
    record=inspection();record['captured_at']=time.time()
    source=tmp_path/'inspection.json';source.write_text(json.dumps(record))
    output=tmp_path/'packet.json';public=tmp_path/'public.json'
    subprocess.run([sys.executable,'-m','scripts.prepare_workload_packet','--inspection',str(source),
        '--output',str(output),'--public-release-output',str(public)],check=True)
    packet=json.loads(output.read_bytes())
    assert packet['schema']=='mldsafail.workload-deployment-review.v3'
    assert packet['deployment']['commands']['install'] and not packet['preparation_blockers']
    assert packet['execution_authority'] is False and packet['execution_requirements']
    text=public.read_text()
    assert '/srv/v3' not in text and 'configuration_templates' not in text


def test_full_systemd_ancestor_chain_contains_proposed_parent_without_births():
    record=inspection();proposal=bootstrap_commands(record,now=1100)
    parent=record['resources']['delegation']['ancestors'][0]
    assert parent['state']=='proposed' and 'inode' not in parent
    assert '/user@1000.service/mldsafail.slice/' in record['installation']['heavy_path']
    assert installed_commands(installed(proposal),proposal,now=1100)['preparation_blockers']==[]
    record['resources']['delegation']['ancestors'].pop()
    with pytest.raises(WorkloadBlocked,match='full_cgroup_ancestry'):bootstrap_commands(record,now=1100)


def test_configuration_births_derive_from_observed_permitted_chain():
    from deploy.workload_configuration import materialize
    from deploy.workload_release import canonical,digest
    record=inspection()
    native=canonical(dict(heavy_birth={'$birth':'delegation'},ancestors={'$ancestor_chain':'delegation'}))
    record['recipe']['configuration_templates']['native']=native.hex()
    record['manifest']['configurations']['native']['sha256']=digest(native)
    proposal=bootstrap_commands(record,now=1100)
    actual=installed(proposal)
    result=materialize(record,actual['resources'])
    import json
    parsed=json.loads(result['native'])
    assert parsed['heavy_birth']['inode']==actual['resources']['delegation']['inode']
    assert parsed['ancestors'][-1]['path']=='/sys/fs/cgroup'
    actual['resources']['delegation']['ancestors'][0]['state']='proposed'
    with pytest.raises(WorkloadBlocked):materialize(record,actual['resources'])


def test_disk_floor_includes_complete_release_allocation():
    data=inspection();data['admission']['backing_free']=5*1024**3
    with pytest.raises(WorkloadBlocked,match='admission_floor'):bootstrap_commands(data,now=1100)


@pytest.mark.parametrize('change,reason',[
    (lambda row:row.pop('control_permissions'),'control_permissions_missing'),
    (lambda row:row.update(subtree_control=['cpu','pids']),'controllers_not_enabled'),
    (lambda row:row['control_permissions']['cgroup.procs'].update(writable=False),'control_not_writable'),
])
def test_existing_ancestor_must_already_delegate_required_controllers(change,reason):
    record=inspection();change(record['resources']['delegation']['ancestors'][1])
    with pytest.raises(WorkloadBlocked,match=reason):bootstrap_commands(record,now=1100)
