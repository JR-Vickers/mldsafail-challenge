"""Installed adapter tests with fixed inert host observations, no VPS execution."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from deploy.workload_installation import Journal,exclusive,identity
from deploy.workload_release import canonical,digest
from deploy.workload_native_resources import NativeResources,PGOPTIONS,LIMIT,ROW_LIMIT,table_allowlist,table_query
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_native_workload import fixture as native_fixture
from tests.test_workload_installation import packet


@pytest.fixture
def native_context(tmp_path,monkeypatch,native_fixture):
    import deploy.workload_native_resources as adapter
    import deploy.workload_installed as installed
    import deploy.workload_fixture_resources as fixture_resources
    from mldsafail.evaluator.workload_client import WorkloadClient
    proposal,_,_,_=packet(tmp_path);source=proposal['identities']
    source['origin']='local_linux'
    config=deepcopy(native_fixture[0].config);source['host']['runtime_identity']=native_fixture[0].identity()
    source['host']['daemon_id']=source['host']['runtime_identity']['daemon_id'];source['host']['uid']=os.getuid()
    raw=canonical(config);source['recipe']['configuration_templates']['native']=raw.hex()
    path=tmp_path/'installed-native.json';exclusive(path,raw)
    source['manifest']['configurations']['native']=dict(path=str(path),sha256=digest(raw))
    source['resources']['delegation']=dict(identity(native_fixture[3]),ancestors=[identity(native_fixture[4])])
    source['resources']['output'].update(path=config['output'],device=Path(config['output']).stat().st_dev,inode=Path(config['output']).stat().st_ino,mount_id=55)
    source['installation']['heavy_path']=str(native_fixture[3]);(native_fixture[3]/'cgroup.events').write_text('populated 0\n')
    root=tmp_path/'native-context';root.mkdir(mode=0o700);(root/'artifacts').mkdir(mode=0o700)
    release=tmp_path/'frozen-release';release.mkdir();(release/'bundle').mkdir();source['resources']['release']['path']=str(release)
    journal_root=root/'runtime-journal';journal_root.mkdir(mode=0o700)
    context=SimpleNamespace(root=root,source=source,native_configuration=config,settings={'postgres_image':'sha256:'+'7'*64},
        manifest={'source_root':str(release/'bundle')},journal=Journal(journal_root,'9'*64),baseline_capture_allowed=True)
    context.proposal=lambda:(canonical(proposal),proposal)
    schema=b'-- inert schema\nCREATE TABLE fixed_source_model (id text);\n'
    source['rollback']['schema_sha256']=source['rollback']['installed_schema_sha256']=digest(b'CREATE TABLE fixed_source_model (id text);\n')
    source['rollback']['schema'].update(database='retained_native',username='postgres')
    tables={name:(b'{"version_num":"baseline"}\n' if name=='alembic_version' else b'') for name in table_allowlist()}
    responses=SimpleNamespace(schema=schema,inventory='\n'.join(table_allowlist()).encode()+b'\n',
        database=b'retained_native\tpostgres\t42\n',tables=tables,services=deepcopy(source['retained_services']),restart_on_table=False,identity_on_table=None)
    calls=[]
    owner=source['host']['uid'];unit='compute.service';directory=tmp_path/'units';directory.mkdir()
    dropin=directory/(unit+'.d');dropin.mkdir();file=dropin/'90-mldsafail-paused.conf';exclusive(file,b'[Unit]\nConditionPathExists=/never-enabled\n')
    source['permission_root']=str(tmp_path/'permissions')
    source['scheduling']={'owners':{unit:dict(manager='user',uid=owner,disposition='pause')},'computational_units':[unit]}
    proposal['scheduling']['resources']=[dict(path=str(file),owner_uid=owner,contents=file.read_text())]
    proc=native_fixture[2];cgroup=native_fixture[4];pid=54321
    (proc/str(pid)).mkdir();(proc/str(pid)/'stat').write_text(str(pid)+' (supervisor) '+' '.join(['S']+['0']*18+['777']+['0']*20))
    (proc/str(pid)/'cgroup').write_text('0::/supervisor')
    endpoint_path=Path(config['docker'][2].removeprefix('unix://')).parent/'supervisor.sock'
    endpoint=socket.socket(socket.AF_UNIX);endpoint.bind(str(endpoint_path));endpoint_path.chmod(0o600)
    source['resources']['socket']['path']=str(endpoint_path)
    born=identity(endpoint_path);exclusive(endpoint_path.parent/'socket.json',canonical(dict(path=str(endpoint_path),device=born['device'],
        inode=born['inode'],process=dict(pid=pid,start_ticks=777))))
    status=dict(paused=True,phase='complete',request_counts={'intent':0,'complete':0},inflight_resumes=0,inflight_launches=0)
    monkeypatch.setattr(WorkloadClient,'status',lambda self:deepcopy(status))
    def mapped(value):
        value=str(value)
        if value.startswith('/proc/'):return proc/value.removeprefix('/proc/')
        if value.startswith('/sys/fs/cgroup/'):return cgroup/value.removeprefix('/sys/fs/cgroup/')
        return Path(value)
    monkeypatch.setattr(adapter,'Path',mapped);monkeypatch.setattr(installed,'Path',mapped);monkeypatch.setattr(fixture_resources,'Path',mapped)
    def command(argv,*,cleanup=False,seconds=35):
        assert 0<seconds<=4.65 and argv[:4]==[__import__('sys').executable,'-I','-B','-c']
        tree=ast.parse(argv[4]);matches=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='command']
        assert len(matches)==1 and ast.literal_eval(matches[0].keywords[0].value)==.65
        actual=ast.literal_eval(matches[0].args[0]);calls.append(actual)
        if actual[:2]==['/usr/bin/systemctl','--user']:
            raw=str(pid).encode() if '--property=MainPID' in actual else b'inactive'
        else:
            assert actual[:3]==config['docker'];args=actual[3:]
            if args[0]=='info':raw=canonical(dict(ID='daemon',CgroupDriver='systemd',CgroupVersion='2',SecurityOptions=['name=rootless']))
            elif args[0]=='inspect':
                record=next(row for row in responses.services.values() if row['id']==args[-1])
                raw=canonical([dict(Id=record['id'],Image=record['image'],State=dict(StartedAt=record['started_at'],Running=record['running']))])
            else:
                assert args[:3]==['exec','--env',PGOPTIONS] and '--user' in args and args[args.index('--user')+1]=='postgres'
                assert args[args.index('--user')+2]==source['rollback']['schema']['container_id']
                if 'pg_dump' in args:raw=responses.schema
                else:
                    assert 'psql' in args and '--no-psqlrc' in args and 'ON_ERROR_STOP=1' in args
                    sql=args[-1];assert sql.startswith('BEGIN TRANSACTION READ ONLY; SET LOCAL statement_timeout = 500; SET LOCAL lock_timeout = 500; ') and sql.endswith(' ROLLBACK;')
                    if 'information_schema.tables' in sql:raw=responses.inventory
                    elif 'current_database()' in sql:raw=responses.database
                    else:
                        name=next(name for name in table_allowlist() if 'public."'+name+'"' in sql)
                        assert table_query(name) in sql;raw=responses.tables[name]
                        if responses.restart_on_table:responses.services['database']['started_at']='restarted'
                        if responses.identity_on_table is not None:responses.database=responses.identity_on_table
        output=root/'artifacts'/('command-'+str(len(calls))+'.log');exclusive(output,raw)
        return output
    context.command=command
    context.lifecycle_journal=context.journal
    context.inspection=dict(origin=source['origin'],proposal_sha256=digest(canonical(proposal)),resources={
        'output':dict(source['resources']['output']),
        'delegation':{key:config['heavy_birth'][key] for key in ('path','device','inode')}})
    context.inspection['supervisor']=dict(pid=pid,start_ticks=777)
    context.inspection['resources']['socket']=dict(born)
    def verify_supervisor_transition(record,observed):
        assert record['process']==context.inspection['supervisor']
        assert all(observed[key]==context.inspection['resources']['socket'][key] for key in ('path','device','inode'))
    context.verify_supervisor_transition=verify_supervisor_transition
    try:yield SimpleNamespace(context=context,proposal=proposal,source=source,config=config,responses=responses,calls=calls,
        status=status,proc=proc,heavy=native_fixture[3],dropin=file,supervisor_socket=endpoint_path)
    finally:endpoint.close()


def test_native_resources_constructor_uses_live_context_not_fixture_inputs(native_context):
    own=native_context;resources=NativeResources(own.context)
    assert not own.calls  # Construction does not touch Docker, including cleanup.
    assert resources.settings['postgres_image']==own.context.settings['postgres_image']
    with pytest.raises(WorkloadBlocked,match='runtime_input_forbidden'):resources.input('settings')
    proof=resources.fingerprint(own.source)
    assert proof['schema_sha256']==own.source['rollback']['schema_sha256']
    assert set(proof['tables'])==set(table_allowlist()) and proof['identity']['oid']==42
    assert proof['tables']['alembic_version']['rows']==1
    assert len([row for row in own.context.journal.rows if row['event']=='fixture_daemon_bound'])==1
    assert all('inert_fixture_state' not in repr(call) for call in own.calls)


@pytest.mark.parametrize('change',['missing_image','configuration','database_reference'])
def test_native_constructor_blocks_missing_or_changed_facts_before_commands(native_context,change):
    own=native_context
    if change=='missing_image':own.context.settings={}
    elif change=='configuration':own.context.native_configuration=dict(own.config,root='/not-reviewed')
    else:own.source['rollback']['schema']['container_id']='0'*64
    with pytest.raises(WorkloadBlocked):NativeResources(own.context)
    assert own.calls==[]


@pytest.mark.parametrize('change',['unknown_table','missing_table','wrong_identity','schema','cap','row_limit','partial_row'])
def test_retained_database_fingerprint_refuses_incomplete_or_unbounded_observations(native_context,change):
    own=native_context;resources=NativeResources(own.context);name=next(iter(table_allowlist()))
    if change=='unknown_table':own.responses.inventory+=b'unknown_runtime_table\n'
    elif change=='missing_table':own.responses.inventory=b'\n'.join(own.responses.inventory.splitlines()[1:])+b'\n'
    elif change=='wrong_identity':own.responses.database=b'other\tpostgres\t42\n'
    elif change=='schema':own.responses.schema=b'CREATE TABLE substituted (id text);\n'
    elif change=='cap':own.responses.tables[name]=b'x'*(LIMIT-1)+b'\n'
    elif change=='row_limit':own.responses.tables[name]=b'{}\n'*(ROW_LIMIT+1)
    else:own.responses.tables[name]=b'{"truncated"'
    with pytest.raises(WorkloadBlocked):resources.fingerprint(own.source)
    assert not (own.context.root/'baseline.json').exists()


def test_fixed_table_sql_and_primary_key_order_allow_no_runtime_selection():
    for name,columns in table_allowlist().items():
        sql=table_query(name)
        assert 'LIMIT 10001' in sql and 'ORDER BY '+','.join('"'+column+'"' for column in columns) in sql
        assert 'public."'+name+'"' in sql
    for name in ('pg_authid','users; DROP TABLE users','epoch_keys','inert_fixture_state'):
        with pytest.raises(WorkloadBlocked,match='table_not_allowed'):table_query(name)


def test_native_postflight_freezes_fresh_baseline_and_compares_retained_data(native_context):
    own=native_context;resources=NativeResources(own.context)
    baseline=resources.postflight(own.proposal);assert baseline['verified'] and baseline['supervisor_paused'] and baseline['heavy_empty']
    own.context.baseline_capture_allowed=False
    assert NativeResources(own.context).postflight(own.proposal)==baseline
    own.responses.tables['users']=b'{"id":"changed"}\n'
    with pytest.raises(WorkloadBlocked,match='retained_postflight_changed'):resources.postflight(own.proposal)


@pytest.mark.parametrize('change',['unpaused','request_pending','heavy_populated','permission','baseline_replaced','capture_forbidden'])
def test_native_postflight_observes_global_pause_and_exact_baseline(native_context,change):
    own=native_context;resources=NativeResources(own.context)
    if change=='unpaused':own.status['paused']=False
    elif change=='request_pending':own.status['request_counts']['intent']=1
    elif change=='heavy_populated':(own.heavy/'cgroup.events').write_text('populated 1\n')
    elif change=='permission':
        root=Path(own.source['permission_root']);root.mkdir();exclusive(root/('user-'+str(os.getuid())+'.allow'),b'permission')
    elif change=='baseline_replaced':
        resources.postflight(own.proposal);path=own.context.root/'baseline.json';data=path.read_bytes();path.rename(path.with_name('preserved'));exclusive(path,data)
    else:own.context.baseline_capture_allowed=False
    with pytest.raises(WorkloadBlocked):resources.postflight(own.proposal)


@pytest.mark.parametrize('counter',['inflight_resumes','inflight_launches'])
@pytest.mark.parametrize('value',[1,None,False])
def test_atomic_supervisor_snapshot_requires_explicit_idle_counters(native_context,counter,value):
    own=native_context;resources=NativeResources(own.context)
    if value is None:own.status.pop(counter)
    else:own.status[counter]=value
    with pytest.raises(WorkloadBlocked,match='supervisor_not_paused_or_transaction_pending'):
        resources.postflight(own.proposal)
    assert not (own.context.root/'baseline.json').exists()


def test_startup_baseline_ack_and_daemon_binding_survive_worker_journal_split(native_context):
    own=native_context;startup=NativeResources(own.context);baseline=startup.postflight(own.proposal)
    lifecycle_head=own.context.lifecycle_journal.head
    runtime=own.context.root/'worker-runtime';runtime.mkdir(mode=0o700)
    own.context.journal=Journal(runtime,'9'*64);own.context.baseline_capture_allowed=False
    worker=NativeResources(own.context)
    assert worker.postflight(own.proposal)==baseline
    assert own.context.lifecycle_journal.head==lifecycle_head
    assert len([row for row in own.context.journal.rows if row['event']=='fixture_daemon_bound'])==1
    assert not any(row['event']=='native_control_baseline' for row in own.context.journal.rows)


def test_partial_runtime_constructor_issues_no_docker_or_new_binding(native_context):
    own=native_context;startup=NativeResources(own.context);startup.postflight(own.proposal)
    before=len(own.calls)
    def forbidden(*args,**kwargs):pytest.fail('partial cleanup constructor must not append or issue Docker')
    own.context.journal=SimpleNamespace(rows=[],complete=False,append=forbidden)
    resources=NativeResources(own.context)
    assert resources._daemon_binding is not None and own.calls[before:]==[]


@pytest.mark.parametrize('change',['missing_inspection','output_birth','mount_id'])
def test_installed_births_are_bound_to_fresh_inspection(native_context,change):
    own=native_context
    if change=='missing_inspection':
        own.context.inspection={}
        with pytest.raises(WorkloadBlocked,match='installed_observation'):NativeResources(own.context)
    else:
        resources=NativeResources(own.context)
        if change=='output_birth':own.context.inspection['resources']['output']['inode']+=1
        else:
            path=own.proc/'self/mountinfo';path.write_text(path.read_text().replace('55 1 ','56 1 '))
        with pytest.raises(WorkloadBlocked,match='output_birth_or_mount_changed'):resources.postflight(own.proposal)
    assert not (own.context.root/'baseline.json').exists()


def test_retained_database_replacement_during_read_is_rejected(native_context):
    own=native_context;resources=NativeResources(own.context);own.responses.restart_on_table=True
    with pytest.raises(WorkloadBlocked,match='database_container_changed'):resources.fingerprint(own.source)
    assert not (own.context.root/'baseline.json').exists()


def test_changed_database_oid_is_detected_even_when_rows_and_schema_match(native_context):
    own=native_context;resources=NativeResources(own.context);resources.postflight(own.proposal)
    own.responses.database=b'retained_native\tpostgres\t43\n'
    with pytest.raises(WorkloadBlocked,match='retained_postflight_changed'):resources.postflight(own.proposal)


@pytest.mark.parametrize('arguments',[dict(seconds=180),dict(seconds=-1),dict(inner_seconds=1)])
def test_native_subcommand_limits_cannot_be_extended(native_context,arguments):
    own=native_context;resources=NativeResources(own.context)
    with pytest.raises(WorkloadBlocked,match='command_deadline_changed'):resources.run(['/unbound'],**arguments)
    assert own.calls==[]


@pytest.mark.parametrize('query',["SELECT * FROM pg_authid;","DELETE FROM users;","COPY (SELECT * FROM unreviewed_table) TO STDOUT;"])
def test_native_database_queries_cannot_be_supplied_at_runtime(native_context,query):
    own=native_context;resources=NativeResources(own.context)
    with pytest.raises(WorkloadBlocked,match='query_not_allowed'):resources._psql(query)
    assert own.calls==[]


def test_native_reader_source_cannot_follow_an_operator_checkout(native_context):
    own=native_context;resources=NativeResources(own.context)
    own.context.manifest['source_root']='/operator/current-checkout'
    with pytest.raises(WorkloadBlocked,match='frozen_source_root_changed'):resources.run(['/usr/bin/true'])
    assert own.calls==[]


def test_postflight_requires_context_supervisor_transition_proof(native_context):
    own=native_context;resources=NativeResources(own.context)
    del own.context.verify_supervisor_transition
    with pytest.raises(WorkloadBlocked,match='supervisor_transition_observer_missing'):resources.postflight(own.proposal)
    assert not (own.context.root/'baseline.json').exists()


def test_database_oid_change_during_table_reads_blocks_mixed_fingerprint(native_context):
    own=native_context;resources=NativeResources(own.context)
    own.responses.identity_on_table=b'retained_native\tpostgres\t43\n'
    with pytest.raises(WorkloadBlocked,match='database_identity_changed_during_read'):resources.fingerprint(own.source)
    assert not (own.context.root/'baseline.json').exists()


@pytest.mark.parametrize('replacement',['record','process','placement','socket'])
def test_supervisor_replacement_during_status_blocks_mixed_identity(native_context,monkeypatch,replacement):
    from mldsafail.evaluator.workload_client import WorkloadClient
    own=native_context;resources=NativeResources(own.context);replacement_sockets=[]
    def status(client):
        if replacement=='record':
            path=own.supervisor_socket.parent/'socket.json';data=path.read_bytes();path.rename(path.with_name('preserved-socket.json'));exclusive(path,data)
        elif replacement=='process':
            path=own.proc/'54321/stat';path.write_text(path.read_text().replace('777','888'))
        elif replacement=='placement':(own.proc/'54321/cgroup').write_text('0::/different-supervisor')
        else:
            own.supervisor_socket.rename(own.supervisor_socket.with_name('preserved.sock'))
            endpoint=socket.socket(socket.AF_UNIX);endpoint.bind(str(own.supervisor_socket));own.supervisor_socket.chmod(0o600)
            replacement_sockets.append(endpoint)
        return deepcopy(own.status)
    monkeypatch.setattr(WorkloadClient,'status',status)
    try:
        with pytest.raises(WorkloadBlocked,match='supervisor_.*changed'):resources.postflight(own.proposal)
        assert not (own.context.root/'baseline.json').exists()
    finally:
        for endpoint in replacement_sockets:endpoint.close()
