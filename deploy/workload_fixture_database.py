"""A single generation-owned PostgreSQL service for fixed fixture controls.

It is distinct from every retained database and from the computational scope.
Only synthetic rows are written. No arbitrary database URL is accepted. The
container has a loopback-only published port, private generated credentials,
finite resources and independently acknowledged immutable births.
"""
import json
import re
from pathlib import Path
import secrets
import time

from deploy.workload_installation import exclusive,private,identity
from deploy.workload_release import canonical
from mldsafail.evaluator.native_workload import require

LABEL='org.mldsafail.fixture-control-database'


class OwnedDatabase:
    def __init__(self,fixture,resources,native,root,token,deadline):
        from scripts.workload_fixture_worker import inherited_lock
        inherited_lock(fixture.root,fixture.lock_fd);fixture.require_target()
        from scripts.rehearse_workload_installation_fixture import component_review
        component_review(fixture)
        require(len(token)==32 and all(c in '0123456789abcdef' for c in token),'fixture_database_token_invalid')
        self.fixture,self.resources,self.native=fixture,resources,native
        control_root=Path(root).absolute()
        require(control_root==fixture.root/'artifacts'/('control-'+token) and
            not any(path.is_symlink() for path in (control_root,*control_root.parents)),
            'fixture_database_namespace_changed')
        intent=private(control_root/'intent.json')[1]
        require(intent.get('generation')==fixture.manifest['generation'] and
            intent.get('manifest_sha256')==fixture.binding and intent.get('token')==token,
            'fixture_database_context_changed')
        self.root=control_root/'database';self.root.mkdir(mode=0o700)
        self.token,self.deadline=token,deadline;self.identifier=None;self.binding=None;self.engines=[];self.databases=[]
        self.name='mlwe-fixture-database-'+token
        self.image=resources.settings['postgres_image'];self.password=secrets.token_hex(32)
        require(type(self.image) is str and re.fullmatch('sha256:[a-f0-9]{64}',self.image) is not None,
            'fixture_database_image_not_immutable')
        self.credentials_file=self.root/'postgres.env'
        exclusive(self.credentials_file,('POSTGRES_DB=mldsafail_acceptance_'+token+'\nPOSTGRES_PASSWORD='+self.password+'\n').encode())
        exclusive(self.root/'intent.json',canonical(dict(generation=fixture.manifest['generation'],
            manifest_sha256=fixture.binding,name=self.name,image=self.image,token=token)))
    def call(self,args):
        left=self.deadline-time.monotonic();require(left>0,'fixture_database_deadline_expired')
        return self.resources.docker(args,seconds=min(4.65,left),inner_seconds=.65)
    def start(self):
        actual=json.loads(self.call(['image','inspect',self.image]))[0]
        require(actual['Id']==self.image,'fixture_database_image_changed')
        self.identifier=self.call(['create','--name',self.name,'--label',LABEL+'='+self.token,
            '--label','org.mldsafail.fixture-generation='+self.fixture.manifest['generation'],
            '--network=bridge','--publish','127.0.0.1::5432','--read-only','--restart=no','--log-driver=none',
            '--cpus=.25','--memory=128m','--memory-swap=128m','--pids-limit=32',
            '--tmpfs','/var/lib/postgresql/data:rw,size=64m','--tmpfs','/var/run/postgresql:rw,size=8m',
            '--tmpfs','/tmp:rw,size=8m','--env-file',str(self.credentials_file),self.image,
            'postgres','-c','shared_buffers=8MB','-c','max_connections=8']).decode().strip()
        require(len(self.identifier)==64 and all(c in '0123456789abcdef' for c in self.identifier),
            'fixture_database_create_ack_ambiguous')
        row=json.loads(self.call(['inspect',self.identifier]))[0]
        self.binding=dict(id=row['Id'],created_at=row['Created'],started_at=None,image=row['Image'])
        self.inspect(require_started=False)
        exclusive(self.root/'created.json',canonical(self.binding))
        self.fixture.journal.append('fixture_control_database_created',token=self.token,
            observed=identity(self.root/'created.json'),binding=dict(self.binding))
        self.call(['start',self.identifier])
        row=self.inspect(require_started=False);require(row['State']['Running'],'fixture_database_start_unverified')
        self.binding['started_at']=row['State']['StartedAt'];exclusive(self.root/'started.json',canonical(self.binding))
        self.fixture.journal.append('fixture_control_database_started',token=self.token,
            observed=identity(self.root/'started.json'),binding=dict(self.binding))
        ports=row['NetworkSettings']['Ports'].get('5432/tcp')
        require(type(ports) is list and len(ports)==1 and ports[0]['HostIp']=='127.0.0.1' and
            ports[0]['HostPort'].isdecimal(),'fixture_database_port_not_loopback')
        self.port=int(ports[0]['HostPort'])
        require(0<self.port<65536,'fixture_database_port_invalid')
        self.native.config['retained_services']['fixture_control_database']=self.identifier
        while True:
            self.inspect()
            try:
                with self.connect() as connection:
                    database_identity=connection.execute('SELECT current_database(),(SELECT oid FROM pg_database WHERE datname=current_database())').fetchone()
                self.databases.append(dict(name=database_identity[0],oid=database_identity[1]))
                exclusive(self.root/'database.json',canonical(dict(container=self.binding,databases=self.databases)))
                break
            except self.psycopg.OperationalError:
                require(time.monotonic()<self.deadline,'fixture_database_startup_expired');time.sleep(.05)
        return self
    @property
    def psycopg(self):
        import psycopg
        return psycopg
    def inspect(self,*,require_started=True):
        require(self.identifier is not None and self.binding is not None,'fixture_database_unacknowledged_preserve')
        rows=json.loads(self.call(['inspect',self.identifier]));require(len(rows)==1,'fixture_database_inspection_incomplete')
        row=rows[0];labels=row['Config'].get('Labels',{})
        require(row['Id']==self.identifier==self.binding['id'] and row['Name']=='/'+self.name and
            row['Image']==self.image==self.binding['image'] and row['Created']==self.binding['created_at'] and
            labels.get(LABEL)==self.token and labels.get('org.mldsafail.fixture-generation')==self.fixture.manifest['generation'] and
            row['HostConfig']['NetworkMode']=='bridge' and row['HostConfig']['ReadonlyRootfs'] and
            row['HostConfig']['Memory']==128*1024**2 and row['HostConfig']['MemorySwap']==128*1024**2 and
            row['HostConfig']['PidsLimit']==32 and row['HostConfig']['RestartPolicy']['Name']=='no',
            'fixture_database_birth_or_policy_changed_preserve')
        if require_started:
            require(row['State']['Running'] and row['State']['StartedAt']==self.binding['started_at'],
                'fixture_database_restart_changed_preserve')
        return row
    def connect(self,index=0):
        self.inspect();name='mldsafail_acceptance_'+self.token+('_1' if index else '')
        require(index in (0,1),'fixture_database_index_invalid')
        connection=self.psycopg.connect(host='127.0.0.1',port=self.port,dbname=name,user='postgres',password=self.password,
            autocommit=True,connect_timeout=1,options='-c statement_timeout=500 -c lock_timeout=500')
        try:
            actual=connection.execute('SELECT current_database(),(SELECT oid FROM pg_database WHERE datname=current_database())').fetchone()
            expected=next((row for row in self.databases if row['name']==name),None)
            require(actual[0]==name and (expected is None and not self.databases and index==0 or
                expected is not None and actual[1]==expected['oid']),'fixture_database_oid_changed_preserve')
        except BaseException:
            connection.close();raise
        return connection
    def engine(self,index=0):
        from sqlalchemy import create_engine,inspect,event
        from sqlalchemy.engine import URL
        require(index in (0,1),'fixture_database_index_invalid')
        self.inspect()
        if index==1:
            from psycopg import sql
            name='mldsafail_acceptance_'+self.token+'_1'
            require(not any(row['name']==name for row in self.databases),'fixture_database_already_created')
            with self.connect() as connection:
                connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
                oid=connection.execute('SELECT oid FROM pg_database WHERE datname=%s',(name,)).fetchone()[0]
            self.databases.append(dict(name=name,oid=oid));exclusive(self.root/'second-database.json',canonical(self.databases[-1]))
        name='mldsafail_acceptance_'+self.token+('_1' if index else '')
        engine=create_engine(URL.create('postgresql+psycopg',username='postgres',password=self.password,
            host='127.0.0.1',port=self.port,database=name),connect_args={'connect_timeout':1,'options':'-c statement_timeout=500 -c lock_timeout=500'})
        self.engines.append(engine)
        expected=next(row for row in self.databases if row['name']==name)
        @event.listens_for(engine,'connect')
        def verify_database(connection,record):
            self.inspect()
            actual=connection.execute('SELECT current_database(),(SELECT oid FROM pg_database WHERE datname=current_database())').fetchone()
            connection.rollback()
            require(actual==(expected['name'],expected['oid']),'fixture_database_oid_changed_preserve')
        require(not inspect(engine).get_table_names(),'fixture_database_not_empty_preserve')
        return engine
    def cleanup(self,deadline):
        for engine in self.engines:engine.dispose()
        self.deadline=deadline
        # A missing create/start acknowledgement receives no name/label adoption.
        # Preserve the intent for fixture reconciliation instead of guessing.
        for event,name in (('fixture_control_database_created','created.json'),('fixture_control_database_started','started.json')):
            records=[row for row in self.fixture.journal.rows if row['event']==event and row.get('token')==self.token]
            path=self.root/name
            require(len(records)==1 and records[0].get('observed')==identity(path) and
                records[0].get('binding')==private(path)[1], 'fixture_database_receipt_unacknowledged_or_replaced')
        row=self.inspect(require_started=self.binding is not None and self.binding.get('started_at') is not None)
        require(self.binding.get('started_at') is not None,'fixture_database_start_ack_missing_preserve')
        self.call(['rm','-f',self.identifier])
        remaining=self.call(['ps','-aq','--no-trunc','--filter','label='+LABEL+'='+self.token]).decode().split()
        require(not remaining,'fixture_database_cleanup_unverified')
        self.native.config['retained_services'].pop('fixture_control_database',None)
        receipt=dict(binding=self.binding,databases=self.databases,remaining=remaining,
            before_state=row['State'],retained_database_touched=False)
        exclusive(self.root/'cleanup.json',canonical(receipt));return receipt
