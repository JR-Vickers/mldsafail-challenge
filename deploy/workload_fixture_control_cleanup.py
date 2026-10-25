"""Independent, fixed cleanup of acknowledged disposable control resources.

This is a fixture worker adapter, not execution authority. Reconstruct ownership
from the pre-effect context and immutable births. Never call NativeRuntime's
name-discovery cleanup, replay creators, or remove retained services/databases.
"""
import copy
import json
import os
import re
import time
from types import SimpleNamespace
from pathlib import Path

from deploy.workload_installation import Journal,exclusive,identity,private
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.native_workload import NativeRuntime,LABEL,birth,publish,require,values
from mldsafail.evaluator.workload import HostGate,ResourcePolicy

SCHEMA='mldsafail.fixture-independent-control-cleanup.v1'
DB_LABEL='org.mldsafail.fixture-control-database'


def _guard(fixture,control,scenario,token):
    from scripts.workload_fixture_worker import inherited_lock
    from scripts.rehearse_workload_installation_fixture import component_review
    from deploy.workload_control_registry import OWNED_FIXTURE_CASES
    inherited_lock(fixture.root,fixture.lock_fd);fixture.require_target();component_review(fixture)
    require(re.fullmatch('[a-f0-9]{32}',token) and (control,scenario) in OWNED_FIXTURE_CASES,
            'fixture_independent_cleanup_selection_invalid')
    root=fixture.root/'artifacts'/('control-'+token)
    require(not any(path.is_symlink() for path in (root,*root.parents)),
            'fixture_independent_cleanup_namespace_symlink')
    intent=private(root/'intent.json')[1]
    require(intent.get('generation')==fixture.manifest['generation'] and intent.get('manifest_sha256')==fixture.binding and
            (intent.get('control'),intent.get('scenario'),intent.get('token'))==(control,scenario,token),
            'fixture_independent_cleanup_intent_changed')
    raw,proposal=fixture.proposal()
    return root,raw,proposal


def _installed_configuration(source):
    from deploy.workload_configuration import materialize,measured_resources
    expected=materialize(source,measured_resources(source))['native']
    path=Path(source['manifest']['configurations']['native']['path']);raw,configuration=private(path)
    require(raw==expected,'fixture_cleanup_installed_configuration_changed')
    return configuration,identity(path)


def prepare_context(fixture,proposal,control,scenario,token,baseline):
    root,raw,actual=_guard(fixture,control,scenario,token)
    require(actual==proposal,'fixture_cleanup_proposal_changed')
    installed,installed_identity=_installed_configuration(proposal['identities'])
    runtime=root/'runtime';runtime.mkdir(mode=0o700)
    configuration=copy.deepcopy(installed);configuration['root']=str(runtime)
    configuration['roles']={'participant':{'timeout_seconds':90}}
    NativeRuntime(configuration)  # Structural validation, never an effect.
    path=root/'native-configuration.json';exclusive(path,canonical(configuration))
    require(private(root/'baseline.json')[1]==baseline,'fixture_cleanup_baseline_changed')
    context=dict(schema=SCHEMA,fixture_only=True,generation=fixture.manifest['generation'],
        manifest_sha256=fixture.binding,proposal_sha256=digest(raw),control=control,scenario=scenario,token=token,
        root=identity(root),runtime_root=identity(runtime),installed_configuration=installed_identity,
        native_configuration=identity(path),baseline=identity(root/'baseline.json'))
    exclusive(root/'cleanup-context.json',canonical(context))
    fixture.journal.append('fixture_control_cleanup_context',token=token,observed=identity(root/'cleanup-context.json'))
    return configuration


def acquisition_intent(root,state,record):
    """Tie the physical workload to this case before native.prepare effects."""
    root=Path(root);context=private(root/'cleanup-context.json')[1]
    require(context.get('root')==identity(root) and context.get('runtime_root')==identity(root/'runtime') and
        re.fullmatch('[a-f0-9]{32}',state.get('workload_id','')) and state.get('kind')=='administration' and
        state.get('reference')==dict(fixture=context['scenario'],generation=context['generation']),
        'fixture_cleanup_acquisition_context_changed')
    value=dict(context=identity(root/'cleanup-context.json'),token=context['token'],generation=context['generation'],
        workload_id=state['workload_id'],identity=state['identity'],reference=state['reference'],kind=state['kind'],
        policy_sha256=state['policy_sha256'])
    exclusive(root/'acquisition-intent.json',canonical(value))
    record('control_acquisition_intent',observed=identity(root/'acquisition-intent.json'))


