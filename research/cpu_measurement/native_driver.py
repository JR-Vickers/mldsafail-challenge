"""Source-bound disposable daemon provisioning and same-unit native acceptance.

No staging service is controlled. Private configuration and independent review
packets must be supplied explicitly; this tool never grants adoption/activation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid
from deploy import owned_client,owned_daemon
from research.cpu_measurement.ownership import canonical_directory


def source_digest(repository):
    files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((repository/'research/cpu_measurement').glob('*.py'))}
    files.update({'deploy/'+name:hashlib.sha256((repository/'deploy'/name).read_bytes()).hexdigest() for name in ('owned_client.py','owned_daemon.py','recovery_daemon.py')})
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def install(path,text):
    path=owned_daemon._canonical(path)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as stream:
        stream.write(text);stream.flush();os.fsync(stream.fileno())
    receipt=dict(path=str(path),sha256=hashlib.sha256(text.encode()).hexdigest(),device=path.stat().st_dev,inode=path.stat().st_ino)
    descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    return receipt


def render(values):
    template=Path(__file__).parent/'templates/owned-daemon.service.in'
    text=template.read_text()
    if set(values)!={'ROOTLESS_STATE','DOCKERD_ROOTLESS','SOCKET','DATA_ROOT','EXEC_ROOT','WORKER_SLICE','DAEMON_CONFIG','PIDFILE'}:
        raise ValueError('Complete fixed dedicated daemon substitutions required')
    for name,value in values.items():
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_/.-]+',value):
            raise ValueError('Safe literal systemd substitution required')
        text=text.replace('@'+name+'@',value)
    if '@' in text: raise ValueError('Unresolved unit template field')
    return text


def validate(config,repository):
    fields={'schema','source_commit','supervisor_source_sha256','state_root','operator_unit','operator_parent',
            'protected_roots','protected_cgroups','image','image_archive','image_archive_sha256',
            'dockerd_sha256','rootless_script','rootless_script_sha256','server_version','server_git_commit',
            'api_version','review_packet'}
    if set(config)-{'acceptance_source_sha256','additional_images'}!=fields or config['schema'] not in {'mldsafail.cpu-native-driver.v1','mldsafail.owned-native-driver.v1'}:
        raise ValueError('Exact private native driver configuration required')
    if not isinstance(config['api_version'],str) or not re.fullmatch(r'[0-9]+\.[0-9]+',config['api_version']):
        raise ValueError('Exact numeric Docker API version required before native mutation')
    if sys.platform!='linux': raise RuntimeError('Native Linux driver required')
    if subprocess.check_output(['git','-C',str(repository),'status','--porcelain'],timeout=15):
        raise RuntimeError('Clean retained source required before native maintenance')
    if subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],timeout=15).decode().strip()!=config['source_commit'] or source_digest(repository)!=config['supervisor_source_sha256']:
        raise RuntimeError('Retained source/configuration identity mismatch')
    for key in ('supervisor_source_sha256','image_archive_sha256','dockerd_sha256','rootless_script_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',config[key]): raise ValueError('Pinned artifact digest required')
    if not re.fullmatch('sha256:[0-9a-f]{64}',config['image']): raise ValueError('Immutable native worker image required')
    if not config['protected_roots'] or not config['protected_cgroups']:
        raise ValueError('Explicit real staging/evaluator protections required')
    packet=owned_daemon.read_private_json(config['review_packet'])
    if packet.get('schema')!='mldsafail.cpu-native-review.v1' or packet.get('supervisor_source_sha256')!=config['supervisor_source_sha256'] or any(packet.get(name) is not True for name in ('supervisor_review_passed','auditor_review_passed','native_protocol_review_passed')) or not packet.get('evidence_refs'):
        raise RuntimeError('Actual independent source-bound reviews required before provisioning')
    values=subprocess.check_output(['systemctl','--user','show',config['operator_unit'],'--property=ControlGroup','--property=Delegate','--property=UMask','--property=Restart'],timeout=15,text=True)
    unit=dict(line.split('=',1) for line in values.splitlines() if '=' in line)
    parent=owned_daemon._canonical(config['operator_parent'])
    if unit.get('Delegate')!='yes' or unit.get('UMask')!='0077' or unit.get('Restart')!='no' or Path('/sys/fs/cgroup')/unit['ControlGroup'].lstrip('/')!=parent:
        raise RuntimeError('Dedicated delegated operator unit with UMask0077/Restartno required')
    current=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
    if current!=parent and parent not in current.parents: raise RuntimeError('Driver must execute inside the same declared operator unit')
    os.environ['MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT']=str(parent)
    os.environ.pop('DOCKER_CONTEXT',None)
    owned_client.prepare_domain({'id':uuid.uuid4().hex},parent)
    script=owned_daemon._canonical(config['rootless_script'])
    if hashlib.sha256(script.read_bytes()).hexdigest()!=config['rootless_script_sha256'] or script.stat().st_mode & 0o022:
        raise RuntimeError('Reviewed rootless startup executable mismatch')
    return config


class Journal:
    def __init__(self,path,data): self.path,self.data=Path(path),data
    def save(self): owned_daemon.publish(self.path,self.data)
    def command(self,argv,*,kind='read',timeout=45,**kwargs):
        intent=dict(id=uuid.uuid4().hex,argv=list(argv),kind=kind,state='running')
        self.data['commands'].append(intent);self.save()
        original=None
        try:
            result=owned_client.run(argv,self.data['clients'],self.save,self.path.parent,timeout=timeout,
                                    capture_output=True,**kwargs)
            intent.update(state='passed',returncode=result.returncode,
                          stdout_sha256=hashlib.sha256(result.stdout or b'').hexdigest(),stderr_sha256=hashlib.sha256(result.stderr or b'').hexdigest())
            return result
        except BaseException as error:
            original=error
            intent.update(state='uncertain' if kind!='read' else 'failed',error=repr(error));raise
        finally:
            try: self.save()
            except BaseException as publication_error:
                if original is None: raise
                original.add_note('Command receipt publication failed: '+repr(publication_error))


def register(journal,*,teardown_only=False):
    data=journal.data;config=data['config'];provision=data['provisioning']
    os.environ['DOCKER_HOST']='unix://'+data['socket']
    os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']=data['manifest_path']
    os.environ.pop('MLDSAFAIL_CPU_DAEMON_MANIFEST',None)
    return owned_daemon.register(unit=data['daemon_unit'],socket=data['socket'],
        **{name:value['path'] for name,value in provision['roots'].items()},manifest_path=data['manifest_path'],
        expected_server_version=config['server_version'],expected_server_git_commit=config['server_git_commit'],
        expected_executable_sha256=config['dockerd_sha256'],worker_parent=data['worker_parent'],
        worker_cgroup_parent=data['worker_slice'],provisioning=provision,teardown_only=teardown_only)


def cleanup(journal,*,terminal=False):
    """Every cleanup independent; unknown setup requests retain explicit fence."""
    data=journal.data;errors=[];barrier=None
    measurement_directory=None
    try:
        if data.get('worker_parent'): measurement_directory=canonical_directory(Path(data['worker_parent']))
    except BaseException as error: errors.append(dict(step='measurement_directory',error=repr(error)))
    measurement_needs_cleanup=False
    if not terminal and measurement_directory is not None and (measurement_directory/'journal.json').exists():
        try:
            measurement=owned_daemon.read_private_json(measurement_directory/'journal.json',cap=4*1024*1024)
            measurement_needs_cleanup=measurement.get('state')!='complete'
            if measurement_needs_cleanup:
                from research.cpu_measurement.reconcile import reconcile
                first=reconcile(measurement_directory,Path(data['worker_parent']))
                data.setdefault('measurement_cleanup_attempts',[]).append(first)
                measurement_needs_cleanup=not first.get('cleanup_complete',False)
        except BaseException as error:
            measurement_needs_cleanup=True
            data.setdefault('measurement_cleanup_attempts',[]).append(dict(cleanup_complete=False,error=repr(error)))
    manifest=None
    try:
        if Path(data.get('manifest_path','/nonexistent')).exists():
            manifest=owned_daemon.load_manifest(data['manifest_path'])
        elif data.get('start_intent') and data.get('worker_parent'):
            manifest=register(journal,teardown_only=terminal)  # Exact live birth/config proof, never a default daemon.
    except BaseException as error: errors.append(dict(step='cleanup_registration',error=repr(error)))
    if manifest is not None:
        try: barrier=owned_daemon.shutdown_barrier(manifest,evidence_directory=journal.path.parent,attempt_id=data['id'])
        except BaseException as error: errors.append(dict(step='daemon_barrier',error=repr(error)))
        if barrier and not barrier['shutdown_proven']: errors.extend(barrier['errors'])
    elif data.get('start_intent'):
        # Do not manufacture positive kernel authority when startup identity is
        # unproved. Still cancel the exact fresh unit if its retained fragment
        # remains unchanged; the uncertainty fence survives this best effort.
        try:
            state=owned_daemon._unit(data['daemon_unit'])
            fragment=[entry for entry in data['units'] if Path(entry['path']).name==data['daemon_unit']][0]
            if state['unit_fragment_sha256']!=fragment['sha256']: raise RuntimeError('Fresh unit config changed; control prohibited')
            journal.command(['systemctl','--user','stop',data['daemon_unit']],kind='service_stop')
        except BaseException as error: errors.append(dict(step='fresh_daemon_best_effort_stop',error=repr(error)))
        try: startup=owned_daemon.failed_startup_barrier(data,evidence_directory=journal.path.parent,attempt_id=data['id'])
        except BaseException as error:
            startup=dict(startup_shutdown_proven=False,errors=[dict(step='failed_startup_proof',error=repr(error))])
        data['failed_startup_barrier']=startup
        if startup['startup_shutdown_proven']:
            # Distinct terminal setup proof; never an accepted daemon epoch.
            data.setdefault('startup_registration_failures',[]).extend(row for row in errors if row['step']=='cleanup_registration')
            errors[:]=[row for row in errors if row['step']!='cleanup_registration']
            barrier=dict(shutdown_proven=True,errors=[],failed_startup_receipt=startup)
        else:
            errors.extend(startup['errors'])
            errors.append(dict(step='setup_authority',error='Unproved daemon startup remains fenced; no positive barrier'))
    # Guardian/client domain cleanup follows positive daemon quiescence whenever
    # there may have been Docker mutations. Never cancel unknown daemon creators
    # and then use an empty inventory as proof of completed cleanup.
    commands=data.get('commands',[])
    clients=data.get('clients',[])
    if not isinstance(commands,list) or any(not isinstance(row,dict) for row in commands):
        errors.append(dict(step='command_receipts',error='Malformed command receipts'));commands=[]
        uncertain_mutations=True
    else: uncertain_mutations=any(command.get('kind')!='read' and command.get('state') in {'running','uncertain'} for command in commands)
    if not isinstance(clients,list):
        errors.append(dict(step='client_receipts',error='Malformed client receipts'));clients=[]
    needs_barrier=bool(data.get('image_load_intent') or data.get('start_intent') or uncertain_mutations)
    can_stop_clients=not needs_barrier or bool(barrier and barrier['shutdown_proven'])
    for entry in clients:
        if not can_stop_clients and not (isinstance(entry,dict) and entry.get('finished') is True):
            errors.append(dict(step='client_fence',error='Daemon quiescence required before client cancellation'));continue
        try: owned_client.stop(entry)
        except BaseException as error: errors.append(dict(step='client_cleanup',error=repr(error)))
    if terminal and measurement_directory is not None and (measurement_directory/'journal.json').exists():
        try:
            if not barrier or not barrier['shutdown_proven']: raise RuntimeError('Positive terminal daemon barrier required before measurement-client cleanup')
            measurement=owned_daemon.read_private_json(measurement_directory/'journal.json',cap=4*1024*1024)
            prior=measurement_directory/(measurement['generation']+'-terminal-interrupted.json')
            if not prior.exists(): owned_daemon.publish(prior,measurement)
            clients={row['id']:row for row in measurement['mutations'] if row['operation']=='host_client_domain'}
            for entry in clients.values(): owned_client.stop(entry)
            receipt=dict(schema='mldsafail.cpu-terminal-cleanup.v1',generation=measurement['generation'],cleanup_complete=True,authoritative_result_available=False,daemon_barrier=barrier)
            name=measurement['generation']+'-terminal-cleanup-'+uuid.uuid4().hex+'.json'
            owned_daemon.publish(measurement_directory/name,receipt)
            measurement.update(state='complete',terminal_cleanup=True,authoritative_result_available=False,latest_cleanup_evidence=name)
            owned_daemon.publish(measurement_directory/'journal.json',measurement)
        except BaseException as error: errors.append(dict(step='terminal_measurement_cleanup',error=repr(error)));measurement_needs_cleanup=True
    if not terminal and measurement_needs_cleanup and can_stop_clients:
        try:
            from research.cpu_measurement.reconcile import reconcile
            second=reconcile(measurement_directory,Path(data['worker_parent']))
            data.setdefault('measurement_cleanup_attempts',[]).append(second)
            if second.get('cleanup_complete') is not True: raise RuntimeError('Owned measurement cleanup remains incomplete')
            measurement_needs_cleanup=False
            refreshed=owned_daemon.load_manifest(data['manifest_path'])
            barrier=owned_daemon.shutdown_barrier(refreshed,evidence_directory=journal.path.parent,attempt_id=data['id'])
            if not barrier['shutdown_proven']: errors.extend(barrier['errors'])
        except BaseException as error: errors.append(dict(step='measurement_reconcile',error=repr(error)))
    elif measurement_needs_cleanup:
        errors.append(dict(step='measurement_fence',error='Owned measurement cleanup cannot complete before daemon quiescence'))
    if data.get('worker_slice') and not measurement_needs_cleanup and (not data.get('start_intent') or bool(barrier and barrier['shutdown_proven'])):
        try:
            receipt=[entry for entry in data['units'] if Path(entry['path']).name==data['worker_slice']][0]
            if hashlib.sha256(Path(receipt['path']).read_bytes()).hexdigest()!=receipt['sha256']: raise RuntimeError('Owned worker slice fragment changed; control prohibited')
            journal.command(['systemctl','--user','stop',data['worker_slice']],kind='worker_stop')
        except BaseException as error: errors.append(dict(step='worker_slice_stop',error=repr(error)))
    receipt=dict(schema='mldsafail.cpu-native-driver-cleanup.v1',id=data['id'],cleanup_complete=not errors,errors=errors,daemon_barrier=barrier)
    data['cleanup']=receipt;data['state']='complete' if not errors else 'cleanup_incomplete';journal.save()
    return receipt


def execute(config,repository,*,acceptance=None,daemon_kind='cpu'):
    if daemon_kind not in {'cpu','owned'} or (daemon_kind=='owned' and acceptance is None):
        raise ValueError('Explicit reviewed dedicated daemon purpose required')
    if acceptance is not None:
        module=sys.modules[acceptance.__module__]
        file=Path(module.__file__).resolve()
        if not file.is_relative_to(repository.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=config.get('acceptance_source_sha256'):
            raise RuntimeError('Trusted source-bound operator callback required')
        packet=owned_daemon.read_private_json(config['review_packet'])
        if packet.get('acceptance_source_sha256')!=config['acceptance_source_sha256']:
            raise RuntimeError('Operator callback absent from independent review packet')
    validate(config,repository)
    os.umask(0o077)
    root=owned_daemon._canonical(config['state_root']);owned_daemon._private_directory(root.parent)
    root.mkdir(mode=0o700)
    data=dict(schema='mldsafail.cpu-native-driver-state.v1',id=uuid.uuid4().hex,config=config,
              state='provisioning',commands=[],clients=[],units=[],native_acceptance_passed=False,daemon_kind=daemon_kind)
    journal=Journal(root/'driver.json',data);journal.save();original=None;lease=None;lease_entered=False
    try:
        unit='mldsafail-'+daemon_kind+'-daemon-'+data['id']+'.service'
        provision=owned_daemon.provision(root/'daemon',unit=unit,protected_roots=config['protected_roots'])
        data.update(daemon_unit=unit,provisioning=provision);journal.save()
        from deploy.recovery_daemon import provision_lock
        lease=provision_lock(provision);lease.__enter__();lease_entered=True
        worker='mldsafail-'+daemon_kind+'-workers-'+provision['id']+'.slice'
        units=Path.home()/'.config/systemd/user';units.mkdir(mode=0o700,parents=True,exist_ok=True)
        for directory in (units,units.parent,units.parent.parent,Path.home()):
            info=directory.stat()
            if info.st_uid!=os.getuid() or info.st_mode & 0o022 or directory.is_symlink(): raise RuntimeError('Owner-controlled systemd configuration ancestors required')
        data.update(daemon_unit=unit,worker_slice=worker,socket=str(root/'daemon/docker.sock'),manifest_path=str(root/'daemon-manifest.json'),provisioning=provision)
        journal.save()
        data['units'].append(install(units/worker,'[Unit]\nDescription=Fresh isolated MLDSA accounting parent\n[Slice]\nCPUAccounting=yes\nMemoryAccounting=yes\n'))
        journal.save();journal.command(['systemctl','--user','daemon-reload'],kind='unit_reload')
        data['worker_start_intent']=True;journal.save()
        journal.command(['systemctl','--user','start',worker],kind='worker_start')
        control=journal.command(['systemctl','--user','show',worker,'--property=ControlGroup','--value']).stdout.decode().strip()
        parent=Path('/sys/fs/cgroup')/control.lstrip('/')
        if parent.name!=worker: raise RuntimeError('Fresh worker slice has unexpected kernel path')
        owned_daemon._disjoint([parent,Path(config['operator_parent'])],[owned_daemon._canonical(path) for path in config['protected_cgroups']])
        data['worker_parent']=str(parent);data['worker_permission_intent']=True;journal.save()
        secured=dict(id='fresh-worker-'+data['id'])
        owned_client.secure_created_domain(secured,parent)
        data['worker_secured_birth']=secured['cgroup'];journal.save()
        provision=owned_daemon.bind_worker(provision,worker_parent=parent,worker_cgroup_parent=worker,
                operator_parent=config['operator_parent'],protected_domains=config['protected_cgroups'])
        data['provisioning']=provision;journal.save()
        substitutions=dict(PIDFILE=provision['daemon_pidfile'],DAEMON_CONFIG=provision['daemon_config']['path'],ROOTLESS_STATE=provision['roots']['rootless_state']['path'],DOCKERD_ROOTLESS=config['rootless_script'],SOCKET=data['socket'],DATA_ROOT=provision['roots']['root_dir']['path'],EXEC_ROOT=provision['roots']['exec_root']['path'],WORKER_SLICE=worker)
        data['units'].append(install(units/unit,render(substitutions)));journal.save()
        journal.command(['systemctl','--user','daemon-reload'],kind='unit_reload')
        data['start_intent']=True;journal.save()
        journal.command(['systemctl','--user','start',unit],kind='daemon_start')
        deadline=time.monotonic()+60
        while True:
            try: manifest=register(journal);break
            except (RuntimeError,subprocess.SubprocessError,FileNotFoundError):
                if time.monotonic()>deadline: raise
                time.sleep(.1)
        data['registered_manifest']=manifest;journal.save()
        data['loaded_images']=[]
        images=[dict(image=config['image'],archive=config['image_archive'],archive_sha256=config['image_archive_sha256']),*config.get('additional_images',[])]
        for artifact in images:
            if not isinstance(artifact,dict) or set(artifact)!={'image','archive','archive_sha256'} or not re.fullmatch('sha256:[0-9a-f]{64}',artifact['image']) or not re.fullmatch('[0-9a-f]{64}',artifact['archive_sha256']): raise RuntimeError('Strict pinned additional image inputs required')
            archive=owned_daemon._canonical(artifact['archive'])
            descriptor=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            import stat
            with os.fdopen(descriptor,'rb') as stream:
                info=os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077 or hashlib.file_digest(stream,'sha256').hexdigest()!=artifact['archive_sha256']:
                    raise RuntimeError('Private immutable retained image archive required')
                stream.seek(0);data['image_load_intent']=True;journal.save()
                journal.command(['docker','load'],kind='image_load',timeout=300,stdin=stream)
            loaded=json.loads(journal.command(['docker','image','inspect',artifact['image']]).stdout)[0]
            if loaded['Id']!=artifact['image']: raise RuntimeError('Loaded worker digest mismatch')
            data['loaded_images'].append(artifact['image']);journal.save()
        if acceptance is not None:
            data['state']='operator_acceptance';journal.save()
            result=acceptance(journal,config,data)
            if not isinstance(result,dict) or set(result)!={'schema','passed','native_executed','evidence_refs','source_sha256'} or result.get('schema')!='mldsafail.owned-native-acceptance.v1' or result.get('source_sha256')!=config['acceptance_source_sha256'] or result.get('passed') is not True or result.get('native_executed') is not True or not result.get('evidence_refs'):
                raise RuntimeError('Complete source-bound native operator acceptance receipt required')
            data['operator_acceptance']=result;data['native_cpu_gates_passed']=False;journal.save()
        else:
            args=['--image',config['image'],'--parent',str(parent),'--cgroup-parent',worker]
            data['state']='faults';journal.save()
            journal.command([sys.executable,'-m','research.cpu_measurement.native_fault_suite',*args,'--output',str(root/'faults'),'--api-version',config['api_version']],kind='native_faults',timeout=3600)
            faults=owned_daemon.read_private_json(root/'faults/report.json',cap=4*1024*1024)
            if faults.get('contract_fault_gate_passed') is not True: raise RuntimeError('Complete native fault gate did not pass')
            # Fault repair can replace the daemon epoch. Verify refreshed identity
            # before the one predeclared pair run; source/image/thresholds stay fixed.
            owned_daemon.verify_environment(owned_daemon.load_manifest(),measurement_parent=parent)
            data['state']='pairs';journal.save()
            journal.command([sys.executable,'-m','research.cpu_measurement.native_suite',*args,'--output',str(root/'pairs'),'--ownership-directory',str(canonical_directory(parent))],kind='native_pairs',timeout=3600)
            pairs=owned_daemon.read_private_json(root/'pairs/report.json',cap=4*1024*1024)
            if pairs.get('passed') is not True or pairs.get('native_executed') is not True: raise RuntimeError('Predeclared native pair gate failed')
            data['native_cpu_gates_passed']=True
        data['native_consumer_passed']=True;journal.save()
    except BaseException as error:
        original=error;data['failure']=dict(type=type(error).__name__,message=str(error))
        try: journal.save()
        except BaseException as publication: error.add_note('Native failure publication failed: '+repr(publication))
        raise
    finally:
        try: cleanup(journal)
        except BaseException as error:
            if original is not None: original.add_note('Independent native driver cleanup failed: '+repr(error))
            else: raise
        finally:
            if lease_entered: lease.__exit__(None,None,None)
    data['native_acceptance_passed']=data.get('native_consumer_passed') is True and data['cleanup']['cleanup_complete'] is True
    journal.save()
    if not data['cleanup']['cleanup_complete']: raise RuntimeError('Native driver cleanup remains fenced')
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--cleanup-state',type=Path)
    parser.add_argument('--controller-config',type=Path)
    args=parser.parse_args()
    repository=Path(__file__).resolve().parents[2]
    if bool(args.config)==bool(args.cleanup_state): parser.error('Choose explicit configuration or cleanup state')
    if args.cleanup_state:
        if args.controller_config is None: parser.error('Terminal cleanup requires explicit new controller configuration')
        report=cleanup_state(args.cleanup_state,controller_config=owned_daemon.read_private_json(args.controller_config),repository=repository)
        raise SystemExit(0 if report['cleanup_complete'] else 1)
    execute(owned_daemon.read_private_json(args.config),repository)




def cleanup_state(path,*,controller_config,repository):
    """Retire terminal ownership without leaking its endpoint into callers."""
    names=('DOCKER_HOST','DOCKER_CONTEXT','MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','MLDSAFAIL_CPU_DAEMON_MANIFEST')
    previous={name:os.environ.get(name) for name in names}
    original=None
    try:
        return _cleanup_state(path,controller_config=controller_config,repository=repository)
    except BaseException as error:
        original=error;raise
    finally:
        errors=[]
        for name,value in previous.items():
            try:
                if value is None:os.environ.pop(name,None)
                else:os.environ[name]=value
            except BaseException as error:errors.append(repr(error))
        if errors:
            if original is None:raise RuntimeError('Terminal environment restoration failed: '+repr(errors))
            original.add_note('Terminal environment restoration failed: '+repr(errors))


def _cleanup_state(path,*,controller_config,repository):
    """New source-bound controller terminally retires the old owned epoch.

    The original manifest/provisioning/measurement contract stays immutable.
    The new delegated parent hosts only cleanup command clients; no evaluation,
    callback or old daemon restart is admitted under this borrowed authority.
    """
    validate(controller_config,repository)
    data=owned_daemon.read_private_json(path,cap=4*1024*1024)
    if data.get('schema')!='mldsafail.cpu-native-driver-state.v1': raise RuntimeError('Exact retained native driver state required')
    controller=owned_daemon._canonical(controller_config['operator_parent'])
    old_provision=data['provisioning']
    domains=[Path(old_provision['worker_birth']['path'])]
    if Path(data['manifest_path']).exists(): domains.append(Path(owned_daemon.load_manifest(data['manifest_path'])['domain']['path']))
    owned_daemon._disjoint([controller,*domains],[Path(value) for value in old_provision['protected_domains']])
    from deploy.recovery_daemon import provision_lock
    journal=Journal(path,data)
    with provision_lock(data['provisioning']):
        retained=owned_daemon.read_private_json(path,cap=4*1024*1024)
        if retained!=data: raise RuntimeError('Driver state changed while acquiring terminal lease')
        data=retained
        owned_daemon.publish(Path(path).parent/('prior-driver-state-'+uuid.uuid4().hex+'.json'),data)
        journal=Journal(path,data)
        os.environ['DOCKER_HOST']='unix://'+data['socket']
        os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']=data['manifest_path']
        os.environ.pop('MLDSAFAIL_CPU_DAEMON_MANIFEST',None)
        data['terminal_controller']=dict(operator_parent=controller_config['operator_parent'],source_commit=controller_config['source_commit'],supervisor_source_sha256=controller_config['supervisor_source_sha256'])
        journal.save()
        return cleanup(journal,terminal=True)

if __name__=='__main__': main()
