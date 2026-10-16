"""Retire interrupted disposable job authority, then restore known shared services.

A positive owned-daemon barrier never resolves shared/staging RPC uncertainty.
"""
from pathlib import Path
from contextlib import contextmanager
import threading
import os
from deploy import owned_daemon, owned_client
from deploy.recovery_daemon import _positive

_observations=threading.local()


@contextmanager
def observe_job_journal(expected_path, callback):
    """Durably acknowledge journal publication before trusted command admission."""
    from deploy.recovery_journal import safe_path
    path=safe_path(expected_path)
    previous=getattr(_observations,'current',None)
    _observations.current=(os.getpid(),path,callback)
    try:yield
    finally:_observations.current=previous


def journal_published(path):
    observation=getattr(_observations,'current',None)
    if observation is not None and observation[0]==os.getpid() and Path(path)==observation[1]:
        observation[2]()  # Failure propagates before the caller can issue its RPC.


CONTRACT=('unit','socket','worker_domain','worker_cgroup_parent','provisioning',
          'unit_fragment_sha256','server_version','server_git_commit','daemon_executable_sha256')


def validate_retirement(record,context_key):
    proof=record['terminal_retirement']
    manifest=proof['manifest']
    if not manifest['unit'].startswith('mldsafail-owned-daemon-'):
        raise ValueError('Only disposable operational daemon authority may be retired')
    _positive(proof['barrier'],manifest,proof['attempt_id'])
    current=owned_daemon.load_manifest(proof['manifest_path'])
    if owned_daemon.fingerprint(current)!=owned_daemon.fingerprint(manifest):
        raise ValueError('Retired manifest epoch has changed')
    for domain in (manifest['domain'],manifest['worker_domain']):
        if owned_client.verify_domain({'cgroup':domain}) is not None:
            raise ValueError('Retired kernel domain must be absent')
    context=record['daemon_contexts'][context_key]['manifest']
    if owned_daemon.fingerprint(context)!=context_key or any(context[key]!=manifest[key] for key in CONTRACT):
        raise ValueError('Retired context differs from exact stopped daemon/worker contract')
    for name in ('root_dir','exec_root'):
        if context['roots'][name]!=manifest['roots'][name]:
            raise ValueError('Persistent retired root identity changed')
    old=context['roots']['rootless_state'];new=manifest['roots']['rootless_state']
    if any(old[key]!=new[key] for key in ('path','uid','mode')):
        raise ValueError('Transient retired root contract changed')
    return proof


def terminal_job_cleanup(job,config,driver_state):
    """Call under activation serialization after exact terminal driver cleanup."""
    from deploy.recovery_journal import Journal,atomic_json,safe_path
    if job=='daily-recovery':
        path=safe_path(Path(config['recovery_root'])/'journals/operation.json')
    elif job=='recovery-check':
        path=safe_path(Path(config['backup_state']).parent/'.mldsafail-restic-operation/operation.json')
    else:raise ValueError('Fixed recovery job required')
    if not path.exists():
        raise ValueError('Expected interrupted job journal is missing; authority remains fenced')
    operation=Journal(path,config)
    # Terminal reconciliation must never restart an old backend, even if its
    # proof is corrupt. Known clients and shared service restoration still run.
    operation.data['terminal_no_restart']=True
    try:
        return _retire(operation,job,path,driver_state)
    except BaseException as original:
        try:operation.cleanup()
        except BaseException as error:original.add_note('Independent terminal cleanup: '+type(error).__name__)
        raise


def _retire(operation,job,path,driver_state):
    from deploy.recovery_journal import atomic_json
    cleanup=driver_state['cleanup']
    if (cleanup.get('schema')!='mldsafail.cpu-native-driver-cleanup.v1' or
        cleanup.get('id')!=driver_state['id'] or cleanup.get('cleanup_complete') is not True or cleanup.get('errors')!=[]):
        raise ValueError('Complete exact terminal driver cleanup required')
    manifest=owned_daemon.load_manifest(driver_state['manifest_path'])
    barrier=cleanup['daemon_barrier']
    _positive(barrier,manifest,driver_state['id'])
    if driver_state.get('daemon_kind')!='owned':raise ValueError('Operational owned daemon required')
    proof={'manifest':manifest,'manifest_path':driver_state['manifest_path'],'barrier':barrier,'attempt_id':driver_state['id']}
    operation.data['terminal_retirement']=proof
    errors=[]
    contexts=operation.data.get('daemon_contexts',{})
    if not isinstance(contexts,dict):contexts={};errors.append('corrupt_context_authority')
    retired=set()
    for key in contexts:
        try:validate_retirement(operation.data,key);retired.add(key)
        except BaseException as error:errors.append('context:'+str(key)+':'+type(error).__name__)
    for item in operation.data.get('containers',[]) if isinstance(operation.data.get('containers',[]),list) else []:
        if isinstance(item,dict) and item.get('daemon_context') in retired:
            item['retired_by_terminal_barrier']=True
    for item in operation.data.get('daemon_mutations',[]) if isinstance(operation.data.get('daemon_mutations',[]),list) else []:
        if isinstance(item,dict) and item.get('daemon_context') in retired:
            item['resolved_by_barrier']={'terminal_retirement':True,'daemon_epoch':manifest['epoch'],
                                         'attempt_id':driver_state['id']}
    # Publish before cleanup; never restart the already-stopped private backend.
    original=None
    try:operation.save('terminal disposable authority retirement')
    except BaseException as error:original=error
    try:operation.cleanup()
    except BaseException as error:
        if original is None:original=error
        else:original.add_note('Independent terminal job cleanup failed: '+type(error).__name__)
    if errors:
        operation.data.update(cleanup_complete=False,terminal_retirement_errors=errors)
        try:operation.save('terminal job retirement incomplete')
        except BaseException as error:
            if original is None:original=error
            else:original.add_note('Terminal retirement publication failed: '+type(error).__name__)
        if original is None:original=RuntimeError('Unproved terminal context authority')
    if job=='daily-recovery':
        from deploy.daily_recovery import record_cleanup
        try:record_cleanup(operation,path.parent)
        except BaseException as error:
            if original is None:original=error
            else:original.add_note('Daily terminal record publication failed: '+type(error).__name__)
    if original is not None:raise original
    result={'schema':'mldsafail.terminal-recovery-job.v1','cleanup_complete':True,
            'journal_present':True,'journal':str(path),'terminal_daemon_epoch':manifest['epoch'],
            'shared_rpc_uncertainty_resolved':False}
    atomic_json(path.parent/('terminal-job-'+driver_state['id']+'.json'),result)
    return result
