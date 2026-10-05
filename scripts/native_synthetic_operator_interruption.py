"""End-to-end disposable HTTPS S3 check interruption; no staging timers.

Invoke as an owned native-driver callback. All service units are fresh temporary
user units; source-bound fixture credentials and private journals stay local.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import ssl
import sys
import time
import urllib.request
import uuid
from deploy import owned_client, owned_daemon
from deploy.native_synthetic_s3 import Server, digest, port
from scripts.native_interrupted_job_signal import execute as interrupt, signal_exact_owner
from scripts.native_repeat_activation_verification import verify


def backend_signal(entry, signum):
    birth = owned_client.identity(entry['pid'])
    if (any(birth[key] != entry.get(key) for key in ('pid','uid','start_ticks','boot_id')) or
        birth['cmdline_sha256'] != entry.get('expected_cmdline_sha256') or
        owned_client.verify_domain(entry) is None):
        raise RuntimeError('Exact disposable backend birth/domain required')
    fd=os.pidfd_open(entry['pid'])
    try:
        if owned_client.identity(entry['pid']) != birth or owned_client.verify_domain(entry) is None:
            raise RuntimeError('Disposable backend changed after descriptor acquisition')
        signal.pidfd_send_signal(fd,signum)
    finally:os.close(fd)


def start_unit(driver, unit, source, configuration, *, wait=False, cleanup=False, cacert=None):
    argv=['systemd-run','--user','--unit='+unit,'--property=Delegate=yes','--property=UMask=0077',
        '--property=Restart=no','--property=RuntimeMaxSec=600',
        '--property=KillMode='+('control-group' if wait else 'process'),
        '--working-directory='+str(source), '--setenv=PYTHONPATH='+str(source/'src')+':'+str(source)]
    if cacert:argv.append('--setenv=RESTIC_CACERT='+str(cacert))
    if wait:argv.append('--wait')
    argv += [sys.executable,'-m','deploy.operator_activation','--config',str(configuration),'--unit',unit]
    if cleanup:argv.append('--cleanup')
    return driver.command(argv,kind='read',timeout=650 if wait else 30)


def unit_owner(driver, unit, activation, source):
    result=driver.command(['systemctl','--user','show',unit,'--property=MainPID','--property=ControlGroup',
                          '--property=Delegate'],kind='read',timeout=15)
    props=dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
    pid=int(props['MainPID'])
    if pid<=1 or props.get('Delegate')!='yes':raise RuntimeError('Exact disposable delegated owner required')
    birth=owned_client.identity(pid)
    argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')[:-1]
    wanted=list(map(os.fsencode,[sys.executable,'-m','deploy.operator_activation','--config',str(activation),'--unit',unit]))
    if argv!=wanted or birth['uid']!=os.getuid():raise RuntimeError('Exact direct disposable activation argv required')
    parent=Path('/sys/fs/cgroup')/props['ControlGroup'].lstrip('/')
    return dict(birth=birth,domain=owned_client.domain_identity(parent))


def terminal_unit(driver, unit):
    result=driver.command(['systemctl','--user','show',unit,'--property=MainPID',
                          '--property=ActiveState','--property=ControlGroup'],kind='read',timeout=15)
    properties=dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
    jobs=driver.command(['systemctl','--user','list-jobs','--no-pager','--no-legend'],kind='read',timeout=15).stdout.decode()
    if (properties.get('MainPID')!='0' or properties.get('ActiveState') not in {'inactive','failed'} or
        properties.get('ControlGroup') or any(unit in line.split() for line in jobs.splitlines())):
        raise RuntimeError('Disposable unit must be terminal with no domain or pending job')
    return dict(unit=unit,terminal=True,controller_absent=True,pending_jobs_absent=True)


def retry_cleanup(driver, config, root):
    """New controller retries only recorded ownership; never replays a check."""
    root=owned_daemon._canonical(root)
    owned_daemon._private_directory(root)
    original=owned_daemon.read_private_json(root/'report.json')
    if (original.get('schema')!='mldsafail.synthetic-operator-interruption-result.v1' or
        original.get('source_commit')!=config['source_commit'] or
        original.get('acceptance_source_sha256')!=config['acceptance_source_sha256']):
        raise RuntimeError('Exact retained original fixture source authority required')
    source=Path(__file__).resolve().parents[1]
    errors=[]
    outcome=dict(schema='mldsafail.synthetic-operator-cleanup.v1',cleanup_complete=False,errors=errors,
                 original_source_commit=original['source_commit'],gate_acceptance_replayed=False,
                 owner_stop_intent=original.get('original_owner'),units=[])
    target=root/('cleanup-retry-'+uuid.uuid4().hex+'.json')
    owned_daemon.publish(target,outcome)  # Durable retry authority before signaling.
    owner=original.get('original_owner')
    if owner is not None:
        try:
            try:current=owned_client.identity(owner['birth']['pid'])
            except (FileNotFoundError,ProcessLookupError):current=None
            if current is not None:
                if current!=owner['birth']:raise RuntimeError('Original owner birth replaced')
                signal_exact_owner(current['pid'],current,Path(owner['domain']['path']),owner['domain'])
        except BaseException as error:errors.append('owner:'+type(error).__name__)
    server_state=root/'server-clients.json'
    entries=owned_daemon.read_private_json(server_state)['clients'] if server_state.exists() else []
    for entry in entries:
        try:
            if owned_client.verify_domain(entry) is not None:backend_signal(entry,signal.SIGCONT)
        except BaseException as error:errors.append('resume:'+type(error).__name__)
    fixture=root/'fixture-activation.json'
    if fixture.exists():
        try:
            active=owned_daemon.read_private_json(fixture)
            if active.get('activation_root')!=str(root/'activations') or active.get('job')!='fixture':
                raise RuntimeError('Exact original activation root required')
            name='mldsafail-synthetic-terminal-'+uuid.uuid4().hex+'.service'
            outcome['units'].append(dict(unit=name,intent='independent terminal retry'))
            owned_daemon.publish(target,outcome)
            start_unit(driver,name,source,fixture,wait=True,cleanup=True)
            terminal_unit(driver,name)
        except BaseException as error:errors.append('activation:'+type(error).__name__)
    for record in original.get('units',[]):
        try:terminal_unit(driver,record['unit'])
        except BaseException as error:errors.append('unit:'+type(error).__name__)
    for entry in entries:
        try:owned_client.stop(entry)
        except BaseException as error:errors.append('backend:'+type(error).__name__)
    outcome.update(cleanup_complete=not errors,errors=errors)
    try:owned_daemon.publish(target,outcome)
    except BaseException as error:
        outcome.update(cleanup_complete=False,publication_failed=True)
        try:owned_daemon.publish(target,outcome)
        except BaseException as retry:error.add_note('Negative cleanup publication:'+type(retry).__name__)
        raise
    if errors:raise RuntimeError('Independent retry cleanup incomplete')
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
                source_sha256=config['acceptance_source_sha256'],evidence_refs=[str(target)])


def validate_artifacts(artifacts):
    owned_daemon._private_directory(artifacts)
    from deploy.recovery import private_file
    for name in ('restic','minio'):
        private_file(artifacts/name)
        if not os.access(artifacts/name,os.X_OK):raise ValueError('Private executable native artifacts required')
    pins=owned_daemon.read_private_json(artifacts/'artifacts.json')
    if pins.get('scope')!='synthetic-only' or any(digest(artifacts/name)!=pins[name+'_binary_sha256'] for name in ('restic','minio')):
        raise ValueError('Pinned synthetic restic and MinIO artifacts required')
    return pins


def callback(driver, config, data):
    source=Path(__file__).resolve().parents[1]
    protocol=owned_daemon.read_private_json(Path(config['state_root']).parent/'synthetic-interruption-protocol.json')
    if set(protocol)!={'schema','artifacts_directory'} or protocol['schema']!='mldsafail.synthetic-operator-interruption.v1':
        raise ValueError('Exact disposable interruption protocol required')
    artifacts=owned_daemon._canonical(protocol['artifacts_directory'])
    pins=validate_artifacts(artifacts)
    root=driver.path.parent.parent/('synthetic-interruption-'+uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    report=dict(schema='mldsafail.synthetic-operator-interruption-result.v1',passed=False,
        native_executed=True,synthetic_only=True,source_commit=config['source_commit'],
        acceptance_source_sha256=config['acceptance_source_sha256'],artifacts=pins,
        actual_owner_custody_accepted=False,actual_offhost_storage_accepted=False,
        benchmark_epoch_data_used=False,cleanup_complete=False,units=[])
    def save():owned_daemon.publish(root/'report.json',report)
    save()
    server=None;paused=False;error=None;cleanup_errors=[];activation=None;owner=None
    try:
        certs=root/'certs';certs.mkdir(mode=0o700)
        driver.command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=synthetic-only',
            '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(certs/'private.key'),'-out',str(certs/'public.crt')],kind='read',timeout=60)
        endpoint='https://127.0.0.1:'+str(port())
        storage=root/'storage';storage.mkdir(mode=0o700)
        credentials=dict(AWS_ACCESS_KEY_ID='synthetic-only',AWS_SECRET_ACCESS_KEY=uuid.uuid4().hex,AWS_DEFAULT_REGION='us-east-1')
        owned_daemon.publish(root/'credentials.json',credentials)
        password=root/'password';password.write_text(uuid.uuid4().hex);password.chmod(0o600)
        custody=root/'synthetic-custody-copy';custody.write_bytes(password.read_bytes());custody.chmod(0o600)
        server=Server([str(artifacts/'minio'),'server','--quiet','--address',endpoint.removeprefix('https://'),
            '--console-address','127.0.0.1:'+str(port()),'--certs-dir',str(certs),str(storage)],
            dict(os.environ,MINIO_ROOT_USER=credentials['AWS_ACCESS_KEY_ID'],MINIO_ROOT_PASSWORD=credentials['AWS_SECRET_ACCESS_KEY'],MINIO_BROWSER='off'),root)
        deadline=time.monotonic()+30
        while True:
            try:
                urllib.request.urlopen(endpoint+'/minio/health/ready',context=ssl.create_default_context(cafile=str(certs/'public.crt')),timeout=1).close();break
            except OSError:
                if time.monotonic()>=deadline or not server.thread.is_alive():raise RuntimeError('Bounded disposable backend startup failed')
                time.sleep(.1)
        driver.command(['curl','--fail','--silent','--show-error','--cacert',str(certs/'public.crt'),
            '--aws-sigv4','aws:amz:us-east-1:s3','--user',credentials['AWS_ACCESS_KEY_ID']+':'+credentials['AWS_SECRET_ACCESS_KEY'],
            '-X','PUT',endpoint+'/syntheticbucket'],kind='read',timeout=30)
        repository='s3:'+endpoint+'/syntheticbucket/staging'
        env=dict(os.environ,**credentials,RESTIC_REPOSITORY=repository,RESTIC_PASSWORD_FILE=str(password),RESTIC_CACERT=str(certs/'public.crt'),GOMAXPROCS='2')
        driver.command([str(artifacts/'restic'),'--no-cache','init'],kind='read',env=env,timeout=120)
        payload=root/'tiny-public-fixture';payload.mkdir(mode=0o700)
        (payload/'synthetic.txt').write_text('repository-generated synthetic operator recovery fixture\n')
        driver.command([str(artifacts/'restic'),'--no-cache','backup',str(payload)],kind='read',env=env,timeout=120)
        driver.command([str(artifacts/'restic'),'--no-cache','check','--read-data'],kind='read',env=env,timeout=120)
        check=dict(restic_binary=str(artifacts/'restic'),restic_sha256=pins['restic_binary_sha256'],password_file=str(password),
            credentials_file=str(root/'credentials.json'),environment='staging',repository=repository,owner_retained_recovery_key=True,
            backup_state=str(root/'restic-state.json'),synthetic_only=True,actual_owner_custody_accepted=False,benchmark_epoch_data_used=False)
        owned_daemon.publish(root/'check.json',check)
        template=dict(config)
        review=owned_daemon.read_private_json(config['review_packet'])
        review['acceptance_source_sha256']=digest(source/'deploy/operator_activation.py')
        owned_daemon.publish(root/'activation-review.json',review)
        template['review_packet']=str(root/'activation-review.json')
        template['protected_roots']=list(config['protected_roots'])+[str(driver.path.parent)]
        template['protected_cgroups']=list(config['protected_cgroups'])+[config['operator_parent']]
        template.pop('additional_images',None)
        owned_daemon.publish(root/'template.json',template)
        activation_root=root/'activations';activation_root.mkdir(mode=0o700)
        activation=dict(schema='mldsafail.operator-activation.v1',driver_template=str(root/'template.json'),
            activation_root=str(activation_root),job='recovery-check',job_config=str(root/'check.json'),
            staging_socket='/run/user/'+str(os.getuid())+'/docker.sock')
        owned_daemon.publish(root/'check-activation.json',activation)
        fixture=dict(activation,job='fixture',job_config=None,staging_socket=None)
        owned_daemon.publish(root/'fixture-activation.json',fixture)
        if len(server.entries)!=1:raise RuntimeError('Exactly one owned synthetic backend required')
        # Paused local backend blocks a real restic HTTP request, not a fake job.
        report['backend_pause_intent']=dict(client=server.entries[0],maximum_seconds=450);save()
        backend_signal(server.entries[0],signal.SIGSTOP);paused=True
        unit='mldsafail-synthetic-check-'+uuid.uuid4().hex+'.service'
        report['units'].append(dict(unit=unit,intent='actual interrupted recovery-check'));save()
        start_unit(driver,unit,source,root/'check-activation.json',cacert=certs/'public.crt')
        owner_deadline=time.monotonic()+15
        while True:
            try:owner=unit_owner(driver,unit,root/'check-activation.json',source);break
            except (RuntimeError,FileNotFoundError,ProcessLookupError):
                if time.monotonic()>=owner_deadline:raise
                time.sleep(.1)
        report['original_owner']=owner;save()
        deadline=time.monotonic()+240
        while True:
            paths=list(activation_root.glob('activation-*/driver.json'))
            if len(paths)==1:break
            if len(paths)>1 or time.monotonic()>=deadline:raise TimeoutError('One bounded original driver required')
            time.sleep(.1)
        interrupt(paths[0],root/'check-activation.json',unit,root/'signal',timeout=120)
        backend_signal(server.entries[0],signal.SIGCONT);paused=False
        receipts=[]
        for _ in range(2):
            name='mldsafail-synthetic-replacement-'+uuid.uuid4().hex+'.service'
            report['units'].append(dict(unit=name,intent='fresh fixture and reconciliation'));save()
            before=set(activation_root.glob('activation-*'))
            start_unit(driver,name,source,root/'fixture-activation.json',wait=True)
            added=set(activation_root.glob('activation-*'))-before
            if len(added)!=1:raise RuntimeError('One fresh exited activation context required')
            receipts.append(next(iter(added))/'activation.json')
        outcome=verify(receipts,root/'verification',paths[0])
        if outcome.get('interrupted_job_reconciled') is not True:raise RuntimeError('Actual interrupted job reconciliation required')
        report['native_reconciliation_passed']=True
    except BaseException as caught:
        error=caught;report['failure_class']=type(caught).__name__
    finally:
        if paused and server is not None:
            try:backend_signal(server.entries[0],signal.SIGCONT);paused=False
            except BaseException as caught:cleanup_errors.append('resume:'+type(caught).__name__)
        if owner is not None:
            try:
                try:current=owned_client.identity(owner['birth']['pid'])
                except (FileNotFoundError,ProcessLookupError):current=None
                if current is not None:
                    if current!=owner['birth']:raise RuntimeError('Disposable owner birth changed during failure cleanup')
                    report['failure_owner_stop_intent']=True;save()
                    signal_exact_owner(current['pid'],current,Path(owner['domain']['path']),owner['domain'])
            except BaseException as caught:cleanup_errors.append('owner:'+type(caught).__name__)
        # Exact terminal reconciliation BEFORE killing shared creator clients or
        # the backend. Always run after interruption or partial activation.
        if activation is not None:
            try:
                name='mldsafail-synthetic-terminal-'+uuid.uuid4().hex+'.service'
                report['units'].append(dict(unit=name,intent='independent terminal cleanup'));save()
                start_unit(driver,name,source,root/'fixture-activation.json',wait=True,cleanup=True)
            except BaseException as caught:cleanup_errors.append('activation:'+type(caught).__name__)
        report['terminal_units']=[]
        for record in report['units']:
            try:report['terminal_units'].append(terminal_unit(driver,record['unit']))
            except BaseException as caught:cleanup_errors.append('unit:'+type(caught).__name__)
        if server is not None:
            try:server.stop()
            except BaseException as caught:cleanup_errors.append('backend:'+type(caught).__name__)
        report.update(cleanup_complete=not cleanup_errors,cleanup_errors=cleanup_errors,
                      passed=error is None and not cleanup_errors and report.get('native_reconciliation_passed') is True)
        try:save()
        except BaseException as caught:
            report.update(passed=False,final_publication_failed=True)
            if error is None:error=caught
            else:error.add_note('Final publication:'+type(caught).__name__)
            try:save()
            except BaseException as retry:error.add_note('Negative publication:'+type(retry).__name__)
        if error is not None:raise error
        if cleanup_errors:raise RuntimeError('Independent synthetic fixture cleanup incomplete')
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
        source_sha256=config['acceptance_source_sha256'],evidence_refs=[str(root/'report.json')])


def main():
    import argparse
    from research.cpu_measurement import native_driver
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--cleanup-root',type=Path)
    args=parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),Path(__file__).resolve().parents[1],
                          acceptance=(lambda driver,config,data:retry_cleanup(driver,config,args.cleanup_root)) if args.cleanup_root else callback,daemon_kind='owned')


if __name__=='__main__':main()