def prepared_scope(root,state,native,record):
    """Freeze acknowledged kernel births before any fixture creator may run."""
    root=Path(root);actual=native.record(state)
    value=dict(acquisition=identity(root/'acquisition-intent.json'),context=identity(root/'cleanup-context.json'),
        workload_id=state['workload_id'],scope=actual['scope'],leaf=actual['leaf'],output=actual['output'])
    exclusive(root/'prepared-scope.json',canonical(value))
    record('control_native_prepared',observed=identity(root/'prepared-scope.json'),binding=copy.deepcopy(value))


def _journal_prefix(path,binding):
    raw=private(path,parse=False)[0]
    require(len(raw)<=16*1024**2,'fixture_cleanup_evidence_size_limit')
    complete=raw.endswith(b'\n');lines=raw.splitlines()
    if not complete:lines=lines[:-1]
    rows=[];head='0'*64
    for line in lines:
        row=json.loads(line)
        require(row.get('proposal_sha256')==binding and row.get('previous')==head,'fixture_cleanup_evidence_changed')
        rows.append(row);head=digest(canonical(row))
    return SimpleNamespace(rows=rows,complete=complete,head=head,raw_sha256=digest(raw))


def _evidence(root,binding):return _journal_prefix(root/'evidence/installation.jsonl',binding)


class _PreservedRuntimeJournal:
    """Read-only original prefix plus a separately chained recovery sidecar.

    This is deliberately not continuation or repair of the interrupted journal.
    complete=False prevents removal and success even if older ACKs prove a
    compartment eligible for a Docker-free safety stop.
    """
    complete=False
    def __init__(self,source,prefix,source_identity,sidecar):
        self.source_path=source;self.prefix=prefix;self.source_identity=source_identity
        self.sidecar=sidecar;self.root=sidecar.root;self.path=sidecar.path;self.binding=sidecar.binding
    @property
    def rows(self):return [*self.prefix.rows,*self.sidecar.rows]
    @property
    def head(self):return self.sidecar.head
    def append(self,event,**values):
        require(identity(self.source_path)==self.source_identity,'fixture_cleanup_preserved_runtime_journal_changed')
        self.sidecar.append(event,**values)


def recovery_journal(root,binding,token):
    """Only cleanup workers may select this after exact parent-request checks.

    A partial trailing record is never truncated, rewritten or upgraded. Earlier
    ACKs remain readable, while fresh worker claims/observations go to a fixed
    private sidecar bound to every byte of the interrupted original.
    """
    root=Path(root)
    require(type(token) is str and re.fullmatch('[a-f0-9]{32}',token) and root.is_absolute() and
        root.name=='runtime-journal' and root.is_dir() and root.stat().st_uid==os.getuid() and
        root.stat().st_mode&0o077==0 and not any(path.is_symlink() for path in (root,*root.parents)),
        'fixture_cleanup_recovery_journal_scope_invalid')
    source=root/'installation.jsonl'
    # A never-created runtime journal has no interrupted record to interpret.
    if not source.exists() and not source.is_symlink():return Journal(root,binding)
    prefix=_journal_prefix(source,binding)
    if prefix.complete:return Journal(root,binding)
    original=identity(source)
    require(original.get('sha256')==prefix.raw_sha256,'fixture_cleanup_preserved_runtime_journal_changed')
    sidecar_root=root.parent/('control-recovery-'+token)
    anchor=dict(schema='mldsafail.fixture-preserved-runtime-journal.v1',token=token,binding=binding,
        source=original,source_root=identity(root),raw_sha256=prefix.raw_sha256,prefix_head=prefix.head)
    if sidecar_root.exists() or sidecar_root.is_symlink():
        sidecar=Journal(sidecar_root,binding)
        require(private(sidecar_root/'anchor.json')[1]==anchor,'fixture_cleanup_recovery_sidecar_anchor_changed')
    else:
        sidecar_root.mkdir(mode=0o700);exclusive(sidecar_root/'anchor.json',canonical(anchor))
        sidecar=Journal(sidecar_root,binding)
        sidecar.append('fixture_control_recovery_sidecar',token=token,observed=identity(sidecar_root/'anchor.json'))
    acknowledgements=[row for row in sidecar.rows if row['event']=='fixture_control_recovery_sidecar']
    require(len(acknowledgements)==1 and sidecar.rows[0]==acknowledgements[0] and
        acknowledgements[0].get('token')==token and
        acknowledgements[0].get('observed')==identity(sidecar_root/'anchor.json'),
        'fixture_cleanup_recovery_sidecar_unacknowledged_or_replaced')
    require(identity(source)==original,'fixture_cleanup_preserved_runtime_journal_changed')
    return _PreservedRuntimeJournal(source,prefix,original,sidecar)


