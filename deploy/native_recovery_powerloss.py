"""Disposable changed-boot recovery: immutable tiny database dump, fresh daemon.

Never re-register old Docker roots, old cgroup authority, or benchmark costs.
The first callback deliberately pauses for host-controlled VM hard power loss.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from deploy import owned_daemon, owned_client
from deploy.recovery_journal import Journal, atomic_json
from research.cpu_measurement import native_driver


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def payload():
    from mldsafail.benchmark_v050.generator import generate_mlwe
    public=generate_mlwe('small',0,1).public.to_dict()
    return json.dumps({'scope':'synthetic-recovery-only','public_instance':public},sort_keys=True,separators=(',',':'))


def receipt(config,refs):
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
                evidence_refs=refs,source_sha256=config['acceptance_source_sha256'])


def database(operation,config,name):
    selected=os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']
    image=config['image']
    operation.container(name,image,daemon_manifest_path=selected)
    def call(argv,**kwargs):
        return operation.command(argv,daemon_manifest_path=selected,capture_output=True,check=True,timeout=90,**kwargs).stdout
    info=json.loads(call(['docker','image','inspect',image]))[0]
    if set(info.get('Config',{}).get('Volumes') or {})-{'/var/lib/postgresql/data'}:
        raise ValueError('Unaccounted image volume forbidden')
    identifier=call(['docker','run','-d','--name',name,'--label','org.mldsafail.recovery='+name,
        '--network','none','--memory','256m','--pids-limit','64',
        '--tmpfs','/var/lib/postgresql/data:size=128m','-e','POSTGRES_HOST_AUTH_METHOD=trust',image]).decode().strip()
    deadline=time.monotonic()+60
    while True:
        ready=operation.command(['docker','exec',identifier,'pg_isready','-U','postgres'],
            daemon_manifest_path=selected,capture_output=True,check=False,timeout=10)
        if ready.returncode==0:break
        if time.monotonic()>deadline:raise TimeoutError('Tiny synthetic PostgreSQL not ready')
        time.sleep(.2)
    return identifier,call


def prepare_callback(driver,config,data):
    root=Path(config['state_root']).parent
    operation=Journal(root/'pre-operation.json',{})
    try:
        name='powerloss-db-'+data['id']
        identifier,call=database(operation,config,name)
        statement=('CREATE TABLE synthetic_identity(id integer PRIMARY KEY,payload text NOT NULL);'
                   'INSERT INTO synthetic_identity VALUES (1,\''+payload().replace("'","''")+'\');')
        call(['docker','exec',identifier,'psql','-U','postgres','-v','ON_ERROR_STOP=1','-c',statement])
        dump=root/'immutable-synthetic.dump'
        content=call(['docker','exec',identifier,'pg_dump','-U','postgres','--format=custom','--no-owner','postgres'])
        if len(content)>8*1024*1024:raise ValueError('Synthetic dump cap exceeded')
        descriptor=os.open(dump,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        selected=os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']
        manifest=owned_daemon.load_manifest(selected)
        operation.services([],{'database':True},{'database':identifier},daemon_manifest_path=selected)
        call(['docker','stop',identifier])
        boundary=dict(schema='mldsafail.synthetic-powerloss-boundary.v1',
            boot_id=owned_client.boot_id(),daemon_manifest=manifest,daemon_manifest_path=selected,
            dump_sha256=digest(dump),payload_sha256=hashlib.sha256(payload().encode()).hexdigest(),
            postgres_image=config['image'],source_commit=config['source_commit'],container_id=identifier,
            postgres_version=call(['docker','image','inspect',config['image']]).decode(),synthetic_only=True)
        atomic_json(root/'powerloss-boundary.json',boundary)
        # No successful first-phase acceptance receipt: host must SIGKILL this VM.
        while True:time.sleep(1)
    except BaseException as original:
        try:operation.cleanup()
        except BaseException as error:
            original.add_note('Independent preparation cleanup failed: '+type(error).__name__)
        raise


def validate_reboot(boundary):
    if boundary.get('schema')!='mldsafail.synthetic-powerloss-boundary.v1' or boundary.get('synthetic_only') is not True:
        raise ValueError('Exact synthetic boundary required')
    if boundary['boot_id']==owned_client.boot_id():raise ValueError('Actual changed guest boot required')
    old=boundary['daemon_manifest']
    state=owned_daemon._unit(old['unit'])
    if state['unit_fragment_sha256']!=old['unit_fragment_sha256'] or state['ActiveState'] not in {'inactive','failed'}:
        raise ValueError('Exact old dedicated unit must remain inactive after reboot')
    if old['leader']['boot_id']!=boundary['boot_id']:raise ValueError('Old daemon boot receipt mismatch')
    return dict(old_kernel_retired_by_changed_boot=True,old_unit_inactive=True,old_roots_reused=False,
                previous_boot=boundary['boot_id'],new_boot=owned_client.boot_id())


def restore_callback(driver,config,data):
    root=Path(config['state_root']).parent
    boundary=owned_daemon.read_private_json(root/'powerloss-boundary.json')
    reboot=validate_reboot(boundary)
    if boundary['postgres_image']!=config['image'] or digest(root/'immutable-synthetic.dump')!=boundary['dump_sha256']:
        raise ValueError('Immutable pre-power-loss dump/image changed')
    current=owned_daemon.load_manifest()
    if (current['epoch']==boundary['daemon_manifest']['epoch'] or
        current['roots']['root_dir']['path']==boundary['daemon_manifest']['roots']['root_dir']['path']):
        raise ValueError('Fresh postboot daemon and roots required')
    # Old service authority must stay fenced rather than signaling reused PIDs.
    old_operation=Journal(root/'pre-operation.json',{})
    before_clients=len(old_operation.data.get('clients',[]))
    from deploy.recovery_daemon import scope
    try:
        with scope(boundary['daemon_manifest_path']):
            raise AssertionError('Stale scope unexpectedly admitted')
    except ValueError as error:
        if str(error)!='Recovery operator domain differs from provisioned daemon ownership':raise
    try:old_operation.cleanup()
    except RuntimeError as error:
        expected={'container:'+item['name'] for item in old_operation.data['containers']}
        expected.update('service:'+role for role in old_operation.data.get('services',{}))
        if (str(error)!='Recovery cleanup incomplete' or
            set(old_operation.data.get('cleanup_errors',[]))!=expected or
            len(old_operation.data.get('clients',[]))!=before_clients):
            raise ValueError('Unrelated old cleanup failure cannot prove stale authority') from error
    else:raise ValueError('Stale preboot operator authority unexpectedly accepted')
    atomic_json(root/'old-authority-fenced.json',old_operation.data)
    operation=Journal(root/'post-operation.json',{})
    original=None
    try:
        identifier,call=database(operation,config,'postboot-db-'+data['id'])
        with (root/'immutable-synthetic.dump').open('rb') as stream:
            operation.command(['docker','exec','-i',identifier,'pg_restore','-U','postgres','--dbname=postgres',
                '--no-owner','--no-privileges','--exit-on-error'],daemon_manifest_path=os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'],
                stdin=stream,capture_output=True,check=True,timeout=120)
        value=call(['docker','exec',identifier,'psql','-U','postgres','-At','-c',
            "SELECT payload FROM synthetic_identity WHERE id=1"]).decode().strip()
        schema=call(['docker','exec',identifier,'psql','-U','postgres','-At','-c',
            "SELECT column_name||':'||data_type FROM information_schema.columns WHERE table_name='synthetic_identity' ORDER BY ordinal_position"]).decode().strip()
        if hashlib.sha256(value.encode()).hexdigest()!=boundary['payload_sha256'] or value!=payload() or schema!='id:integer\npayload:text':
            raise ValueError('Restored synthetic identity, public fixture, or schema differs')
        result=dict(schema='mldsafail.synthetic-powerloss-restoration.v1',synthetic_only=True,
            actual_hard_power_loss=True,logical_database_identity_preserved=True,schema_preserved=True,
            public_fixture_preserved=True,dump_sha256=boundary['dump_sha256'],**reboot)
        atomic_json(root/'restoration-result.json',result)
    except BaseException as error:original=error;raise
    finally:
        try:operation.cleanup()
        except BaseException as error:
            if original is None:raise
            original.add_note('Independent postboot database cleanup failed: '+type(error).__name__)
    return receipt(config,['powerloss-boundary.json','old-authority-fenced.json','restoration-result.json'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--phase',choices=['prepare','restore'],required=True)
    args=parser.parse_args()
    config=owned_daemon.read_private_json(args.config)
    callback=prepare_callback if args.phase=='prepare' else restore_callback
    result=native_driver.execute(config,Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')
    print(json.dumps({'native_executed':True,'passed':result['native_acceptance_passed']}))


if __name__=='__main__':
    os.umask(0o077)
    main()
