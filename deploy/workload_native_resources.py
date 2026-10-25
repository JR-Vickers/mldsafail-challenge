"""Read-only installed-host observations for independently authorized controls.

NativeContext supplies the live outer claim and command supervision. This adapter
creates no authority, accepts no reader paths/SQL/tables, and never opens epochs
or signing material. Row bytes stay in host-private command output; receipts carry
only bounded row counts and hashes.
"""
import copy
import json
import re
import threading
from pathlib import Path

from deploy.workload_fixture_resources import Resources
from deploy.workload_installation import exclusive,identity,private
from deploy.workload_release import canonical,digest,regular
from mldsafail.evaluator.native_workload import NativeRuntime,private_json,process_birth,require,values
from mldsafail.evaluator.workload import ResourcePolicy

LIMIT=1024**2
ROW_LIMIT=10000
PGOPTIONS='PGOPTIONS=-c statement_timeout=500 -c lock_timeout=500 -c default_transaction_read_only=on'
TABLE_INVENTORY_QUERY="COPY (SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name) TO STDOUT;"
DATABASE_IDENTITY_QUERY='COPY (SELECT current_database(),current_user,oid FROM pg_database WHERE datname=current_database()) TO STDOUT;'


def table_allowlist():
    from mldsafail.web.models import Base
    result={table.name:tuple(column.name for column in table.primary_key.columns)
            for table in Base.metadata.sorted_tables}
    result['alembic_version']=('version_num',)
    require(result and all(re.fullmatch('[a-z_][a-z0-9_]*',name) and columns and
        all(re.fullmatch('[a-z_][a-z0-9_]*',column) for column in columns) for name,columns in result.items()),
        'native_database_model_allowlist_invalid')
    return dict(sorted(result.items()))


def table_query(name):
    allowed=table_allowlist();require(name in allowed,'native_database_table_not_allowed')
    order=','.join('"'+column+'"' for column in allowed[name])
    return ('COPY (SELECT row_to_json(row_data)::text FROM (SELECT * FROM public."'+name+'" ORDER BY '+order+
            ' LIMIT 10001) AS row_data) TO STDOUT;')


def readonly(query):
    return 'BEGIN TRANSACTION READ ONLY; SET LOCAL statement_timeout = 500; SET LOCAL lock_timeout = 500; '+query+' ROLLBACK;'