def _context(fixture,control,scenario,token):
    root,raw,proposal=_guard(fixture,control,scenario,token)
    path=root/'cleanup-context.json';context=private(path)[1]
    acknowledgements=[row for row in fixture.journal.rows if row['event']=='fixture_control_cleanup_context' and row.get('token')==token]
    require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(path),
            'fixture_cleanup_context_unacknowledged_or_replaced')
    require(context.get('schema')==SCHEMA and context.get('fixture_only') is True and
        context.get('generation')==fixture.manifest['generation'] and context.get('manifest_sha256')==fixture.binding and
        context.get('proposal_sha256')==digest(raw) and
        (context.get('control'),context.get('scenario'),context.get('token'))==(control,scenario,token) and
        context.get('root')==identity(root) and context.get('runtime_root')==identity(root/'runtime') and
        context.get('native_configuration')==identity(root/'native-configuration.json') and
        context.get('baseline')==identity(root/'baseline.json'),'fixture_cleanup_context_changed')
    installed,installed_identity=_installed_configuration(proposal['identities'])
    require(context['installed_configuration']==installed_identity,'fixture_cleanup_installed_configuration_replaced')
    expected=copy.deepcopy(installed);expected['root']=str(root/'runtime');expected['roles']={'participant':{'timeout_seconds':90}}
    configuration=private(root/'native-configuration.json')[1]
    require(configuration==expected,'fixture_cleanup_configuration_transition_changed')
    return root,context,proposal,configuration


def _runner(resources,deadline):
    def run(argv):
        remaining=deadline-time.monotonic();require(remaining>0,'fixture_independent_cleanup_expired')
        return resources.run(argv,seconds=min(4.65,remaining),inner_seconds=.65)
    return run


def _rows(native,args):
    rows=json.loads(native.docker(args));require(type(rows) is list,'fixture_cleanup_docker_observation_invalid')
    return rows


def _census(native,*filters):
    result=native.docker(['ps','-aq','--no-trunc',*[value for item in filters for value in ('--filter',item)]]).decode().split()
    require(len(result)==len(set(result)) and all(re.fullmatch('[a-f0-9]{64}',value) for value in result),
            'fixture_cleanup_docker_census_invalid')
    return set(result)


