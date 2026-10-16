"""Fresh tiny logical database dump/restore under dedicated owned daemon authority."""
import os
from deploy import native_recovery_powerloss as fixture
from deploy.recovery_journal import Journal, atomic_json


def callback(driver,config,data):
    root=driver.path.parent/'synthetic-restoration';root.mkdir(mode=0o700)
    operation=Journal(root/'operation.json',{})
    original=None
    result=dict(schema='mldsafail.synthetic-database-restoration.v1',passed=False,
        native_executed=False,synthetic_only=True,actual_offhost_storage=False,
        owner_password_custody_verified=False,private_epoch_restored=False)
    try:
        source,call=fixture.database(operation,config,'synthetic-source-'+data['id'])
        statement=('CREATE TABLE synthetic_identity(id integer PRIMARY KEY,payload text NOT NULL);'
            "INSERT INTO synthetic_identity VALUES (1,'"+fixture.payload().replace("'","''")+"');")
        call(['docker','exec',source,'psql','-U','postgres','-v','ON_ERROR_STOP=1','-c',statement])
        content=call(['docker','exec',source,'pg_dump','-U','postgres','--format=custom','--no-owner','postgres'])
        if not content or len(content)>8*1024*1024:raise ValueError('Tiny nonempty synthetic dump required')
        dump=root/'synthetic.dump'
        descriptor=os.open(dump,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o400);os.fsync(stream.fileno())
        target,target_call=fixture.database(operation,config,'synthetic-target-'+data['id'])
        with dump.open('rb') as stream:
            operation.command(['docker','exec','-i',target,'pg_restore','-U','postgres','--dbname=postgres',
                '--no-owner','--no-privileges','--exit-on-error'],daemon_manifest_path=os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'],
                stdin=stream,capture_output=True,check=True,timeout=120)
        value=target_call(['docker','exec',target,'psql','-U','postgres','-At','-c',
            'SELECT payload FROM synthetic_identity WHERE id=1']).decode().strip()
        schema=target_call(['docker','exec',target,'psql','-U','postgres','-At','-c',
            "SELECT column_name||':'||data_type FROM information_schema.columns WHERE table_name='synthetic_identity' ORDER BY ordinal_position"]).decode().strip()
        if value!=fixture.payload() or schema!='id:integer\npayload:text':
            raise ValueError('Fresh logical restoration payload/schema mismatch')
        result.update(native_executed=True,dump_sha256=fixture.digest(dump),schema_preserved=True,
            public_fixture_preserved=True,distinct_database_containers=source!=target)
        if source==target:raise ValueError('Fresh restoration target required')
    except BaseException as error:original=error
    finally:
        try:operation.cleanup()
        except BaseException as error:
            if original is None:original=error
            else:original.add_note('Independent restoration cleanup: '+type(error).__name__)
        result['cleanup_complete']=operation.data.get('cleanup_complete') is True
        result['passed']=original is None and result['cleanup_complete']
        try:atomic_json(root/'result.json',result)
        except BaseException as error:
            result['passed']=False
            if original is None:original=error
            else:original.add_note('Restoration publication: '+type(error).__name__)
            try:atomic_json(root/'result.json',result)
            except BaseException as retry:original.add_note('Negative publication: '+type(retry).__name__)
        if original is not None:raise original
    return fixture.receipt(config,[str(root/'result.json'),str(root/'operation.json')])
