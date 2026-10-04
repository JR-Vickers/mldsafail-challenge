"""Actual SSH response-loss callback; owned unit survives the dropped transport."""
import argparse
import os
from pathlib import Path
import time
from deploy import native_recovery_powerloss as fixture, owned_client, owned_daemon
from deploy.recovery_journal import Journal, atomic_json
from research.cpu_measurement import native_driver


def validate_reconnection(proof,boot,pid,owner_identity):
    if (not isinstance(proof,dict) or set(proof)!={'actual_ssh_drop','same_boot_id','same_owner_pid','owner_identity'}
        or proof['actual_ssh_drop'] is not True or proof['same_boot_id']!=boot
        or type(proof['same_owner_pid']) is not int or proof['same_owner_pid']!=pid
        or proof['owner_identity']!=owner_identity):
        raise ValueError('Exact live owner and boot reconnection proof required')


def callback(driver,config,data):
    root=driver.path.parent
    operation=Journal(root/'transport-operation.json',{})
    result=dict(schema='mldsafail.native-transport-restoration.v1',passed=False,
        synthetic_only=True,cleanup_complete=False,actual_transport_drop_required=True)
    original=None
    try:
        identifier,call=fixture.database(operation,config,'transport-db-'+data['id'])
        statement=('CREATE TABLE synthetic_identity(id integer PRIMARY KEY,payload text NOT NULL);'
            "INSERT INTO synthetic_identity VALUES (1,'"+fixture.payload().replace("'","''")+"');")
        call(['docker','exec',identifier,'psql','-U','postgres','-v','ON_ERROR_STOP=1','-c',statement])
        atomic_json(root/'transport-boundary.json',dict(schema='mldsafail.transport-boundary.v1',
            boot_id=owned_client.boot_id(),owner_pid=os.getpid(),owner_identity=owned_client.identity(os.getpid()),container_id=identifier,
            daemon_epoch=owned_daemon.load_manifest()['epoch'],source_commit=config['source_commit']))
        deadline=time.monotonic()+240
        while not (root/'transport-reconnected.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Actual transport reconnection acknowledgement absent')
            time.sleep(.2)
        proof=owned_daemon.read_private_json(root/'transport-reconnected.json')
        validate_reconnection(proof,owned_client.boot_id(),os.getpid(),owned_client.identity(os.getpid()))
        value=call(['docker','exec',identifier,'psql','-U','postgres','-At','-c',
            'SELECT payload FROM synthetic_identity WHERE id=1']).decode().strip()
        if value!=fixture.payload():raise ValueError('Transport-loss fixture data changed')
        operation.cleanup()
        operation.cleanup()  # Actual independently retryable cleanup before retiring owner authority.
        result.update(native_executed=True,repeated_cleanup_passed=True,public_fixture_preserved=True,
            boot_id=owned_client.boot_id(),owner_pid=os.getpid())
    except BaseException as error:original=error
    finally:
        try:operation.cleanup()
        except BaseException as error:
            if original is None:original=error
            else:original.add_note('Independent transport cleanup: '+type(error).__name__)
        result['cleanup_complete']=operation.data.get('cleanup_complete') is True
        result['passed']=original is None and result['cleanup_complete']
        try:atomic_json(root/'transport-result.json',result)
        except BaseException as error:
            result['passed']=False
            if original is None:original=error
            else:original.add_note('Transport publication: '+type(error).__name__)
            try:atomic_json(root/'transport-result.json',result)
            except BaseException as retry:original.add_note('Negative publication: '+type(retry).__name__)
        if original is not None:raise original
    return fixture.receipt(config,[str(root/'transport-result.json'),str(root/'transport-operation.json')])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    fixture.secure_guest_configuration()
    config=owned_daemon.read_private_json(args.config)
    native_driver.execute(config,Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')

if __name__=='__main__':os.umask(0o077);main()