def _physical(native,root,scenario,generation,evidence):
    state=private(root/'runtime/workload.json')[1]
    HostGate(root/'runtime',native)._validate(state)
    acquisition=private(root/'acquisition-intent.json')[1]
    acknowledgements=[row for row in evidence.rows if row['event']=='control_acquisition_intent']
    require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(root/'acquisition-intent.json') and
        acquisition.get('context')==identity(root/'cleanup-context.json') and acquisition.get('token')==root.name.removeprefix('control-') and
        acquisition.get('generation')==generation and all(acquisition.get(key)==state[key] for key in
            ('workload_id','identity','reference','kind','policy_sha256')),'fixture_cleanup_acquisition_unacknowledged_or_changed')
    require(state['kind']=='administration' and state['reference']==dict(fixture=scenario,generation=generation),
            'fixture_cleanup_physical_reference_changed')
    record=private(native.record_path(state))[1]
    scope=native.heavy/('mldsafail-heavy-'+state['workload_id']+'.slice')
    require(record.get('schema')=='mldsafail.native-workload.v1' and record.get('workload_id')==state['workload_id'] and
        record.get('scope_path')==str(scope) and record.get('output')==str(Path(native.config['output'])/state['workload_id']),
        'fixture_cleanup_native_record_changed')
    prepared=private(root/'prepared-scope.json')[1]
    acknowledgements=[row for row in evidence.rows if row['event']=='control_native_prepared']
    require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(root/'prepared-scope.json') and
        acknowledgements[0].get('binding')==prepared and prepared.get('context')==identity(root/'cleanup-context.json') and
        prepared.get('acquisition')==identity(root/'acquisition-intent.json') and prepared.get('workload_id')==state['workload_id'] and
        all(prepared.get(key)==record.get(key) for key in ('scope','leaf','output')),
        'fixture_cleanup_prepared_scope_unacknowledged_or_changed')
    # A matching systemd name is never ownership of an unacknowledged prepare.
    require(type(record.get('scope')) is dict and record['scope'].get('path')==str(scope),
            'fixture_cleanup_scope_birth_unacknowledged_preserve')
    if scope.exists():
        require(birth(scope)==record['scope'],'fixture_cleanup_scope_replaced_preserve')
        leaf=record.get('leaf')
        if type(leaf) is dict and Path(leaf['path']).exists():
            require(leaf['path']==str(scope/'creators') and birth(leaf['path'])==leaf,
                    'fixture_cleanup_leaf_replaced_preserve')
    return state,record


def _compartment_kill(native,state,record):
    scope=Path(record['scope']['path'])
    if not scope.exists():return dict(state='removed',identity=record['scope'])
    # Docker-free safety stop. The boot and exact owned subtree, never an
    # ancestor or a name-only unit, authorize this write after worker death.
    import mldsafail.evaluator.native_workload as native_module
    require((native_module.PROC_ROOT/'sys/kernel/random/boot_id').read_text().strip()==state['identity']['boot_id'],
            'fixture_cleanup_boot_changed')
    native.domains();require(birth(scope)==record['scope'],'fixture_cleanup_scope_replaced_preserve')
    record['revoked']=True;publish(native.record_path(state),record)
    before=values(scope/'cgroup.events');(scope/'cgroup.kill').write_text('1')
    return dict(state='kill_requested',identity=record['scope'],before=before)


