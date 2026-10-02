"""VPS-only acceptance driver. Private journal and evidence never leave the host."""
from __future__ import annotations
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import fcntl
import threading
from contextlib import contextmanager

@contextmanager
def journal_lock(path):
    with path.with_suffix(".journal-lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield

def docker_api_version(server, minimum="1.41", maximum="1.47"):
    parse = lambda value: tuple(map(int, value.split(".")))
    chosen = min(parse(server["ApiVersion"]), parse(maximum))
    require(chosen >= max(parse(server.get("MinAPIVersion", "1.24")), parse(minimum)),
            "Docker API versions do not overlap")
    return ".".join(map(str, chosen))

SCENARIOS = {'cancellation': 'hang', 'timeout': 'hang', 'invalid': 'invalid',
             'crash': 'crash', 'retry': 'reference', 'exhaustion': 'reference', 'lease': 'reference'}


def require(condition, message='Acceptance condition failed'):
    if not condition:
        raise RuntimeError(message)


def command(args, input=None, timeout=30):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)
    require(result.returncode == 0, 'Host command failed (details retained on host only)')
    return result.stdout.strip()


def save(path, data):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def worker_owned(info, submissions, image):
    """A name alone is never sufficient authority to kill a container."""
    mounts = info.get('Mounts', [])
    return (info['Image'] == image and info['Name'].startswith('/mlwe-') and len(mounts) == 1
            and mounts[0]['Destination'] == '/solver' and not mounts[0]['RW']
            and any(mounts[0]['Source'] == '/srv/mldsafail-evaluator/jobs/runs/' + s + '/' + str(a) + '/solver'
                    for s, a in submissions))


def containers():
    ids = command(['docker', 'ps', '-aq']).splitlines()
    return json.loads(command(['docker', 'inspect', *ids])) if ids else []


def cleanup(journal, generation=None):
    with journal_lock(journal):
        if generation is not None and json.loads(journal.read_text()).get("generation", 0) != generation:
            return
        _cleanup(journal)

def _cleanup(journal):
    data = json.loads(journal.read_text())
    data['closing'] = True
    save(journal, data)
    errors = []
    if not data.get('cleanup_complete') and data.get('original_mode') is not None:
        try:
            os.chmod(data['work_root'], data['original_mode'])
        except Exception:
            errors.append('permission restoration failed')
    credential = journal.parent / 'cleanup-token'
    if credential.exists() and not data.get('cleanup_complete'):
        for entry in data.get('scenarios', {}).values():
            if entry.get('submission') and not entry.get('passed'):
                request = urllib.request.Request('http://127.0.0.1:8080/api/v1/submissions/' +
                    entry['submission'] + '/cancel', data=b'{}', headers={
                    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + credential.read_text()})
                try:
                    urllib.request.urlopen(request, timeout=10).close()
                except (urllib.error.URLError, TimeoutError):
                    pass
    try:
        inventory = containers()
    except Exception:
        inventory = []
        errors.append("container inventory failed")
    for info in inventory:
        try:
            if info['Config'].get('Labels', {}).get('org.mldsafail.acceptance') == data['run_id']:
                command(['docker', 'rm', '-f', info['Id']])
            elif worker_owned(info, data.get('owned_attempts', []), data['worker_image']):
                command(['docker', 'rm', '-f', info['Id']])
        except Exception:
            errors.append('container cleanup failed')
    if data.get('cleanup_complete'):
        credential.unlink(missing_ok=True)
        return
    if data.get('restore_command'):
        try:
            command(data['restore_command'], timeout=60)
        except Exception:
            errors.append('release restoration failed')
    if data.get('maintenance'):
        for role, running in data.get('service_states', {'coordinator': True, 'web': True}).items():
            try:
                command(data['compose'] + ['start' if running else 'stop', role])
            except Exception:
                errors.append('service restoration failed')
    try:
        credential.unlink(missing_ok=True)
    except Exception:
        errors.append('credential removal failed')
    if data.get('service_states', {}).get('web'):
        try:
            command(['curl', '--fail', '--silent', 'http://127.0.0.1:8080/health/ready'])
        except Exception:
            errors.append('health verification failed')
    data['cleanup_errors'] = errors
    save(journal, data)
    require(not errors, 'Cleanup incomplete; retry --cleanup')
    data['maintenance'] = False
    data['cleanup_complete'] = True
    save(journal, data)
    credential.unlink(missing_ok=True)


