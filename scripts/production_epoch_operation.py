"""Single-attempt production epoch operation. Preparation never invokes an evaluator."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

from deploy.production_preparation import SOURCE, IMAGES, FINGERPRINT, read_manifest
from deploy.production_preflight import read_private_env, check
from deploy.production_receipts import digest, validate_receipt, render, verify_seal, read_receipt
from deploy.recovery_journal import atomic_json, safe_path, sync_directory

HELPERS = tuple('src/mldsafail/benchmark_v050/' + n + '.py' for n in ('cli', 'evidence', 'execution'))
OPERATOR_FILES = ('deploy/production_inspection.py', 'deploy/production_preparation.py', 'deploy/production_preflight.py', 'deploy/production_receipts.py', 'deploy/recovery_journal.py', 'deploy/host_checks.py')
PURPOSE = 'production_epoch_only'


def require(condition):
    if not condition:
        raise ValueError('production_binding_or_prerequisite_invalid')


def publish(path, value):
    """Exclusive durable private publication."""
    path = safe_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    sync_directory(path.parent)


def source_hashes():
    return {p: hashlib.sha256(subprocess.check_output(['git', 'show', SOURCE + ':' + p], timeout=20)).hexdigest() for p in HELPERS}



def read_packet(path):
    packet = read_manifest(path)
    for key in ('candidate', 'staging', 'receipt', 'manifest'):
        packet[key] = str(safe_path(Path(path).absolute().parent / packet[key]))
    return packet

def validate(packet, *, local_outputs=False):
    require(packet['schema'] == 'mldsafail.production-operation.v1')
    require(packet['purpose'] == PURPOSE and packet['source'] == SOURCE)
    require(packet['helper_hashes'] == source_hashes())
    require(packet['operator_hashes'] == {p: digest(p) for p in OPERATOR_FILES})
    require(packet['wrapper_sha256'] == digest(__file__))
    require(packet['runbook_sha256'] == digest('docs/PRODUCTION_EPOCH_PROCEDURE.md'))
    require(packet['benchmark_version'] == '0.5.0')
    require(re.fullmatch('[a-f0-9]{40}', packet['operator_revision']))
    for source in (*OPERATOR_FILES, 'scripts/production_epoch_operation.py', 'docs/PRODUCTION_EPOCH_PROCEDURE.md'):
        committed = subprocess.check_output(['git', 'show', packet['operator_revision'] + ':' + source], timeout=20)
        require(hashlib.sha256(committed).hexdigest() == digest(source))
    require(packet['host'] == {'address': '178.128.17.58', 'account': 'mldsafail', 'uid': 1000,
        'socket': '/run/user/1000/docker.sock', 'host_key': 'SHA256:OtjIfXCrqewb9FTJ8jpU7Rq7aZL4P8P7U0dKZ8DoB5w'})
    for role, key in (('controller', 'COORDINATOR_IMAGE'), ('worker', 'WORKER_IMAGE')):
        require(packet[role]['index'] == 'sha256:' + IMAGES[key])
        require(all(re.fullmatch('sha256:[a-f0-9]{64}', packet[role][k]) for k in ('index', 'platform_manifest', 'configuration')))
    require(packet['candidate_sha256'] == digest(packet['candidate']))
    require(packet['receipt_sha256'] == digest(packet['receipt']))
    receipt = read_receipt(packet['receipt'])
    require(packet['daemon_id'] == receipt['daemon_id'])
    require(packet['controller'] == receipt['images']['COORDINATOR_IMAGE'])
    require(packet['worker'] == receipt['images']['WORKER_IMAGE'])
    require(packet['manifest_sha256'] == digest(packet['manifest']))
    require(packet['limits'] == {'memory': '512m', 'cpus': '1', 'pids': '256', 'create_timeout': 5400, 'audit_timeout': 600, 'inspection_timeout': 20, 'process_timeout': 10})
    require(re.fullmatch('[a-f0-9]{32}', packet['operation_id']))
    require(re.fullmatch('[A-Za-z0-9_.-]+', packet['worker_cgroup']))
    def output_path(value):
        path = Path(value)
        require(path.is_absolute() and '..' not in path.parts)
        return safe_path(path) if local_outputs else path
    operation = output_path(packet['operation'])
    epoch = output_path(packet['epoch'])
    require(epoch == output_path(read_private_env(packet['candidate'])['PRODUCTION_EVALUATOR_ROOT']) / 'epoch')
    require(output_path(packet['lock']) == operation.parent / 'production-epoch.lock')
    require(output_path(packet['attempt']) == operation.parent / 'production-epoch.attempt.json')
    final = output_path(packet['final_destination'])
    require(not final.is_relative_to(operation) and not operation.is_relative_to(final))
    return operation


def local_host(packet):
    return os.getuid() == packet['host']['uid'] and socket.gethostname() == packet['hostname']


def prepare(packet_path):
    packet = read_packet(packet_path)
    operation = validate(packet)
    if local_host(packet):
        require(not operation.exists() and not Path(packet['attempt']).exists())
        require(not Path(packet['epoch']).parent.exists())
    env = read_private_env(packet['candidate'])
    from deploy.production_preparation import check_manifest
    errors = check(env, read_private_env(packet['staging']), preparation=True)
    errors += check_manifest(env, read_manifest(packet['manifest']), preparation=True)
    errors += validate_receipt(env, packet['candidate'], packet['receipt'], preparation=True)
    if not errors:
        errors += render(env, preparation=True)
    if errors:
        raise ValueError('preparation_preflight_failed')
    return {'schema': 'mldsafail.production-operation-prepared.v1', 'packet_sha256': digest(packet_path),
            'epoch_pending': True, 'authorization_present': False,
            'scheduling_control_required': 'stop_and_verify_existing_coordinator_under_later_owner_authority'}


@contextmanager
def locked(packet):
    path = safe_path(packet['lock'])
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        status = os.fstat(descriptor)
        require(status.st_uid == os.getuid() and status.st_nlink == 1 and not status.st_mode & 0o077)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


def docker(packet, args, **kwargs):
    env = {**os.environ, 'DOCKER_HOST': 'unix://' + packet['host']['socket']}
    env.pop('DOCKER_CONTEXT', None)
    return subprocess.run(['docker', *args], env=env, check=True, capture_output=True, text=True, timeout=20, **kwargs)


def live_gate(packet):
    """No scheduling mutation: require the existing coordinator already stopped."""
    require(not Path(packet['operation']).exists() and not Path(packet['epoch']).parent.exists())
    require(os.getuid() == packet['host']['uid'] and socket.gethostname() == packet['hostname'])
    import stat
    endpoint = safe_path(packet['host']['socket'])
    require(stat.S_ISSOCK(endpoint.stat().st_mode) and endpoint.stat().st_uid == os.getuid())
    info = json.loads(docker(packet, ['info', '--format', '{{json .}}']).stdout)
    require(info['ID'] == packet['daemon_id'])
    from deploy.production_receipts import validate_receipt
    require(not validate_receipt(read_private_env(packet['candidate']), packet['candidate'], packet['receipt'], preparation=True))
    require(time.time() - read_manifest(read_receipt(packet['receipt'])['inspection'])['time'] < 300)
    require(any('rootless' in x for x in info['SecurityOptions']))
    for role in ('controller', 'worker'):
        image = json.loads(docker(packet, ['image', 'inspect', packet[role]['index']]).stdout)[0]
        require(image['Id'] == packet[role]['index'] and image['Os'] == 'linux' and image['Architecture'] == 'amd64')
    containers = json.loads(docker(packet, ['container', 'inspect', *packet['coordinator_ids']]).stdout)
    require(containers and all(not c['State']['Running'] and not c['HostConfig']['RestartPolicy']['Name'] in ('always', 'unless-stopped') for c in containers))
    running = docker(packet, ['ps', '-q']).stdout.split()
    if running:
        rows = json.loads(docker(packet, ['container', 'inspect', *running]).stdout)
        require(all(c['Id'] in packet['allowed_running_services'] for c in rows))
    require(not docker(packet, ['ps', '-q', '--filter', 'label=org.mldsafail.production-epoch']).stdout.strip())
    jobs = subprocess.check_output(['systemctl', '--user', 'list-jobs', '--no-legend'], text=True, timeout=10)
    require(not jobs.strip())
    require(os.getloadavg()[0] < 0.5)
    # Exclude other evaluator processes as well as worker containers.
    processes = subprocess.check_output(['ps', '-eo', 'pid,args'], text=True, timeout=10)
    require(not any('mldsafail.benchmark_v050' in line or 'start-coordinator' in line for line in processes.splitlines()))
    from deploy.host_checks import evaluate
    require(not evaluate(True, {'host': True}, [], None, [], scope='service'))
    require(Path('/sys/fs/cgroup', packet['worker_cgroup']).is_dir())
    return {'daemon_id': info['ID'], 'coordinators': containers, 'processes': processes, 'time': time.time()}


def controller(packet, audit=False):
    operation = Path(packet['operation'])
    epoch = packet['epoch']
    args = ['run', '--name', 'production-epoch-' + packet['operation_id'] + ('-audit' if audit else '-create'),
        '--label', 'org.mldsafail.production-epoch=' + packet['operation_id'],
        '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--user', '0:0', '--memory', packet['limits']['memory'], '--cpus', packet['limits']['cpus'],
        '--pids-limit', packet['limits']['pids'], '--cgroup-parent', packet['worker_cgroup'],
        '--tmpfs', '/tmp:size=128m', '--mount', 'type=bind,src=' + str(Path(epoch).parent) + ',dst=' + str(Path(epoch).parent) + (',readonly' if audit else '')]
    if not audit:
        args += ['--mount', 'type=bind,src=' + packet['host']['socket'] + ',dst=/var/run/docker.sock',
            '--mount', 'type=bind,src=' + str(operation / 'tools') + ',dst=/operation-tools,readonly',
            '-e', 'DOCKER_HOST=unix:///var/run/docker.sock', '-e', 'PATH=/operation-tools:/app/.venv/bin:/usr/local/bin:/usr/bin:/bin']
        code = ('from pathlib import Path; from mldsafail.benchmark_v050 import cli,execution; '
            'cli.environment=lambda:execution.environment(' + repr(packet['worker']['index']) + '); '
            'cli.create_epoch(Path(' + repr(epoch) + '))')
    else:
        code = ('import json; from pathlib import Path; from mldsafail.benchmark_v050.evidence import audit_epoch; '
            'm,r=audit_epoch(Path(' + repr(epoch) + ')); assert len(r)==100; '
            'print(json.dumps(dict(epoch_id=m["id"],environment=m["environment"],reference_cases=len(r))))')
    return ['docker', *args, '--entrypoint', '/app/.venv/bin/python', packet['controller']['index'], '-c', code]


def terminate_owned(packet):
    """Only stop positively identified resources with this operation's unique label."""
    ids = docker(packet, ['ps', '-aq', '--filter', 'label=org.mldsafail.production-epoch=' + packet['operation_id']]).stdout.split()
    for identifier in ids:
        row = json.loads(docker(packet, ['container', 'inspect', identifier]).stdout)[0]
        require(row['Config']['Labels']['org.mldsafail.production-epoch'] == packet['operation_id'])
        if row['State']['Running']:
            docker(packet, ['kill', identifier])