def _computational(native,root,state,record,existing,evidence):
    workload=state['workload_id'];created_path=root/'created-container.json';started_path=root/'started-container.json'
    expected=[]
    if created_path.exists() or created_path.is_symlink():
        created=private(created_path)[1]
        acknowledgements=[row for row in evidence.rows if row['event']=='control_container_created']
        require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(created_path) and
            acknowledgements[0].get('binding')==created,'fixture_cleanup_created_ack_missing_or_changed')
        require(re.fullmatch('[a-f0-9]{64}',created.get('id','')) and created.get('created_at') and
            created.get('name')=='mlwe-fixture-'+workload and created.get('operation_id')==workload and
            created.get('scope')==record['scope'] and created.get('started_at') is None,
            'fixture_cleanup_created_receipt_changed')
        started=private(started_path)[1] if started_path.exists() or started_path.is_symlink() else None
        if started is not None:
            acknowledgements=[row for row in evidence.rows if row['event']=='control_container_started']
            require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(started_path) and
                acknowledgements[0].get('binding')==started,'fixture_cleanup_started_ack_missing_or_changed')
            require({key:value for key,value in started.items() if key!='started_at'}==
                {key:value for key,value in created.items() if key!='started_at'} and
                type(started.get('started_at')) is str and started['started_at'], 'fixture_cleanup_started_receipt_changed')
        expected=[dict(created,started_at=started['started_at'] if started else None)]
    elif started_path.exists() or started_path.is_symlink():require(False,'fixture_cleanup_create_ack_missing_preserve')
    known={row['id'] for row in expected}
    discovered=_census(native,'label='+LABEL+'='+workload)|_census(native,'label=org.mldsafail.fixture-control='+root.name)
    require(discovered<=known,'fixture_cleanup_unacknowledged_container_preserve')
    output=Path(record['output']);router=output/'router'
    intents=[]
    for path in router.glob('*.json') if router.exists() else []:
        row=private(path)[1]
        require(expected and path.name==expected[0]['name']+'.json' and row.get('operation_id')==workload and
                row.get('name')==expected[0]['name'] and row.get('container_id',expected[0]['id'])==expected[0]['id'] and
                row.get('created_at',expected[0]['created_at'])==expected[0]['created_at'],
                'fixture_cleanup_router_unacknowledged_or_replaced')
        require(not (row.get('state')=='start_intent' and expected[0]['started_at'] is None),
                'fixture_cleanup_start_ack_missing_preserve')
        intents.append((path,row))
    restart=root/'restart-injection.json'
    if restart.exists() or restart.is_symlink():
        value=private(restart)[1]
        require(any(row['event']=='control_restart_observed' and row.get('before')==value.get('before') and
                    row.get('after')==value.get('after') for row in evidence.rows),
                'fixture_cleanup_restart_ack_missing_preserve')
        require(expected and value['before']['Id']==value['after']['Id']==expected[0]['id'] and
            value['before']['Created']==value['after']['Created']==expected[0]['created_at'] and
            value['before']['State']['StartedAt']==expected[0]['started_at'],'fixture_cleanup_restart_receipt_changed')
        expected[0]['started_at']=value['after']['State']['StartedAt']
    observed=[]
    for binding in expected:
        if binding['id'] not in existing:continue
        rows=_rows(native,['inspect',binding['id']]);require(len(rows)==1,'fixture_cleanup_container_inspection_incomplete')
        row=rows[0];policy=row['HostConfig'];labels=row['Config'].get('Labels',{})
        require(row['Id']==binding['id'] and row['Name']=='/'+binding['name'] and row['Created']==binding['created_at'] and
            row['Image']==native.config['worker']['image'] and labels.get(LABEL)==workload and
            labels.get('org.mldsafail.fixture-control')==root.name and
            labels.get('org.mldsafail.fixture-generation')==state['reference']['generation'] and policy['CgroupParent']==Path(record['scope']['path']).name and
            policy['NetworkMode']=='none' and policy['ReadonlyRootfs'] is True and
            policy['Memory']==policy['MemorySwap']==32*1024**2 and policy['PidsLimit']==16 and
            policy['RestartPolicy']['Name']=='no' and policy['NanoCpus']==100000000 and
            policy['LogConfig']['Type']=='none' and set(policy['CapDrop'])=={'ALL'} and
            policy['SecurityOpt']==['no-new-privileges'] and not policy.get('Binds'),
            'fixture_cleanup_container_birth_or_policy_changed_preserve')
        require((row['State']['StartedAt']==binding['started_at'] if binding['started_at'] else
            not row['State']['Running'] and row['State']['StartedAt'] in ('','0001-01-01T00:00:00Z')),
            'fixture_cleanup_container_restart_unacknowledged_preserve')
        observed.append(row)
    return expected,observed,intents