def watchdog(path, generation=None):
    low_memory_since = None
    while True:
        time.sleep(5)
        data = json.loads(path.read_text())
        if data.get('cleanup_complete') or (generation is not None and data.get('generation', 0) != generation):
            return
        abort = time.time() > data['heartbeat'] + 45
        if data.get('watch_host'):
            available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:'))) * 1024
            if available < 128 * 1024**2:
                low_memory_since = low_memory_since or time.monotonic()
                abort |= time.monotonic() - low_memory_since >= 30
            else:
                low_memory_since = None
            abort |= shutil.disk_usage('/srv').free < 5 * 1024**3
        if abort:
            for attempt in range(3):
                try:
                    cleanup(path, generation) if generation is not None else cleanup(path)
                    break
                except Exception:
                    time.sleep(5)
            return


class Driver:
    def __init__(self, config):
        self.c = config
        self.directory = Path(config['directory'])
        self.path = self.directory / 'journal.json'
        self.compose = ['docker', 'compose', '--project-directory', config['deployment'],
                        '--env-file', config['env_file'], '-f', config['deployment'] + '/compose.private.yaml']
        self.mutex = threading.RLock()
        self.low_memory_since = None
        self.probe_id = None
        self.process = None
        binding = hashlib.sha256(json.dumps({k: config[k] for k in
            ('fixture_url', 'fixture_sha', 'release_manifest', 'rollback_manifest', 'deployment', 'env_file')},
            sort_keys=True).encode()).hexdigest()
        if self.path.exists():
            self.j = json.loads(self.path.read_text())
            require(self.j['binding'] == binding, 'Run journal belongs to different inputs')
        else:
            self.j = {'run_id': config['run_id'], 'binding': binding, 'scenarios': {},
                      'owned_attempts': [], 'heartbeat': time.time(), 'cleanup_complete': True}
            save(self.path, self.j)

    def touch(self):
        with self.mutex, journal_lock(self.path):
            disk = json.loads(self.path.read_text())
            require(not disk.get('closing') and disk.get('generation', 0) == self.j.get('generation', 0), 'Cleanup has begun; run cannot reopen')
            self.j['heartbeat'] = time.time()
            save(self.path, self.j)

    def mutate(self, args, **kwargs):
        with journal_lock(self.path):
            require(not json.loads(self.path.read_text()).get('closing'), 'Cleanup has begun')
            return command(args, **kwargs)

    def heartbeat(self):
        with self.mutex, journal_lock(self.path):
            data = json.loads(self.path.read_text())
            if data.get('closing'):
                return
            data['heartbeat'] = time.time()
            save(self.path, data)

    def clone(self, template, image=None, once=False):
        with journal_lock(self.path):
            require(not json.loads(self.path.read_text()).get('closing'), 'Cleanup has begun')
            return self._clone(template, image, once)

    def _clone(self, template, image=None, once=False):
        """Create/start while holding the cleanup lock, preserving service isolation."""
        endpoint = os.environ.get('DOCKER_HOST') or json.loads(command(['docker', 'context', 'inspect']))[0]['Endpoints']['docker']['Host']
        require(endpoint.startswith('unix://'), 'Acceptance requires local rootless Docker')
        class UnixConnection(http.client.HTTPConnection):
            def connect(connection):
                connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                connection.sock.settimeout(20)
                connection.sock.connect(endpoint[7:])
        config = template['Config'].copy()
        config.update(Image=image or template['Image'],
                      Entrypoint=['/app/.venv/bin/python'],
                      Cmd=['-m', 'mldsafail.evaluator.coordinator', '--once'] if once else
                          ['-c', 'import time; time.sleep(86400)'],
                      Labels={'org.mldsafail.acceptance': self.c['run_id']})
        host = template['HostConfig'].copy()
        host['RestartPolicy'] = {'Name': 'no', 'MaximumRetryCount': 0}
        config['HostConfig'] = host
        connection = UnixConnection('localhost')
        version = docker_api_version(json.loads(command(['docker', 'version', '--format', '{{json .Server}}'])))
        networks = template.get('NetworkSettings', {}).get('Networks', {})
        if networks:
            config['NetworkingConfig'] = {'EndpointsConfig': {name: {} for name in networks}}
        connection.request('POST', '/v' + version + '/containers/create?name=acceptance-' + uuid.uuid4().hex,
                           json.dumps(config), {'Content-Type': 'application/json'})
        response = connection.getresponse()
        result = json.loads(response.read())
        require(response.status == 201, 'Cannot clone deployed coordinator')
        command(['docker', 'start', result['Id']])
        return result['Id']

    def probe(self, action, **fields):
        code = (self.directory / 'probe.py').read_text()
        # Request is stdin; raw evidence and exception details stay inside the VPS.
        payload = json.dumps({'action': action, **fields})
        wrapper = 'import io,sys;sys.stdin=io.StringIO(' + repr(payload) + ');exec(' + repr(code) + ')'
        return json.loads(command(['docker', 'exec', '-i', self.probe_id,
                                  '/app/.venv/bin/python', '-'], input=wrapper))

    def api(self, route, payload=None, token=None, key=None, expected=200):
        headers = {'Authorization': 'Bearer ' + (token or self.c['token'])}
        if key:
            headers['Idempotency-Key'] = key
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request('http://127.0.0.1:8080' + route,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status, body = response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read().decode()
        require(status in expected if isinstance(expected, tuple) else status == expected, 'API gate failed')
        self.probe('privacy', text=body)
        return json.loads(body)

    def guard(self, allowed=None):
        self.touch()
        active = self.probe('active')['active']
        require(set(active) <= ({allowed} if allowed else set()), 'Unrelated evaluation appeared')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        if available < 128 * 1024**2:
            self.low_memory_since = self.low_memory_since or time.monotonic()
            require(time.monotonic() - self.low_memory_since < 30, 'RAM below acceptance floor')
        else:
            self.low_memory_since = None
        require(shutil.disk_usage('/srv').free >= 5 * 1024**3, 'Disk below acceptance floor')
        workers = [i for i in containers() if i['Name'].startswith('/mlwe-') and i['State']['Running']]
        require(len(workers) <= 1, 'Concurrent worker execution')
        for worker in workers:
            require(worker_owned(worker, self.j['owned_attempts'], self.j['worker_image']), 'Unrelated worker')
            host, config = worker['HostConfig'], worker['Config']
            require(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] and config['User'] == '65534:65534')
            require('ALL' in host['CapDrop'] and any('no-new-privileges' in s for s in host['SecurityOpt']))
            require(host['Memory'] == 2 * 1024**3 and host['PidsLimit'] == 64 and host['NanoCpus'] == 10**9)
            require(not any(e.startswith(('MLDSAFAIL', 'POSTGRES', 'GITHUB')) for e in config['Env']))
        return workers

    def wait(self, predicate, seconds, allowed=None):
        deadline = time.monotonic() + seconds
        while True:
            self.guard(allowed)
            value = predicate()
            if value:
                return value
            require(time.monotonic() < deadline, 'Acceptance deadline exceeded')
            time.sleep(2)

    def one_shot(self, identifier, attempt):
        self.j['owned_attempts'].append([identifier, attempt])
        self.touch()  # Persist ownership before worker creation.
        self.process = self.clone(self.template, once=True)

    def finish_process(self, identifier, seconds=1200):
        self.wait(lambda: not json.loads(command(['docker', 'inspect', self.process]))[0]['State']['Running'],
                  seconds, identifier)
        info = json.loads(command(['docker', 'inspect', self.process]))[0]
        self.probe('privacy', text=command(['docker', 'logs', self.process]))
        require(info['State']['ExitCode'] == 0, 'One-shot coordinator exited abnormally')
        self.mutate(['docker', 'rm', self.process])
        self.process = None

    def fault(self, enabled):
        with journal_lock(self.path):
            require(not json.loads(self.path.read_text()).get('closing'), 'Cleanup has begun')
            os.chmod(self.j['work_root'], self.j['original_mode'] & ~0o222 if enabled else self.j['original_mode'])
        # Prove effective denial under the deployed identity before claiming work.
        if enabled:
            command(['docker', 'exec', self.probe_id, 'python', '-c',
                     "import os; assert not os.access(os.environ['MLDSAFAIL_EVALUATOR_WORK_ROOT'],os.W_OK)"])

    def scenario(self, name, kind):
        entry = self.j['scenarios'].setdefault(name, {'key': self.c['run_id'] + '-' + name})
        if not entry.get('submission'):
            recovered = self.probe('lookup', key=entry['key'], user=self.j['user'])['submission']
            if recovered:
                entry['submission'] = recovered
                self.touch()
        if entry.get('passed'):
            self.verify(name, kind, entry['submission'])
            return
        if entry.get('submission'):
            # Resume only evidence verification of finished work; interrupted faults are cleaned up.
            state = self.probe('state', submission=entry['submission'])
            require(state['job_status'] in {'complete', 'failed'},
                    'Interrupted submission remains active: use --cleanup, then a fresh run-id')
            self.verify(name, kind, entry['submission'])
            entry['passed'] = True
            self.touch()
            return
        self.guard()
        self.touch()  # Key persisted before request; retrying POST cannot duplicate a lost response.
        payload = {'repository_url': self.c['fixture_url'], 'commit_sha': self.c['fixture_sha'],
                   'solver_path': kind, 'benchmark_version': '0.5.0',
                   'hypothesis': 'Synthetic staging acceptance: ' + name, 'tags': ['failure-acceptance']}
        response = self.api('/api/v1/submissions', payload, key=entry['key'], expected=(200, 201))
        identifier = entry['submission'] = response['submission']['id']
        self.touch()
        if name in {'retry', 'exhaustion'}:
            try:
                self.fault(True)
                count = 1 if name == 'retry' else 3
                for attempt in range(1, count + 1):
                    self.one_shot(identifier, attempt)
                    self.finish_process(identifier, 90)
                    state = self.probe('state', submission=identifier)
                    require(state['attempt_count'] == attempt and state['attempts'][-1]['status'] == 'infrastructure_failed')
                    if attempt < count:
                        self.wait(lambda: dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(state['available_at']),
                                  30, identifier)
            finally:
                self.fault(False)
            if name == 'retry':
                self.wait(lambda: dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(state['available_at']),
                          30, identifier)
                self.one_shot(identifier, 2)
                self.finish_process(identifier)
        else:
            self.one_shot(identifier, 1)
            if name in {'cancellation', 'timeout', 'lease'}:
                started = time.monotonic()
                self.wait(lambda: self.probe('state', submission=identifier)['state'] == 'running'
                          and bool(self.guard(identifier)), 90, identifier)
                if name == 'timeout':
                    observed = self.wait(lambda: self.probe('timeout', submission=identifier)['timeout'],
                                         max(1, 150 - (time.monotonic() - started)), identifier)
                    require(observed)
                if name == 'lease':
                    self.mutate(['docker', 'kill', self.process])
                    self.mutate(['docker', 'rm', self.process])
                    self.process = None
                    for worker in containers():
                        if worker_owned(worker, [[identifier, 1]], self.j['worker_image']):
                            self.mutate(['docker', 'rm', '-f', worker['Id']])
                    state = self.probe('state', submission=identifier)
                    expiry = dt.datetime.fromisoformat(state['lease_expires_at'])
                    self.wait(lambda: dt.datetime.now(dt.timezone.utc) > expiry, 150, identifier)
                    self.one_shot(identifier, 2)
                    self.finish_process(identifier)
                else:
                    response = self.api('/api/v1/submissions/' + identifier + '/cancel', {})
                    require(response['submission']['cancel_requested'])
                    self.finish_process(identifier, min(90, 150 - (time.monotonic() - started)) if name == 'timeout' else 90)
            else:
                self.finish_process(identifier)
        self.verify(name, kind, identifier)
        entry['passed'] = True
        self.touch()
        print(json.dumps({'scenario': name, 'passed': True}), flush=True)

    def verify(self, name, kind, identifier):
        state = self.probe('state', submission=identifier)
        self.j['scenarios'][name]['evidence'] = state
        self.touch()
        terminal = {'cancellation': 'cancelled', 'timeout': 'cancelled', 'invalid': 'rejected',
                    'crash': 'accepted', 'retry': 'accepted', 'exhaustion': 'infrastructure_failed', 'lease': 'accepted'}[name]
        require(state['state'] == terminal and state['job_status'] == ('failed' if name == 'exhaustion' else 'complete'))
        expected_attempts = 3 if name == 'exhaustion' else 2 if name in {'retry', 'lease'} else 1
        require(state['attempt_count'] == expected_attempts and len(state['attempts']) == expected_attempts
                and state['max_attempts'] == 3)
        expected_transitions = ['queued']
        for number in range(1, expected_attempts + 1):
            expected_transitions.append('validating')
            if name == 'lease' and number == 1:
                expected_transitions.append('running')
            if number < expected_attempts or name == 'exhaustion':
                expected_transitions.append('infrastructure_failed')
                if number < expected_attempts:
                    expected_transitions.append('queued')
            else:
                expected_transitions += ['running', terminal]
        require(state['transitions'] == expected_transitions, 'Persisted transition chain differs')
        require(state['transitions'].count('validating') == expected_attempts)
        require(state['transitions'][-1] == terminal)
        require(len(state['results']) == (1 if terminal == 'accepted' else 0))
        require(state['attempts'][-1]['status'] == terminal)
        for index, attempt in enumerate(state['attempts'][:-1] if name != 'exhaustion' else state['attempts']):
            require(attempt['status'] == 'infrastructure_failed')
            require(attempt['failure_class'] == ('lease_expired' if name == 'lease' else 'PermissionError'))
            if index + 1 < len(state['attempts']) and name != 'lease':
                require((dt.datetime.fromisoformat(state['attempts'][index+1]['started']) -
                         dt.datetime.fromisoformat(attempt['finished'])).total_seconds() >= 5 * (index + 1))
        if name in {'retry', 'lease', 'exhaustion'}:
            require(state['transitions'].count('infrastructure_failed') == (3 if name == 'exhaustion' else 1))
            require(state['transitions'].count('queued') == expected_attempts)
        if name == 'invalid':
            require(state['rejection_code'] == 'invalid_answer' and state['attempts'][0]['failure_class'] == 'invalid_answer')
        if kind != 'hang' and name != 'exhaustion':
            self.probe('audit', submission=identifier, kind=kind)
        if name == 'timeout':
            require(self.probe('timeout', submission=identifier)['timeout'])
        api = self.api('/api/v1/submissions/' + identifier)['submission']
        require(api['state'] == terminal)
        self.api('/api/v1/submissions/' + identifier + '/logs')
        leaderboard = self.api('/api/v1/leaderboard')['leaderboard']
        ranks = {row['submission'] for row in leaderboard}
        require(all(r in ranks for r in state['results']))
        for result in state['results']:
            body = command(['curl', '--fail', '--silent', 'http://127.0.0.1:8080/experiment/' + result])
            self.probe('privacy', text=body)
        self.probe('privacy', text=command(['curl', '--fail', '--silent', 'http://127.0.0.1:8080/']))
        require(not any(worker_owned(w, self.j['owned_attempts'], self.j['worker_image']) for w in containers()))
        self.guard()

    def switch(self, manifest):
        self.guard()
        override = self.directory / 'switch.json'
        save(override, {'services': {role: {'image': manifest['images'][role]['id']} for role in ('web', 'coordinator')}})
        self.mutate(self.compose + ['stop', 'coordinator'])
        self.mutate(self.compose + ['-f', str(override), 'create', '--no-deps', 'coordinator'], timeout=60)
        self.mutate(self.compose + ['-f', str(override), 'up', '-d', '--no-deps', 'web'], timeout=60)
        self.wait(lambda: self.health(), 90)
        # Validate evaluator compatibility using the switched application image.
        switched = json.loads(command(['docker', 'inspect', command(self.compose + ['ps', '-aq', 'coordinator'])]))[0]
        inspector = self.clone(switched)
        previous = self.probe_id
        try:
            self.probe_id = inspector
            require(self.probe('identity') == self.j['identity'])
        finally:
            self.probe_id = previous
            self.mutate(['docker', 'rm', '-f', inspector])
        require(self.probe('snapshot') == self.j['snapshot'], 'Immutable data changed across switch')
        require(self.api('/api/v1/leaderboard') == self.j['leaderboard'])
        self.api('/api/v1/me')
        require(self.c['revoked_token'], 'Rollback requires a previously revoked token file')
        self.api('/api/v1/me', token=self.c['revoked_token'], expected=401)

    def health(self):
        try:
            return all(json.loads(command(['curl', '--fail', '--silent',
                 'http://127.0.0.1:8080/health/' + route])) for route in ('live', 'ready'))
        except Exception:
            return False

    def run(self):
        if self.c['cleanup']:
            if self.path.exists() and not self.j.get('cleanup_complete'):
                cleanup(self.path)
            return
        require(self.c['revoked_token'], 'Supply a previously revoked disposable token for rollback verification')
        require(self.j.get('cleanup_complete'), 'Previous run interrupted: run --cleanup first')
        coordinator = command(self.compose + ['ps', '-aq', 'coordinator'])
        self.template = json.loads(command(['docker', 'inspect', coordinator]))[0]
        env = dict(e.split('=', 1) for e in self.template['Config']['Env'])
        require(env.get('MLDSAFAIL_ENV', 'private-staging') == 'private-staging')
        require(env['MLDSAFAIL_SKIP_MIGRATIONS'] == '1')
        require(env['MLDSAFAIL_EVALUATOR_WORK_ROOT'] == '/srv/mldsafail-evaluator/jobs')
        require('rootless' in command(['docker', 'info', '--format', '{{json .SecurityOptions}}']))
        release = self.c['release_manifest']
        rollback = self.c['rollback_manifest']
        require(hashlib.sha256(Path(self.c['deployment'], 'compose.private.yaml').read_bytes()).hexdigest()
                == release['configuration_sha256'], 'Deployed configuration differs from frozen release')
        require(release['mlwe_trusted_fingerprint'] == rollback['mlwe_trusted_fingerprint'])
        for manifest in (release, rollback):
            for role in ('web', 'coordinator', 'worker'):
                image = manifest['images'][role]['id']
                require(image.startswith('sha256:') and len(image) == 71)
                inspected = json.loads(command(['docker', 'image', 'inspect', image]))[0]
                require(inspected['Architecture'] == 'amd64')
                if role != 'worker':
                    require(inspected['Config']['Labels']['org.mldsafail.source'] == manifest['source_commit'])
        require(release['images']['worker']['id'] == rollback['images']['worker']['id'])
        require(self.template['Image'] == release['images']['coordinator']['id'])
        web = json.loads(command(['docker', 'inspect', command(self.compose + ['ps', '-aq', 'web'])]))[0]
        require(web['Image'] == release['images']['web']['id'])
        require('MLDSAFAIL_ENV=private-staging' in web['Config']['Env'])
        proxy = json.loads(command(['docker', 'inspect', command(self.compose + ['ps', '-aq', 'proxy'])]))[0]
        require(all(b['HostIp'] == '127.0.0.1' for bindings in proxy['HostConfig']['PortBindings'].values() for b in bindings))
        self.j.update(worker_image=release['images']['worker']['id'], compose=self.compose,
                      work_root=env['MLDSAFAIL_EVALUATOR_WORK_ROOT'],
                      original_mode=os.stat(env['MLDSAFAIL_EVALUATOR_WORK_ROOT']).st_mode & 0o7777)
        self.probe_id = coordinator
        require(not self.probe('active')['active'], 'Unrelated evaluation work prevents preflight')
        require(not any(info['Name'].startswith('/mlwe-') and info['State']['Running'] for info in containers()), 'Unrelated worker prevents preflight')
        identity = self.probe('identity')
        require(self.j.get('identity', identity) == identity, 'Epoch compatibility changed')
        self.j['identity'] = identity
        # Review the actual immutable remote fixture tree before any submission.
        import tempfile
        with tempfile.TemporaryDirectory(dir=self.directory) as temporary:
            checkout = Path(temporary) / 'source'
            command(['git', 'init', str(checkout)])
            command(['git', '-C', str(checkout), '-c', 'credential.helper=', 'fetch', '--depth=1',
                     self.c['fixture_url'], self.c['fixture_sha']], timeout=30)
            command(['git', '-C', str(checkout), 'checkout', '--detach', 'FETCH_HEAD'])
            files = command(['git', '-C', str(checkout), 'ls-files']).splitlines()
            require(all((checkout / name).is_file() and not (checkout / name).is_symlink() for name in files))
            actual = {name: hashlib.sha256((checkout / name).read_bytes()).hexdigest() for name in files}
            require(actual == self.c['fixture_files'], 'Pinned public fixtures differ from reviewed sources')
            require(all((checkout / name).is_file() and not (checkout / name).is_symlink() for name in files))
        self.j['service_states'] = {'coordinator': self.template['State']['Running'], 'web': web['State']['Running']}
        participant = self.api('/api/v1/me')['id']
        require(self.j.get('user', participant) == participant, 'Participant changed on resumption')
        self.j['user'] = participant
        docker_api_version(json.loads(command(['docker', 'version', '--format', '{{json .Server}}'])))
        require(self.health(), 'Preflight health failed')
        self.api('/api/v1/me', token=self.c['revoked_token'], expected=401)
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
        require(available >= 128 * 1024**2, 'Preflight RAM floor')
        require(shutil.disk_usage('/srv').free >= 5 * 1024**3, 'Preflight disk floor')
        # A new invocation may resume only after verified cleanup and full identity preflight.
        self.j.update(closing=False, cleanup_complete=False, generation=self.j.get('generation', 0) + 1)
        with journal_lock(self.path):
            save(self.path, self.j)
        self.touch()
        watcher = subprocess.Popen(['python3', __file__, '--watchdog', str(self.path), str(self.j['generation'])],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        credential = self.directory / 'cleanup-token'
        fd = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(self.c['token'])
        self.probe_id = self.clone(self.template)
        self.guard()
        require(self.health())
        self.j['user'] = self.api('/api/v1/me')['id']
        for role in ('coordinator', 'web', 'proxy', 'db'):
            self.probe('privacy', text=command(self.compose + ['logs', '--no-color', '--tail', '1000', role]))
        self.j['service_identity'] = {
            role: {'image': info['Image'], 'configuration_sha256': hashlib.sha256(json.dumps(
                {'config': info['Config'], 'host': info['HostConfig'], 'mounts': info['Mounts']},
                sort_keys=True).encode()).hexdigest()}
            for role, info in [('web', web), ('coordinator', self.template), ('proxy', proxy)]}
        identity = self.probe('identity')
        require(self.j.get('identity', identity) == identity, 'Epoch compatibility changed')
        self.j['identity'] = identity
        require(self.j['identity']['worker'] == self.j['worker_image'])
        print('Private staging maintenance window: sequential failure tests and application rollback.', flush=True)
        # Cleanup is installed before stopping normal service or injecting any fault.
        self.j.update(maintenance=True, cleanup_complete=False, watch_host=True)
        self.touch()
        try:
            self.mutate(['docker', 'stop', coordinator])
            self.guard()
            for name, kind in SCENARIOS.items():
                self.scenario(name, kind)
            self.guard()
            # Stop web for a quiescent backup; DB remains online and schema untouched.
            self.mutate(self.compose + ['stop', 'web'])
            self.touch()
            # A backup command may take >45s: watchdog heartbeat continues in a thread.
            import threading
            stop = threading.Event()
            def pulse():
                while not stop.wait(5):
                    self.heartbeat()
            thread = threading.Thread(target=pulse, daemon=True)
            thread.start()
            try:
                backup = command(['python3', self.c['deployment'] + '/deploy/backup_postgres.py',
                                  '--env-file', self.c['env_file'], '--compose',
                                  self.c['deployment'] + '/compose.private.yaml', '--output',
                                  str(self.directory / 'backups'), '--verify-restore'], timeout=360)
                require(json.loads(backup)['restore_verified'])
            finally:
                stop.set()
                thread.join()
                self.mutate(self.compose + ['start', 'web'])
            self.wait(lambda: self.health(), 90)
            self.j['snapshot'] = self.probe('snapshot')
            self.j['leaderboard'] = self.api('/api/v1/leaderboard')
            new_override = self.directory / 'restore.json'
            save(new_override, {'services': {role: {'image': release['images'][role]['id']}
                                            for role in ('web', 'coordinator')}})
            self.j['restore_command'] = self.compose + ['-f', str(new_override), 'up', '-d', '--no-deps', 'web', 'coordinator']
            self.touch()
            self.switch(rollback)
            self.switch(release)
            for role in ('coordinator', 'web', 'proxy', 'db'):
                self.probe('privacy', text=command(self.compose + ['logs', '--no-color', '--tail', '1000', role]))
            self.j['rollback_passed'] = True
            report = {'scenario_gates': {n: e.get('passed', False) for n, e in self.j['scenarios'].items()},
                      'rollback_passed': True, 'backup_restore_verified': True,
                      'full_timeout_cohort_tested': False, 'migration_complete': False,
                      'remaining': ['automated off-host backups', 'overall migration acceptance', 'production launch prerequisites'],
                      'worker_image': self.j['worker_image'],
                      'evaluator_fingerprint': self.j['identity']['fingerprint'],
                      'release_commit': release['source_commit'], 'rollback_commit': rollback['source_commit']}
            self.touch()
        finally:
            cleanup(self.path)
            watcher.terminate()
            watcher.wait(timeout=10)
        report['cleanup_verified'] = True
        save(self.directory / 'report.json', report)
        print(json.dumps(report), flush=True)


def main():
    if len(sys.argv) in {3, 4} and sys.argv[1] == '--watchdog':
        watchdog(Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) == 4 else None)
        return
    config = json.load(sys.stdin)
    os.umask(0o077)
    driver = Driver(config)
    # One owner per journal; do not allow simultaneous invocations/resumption.
    import fcntl
    with (driver.directory / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, lambda *_: (_ for _ in ()).throw(InterruptedError()))
        try:
            driver.run()
        except BaseException:
            import traceback
            (driver.directory / 'failure.log').write_text(traceback.format_exc())
            raise
        finally:
            if driver.path.exists() and driver.j.get('worker_image'):
                try:
                    cleanup(driver.path)
                finally:
                    current = json.loads(driver.path.read_text())
                    if not (driver.directory / 'report.json').exists():
                        save(driver.directory / 'report.json', {
                            'acceptance_failed': True,
                            'cleanup_verified': bool(current.get('cleanup_complete')),
                            'cleanup_retry_required': not current.get('cleanup_complete', False),
                            'scenario_gates': {name: bool(entry.get('passed'))
                                               for name, entry in current.get('scenarios', {}).items()},
                            'native_details_retained_on_vps': True})


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Neither secrets, remote command output nor evidence enter off-host logs.
        print(json.dumps({'acceptance_failed': True, 'native_details_retained_on_vps': True}), flush=True)
        sys.exit(1)