def stream(packet, audit=False):
    operation = Path(packet['operation'])
    name = 'audit' if audit else 'create'
    env = {**os.environ, 'DOCKER_HOST': 'unix://' + packet['host']['socket']}
    env.pop('DOCKER_CONTEXT', None)
    with (operation / (name + '.stdout')).open('xb') as out, (operation / (name + '.stderr')).open('xb') as err:
        process = subprocess.Popen(controller(packet, audit), stdout=out, stderr=err, env=env)
        try:
            result = process.wait(timeout=packet['limits'][name + '_timeout'])
            publish(operation / (name + '.exit.json'), {'returncode': result})
            if result:
                raise RuntimeError('controller_failed')
        except BaseException:
            try:
                terminate_owned(packet)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                atomic_json(operation / (name + '.exit.json'), {'returncode': process.returncode, 'terminal': True})
            raise
        finally:
            out.flush(); err.flush()
            os.fsync(out.fileno()); os.fsync(err.fileno())


def execute(packet_path, authorization_path):
    os.umask(0o077)
    packet = read_packet(packet_path)
    operation = validate(packet, local_outputs=True)
    require(str(Path(packet_path).absolute().parent) == packet['remote_bundle'])
    authorization = read_manifest(authorization_path)
    review = read_manifest(authorization['review_file'])
    require(authorization == {'purpose': PURPOSE, 'packet_sha256': digest(packet_path), 'authorized_by': 'owner', 'review_file': authorization['review_file'], 'review_sha256': digest(authorization['review_file'])})
    require(review['packet_sha256'] == digest(packet_path) and review['decision'] == 'approved' and review['reviewer'] != 'implementation_agent')
    with locked(packet):
        require(not operation.exists() and not Path(packet['attempt']).exists() and not Path(packet['epoch']).parent.exists())
        prepare(packet_path)
        gate = live_gate(packet)
        # Global durable marker precedes output creation and every evaluation. Never removed.
        publish(Path(packet['attempt']), {'packet_sha256': digest(packet_path), 'time': time.time()})
        operation.mkdir(mode=0o700)
        publish(operation / 'preflight.json', gate)
        journal = {'packet_sha256': digest(packet_path), 'state': 'creation_started'}
        atomic_json(operation / 'journal.json', journal)
        try:
            safe_path(Path(packet['epoch']).parent).mkdir(mode=0o700)
            tools = operation / 'tools'; tools.mkdir(mode=0o700)
            wrapper = tools / 'docker'
            wrapper.write_text('#!/app/.venv/bin/python\nimport os,sys\na=sys.argv[1:]\n'
                'if a and a[0]=="run": a[1:1]=' + repr(['--label', 'org.mldsafail.production-epoch=' + packet['operation_id'], '--cgroup-parent', packet['worker_cgroup']]) + '\n'
                'os.execv("/usr/local/bin/docker",["docker",*a])\n')
            wrapper.chmod(0o700)
            stream(packet)
            require((Path(packet['epoch']) / 'COMPLETE.json').is_file())
            journal['state'] = 'created'
        except BaseException:
            journal['state'] = 'creation_failed'
            raise
        finally:
            atomic_json(operation / 'journal.json', journal)


