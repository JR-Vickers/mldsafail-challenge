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
