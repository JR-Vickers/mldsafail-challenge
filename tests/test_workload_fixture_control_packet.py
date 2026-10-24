import json
import tempfile
from pathlib import Path
import pytest
from deploy.workload_fixture_control_packet import prepare,validate,SCHEMA
from deploy.workload_installation import identity
from deploy.workload_release import canonical,digest
from deploy.workload_v3 import bootstrap,sha
from deploy.workload_v3_fixture import inspection,installed
from deploy.workload_units import render_v3 as render
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.fixture
def tmp_path():
    # Production unit/socket contracts intentionally reject paths >=108 bytes.
    with tempfile.TemporaryDirectory(prefix='wcp-',dir=Path('/tmp').resolve()) as root:
        yield Path(root)


@pytest.fixture(autouse=True)
def separate_contract_validators(monkeypatch):
    # These unit tests exercise reference/namespace/selection binding. Full v3
    # release and installed-inspection contracts have their own regression suite.
    import deploy.workload_fixture_control_packet as module
    monkeypatch.setattr(module,'validate_proposal',lambda value:value)
    monkeypatch.setattr(module,'installed',lambda value,proposal,**kwargs:value)


def packet(tmp_path):
    root=tmp_path/'fixture';root.mkdir(mode=0o700);(root/'artifacts').mkdir(mode=0o700)
    source=json.loads(json.dumps(inspection()).replace('/srv/v3',str(root)));source['origin']='synthetic'
    for name,data in render(source['installation']).items():
        source['manifest']['files']['generated/'+name].update(sha256=digest(data.encode()),bytes=len(data.encode()))
    source['rollback']['manifest_sha256']=sha(source['rollback']['manifest'])
    proposal=bootstrap(source,now=1100)
    proposal['identities']['origin']='local_linux'
    manifest=dict(schema='mldsafail.installation-fixture.v1',fixture_only=True,execution_authority=False,
        vps_authority=False,generation='a'*32,root=identity(root),
        final_paths={name:str(root/name) for name in ('release','previous','frozen','output','gate','proposal.json')})
    def write(name,value):
        path=root/name;path.write_bytes(canonical(value));path.chmod(0o600);return path
    manifest_path=write('manifest.json',manifest);proposal_path=write('proposal.json',proposal)
    wrapper=dict(schema='mldsafail.installation-fixture.v1',fixture_only=True,generation='a'*32,
        manifest_sha256=digest(canonical(manifest)),runtime_suitability_verified=True,execution_authority=False,
        resources=dict(installed=installed(proposal)))
    observation=write('artifacts/inspection.json',wrapper)
    return prepare(manifest_path,proposal_path,observation,control='durable_launch_intent',scenario='lost_create_ack',
        packet_path=root/'artifacts/packet.json',output=root/'artifacts'/('case-'+'b'*32+'.json'),now=1100)


def test_preparation_binds_existing_fixture_without_granting_authority(tmp_path):
    result=packet(tmp_path)
    assert result['schema']==SCHEMA and result['execution_authority'] is False
    assert sum(result['envelope_seconds'].values())==180
    assert validate(result,now=1100)==result


@pytest.mark.parametrize('field',['fixture','proposal','inspection'])
def test_changed_references_fail(tmp_path,field):
    value=packet(tmp_path);path=Path(value[field]['path']);path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(WorkloadBlocked,match='reference_changed'):validate(value,now=1100)


@pytest.mark.parametrize('change',[
    lambda value:value.update(execution_authority=True),
    lambda value:value.update(output='/tmp/case-'+'b'*32+'.json'),
    lambda value:value.update(control='arbitrary',scenario='command'),
    lambda value:value['envelope_seconds'].update(case=91),
    lambda value:value.update(case_command=['/bin/true']),
])
def test_scope_and_deadline_cannot_expand(tmp_path,change):
    value=packet(tmp_path);change(value)
    with pytest.raises(WorkloadBlocked):validate(value,now=1100)


def execution_context(tmp_path,monkeypatch,*,authorized=True):
    value=packet(tmp_path);path=Path(value['packet_path']);path.write_bytes(canonical(value));path.chmod(0o600)
    import scripts.workload_installation_fixture as module
    import scripts.rehearse_workload_installation_fixture as review
    calls=[]
    class Context:
        def __init__(self,root):
            self.root=root;self.binding=value['fixture']['sha256']
            self.manifest=json.loads(Path(value['fixture']['path']).read_bytes())
        def require_target(self):
            if not authorized:raise WorkloadBlocked('fixture_root_owned_marker_required')
        def proposal(self):
            raw=Path(value['proposal']['path']).read_bytes();return raw,json.loads(raw)
        def deadline(self):return 180
        def control(self,control,scenario):
            calls.append((control,scenario))
            retained=dict(verified=True,database='fixture')
            return dict(fixture_only=True,generation=self.manifest['generation'],control=control,scenario=scenario,
                origin='local_linux',installed_native_eligible=False,paused=True,failure=None,
                cleanup=dict(remaining=[]),retained_before=retained,retained_after=retained,
                fixture_scope_termination=dict(state='empty',identity=dict(inode=5),events=dict(populated=0)),
                observations=dict(create_calls=1,replay_create_calls=0))
    monkeypatch.setattr(module,'Fixture',Context)
    monkeypatch.setattr(review,'component_review',lambda fixture:{})
    return value,path,calls,Context


def test_execution_needs_existing_fixture_authority_before_intent(tmp_path,monkeypatch):
    from deploy.workload_fixture_control_packet import execute
    value,path,calls,_=execution_context(tmp_path,monkeypatch,authorized=False)
    with pytest.raises(WorkloadBlocked,match='root_owned_marker'):
        execute(path,value['control'],value['scenario'],value['output'])
    assert not Path(value['output']).exists() and not calls


def test_exact_fixture_packet_executes_once_without_native_promotion(tmp_path,monkeypatch):
    from deploy.workload_fixture_control_packet import execute
    value,path,calls,_=execution_context(tmp_path,monkeypatch)
    receipt=execute(path,value['control'],value['scenario'],value['output'])
    assert receipt['assertions']['fixture_scenario_passed']
    assert not receipt['assertions']['full_scenario_passed'] and not receipt['installed_native_eligible']
    with pytest.raises(FileExistsError):execute(path,value['control'],value['scenario'],value['output'])
    assert len(calls)==1


@pytest.mark.parametrize('field',['observations','cleanup','fixture_scope_termination','retained_after'])
def test_partial_or_unverified_result_never_publishes_success(tmp_path,monkeypatch,field):
    from deploy.workload_fixture_control_packet import execute
    value,path,calls,context=execution_context(tmp_path,monkeypatch)
    original=context.control
    def broken(self,*args):
        receipt=original(self,*args);receipt[field]={};return receipt
    monkeypatch.setattr(context,'control',broken)
    with pytest.raises(WorkloadBlocked):execute(path,value['control'],value['scenario'],value['output'])
    assert Path(value['output']).exists()
    assert not Path(value['output']+'.result.json').exists()