def audit(packet_path):
    os.umask(0o077)
    packet = read_packet(packet_path); operation = validate(packet, local_outputs=True)
    with locked(packet):
        journal = read_manifest(operation / 'journal.json')
        require(journal == {'packet_sha256': digest(packet_path), 'state': 'created'})
        require(read_manifest(packet['attempt'])['packet_sha256'] == digest(packet_path))
        require((Path(packet['epoch']) / 'COMPLETE.json').is_file())
        journal['state'] = 'audit_started'; atomic_json(operation / 'journal.json', journal)
        try:
            stream(packet, audit=True)
            result = json.loads((operation / 'audit.stdout').read_text())
            require(result['reference_cases'] == 100)
            require(result['environment']['image_id'] == packet['worker']['index'])
            require(result['environment']['trusted_fingerprint'] == FINGERPRINT)
            require(result['environment']['host']['ID'] == packet['daemon_id'])
            verify_seal(packet['epoch'])
            result.update(manifest_sha256=digest(Path(packet['epoch']) / 'manifest.json'), reference_sha256=digest(Path(packet['epoch']) / 'reference-costs.json'))
            result.update(audited=True, epoch=packet['epoch'], packet_sha256=digest(packet_path),
                          seal_sha256=digest(Path(packet['epoch']) / 'COMPLETE.json'))
            publish(operation / 'audited.json', result)
            journal['state'] = 'audited'
        except BaseException:
            journal['state'] = 'audit_failed'
            raise
        finally:
            atomic_json(operation / 'journal.json', journal)