def _database(native,root,fixture,token,existing,postgres_image):
    directory=root/'database';discovered=_census(native,'label='+DB_LABEL+'='+token)
    if not directory.exists():
        require(not discovered,'fixture_cleanup_unknown_database_preserve');return [],[]
    intent=private(directory/'intent.json')[1]
    require(intent.get('generation')==fixture.manifest['generation'] and intent.get('manifest_sha256')==fixture.binding and
        intent.get('token')==token and intent.get('name')=='mlwe-fixture-database-'+token and
        intent.get('image')==postgres_image,'fixture_cleanup_database_intent_changed')
    # Even an empty census cannot resolve an asynchronous unacknowledged create.
    require((directory/'created.json').exists() and (directory/'started.json').exists(),
            'fixture_cleanup_database_ack_missing_preserve')
    created=private(directory/'created.json')[1];binding=private(directory/'started.json')[1]
    for event,path,value in (('fixture_control_database_created',directory/'created.json',created),
                             ('fixture_control_database_started',directory/'started.json',binding)):
        acknowledgements=[row for row in fixture.journal.rows if row['event']==event and row.get('token')==token]
        require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(path) and
                acknowledgements[0].get('binding')==value,'fixture_cleanup_database_ack_changed')
    require(created.get('started_at') is None and binding.get('started_at') and
        {key:value for key,value in created.items() if key!='started_at'}==
        {key:value for key,value in binding.items() if key!='started_at'} and
        re.fullmatch('[a-f0-9]{64}',binding.get('id','')) and binding.get('image')==postgres_image,
        'fixture_cleanup_database_receipt_changed')
    require(discovered<={binding['id']},'fixture_cleanup_unknown_database_preserve')
    rows=[]
    if binding['id'] in existing:
        observed=_rows(native,['inspect',binding['id']]);require(len(observed)==1,'fixture_cleanup_database_inspection_incomplete')
        row=observed[0];policy=row['HostConfig'];labels=row['Config'].get('Labels',{})
        require(row['Id']==binding['id'] and row['Created']==binding['created_at'] and row['Image']==postgres_image and
            row['Name']=='/'+intent['name'] and row['State']['StartedAt']==binding['started_at'] and
            labels.get(DB_LABEL)==token and labels.get('org.mldsafail.fixture-generation')==fixture.manifest['generation'] and
            policy['NetworkMode']=='bridge' and policy['ReadonlyRootfs'] is True and policy['Memory']==policy['MemorySwap']==128*1024**2 and
            policy['PidsLimit']==32 and policy['RestartPolicy']['Name']=='no' and not policy.get('Binds') and
            policy['NanoCpus']==250000000 and policy['LogConfig']['Type']=='none' and policy['Tmpfs']=={
                '/var/lib/postgresql/data':'rw,size=64m','/var/run/postgresql':'rw,size=8m','/tmp':'rw,size=8m'},
            'fixture_cleanup_database_birth_or_policy_changed_preserve')
        ports=row['NetworkSettings']['Ports'].get('5432/tcp')
        require(set(row['NetworkSettings']['Ports'])=={'5432/tcp'} and type(ports) is list and len(ports)==1 and
            ports[0]['HostIp']=='127.0.0.1' and ports[0]['HostPort'].isdecimal() and 0<int(ports[0]['HostPort'])<65536,
                'fixture_cleanup_database_not_loopback_preserve')
        rows=[row]
    return [binding],rows


def _same_resource(before,current):
    require(all(current.get(key)==before.get(key) for key in ('Id','Name','Created','Image','Config','HostConfig')) and
        current['State']['StartedAt']==before['State']['StartedAt'] and
        (before['State']['Running'] or not current['State']['Running']),
        'fixture_cleanup_container_changed_before_removal')
    if not current['State']['Running']:
        require(current['State'].get('Pid',0)==0,'fixture_cleanup_stopped_container_pid_changed')


def _terminated(expected):
    require(type(expected) is dict and set(expected)=={'pid','start_ticks'} and
        all(type(value) is int and value>0 for value in expected.values()),'fixture_cleanup_process_identity_invalid')
    import mldsafail.evaluator.native_workload as native_module
    try:
        current=native_module.process_birth(expected['pid'])
        if current!=expected:return True
        state=(native_module.PROC_ROOT/str(expected['pid'])/'stat').read_text().rsplit(')',1)[1].split()[0]
        return state=='Z'
    except FileNotFoundError:return True


def cleanup(fixture,resources,control,scenario,token,deadline=None):
    started=time.monotonic();deadline=min(started+45,deadline if deadline is not None else started+45)
    require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
    root,context,proposal,configuration=_context(fixture,control,scenario,token)
    native=NativeRuntime(configuration,run=_runner(resources,deadline))
    gate=HostGate(root/'runtime',native)
    with gate.locked():
        return _cleanup_locked(fixture,resources,root,context,configuration,native,gate,scenario,token,deadline)


