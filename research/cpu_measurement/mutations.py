"""Resolve guardian receipts or stop the exact dedicated daemon epoch first."""
import base64
import json
import os
from pathlib import Path
import re
import stat
from deploy import owned_client, owned_daemon


def receipt(directory, name, *, operation, epoch):
    if not isinstance(name,str) or Path(name).name!=name:
        raise RuntimeError('Invalid guardian receipt reference')
    path=Path(directory)/name
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077: raise RuntimeError('Private guardian receipt required')
        data=stream.read(3*1024*1024+1)
    if len(data)>3*1024*1024: raise RuntimeError('Guardian receipt exceeds cap')
    value=json.loads(data)
    if not isinstance(value,dict): raise RuntimeError('Guardian receipt must be an object')
    if value.get('schema')!='mldsafail.cpu-mutation-receipt.v1' or value.get('operation')!=operation or value.get('daemon_epoch')!=epoch or value.get('acknowledged') is not True or value.get('returncode')!=0 or value.get('cleanup_errors')!=[]:
        raise RuntimeError('Mutation acknowledgement is incomplete')
    encoded=value.get('raw_stdout_base64')
    if not isinstance(encoded,str) or len(encoded)>1400000: raise RuntimeError('Invalid bounded CLI acknowledgement')
    stderr=value.get('raw_stderr_base64')
    if not isinstance(stderr,str) or len(stderr)>1400000: raise RuntimeError('Invalid bounded stderr acknowledgement')
    if len(base64.b64decode(stderr,validate=True))>1024*1024: raise RuntimeError('Stderr acknowledgement exceeds cap')
    output=base64.b64decode(encoded,validate=True).strip()
    if not re.fullmatch(b'[0-9a-f]{64}',output) or value.get('container_id')!=output.decode():
        raise RuntimeError('Immutable container acknowledgement differs from raw response')
    return value


def resolve(journal, directory, parent):
    clients={entry['id']:entry for entry in journal['mutations'] if entry['operation']=='host_client_domain'}
    released={entry['id'] for entry in journal['mutations'] if entry['operation']=='host_client_release_intent'}
    repaired=[entry['manifest'] for entry in journal['mutations'] if entry['operation']=='daemon_epoch_repaired']
    if repaired:
        owned_daemon.verify_environment(repaired[-1],measurement_parent=parent)
        return dict(errors=[],daemon_barrier=None,new_manifest=repaired[-1])
    manifests=[entry['manifest'] for entry in journal['mutations'] if entry['operation']=='dedicated_daemon_verified']
    if not manifests: return dict(errors=[],daemon_barrier=None)
    manifest=manifests[-1]
    uncertain=[]
    acknowledged_ids=[]
    for entry in clients.values():
        if entry['id'] not in released or entry.get('phase')=='attach': continue
        if entry.get('phase') not in {'create','start'}:
            uncertain.append(entry['id'])
            continue
        try:
            value=receipt(directory,entry.get('receipt_file'),operation=entry['phase'],epoch=manifest['epoch'])
            if entry['phase']=='create': acknowledged_ids.append(value['container_id'])
            elif value['container_id'] not in acknowledged_ids:
                raise RuntimeError('Start acknowledgement has no retained create identity')
        except (OSError,ValueError,RuntimeError): uncertain.append(entry['id'])
    if not uncertain: return dict(errors=[],daemon_barrier=None)
    worker=owned_client.domain_identity(parent)
    if (worker['device'],worker['inode'])!=(journal['parent_device'],journal['parent_inode']):
        raise RuntimeError('Worker parent identity changed before daemon barrier')
    barrier=owned_daemon.shutdown_barrier(manifest,worker_domains=[worker],
            evidence_directory=directory,attempt_id=journal['generation'])
    errors=[]
    if not barrier['shutdown_proven']: errors.extend(barrier['errors'])
    # Never cancel a possibly submitted guardian BEFORE kernel-proven shutdown.
    if barrier['shutdown_proven']:
        for entry in clients.values():
            try: owned_client.stop(entry)
            except BaseException as error: errors.append(dict(step='post_barrier_client_stop',error=repr(error)))
    refreshed=None
    if not errors:
        aliases=[value for value in (os.environ.get('MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'),os.environ.get('MLDSAFAIL_CPU_DAEMON_MANIFEST')) if value]
        if len(set(aliases))!=1: raise RuntimeError('One explicit manifest path required for restart')
        try:
            refreshed=owned_daemon.restart_and_refresh(manifest,barrier,manifest_path=aliases[0],
                    client_entries=list(clients.values()),evidence_directory=directory,attempt_id=journal['generation'])
        except BaseException as error: errors.append(dict(step='dedicated_daemon_restart',error=repr(error)))
    return dict(errors=errors,daemon_barrier=barrier,new_manifest=refreshed,uncertain_clients=uncertain)
