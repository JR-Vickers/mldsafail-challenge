"""Bounded, birth-fenced SIGKILL at actual synthetic scheduled check admission.

Does not provision repositories, units, or timers. Root starts the reviewed
synthetic repository and direct delegated activation unit, then invokes this
owned native controller. The next fresh activation performs terminal cleanup.
"""
import argparse
import hashlib
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time
from deploy import owned_client, owned_daemon
from deploy.operator_activation import configuration_digest, job_journal_path


def admitted(state, operation, effective):
    job = state.get('operator_job', {})
    if (state.get('daemon_kind') != 'owned' or job.get('job') != 'recovery-check' or
        job.get('state') != 'running' or job.get('journal_created') is not True or
        configuration_digest(effective) != job.get('effective_config_digest') or
        str(job_journal_path('recovery-check', effective)) != job.get('journal_path') or
        operation.get('cleanup_complete') is not False):
        raise RuntimeError('Actual admitted running recovery check required')
    manifest = owned_daemon.load_manifest(state['manifest_path'])
    contexts = operation.get('daemon_contexts', {})
    if owned_daemon.fingerprint(manifest) not in contexts:
        raise RuntimeError('Actual check must bind its exact owned daemon epoch')
    return job


def signal_exact_owner(pid, birth, parent, domain):
    descriptor = os.pidfd_open(pid)
    try:
        if owned_client.identity(pid) != birth or owned_client.domain_identity(parent) != domain:
            raise RuntimeError('Activation changed after PID descriptor acquisition')
        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
    finally:
        os.close(descriptor)


def publish_final(report, save, original, errors):
    report.update(cleanup_complete=not errors, cleanup_errors=errors,
                  job_cleanup_pending=report['signal_sent'],
                  passed=original is None and not errors and report['signal_sent'])
    try:
        save()
    except BaseException as publication:
        report.update(passed=False, failure_class=type(publication).__name__,
                      final_publication_failed=True)
        try: save()
        except BaseException as retry: publication.add_note('Negative publication retry: '+type(retry).__name__)
        if original is not None:
            original.add_note('Signal evidence publication: '+type(publication).__name__)
        else:
            raise publication
    if errors and original is None:
        raise RuntimeError('Independent observer cleanup incomplete')


def execute(driver, activation_config, unit, output, timeout=60):
    if sys.platform != 'linux' or not 1 <= timeout <= 120 or not re.fullmatch(r'mldsafail-[a-z0-9-]+\.service',unit):
        raise ValueError('Bounded native Linux gate required')
    source = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],timeout=15):
        raise RuntimeError('Clean retained source required')
    head = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],timeout=15).decode().strip()
    config = owned_daemon.read_private_json(activation_config)
    # The fixture is private and explicitly synthetic. No owner or staging
    # repository may be inferred from an ordinary operational configuration.
    private = owned_daemon.read_private_json(config['job_config'])
    if (config['job'] != 'recovery-check' or private.get('synthetic_only') is not True or
        private.get('actual_owner_custody_accepted') is not False or
        private.get('benchmark_epoch_data_used') is not False or
        '/syntheticbucket/' not in private['repository']):
        raise ValueError('Explicit disposable synthetic repository required')
    output = owned_daemon._canonical(output)
    owned_daemon._private_directory(output.parent)
    output.mkdir(mode=0o700)
    report = dict(schema='mldsafail.interrupted-job-signal.v1', source_commit=head,
                  passed=False, signal_sent=False, cleanup_complete=False, clients=[])
    def save(): owned_daemon.publish(output/'report.json',report)
    save()
    error = None
    try:
        result = owned_client.run(['systemctl','--user','show',unit,'--property=MainPID',
            '--property=ControlGroup','--property=Delegate','--property=ActiveState'],
            report['clients'],save,output,timeout=15,capture_output=True)
        props = dict(line.split('=',1) for line in result.stdout.decode().splitlines() if '=' in line)
        pid = int(props['MainPID'])
        if pid <= 1 or props.get('Delegate') != 'yes' or props.get('ActiveState') != 'active':
            raise RuntimeError('Actual active delegated activation unit required')
        birth = owned_client.identity(pid)
        argv = (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')[:-1]
        expected = [os.fsencode(sys.executable),b'-m',b'deploy.operator_activation',
                    b'--config',os.fsencode(activation_config),b'--unit',os.fsencode(unit)]
        if argv != expected or birth['uid'] != os.getuid():
            raise RuntimeError('Only direct exact reviewed activation process may be signaled')
        parent = Path('/sys/fs/cgroup')/props['ControlGroup'].lstrip('/')
        domain = owned_client.domain_identity(parent)
        deadline = time.monotonic()+timeout
        while True:
            if owned_client.identity(pid) != birth or owned_client.domain_identity(parent) != domain:
                raise RuntimeError('Activation birth changed before interruption')
            state = owned_daemon.read_private_json(driver,cap=4*1024*1024)
            if (state['config']['source_commit'] != head or state['config']['operator_unit'] != unit or
                state['config']['operator_parent'] != str(parent) or
                state['config']['state_root'] != str(Path(driver).parent)):
                raise RuntimeError('Exact original driver source/unit/root required')
            job = state.get('operator_job',{})
            if job.get('journal_created') is True:
                effective = owned_daemon.read_private_json(job['effective_config_path'])
                operation = owned_daemon.read_private_json(job['journal_path'],cap=4*1024*1024)
                admitted(state,operation,effective)
                restic = str(Path(effective['restic_binary']).resolve())
                if hashlib.sha256(Path(restic).read_bytes()).hexdigest() != effective['restic_sha256']:
                    raise RuntimeError('Pinned actual restic binary changed')
                wanted = hashlib.sha256(b'\0'.join(map(os.fsencode,[restic,'check','--read-data']))+b'\0').hexdigest()
                for client in operation.get('clients',[]):
                    if client.get('expected_cmdline_sha256') != wanted:
                        continue
                    try: current = owned_client.identity(client['pid'])
                    except (KeyError,FileNotFoundError,ProcessLookupError): continue
                    if (current['cmdline_sha256'] == wanted and
                        all(current[key] == client.get(key) for key in ('pid','uid','boot_id','start_ticks')) and
                        owned_client.verify_domain(client) is not None):
                        report.update(driver_state=str(driver), attempt_id=state['id'],
                            owner_birth=birth,owner_domain=domain,actual_restic_birth=current,
                            daemon_epoch=state['registered_manifest']['epoch'],
                            job_journal=job['journal_path'],signal_intent='SIGKILL')
                        save()  # Durable actual admission/birth evidence before signal.
                        if owned_client.identity(pid) != birth or owned_client.domain_identity(parent) != domain:
                            raise RuntimeError('Activation changed after durable signal intent')
                        signal_exact_owner(pid,birth,parent,domain)
                        report.update(signal_sent=True)
                        save()
                        return report
            if time.monotonic() >= deadline:
                raise TimeoutError('Actual restic check did not reach bounded admission')
            time.sleep(.1)
    except BaseException as caught:
        error=caught
        report['failure_class']=type(caught).__name__
        raise
    finally:
        errors=[]
        for client in report['clients']:
            try: owned_client.stop(client)
            except BaseException as caught: errors.append(type(caught).__name__)
        publish_final(report,save,error,errors)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver',type=Path,required=True)
    parser.add_argument('--activation-config',type=Path,required=True)
    parser.add_argument('--unit',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=60)
    args=parser.parse_args()
    execute(args.driver,args.activation_config,args.unit,args.output,args.timeout)