def _cleanup_locked(fixture,resources,root,context,configuration,native,gate,scenario,token,deadline):
    evidence=_evidence(root,fixture.binding)
    state,record=_physical(native,root,scenario,fixture.manifest['generation'],evidence)
    require(gate.state==state,'fixture_cleanup_physical_state_changed')
    require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
    gate.state.update(paused=True,reason='independent_fixture_cleanup_started');gate._write()
    state=copy.deepcopy(gate.state)
    require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
    fixture.journal.append('fixture_control_cleanup_scope_kill_intent',token=token,scope=record['scope'])
    safety=_compartment_kill(native,state,record)
    fixture.journal.append('fixture_control_cleanup_scope_kill_acknowledged',token=token,observed=safety)
    require(record.get('phase')=='prepared' and type(record.get('leaf')) is dict and
        record['leaf'].get('path')==str(Path(record['scope']['path'])/'creators'),
        'fixture_cleanup_prepare_incomplete_preserve')
    require(evidence.complete,'fixture_cleanup_partial_evidence_preserve')
    require(getattr(fixture.journal,'complete',True),'fixture_cleanup_partial_runtime_journal_preserve')
    require(gate.state['phase'] in ('acquired','launch_intent','running','termination_intent','cleaned','complete') and
        not gate.state.get('database_commit') and not any(row.get('phase')!='complete' for row in gate.state.get('requests',{}).values()),
        'fixture_cleanup_transaction_unresolved_preserve')
    require(native.identity()==state['identity'],'fixture_cleanup_runtime_replaced_preserve')
    existing=_census(native)
    expected,containers,routers=_computational(native,root,state,record,existing,evidence)
    database,databases=_database(native,root,fixture,token,existing,resources.settings['postgres_image'])
    # Validate every resource before the first Docker mutation. Unknown effects
    # remain preserved; the independently proven scope was already safety-stopped.
    for row in [*containers,*databases]:
        current=_rows(native,['inspect',row['Id']]);require(len(current)==1,'fixture_cleanup_container_inspection_incomplete')
        _same_resource(row,current[0])
        fixture.journal.append('fixture_control_cleanup_remove_intent',token=token,observed=current[0])
        if current[0]['State']['Running']:native.docker(['kill',row['Id']])
        native.docker(['rm',row['Id']])
        fixture.journal.append('fixture_control_cleanup_remove_acknowledged',token=token,container=row['Id'])
    remaining=_census(native)
    require(not ({row['id'] for row in [*expected,*database]} & remaining) and
        not _census(native,'label='+LABEL+'='+state['workload_id']) and
        not _census(native,'label=org.mldsafail.fixture-control='+root.name) and
        not _census(native,'label='+DB_LABEL+'='+token),'fixture_cleanup_containers_remaining')
    for path,row in routers:publish(path,dict(row,state='removed',cleanup_disposition='independent_exact_birth_removed'))
    scope=Path(record['scope']['path']);extras=[]
    for row in evidence.rows:
        if row['event']=='control_cgroup_created':extras.append(row['observed'])
        if row['event']=='control_quota_file_created':
            observed=row['observed'];path=Path(observed['path'])
            require(path==Path(record['output'])/'fixture-quota.bin','fixture_cleanup_quota_path_changed')
            if path.exists():
                require(identity(path,content=False)==observed and path.stat().st_nlink==1,'fixture_cleanup_quota_replaced_preserve')
                require(native.output_mount(ResourcePolicy())==record['baseline']['output'],'fixture_cleanup_quota_mount_changed')
                require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
                path.unlink()
    controllers=[{key:row[key] for key in ('pid','start_ticks')} for row in record.get('controllers',[])]
    controllers.extend(row['identity'] for row in evidence.rows if row['event'] in
                       ('control_process_created','control_controller_created'))
    while not all(_terminated(expected) for expected in controllers):
        require(time.monotonic()<deadline,'fixture_cleanup_recorded_process_survives');time.sleep(.01)
    if scope.exists():
        require(birth(scope)==record['scope'],'fixture_cleanup_scope_replaced_preserve')
        while values(scope/'cgroup.events')['populated']:
            require(time.monotonic()<deadline,'fixture_cleanup_scope_still_populated');time.sleep(.01)
        children={str(path) for path in scope.iterdir() if path.is_dir()}
        allowed={record['leaf']['path']}|{row['path'] for row in extras}
        require(children<=allowed,'fixture_cleanup_unknown_cgroup_preserve')
        for expected_birth in [*reversed(extras),record['leaf']]:
            require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
            path=Path(expected_birth['path']);require(path.parent==scope,'fixture_cleanup_cgroup_outside_owned_scope')
            if path.exists():
                require(birth(path)==expected_birth and values(path/'cgroup.events')['populated']==0,
                        'fixture_cleanup_cgroup_replaced_or_populated');path.rmdir()
        require(birth(scope)==record['scope'],'fixture_cleanup_scope_replaced_preserve')
        native.run(['/usr/bin/systemctl','--user','stop',scope.name])
    after=identity(scope,content=False)
    require(after['state']=='absent' or birth(scope)==record['scope'] and values(scope/'cgroup.events')['populated']==0,
            'fixture_cleanup_scope_not_empty_or_removed')
    require(time.monotonic()<deadline,'fixture_independent_cleanup_expired')
    gate.state.update(phase='cleaned',paused=True,reason='independent_fixture_cleanup_verified');gate._write()
    resolved=copy.deepcopy(gate.state)
    receipt=dict(schema=SCHEMA,fixture_only=True,verified=True,generation=fixture.manifest['generation'],token=token,
        context=identity(root/'cleanup-context.json'),safety_stop=safety,remaining=[],transactions='resolved',gate_state=resolved,
        computational_bindings=expected,database_bindings=database,scope_termination=dict(state='removed' if after['state']=='absent' else 'empty',
            identity=record['scope'],events={} if after['state']=='absent' else values(scope/'cgroup.events')),
        retained_services_touched=False)
    exclusive(root/'independent-cleanup.json',canonical(receipt))
    fixture.journal.append('fixture_control_independent_cleanup',token=token,observed=identity(root/'independent-cleanup.json'))
    return receipt


