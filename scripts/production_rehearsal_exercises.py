"""Synthetic failure/load exercises confined to a reviewed disposable application.

Never invokes the historical staging runner, its activation, or fixed endpoints.
The outer production rehearsal owns every creator and performs daemon cleanup.
"""
import json
import datetime as dt
import os
import shutil
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

from deploy import owned_daemon
from scripts import hosted_vps_failure_driver as historical
from scripts.native_operator_unit import REHEARSAL_CREDENTIAL_SECONDS
from scripts.production_rehearsal import command, LABEL, ROLE


def clone_labels(template):
    """Keep cleanup ownership, without admitting fixtures to Compose services."""
    labels = template['Config'].get('Labels') or {}
    if any(not isinstance(labels.get(key), str) or not labels[key] for key in (LABEL, ROLE)):
        raise ValueError('Disposable clone ownership labels required')
    return {key: labels[key] for key in (LABEL, ROLE)}


class Exercises(historical.Driver):
    """Reuse declared scenario assertions with explicit disposable I/O/lifecycle."""
    def __init__(self, root, source, compose, env, base, token, images, config):
        self.directory = root / 'exercises'
        self.directory.mkdir(mode=0o700)
        self.path = self.directory / 'journal.json'
        self.compose, self.env, self.base = compose, env, base
        run_id = json.loads((root / 'journal.json').read_text())['run_id']
        self.c = dict(run_id=run_id, token=token, fixture_url=config['fixture_repository'],
                      fixture_sha=config['fixture_commit'])
        self.j = dict(run_id=run_id, scenarios={}, owned_attempts=[], worker_image=images['worker'],
                      closing=False, generation=1)
        self.low_memory_since = None
        self.process = None
        self.touch()
        self.probe_source = (source / 'scripts/hosted_vps_failure_probe.py').read_text()
        self.template = self.inspect(self.call(compose + ['ps', '-q', 'coordinator']))
        environment = dict(item.split('=', 1) for item in self.template['Config']['Env'])
        self.j.update(work_root=environment['MLDSAFAIL_EVALUATOR_WORK_ROOT'],
                      original_mode=os.stat(environment['MLDSAFAIL_EVALUATOR_WORK_ROOT']).st_mode & 0o7777)
        self.call(compose + ['stop', 'coordinator'])
        self.probe_id = self.clone(self.template, once=False)
        self.j['user'] = self.api('/api/v1/me')['id']
        self.touch()

    def touch(self):
        self.j['heartbeat'] = time.time()
        owned_daemon.publish(self.path, self.j)

    def call(self, argv, timeout=120, input=None):
        return command(argv, env=self.env, timeout=timeout,
                       input=input.encode() if isinstance(input, str) else input).decode().strip()

    def inspect(self, identifier):
        return json.loads(self.call(['docker', 'inspect', identifier]))[0]

    def mutate(self, args, **kwargs):
        return self.call(args, **kwargs)

    def clone(self, template, image=None, once=False):
        """Tracked CLI creation only, preserving mounts/network/domain restrictions."""
        host = template['HostConfig']
        networks = list(template['NetworkSettings']['Networks'])
        if len(networks) != 1 or image is not None:
            raise ValueError('Exact disposable coordinator network and image required')
        argv = ['docker', 'create', '--name', 'production-attempt-' + uuid.uuid4().hex,
                '--network', networks[0], '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', template['Config']['User'],
                '--memory', str(host['Memory']), '--restart', 'no',
                '--cgroup-parent', host['CgroupParent'], '--entrypoint', '/app/.venv/bin/python']
        for key, value in clone_labels(template).items():
            argv += ['--label', key + '=' + value]
        for value in template['Config']['Env']:
            argv += ['-e', value]
        for mount in template['Mounts']:
            if mount['Type'] != 'bind':
                raise ValueError('Only reviewed coordinator bind mounts allowed')
            argv += ['--mount', 'type=bind,src=' + mount['Source'] + ',dst=' + mount['Destination'] +
                     (',readonly' if not mount['RW'] else '')]
        for target, options in host['Tmpfs'].items():
            argv += ['--tmpfs', target + ':' + options]
        argv += [template['Image']]
        argv += ['-m', 'mldsafail.evaluator.coordinator', '--once'] if once else ['-c', 'import time;time.sleep(' + str(REHEARSAL_CREDENTIAL_SECONDS) + ')' ]
        identifier = self.call(argv)
        self.j.setdefault('controllers', []).append(identifier)
        self.touch()
        self.call(['docker', 'start', identifier])
        return identifier

    def probe(self, action, **fields):
        payload = json.dumps(dict(action=action, **fields))
        code = 'import io,sys;sys.stdin=io.StringIO(' + repr(payload) + ');exec(' + repr(self.probe_source) + ')'
        return json.loads(self.call(['docker', 'exec', '-i', self.probe_id,
                                    '/app/.venv/bin/python', '-c', code], timeout=600))

    def api(self, route, payload=None, token=None, key=None, expected=200):
        headers = {'Authorization': 'Bearer ' + (token or self.c['token'])}
        if key:
            headers['Idempotency-Key'] = key
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base + route, headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None)
        from deploy.alert_webhook import NoRedirect
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            with opener.open(request, timeout=10) as response:
                status, body = response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read().decode()
        historical.require(status in expected if isinstance(expected, tuple) else status == expected)
        self.probe('privacy', text=body)
        return json.loads(body)

    def wait(self, predicate, seconds, allowed=None):
        deadline = time.monotonic() + seconds
        interval = 10 if seconds > 150 else 2
        while True:
            self.guard(allowed)
            value = predicate()
            if value:
                return value
            remaining = deadline - time.monotonic()
            historical.require(remaining > 0, 'Acceptance deadline exceeded')
            time.sleep(min(interval, remaining))

    def finish_process(self, identifier, seconds=2400):
        # Outer orchestration only: worker caps, leases and scoring stay frozen.
        self.wait(lambda: not self.inspect(self.process)['State']['Running'], seconds, identifier)
        info = self.inspect(self.process)
        self.probe('privacy', text=self.call(['docker', 'logs', self.process]))
        historical.require(info['State']['ExitCode'] == 0)
        self.call(['docker', 'rm', self.process])
        self.process = None


    def containers(self):
        identifiers = self.call(['docker', 'ps', '-aq']).splitlines()
        rows = []
        for identifier in identifiers:
            try:
                rows.append(self.inspect(identifier))
            except Exception:
                # A disappearing frozen worker is expected only when its exact
                # ID is absent from a second complete isolated-daemon listing.
                if identifier in self.call(['docker', 'ps', '-aq']).splitlines():
                    raise
        return rows

    def worker_owned(self, info, submissions, image):
        mounts = info.get('Mounts', [])
        return (info['Image'] == image and info['Name'].startswith('/mlwe-') and len(mounts) == 1
                and mounts[0]['Destination'] == '/solver' and not mounts[0]['RW']
                and any(mounts[0]['Source'] == str(Path(self.j['work_root']) / 'runs' / submission / str(attempt) / 'solver')
                        for submission, attempt in submissions))

    def html(self, route):
        from deploy.alert_webhook import NoRedirect
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(self.base + route, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError('Disposable HTML read failed')
            return response.read().decode()

    def guard(self, allowed=None):
        self.touch()
        active = self.probe('active')['active']
        historical.require(set(active) <= ({allowed} if allowed else set()), 'Unrelated evaluation appeared')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        if available < 128 * 1024**2:
            self.low_memory_since = self.low_memory_since or time.monotonic()
            historical.require(time.monotonic() - self.low_memory_since < 30, 'RAM below acceptance floor')
        else:
            self.low_memory_since = None
        historical.require(shutil.disk_usage('/srv').free >= 5 * 1024**3, 'Disk below acceptance floor')
        workers = [i for i in self.containers() if i['Name'].startswith('/mlwe-') and i['State']['Running']]
        historical.require(len(workers) <= 1, 'Concurrent worker execution')
        for worker in workers:
            historical.require(self.worker_owned(worker, self.j['owned_attempts'], self.j['worker_image']), 'Unrelated worker')
            host, config = worker['HostConfig'], worker['Config']
            historical.require(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] and config['User'] == '65534:65534')
            historical.require('ALL' in host['CapDrop'] and any('no-new-privileges' in s for s in host['SecurityOpt']))
            historical.require(host['Memory'] == 2 * 1024**3 and host['PidsLimit'] == 64 and host['NanoCpus'] == 10**9)
            historical.require(not any(e.startswith(('MLDSAFAIL', 'POSTGRES', 'GITHUB')) for e in config['Env']))
        return workers


    def fault(self, enabled):
        with historical.journal_lock(self.path):
            historical.require(not json.loads(self.path.read_text()).get('closing'), 'Cleanup has begun')
            os.chmod(self.j['work_root'], self.j['original_mode'] & ~0o222 if enabled else self.j['original_mode'])
        # Prove effective denial under the deployed identity before claiming work.
        if enabled:
            self.call(['docker', 'exec', self.probe_id, 'python', '-c',
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
            historical.require(state['job_status'] in {'complete', 'failed'},
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
                    historical.require(state['attempt_count'] == attempt and state['attempts'][-1]['status'] == 'infrastructure_failed')
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
                    historical.require(observed)
                if name == 'lease':
                    self.mutate(['docker', 'kill', self.process])
                    self.mutate(['docker', 'rm', self.process])
                    self.process = None
                    for worker in self.containers():
                        if self.worker_owned(worker, [[identifier, 1]], self.j['worker_image']):
                            self.mutate(['docker', 'rm', '-f', worker['Id']])
                    state = self.probe('state', submission=identifier)
                    expiry = dt.datetime.fromisoformat(state['lease_expires_at'])
                    self.wait(lambda: dt.datetime.now(dt.timezone.utc) > expiry, 150, identifier)
                    self.one_shot(identifier, 2)
                    self.finish_process(identifier)
                else:
                    response = self.api('/api/v1/submissions/' + identifier + '/cancel', {})
                    historical.require(response['submission']['cancel_requested'])
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
        historical.require(state['state'] == terminal and state['job_status'] == ('failed' if name == 'exhaustion' else 'complete'))
        expected_attempts = 3 if name == 'exhaustion' else 2 if name in {'retry', 'lease'} else 1
        historical.require(state['attempt_count'] == expected_attempts and len(state['attempts']) == expected_attempts
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
        historical.require(state['transitions'] == expected_transitions, 'Persisted transition chain differs')
        historical.require(state['transitions'].count('validating') == expected_attempts)
        historical.require(state['transitions'][-1] == terminal)
        historical.require(len(state['results']) == (1 if terminal == 'accepted' else 0))
        historical.require(state['attempts'][-1]['status'] == terminal)
        for index, attempt in enumerate(state['attempts'][:-1] if name != 'exhaustion' else state['attempts']):
            historical.require(attempt['status'] == 'infrastructure_failed')
            historical.require(attempt['failure_class'] == ('lease_expired' if name == 'lease' else 'PermissionError'))
            if index + 1 < len(state['attempts']) and name != 'lease':
                historical.require((dt.datetime.fromisoformat(state['attempts'][index+1]['started']) -
                         dt.datetime.fromisoformat(attempt['finished'])).total_seconds() >= 5 * (index + 1))
        if name in {'retry', 'lease', 'exhaustion'}:
            historical.require(state['transitions'].count('infrastructure_failed') == (3 if name == 'exhaustion' else 1))
            historical.require(state['transitions'].count('queued') == expected_attempts)
        if name == 'invalid':
            historical.require(state['rejection_code'] == 'invalid_answer' and state['attempts'][0]['failure_class'] == 'invalid_answer')
        if kind != 'hang' and name != 'exhaustion':
            self.probe('audit', submission=identifier, kind=kind)
        if name == 'timeout':
            historical.require(self.probe('timeout', submission=identifier)['timeout'])
        api = self.api('/api/v1/submissions/' + identifier)['submission']
        historical.require(api['state'] == terminal)
        self.api('/api/v1/submissions/' + identifier + '/logs')
        leaderboard = self.api('/api/v1/leaderboard')['leaderboard']
        ranks = {row['submission'] for row in leaderboard}
        historical.require(all(r in ranks for r in state['results']))
        for result in state['results']:
            body = self.html('/experiment/' + result)
            self.probe('privacy', text=body)
        self.probe('privacy', text=self.html('/'))
        historical.require(not any(self.worker_owned(w, self.j['owned_attempts'], self.j['worker_image']) for w in self.containers()))
        self.guard()



def verify_restored_coordinator(runner):
    """Require the original service and independent live probe before monitoring."""
    identifiers = runner.call(runner.compose + ['ps', '-q', 'coordinator']).splitlines()
    if runner.probe_id == runner.template['Id'] or identifiers != [runner.template['Id']]:
        raise RuntimeError('Exactly the original Compose coordinator must be restored')
    service = runner.inspect(identifiers[0])
    probe = runner.inspect(runner.probe_id)
    for key in ('Entrypoint', 'Cmd'):
        if service['Config'].get(key) != runner.template['Config'].get(key):
            raise RuntimeError('Restored coordinator command differs')
    if not service['State']['Running'] or not probe['State']['Running']:
        raise RuntimeError('Coordinator and independent probe must both be running')
    if any(key.startswith('com.docker.compose.') for key in probe['Config'].get('Labels', {})):
        raise RuntimeError('Probe must remain outside Compose service ownership')


def exercise(*, root, source, compose, env, base, token, images, daemon, epoch, request, config, stage):
    runner = Exercises(root, source, compose, env, base, token, images, config)
    # The original ordered scenario definitions and frozen penalties remain intact.
    for name, kind in historical.SCENARIOS.items():
        runner.scenario(name, kind)
        stage('failure_' + name, runner.j['scenarios'][name])
    runner.call(compose + ['up', '-d', '--no-deps', 'coordinator'])
    verify_restored_coordinator(runner)
    from scripts.production_rehearsal_monitor_load import monitor_and_load
    monitor_and_load(root=root, source=source, compose=compose, env=env, base=base, token=token,
                     images=images, daemon=daemon, config=config, stage=stage, runner=runner)
    runner.call(['docker', 'rm', '-f', runner.probe_id])


def check_cohort_filter(*, root, compose, env, images, daemon, token, original_request):
    """Test exclusion with foreign web configurations against unchanged real rows."""
    from deploy.alert_webhook import NoRedirect
    web_id = command(compose + ['ps', '-q', 'web'], env=env).decode().strip()
    template = json.loads(command(['docker', 'inspect', web_id], env=env))[0]
    networks = list(template['NetworkSettings']['Networks'])
    if len(networks) != 1:
        raise RuntimeError('Exact disposable web network required')
    original = original_request('/api/v1/leaderboard')[1]
    if not original['leaderboard']:
        raise RuntimeError('Accepted original cohort must be populated')
    rows = []
    for field in ('MLDSAFAIL_MLWE_EPOCH_ID', 'MLDSAFAIL_EVALUATOR_FINGERPRINT',
                  'MLDSAFAIL_HIDDEN_SUITE_VERSION', 'MLDSAFAIL_WORKER_CLASS'):
        environment = dict(value.split('=', 1) for value in template['Config']['Env'])
        environment[field] = uuid.uuid4().hex * 2
        argv = ['docker', 'create', '--name', 'foreign-cohort-' + uuid.uuid4().hex,
                '--network', networks[0], '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', template['Config']['User'],
                '--memory', str(template['HostConfig']['Memory']), '--restart', 'no',
                '--cgroup-parent', daemon['worker_cgroup_parent'], '--publish', '127.0.0.1::8000',
                '--tmpfs', '/tmp:size=32m,noexec,nosuid,nodev']
        for key, value in clone_labels(template).items(): argv += ['--label', key + '=' + value]
        for key, value in environment.items(): argv += ['-e', key + '=' + value]
        argv += [images['web']]
        identifier = command(argv, env=env).decode().strip()
        if not __import__('re').fullmatch('[a-f0-9]{64}', identifier):
            raise RuntimeError('Foreign web creation identity missing')
        try:
            command(['docker', 'start', identifier], env=env)
            endpoint = command(['docker', 'port', identifier, '8000/tcp'], env=env).decode().strip()
            if not endpoint.startswith('127.0.0.1:'):
                raise RuntimeError('Foreign cohort test is not loopback-only')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            deadline = time.monotonic() + 120
            while True:
                try:
                    request = urllib.request.Request('http://' + endpoint + '/api/v1/leaderboard',
                        headers={'Authorization': 'Bearer ' + token})
                    with opener.open(request, timeout=5) as response:
                        board = json.load(response)
                    break
                except Exception:
                    if time.monotonic() >= deadline: raise
                    time.sleep(1)
            if board['leaderboard']:
                raise RuntimeError('Foreign cohort leaked accepted rows')
            rows.append(dict(field=field, excluded=True, original_results=len(original['leaderboard'])))
        finally:
            command(['docker', 'rm', '-f', identifier], env=env)
    if original_request('/api/v1/leaderboard')[1] != original:
        raise RuntimeError('Original accepted cohort changed during exclusion tests')
    owned_daemon.publish(root / 'cohort-filtering.json', rows)
    return rows