class NativeResources(Resources):
    def __init__(self,context):
        from deploy.workload_configuration import materialize,measured_resources
        self.fixture=context;self.root=context.root;self.journal=context.journal;self.cleanup_mode=False
        proposal_raw,proposal=context.proposal();self.proposal=proposal;self.source=proposal['identities']
        require(context.source==self.source and self.source['origin'] in ('local_linux','host_observation'),
                'native_resource_proposal_source_changed')
        self.source_root=str(Path(self.source['resources']['release']['path'])/'bundle')
        require(context.manifest.get('source_root')==self.source_root,'native_resource_frozen_source_root_changed')
        self.lifecycle_journal=context.lifecycle_journal
        self.inspection=context.inspection
        require(type(self.inspection) is dict and self.inspection.get('proposal_sha256')==digest(proposal_raw) and
            self.inspection.get('origin')==self.source['origin'] and type(self.inspection.get('resources')) is dict and
            all(type(self.inspection['resources'].get(role)) is dict and
                all(key in self.inspection['resources'][role] for key in keys) for role,keys in
                (('output',('path','device','inode','mount_id','bytes')),('delegation',('path','device','inode')))),
            'native_resource_installed_observation_missing_or_changed')
        raw,configuration=private(self.source['manifest']['configurations']['native']['path'])
        expected=materialize(self.source,measured_resources(self.source))['native']
        require(raw==expected and configuration==context.native_configuration,'native_resource_configuration_changed')
        NativeRuntime(configuration)  # Structural validation only, no Docker.
        self.configuration=copy.deepcopy(configuration)
        image=context.settings.get('postgres_image')
        require(type(image) is str and re.fullmatch('sha256:[a-f0-9]{64}',image),
                'native_control_postgres_image_fact_missing')
        self.settings=dict(postgres_image=image,daemon_pid_file=configuration['daemon_pid_file'],
                           daemon_executable=configuration['daemon_executable'])
        self.endpoint=list(configuration['docker'])
        require(self.endpoint==['/usr/bin/docker','--host','unix://'+self.source['host']['runtime_identity']['socket_birth']['path']],
                'native_resource_daemon_endpoint_changed')
        self.plan=dict(heavy=configuration['heavy'])
        bindings=[row for row in self.journal.rows if row['event']=='fixture_daemon_bound']
        startup=[row for row in self.lifecycle_journal.rows if row['event']=='fixture_daemon_bound']
        require(len(bindings)<=1 and len(startup)<=1 and
            all(row.get('daemon_id')==self.source['host']['daemon_id'] for row in [*bindings,*startup]) and
            (not bindings or not startup or bindings[0]['observed']==startup[0]['observed']),
            'native_resource_daemon_binding_changed')
        self._local_binding=bool(bindings)
        selected=bindings or startup
        self._daemon_binding=selected[0]['observed'] if selected else None
        self._binding_lock=threading.RLock()
        self._database_binding()

    def input(self,name):
        require(False,'native_resource_runtime_input_forbidden')

    def _database_binding(self):
        row=self.source['rollback']['schema']
        require(set(row)=={'container_id','database','username'} and
            row['container_id']==self.source['retained_services']['database']['id'] and
            re.fullmatch('[a-f0-9]{64}',row['container_id']) and
            all(type(row[key]) is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}',row[key]) for key in ('database','username')),
            'native_retained_database_reference_invalid')
        return row

    def _raw(self,argv,*,seconds=4.65,inner_seconds=.65):
        return Resources.run(self,argv,seconds=seconds,inner_seconds=inner_seconds)

    def _bind(self):
        with self._binding_lock:
            if self._daemon_binding is not None:
                if not self._local_binding:
                    self.check_daemon()
                    self.journal.append('fixture_daemon_bound',observed=self._daemon_binding,daemon_id=self.source['host']['daemon_id'])
                    self._local_binding=True
                return
            executable=Path(self.settings['daemon_executable'])
            require(digest(regular(executable.parent,executable.name)[0])==self.configuration['daemon_sha256'],
                    'native_resource_daemon_executable_changed')
            observed=NativeRuntime(self.configuration,run=self._raw).identity()
            require(observed==self.source['host']['runtime_identity'],'native_resource_runtime_identity_changed')
            actual=self.daemon_birth()
            self.journal.append('fixture_daemon_bound',observed=actual,daemon_id=observed['daemon_id'])
            self._daemon_binding=actual;self._local_binding=True

    def run(self,argv,*,seconds=4.65,inner_seconds=None):
        require(type(seconds) in (int,float) and 0<seconds<=35 and inner_seconds in (None,.65),
                'native_resource_command_deadline_changed')
        require(self.fixture.manifest.get('source_root')==self.source_root,'native_resource_frozen_source_root_changed')
        self._bind()
        return self._raw(argv,seconds=min(4.65,seconds),inner_seconds=.65)

    def _psql(self,query):
        require(query in {TABLE_INVENTORY_QUERY,DATABASE_IDENTITY_QUERY}|{table_query(name) for name in table_allowlist()},
                'native_database_query_not_allowed')
        row=self._database_binding()
        raw=self.docker(['exec','--env',PGOPTIONS,'--user','postgres',row['container_id'],'psql',
            '--no-psqlrc','--quiet','--tuples-only','--no-align','--set','ON_ERROR_STOP=1',
            '--username',row['username'],'--dbname',row['database'],'--command',readonly(query)])
        require(len(raw)<LIMIT and (not raw or raw.endswith(b'\n')),'native_retained_database_output_truncated_or_capped')
        return raw

    def _retained_database(self):
        expected=self.source['retained_services']['database']
        rows=json.loads(self.docker(['inspect',expected['id']]))
        require(type(rows) is list and len(rows)==1,'native_retained_database_inspection_incomplete')
        row=rows[0]
        observed=dict(id=row['Id'],image=row['Image'],started_at=row['State']['StartedAt'],running=row['State']['Running'])
        require(observed==expected,'native_retained_database_container_changed')
        return observed

    def fingerprint(self,source):
        from deploy.workload_installed import observation_runner,schema_fingerprint
        require(source==self.source,'native_retained_database_source_changed')
        row=self._database_binding();container=self._retained_database()
        expected=[*self.endpoint,'exec','--user','postgres',row['container_id'],'pg_dump','--schema-only','--no-owner',
                  '--no-privileges','--username',row['username'],'--dbname',row['database']]
        def schema_reader(argv):
            require(argv==expected,'native_retained_schema_reader_changed')
            raw=self.run([*self.endpoint,'exec','--env',PGOPTIONS,*argv[len(self.endpoint)+1:]])
            require(len(raw)<LIMIT,'native_retained_database_output_truncated_or_capped')
            return raw
        with observation_runner(schema_reader):schema=schema_fingerprint(source)
        require(schema==source['rollback']['schema_sha256']==source['rollback']['installed_schema_sha256'],
                'native_retained_database_schema_changed')
        inventory=self._psql(TABLE_INVENTORY_QUERY)
        tables=inventory.decode('ascii').splitlines();allowed=table_allowlist()
        require(tables==list(allowed),'native_retained_database_table_inventory_incomplete_or_unknown')
        identity_raw=self._psql(DATABASE_IDENTITY_QUERY)
        fields=identity_raw.decode('ascii').rstrip('\n').split('\t')
        require(len(fields)==3 and fields[:2]==[row['database'],row['username']] and fields[2].isdecimal() and int(fields[2])>0,
                'native_retained_database_identity_changed')
        fingerprints={}
        for name in allowed:
            raw=self._psql(table_query(name));count=len(raw.splitlines())
            require(count<=ROW_LIMIT,'native_retained_database_row_limit_exceeded')
            fingerprints[name]=dict(rows=count,sha256=digest(raw))
        require(self._retained_database()==container,'native_retained_database_container_changed')
        return dict(schema_sha256=schema,identity=dict(row,oid=int(fields[2])),container=container,tables=fingerprints,
                    data_sha256=digest(canonical(fingerprints)))

    def _supervisor(self):
        from mldsafail.evaluator.workload_client import WorkloadClient
        source=self.source;path=Path(source['resources']['socket']['path'])
        record=private_json(path.parent/'socket.json');observed=identity(path);process=record['process']
        require(observed.get('mode')==0o600 and observed.get('uid')==source['host']['uid'] and
            all(observed.get(key)==record.get(key) for key in ('path','device','inode')) and
            process_birth(process['pid'])==process and Path('/proc/'+str(process['pid'])).stat().st_uid==source['host']['uid'],
            'native_resource_supervisor_birth_changed')
        main=self.run(['/usr/bin/systemctl','--user','show','mldsafail-workload-supervisor.service','--property=MainPID','--value'])
        membership=Path('/proc/'+str(process['pid'])+'/cgroup').read_text().strip()
        require(main.strip()==str(process['pid']).encode() and membership.startswith('0::/') and
            not Path('/sys/fs/cgroup'+membership[3:]).is_relative_to(source['installation']['heavy_path']),
            'native_resource_supervisor_placement_changed')
        transition=getattr(self.fixture,'verify_supervisor_transition',None)
        require(callable(transition),'native_resource_supervisor_transition_observer_missing')
        transition(record,observed)
        state=WorkloadClient(str(path),self.root/'supervisor-inspection').status()
        require(state and state.get('paused') is True and state.get('phase') in ('cleaned','complete') and
            type(state.get('request_counts')) is dict and type(state['request_counts'].get('intent')) is int and
            state['request_counts']['intent']==0 and all(type(state.get(key)) is int and state[key]==0
                for key in ('inflight_resumes','inflight_launches')),
            'native_resource_supervisor_not_paused_or_transaction_pending')
        self.journal.append('native_control_supervisor_observed',process=process,socket=observed,
                            phase=state['phase'],paused=True)
        return True

    def postflight(self,proposal):
        from deploy.workload_installed import retained,scheduling,mount,observation_runner
        require(proposal==self.proposal,'native_resource_postflight_proposal_changed')
        with observation_runner(self.run):
            services=retained(self.source)
            require(services==self.source['retained_services'],'native_resource_retained_service_changed')
            schedule=scheduling(proposal)
            output_path=self.source['resources']['output']['path'];output=dict(identity(output_path),**mount(output_path))
            require(output['filesystem']==self.source['resources']['output']['filesystem'] and
                set(output['mount_options'])>={'noexec','nosuid','nodev'},'native_resource_output_enforcement_changed')
            expected_output=self.inspection['resources']['output']
            require(all(output.get(key)==expected_output[key] for key in ('path','device','inode','mount_id')),
                    'native_resource_output_birth_or_mount_changed')
            bounded=NativeRuntime(self.configuration).output_mount(ResourcePolicy())
            require(bounded['bytes']<=expected_output['bytes'],'native_resource_output_capacity_changed')
            output['bytes']=bounded['bytes']
            require(all(self.configuration['heavy_birth'].get(key)==self.inspection['resources']['delegation'][key]
                for key in ('path','device','inode')),'native_resource_heavy_birth_changed')
            NativeRuntime(self.configuration).domains()
            require(values(Path(self.configuration['heavy'])/'cgroup.events')['populated']==0,
                    'native_resource_heavy_descendants_present')
            require(self._supervisor(),'native_resource_supervisor_not_paused')
            database=self.fingerprint(self.source)
            require(retained(self.source)==services,'native_resource_retained_service_changed')
        result=dict(verified=True,retained_services=services,database=database,output=output,
                    scheduling=schedule,supervisor_paused=True,heavy_empty=True)
        baseline_path=self.root/'baseline.json'
        if baseline_path.exists() or baseline_path.is_symlink():
            acknowledgements=[row for row in self.lifecycle_journal.rows if row['event']=='native_control_baseline']
            require(len(acknowledgements)==1 and acknowledgements[0].get('observed')==identity(baseline_path),
                    'native_resource_baseline_unacknowledged_or_replaced')
            require(private(baseline_path)[1]==result,'native_resource_retained_postflight_changed')
        else:
            require(getattr(self.fixture,'baseline_capture_allowed',False) is True,
                    'native_resource_baseline_capture_not_authorized')
            exclusive(baseline_path,canonical(result))
            self.lifecycle_journal.append('native_control_baseline',observed=identity(baseline_path))
        return result