def postflight(fixture,resources,control,scenario,token,deadline=None):
    started=time.monotonic();deadline=min(started+15,deadline if deadline is not None else started+15)
    root,context,proposal,configuration=_context(fixture,control,scenario,token)
    require(getattr(fixture.journal,'complete',True),'fixture_cleanup_partial_runtime_journal_preserve')
    receipt=private(root/'independent-cleanup.json')[1]
    acknowledgements=[row for row in fixture.journal.rows if row['event']=='fixture_control_independent_cleanup' and row.get('token')==token]
    require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(root/'independent-cleanup.json') and
        receipt.get('context')==identity(root/'cleanup-context.json') and receipt.get('token')==token,
        'fixture_cleanup_final_receipt_changed')
    native=NativeRuntime(configuration,run=_runner(resources,deadline));state=private(root/'runtime/workload.json')[1]
    HostGate(root/'runtime',native)._validate(state)
    require(state==receipt['gate_state'] and state['paused'] is True and state['phase']=='cleaned',
            'fixture_cleanup_postflight_not_paused')
    require(native.identity()==state['identity'],'fixture_cleanup_postflight_runtime_changed')
    scope=receipt['scope_termination']['identity']
    require(not Path(scope['path']).exists() or birth(scope['path'])==scope and values(Path(scope['path'])/'cgroup.events')['populated']==0,
            'fixture_cleanup_postflight_scope_changed')
    existing=_census(native)
    require(not ({row['id'] for row in receipt['computational_bindings']+receipt['database_bindings']} & existing) and
        not _census(native,'label='+LABEL+'='+state['workload_id']) and
        not _census(native,'label=org.mldsafail.fixture-control='+root.name) and
        not _census(native,'label='+DB_LABEL+'='+token),'fixture_cleanup_postflight_container_survives')
    original_run=resources.run
    def bounded(argv,*,seconds=35,inner_seconds=None):
        remaining=deadline-time.monotonic();require(remaining>0,'fixture_cleanup_postflight_expired')
        return original_run(argv,seconds=min(4.65,remaining),inner_seconds=.65)
    resources.run=bounded
    try:actual=resources.postflight(proposal)
    finally:resources.run=original_run
    baseline=private(root/'baseline.json')[1]
    require(actual==baseline and time.monotonic()<deadline,'fixture_cleanup_retained_postflight_changed_or_expired')
    result=dict(schema=SCHEMA,fixture_only=True,verified=True,generation=fixture.manifest['generation'],token=token,
        cleanup=identity(root/'independent-cleanup.json'),retained_before=baseline,retained_after=actual,
        paused=True,transactions='resolved',scope_termination=receipt['scope_termination'])
    exclusive(root/'independent-postflight.json',canonical(result))
    return result
