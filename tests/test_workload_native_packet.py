from pathlib import Path
import pytest
from deploy.workload_release import canonical
from deploy.workload_v3 import bootstrap
from deploy.workload_v3_fixture import inspection,installed
from deploy.workload_native_packet import prepare,FACTS
from mldsafail.evaluator.workload import WorkloadBlocked


def inputs(tmp_path,monkeypatch):
    import deploy.workload_native_packet as module
    proposal=bootstrap(inspection(),now=1100);proposal['identities']['origin']='host_observation'
    # Compiler binding tests; full v3 release/installed validators have separate suites.
    monkeypatch.setattr(module,'validate_proposal',lambda value:value)
    monkeypatch.setattr(module,'installed',lambda value,proposal,**kwargs:value)
    def write(name,value):
        path=tmp_path/name;path.write_bytes(canonical(value));path.chmod(0o600);return path
    source=proposal['identities']
    facts=dict(schema=FACTS,origin='host_observation',captured_at=1100,
        host={key:source['host'][key] for key in ('hostname','uid','boot_id')},
        authority_journal=dict(state='observed',path=source['recipe']['journal_root'],uid=1000,mode=0o700,device=1,inode=5),
        fixture_cgroup=dict(path=source['installation']['heavy_path']+'/owned-anchor',device=1,inode=8,populated=0,processes=[]),
        postgres_image='sha256:'+'e'*64)
    return write,write('proposal',proposal),write('installed',installed(proposal)),facts,source


def compile_packet(tmp_path,monkeypatch,change=None):
    write,proposal,inspection,facts,source=inputs(tmp_path,monkeypatch)
    if change:change(facts)
    return prepare(proposal,inspection,packet_path=tmp_path/'packet',watchdog_root=Path(source['recipe']['journal_root'])/('native-control-'+'a'*32),
        control='durable_launch_intent',scenario='lost_create_ack',generation='a'*32,facts_path=write('facts',facts),now=1100)


def test_exact_native_case_order_and_envelope_without_authority(tmp_path,monkeypatch):
    report=compile_packet(tmp_path,monkeypatch);packet=report['packet'];protocol=packet['protocol']
    assert report['execution_authority'] is False and not report['blockers']
    assert protocol['origin']=='installed_native' and protocol['timeout_seconds']==180
    assert [row['seconds'] for row in [protocol['startup'],*protocol['cases'],protocol['cleanup'],protocol['postflight']]]==[30,90,45,15]
    assert len(protocol['cases'])==1
    for phase,row in [('case',protocol['cases'][0]),('cleanup',protocol['cleanup']),('postflight',protocol['postflight'])]:
        assert row['argv'][-2:]==['--native-phase',phase]
    assert protocol['identities']['installation']['proposal']==packet['proposal']


@pytest.mark.parametrize('missing',['authority_journal','fixture_cgroup','postgres_image'])
def test_missing_facts_are_explicit_blockers_without_guessed_packet(tmp_path,monkeypatch,missing):
    report=compile_packet(tmp_path,monkeypatch,lambda facts:facts.pop(missing))
    assert report['packet'] is None and 'native_control_fact_missing:'+missing in report['blockers']


@pytest.mark.parametrize('change',[
    lambda facts:facts['host'].update(boot_id='replacement'),
    lambda facts:facts['fixture_cgroup'].update(path='/sys/fs/cgroup/unowned'),
    lambda facts:facts['fixture_cgroup'].update(populated=1),
    lambda facts:facts['authority_journal'].update(mode=0o755),
    lambda facts:facts.update(captured_at=0),
])
def test_wrong_host_scope_or_visibility_rejected(tmp_path,monkeypatch,change):
    with pytest.raises(WorkloadBlocked):compile_packet(tmp_path,monkeypatch,change)