def finalize(packet_path, destination):
    """Create a new final candidate; full preflight must pass before readiness."""
    packet = read_packet(packet_path); operation = validate(packet, local_outputs=True)
    with locked(packet):
        journal = read_manifest(operation / 'journal.json')
        require(journal == {'packet_sha256': digest(packet_path), 'state': 'audited'})
        audited = read_manifest(operation / 'audited.json')
        require(audited['seal_sha256'] == digest(Path(packet['epoch']) / 'COMPLETE.json'))
        require(audited['packet_sha256'] == digest(packet_path))
        verify_seal(packet['epoch'])
        require(str(destination) == packet['final_destination'])
        destination = safe_path(destination); destination.mkdir(mode=0o700)
        env = read_private_env(packet['candidate'])
        env['MLDSAFAIL_MLWE_EPOCH_ID'] = audited['epoch_id']
        candidate = destination / 'production.env'
        fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(''.join(k + '=' + v + '\n' for k, v in env.items()))
            out.flush(); os.fsync(out.fileno())
        manifest = read_manifest(packet['manifest'])
        manifest.update(schema='mldsafail.production-final.v1', unresolved={})
        publish(destination / 'manifest.json', manifest)
        audited['candidate_sha256'] = digest(candidate)
        publish(destination / 'binding.json', audited)
        receipt = read_receipt(packet['receipt'])
        receipt.update(candidate_sha256=digest(candidate), final_binding=str(destination / 'binding.json'))
        publish(destination / 'receipt.json', receipt)
        from deploy.production_preparation import check_manifest
        errors = check(env, read_private_env(packet['staging'])) + check_manifest(env, manifest)
        errors += validate_receipt(env, candidate, destination / 'receipt.json', preparation=False)
        errors += render(env)
        publish(destination / 'preflight.json', {'errors': errors, 'ready': not errors})
        if errors:
            raise ValueError('final_preflight_failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'execute', 'audit', 'finalize'))
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            print(json.dumps(prepare(args.packet), sort_keys=True))
        elif args.action == 'execute':
            execute(args.packet, args.authorization)
        elif args.action == 'audit':
            audit(args.packet)
        else:
            finalize(args.packet, args.destination)
    except (Exception, KeyboardInterrupt):
        print('production_operation_refused_or_failed_evidence_retained')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
