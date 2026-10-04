"""Guest-only power-loss fixture; runs solely in the disposable local VM."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from deploy.recovery_journal import Journal, atomic_json

ROOT = Path.home() / 'powerloss-fixture'
PROJECT = 'disposable-powerloss'


def command(argv, timeout=120):
    return subprocess.check_output(argv, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()


def main(mode):
    os.environ['DOCKER_HOST'] = 'unix:///run/user/1000/docker.sock'
    os.environ['XDG_RUNTIME_DIR'] = '/run/user/1000'
    compose = ['docker', 'compose', '-p', PROJECT, '-f', str(ROOT / 'compose.yaml')]
    if mode == 'prepare':
        ROOT.mkdir(mode=0o700)
        info = json.loads(command(['docker', 'info', '--format', '{{json .}}']))
        if not any('rootless' in value for value in info['SecurityOptions']):
            raise RuntimeError('Rootless daemon required')
        command(['docker', 'pull', 'alpine:3.21'])
        image = json.loads(command(['docker', 'image', 'inspect', 'alpine:3.21']))[0]['Id']
        (ROOT / 'compose.yaml').write_text('''services:
  migrate:
    image: IMAGE
    command: [sh, -c, "echo invocation >> /state/migrations"]
    volumes: ["state:/state"]
  web:
    image: IMAGE
    command: [sleep, "3600"]
    volumes: ["state:/state:ro"]
    depends_on: {migrate: {condition: service_completed_successfully}}
  coordinator:
    image: IMAGE
    command: [sleep, "3600"]
    depends_on: {migrate: {condition: service_completed_successfully}}
volumes:
  state:
'''.replace('IMAGE', image))
        command(compose + ['up', '-d', 'web', 'coordinator'])
        identities = {role: command(compose + ['ps', '-aq', role]) for role in ('web', 'coordinator', 'migrate')}
        baseline = {'identities': identities, 'image': image,
                    'migration_state': json.loads(command(['docker', 'inspect', identities['migrate']]))[0]['State'],
                    'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    'python': sys.version, 'kernel': command(['uname', '-r']), 'docker': info['ServerVersion']}
        atomic_json(ROOT / 'baseline.json', baseline)
        atomic_json(ROOT / 'identities.json', {role: identities[role] for role in ('web', 'coordinator')})
        process = subprocess.Popen([sys.executable, '-m', 'deploy.native_recovery_acceptance', '--child',
                                    '--output', str(ROOT), '--boundary', 'hard-power-loss'],
                                   stdout=(ROOT / 'child.log').open('w'), stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while not (ROOT / 'boundary.json').exists():
            if process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Durable power-loss boundary unavailable')
            time.sleep(0.1)
        print(json.dumps(baseline))
    elif mode == 'reconcile':
        baseline = json.loads((ROOT / 'baseline.json').read_text())
        if baseline['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip():
            raise RuntimeError('Guest did not reboot')
        lock = (ROOT / 'lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = Journal(ROOT / 'operation.json', {})
        atomic_json(ROOT / 'interrupted.json', journal.data)
        if journal.data['cleanup_complete']:
            raise RuntimeError('No interrupted maintenance evidence')
        journal.cleanup()
        journal.cleanup()
        for role, identifier in baseline['identities'].items():
            if command(compose + ['ps', '-aq', role]) != identifier:
                raise RuntimeError('Original container identity changed')
        migrate = baseline['identities']['migrate']
        if json.loads(command(['docker', 'inspect', migrate]))[0]['State'] != baseline['migration_state']:
            raise RuntimeError('Migration activated after hard power loss')
        if command(['docker', 'exec', baseline['identities']['web'], 'cat', '/state/migrations']) != 'invocation':
            raise RuntimeError('Migration sentinel changed')
        atomic_json(ROOT / 'reconciled.json', journal.data)
        command(compose + ['down', '-v', '--remove-orphans'])
        for kind in ('container', 'volume', 'network'):
            if command(['docker', kind, 'ls', '-aq' if kind == 'container' else '-q', '--filter',
                        'label=com.docker.compose.project=' + PROJECT]):
                raise RuntimeError('Owned fixture resources remain')
        result = {'hard_power_loss_passed': True, 'cleanup_complete': True,
                  'identity_preserved': True, 'migration_invocations': 1, 'repeated_cleanup_passed': True,
                  'new_boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
        atomic_json(ROOT / 'result.json', result)
        print(json.dumps(result))
    else:
        raise ValueError('Unknown fixture mode')


if __name__ == '__main__':
    os.umask(0o077)
    main(sys.argv[1])
