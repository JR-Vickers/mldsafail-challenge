"""Scheduled service-only monitoring and the two declared 300-second load phases."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import sys
import time
import uuid

from deploy import host_checks, owned_daemon
from deploy.render_operator_units import render
from scripts import staging_read_load
from scripts.production_rehearsal import command, client_run


def stop_monitors(root, env):
    """Stop only source-bound disposable monitor units; retain their configuration."""
    journal_path = root / 'journal.json'
    journal = json.loads(journal_path.read_text())
    errors = []
    for item in reversed(journal.get('monitor_units', [])):
        try:
            path = Path(item['path'])
            output = command(['systemctl', '--user', 'show', path.name,
                              '--property=FragmentPath,LoadState,ActiveState'], env=env).decode()
            state = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
            never_started = not journal.get('monitor_start_intent', False)
            if never_started and state.get('LoadState') == 'not-found' and state.get('ActiveState') == 'inactive':
                if path.exists() and (path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']):
                    raise RuntimeError('Unactivated monitor artifact changed')
                continue
            if (path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']
                    or state.get('FragmentPath') != str(path)):
                raise RuntimeError('Disposable monitor fragment identity changed; control prohibited')
            command(['systemctl', '--user', 'stop', path.name], env=env, timeout=45)
            state = command(['systemctl', '--user', 'show', path.name,
                             '--property=ActiveState', '--value'], env=env).decode().strip()
            if state not in {'inactive', 'failed'}:
                raise RuntimeError('Disposable monitor remains active')
        except Exception as error:
            errors.append(dict(unit=Path(item['path']).name, error_type=type(error).__name__))
    config_path = root / 'monitor.json'
    if config_path.exists():
        try:
            config = owned_daemon.read_private_json(config_path)
            config['healthchecks']['enabled'] = False
            owned_daemon.publish(config_path, config)
        except Exception as error:
            errors.append(dict(step='disable_endpoint', error_type=type(error).__name__))
    journal['monitor_cleanup'] = dict(complete=not errors, errors=errors)
    owned_daemon.publish(journal_path, journal)
    if errors:
        raise RuntimeError('Disposable monitor cleanup incomplete')


def monitor_rows(raw, *, since=0, excluded=()):
    """Select complete monitor receipts by precise journal time and invocation."""
    rows = []
    for line in raw.splitlines():
        entry = json.loads(line)
        try:
            result = json.loads(entry.get('MESSAGE', ''))
        except (ValueError, TypeError):
            continue
        invocation = entry.get('_SYSTEMD_INVOCATION_ID')
        if (isinstance(result, dict) and result.get('scope') == 'service'
                and invocation and invocation not in excluded
                and int(entry['__REALTIME_TIMESTAMP']) >= int(since * 1_000_000)):
            rows.append(dict(invocation=invocation, timestamp_us=entry['__REALTIME_TIMESTAMP'], result=result))
    return rows


def require_notification(rows, healthy):
    if not rows or any(row['result'].get('healthy') is not healthy
                       or row['result'].get('backup_status') != 'deferred' for row in rows):
        raise RuntimeError('Complete delivered monitor receipt required')
    if not healthy and not any('readiness' in row['result'].get('checks', [])
                               or 'service:web' in row['result'].get('checks', []) for row in rows):
        raise RuntimeError('Disposable web failure receipt required')
    return rows


def wait_monitor_inactive(name, env, *, timeout=120):
    """Let an existing oneshot finish before requesting a distinct invocation."""
    deadline = time.monotonic() + timeout
    while True:
        state = command(['systemctl', '--user', 'show', name + '.service',
                         '--property=ActiveState', '--value'], env=env).decode().strip()
        if state in {'inactive', 'failed'}:
            return
        if state not in {'active', 'activating', 'deactivating'}:
            raise RuntimeError('Unexpected disposable monitor service state')
        if time.monotonic() >= deadline:
            raise RuntimeError('Disposable monitor invocation did not settle')
        time.sleep(1)


def wait_monitor_receipt(name, env, *, since, healthy, excluded=(), timeout=30):
    """Journal ingestion may lag a completed oneshot; empty is never success."""
    deadline = time.monotonic() + timeout
    while True:
        raw = command(['journalctl', '--user', '-u', name + '.service', '--since',
                       '@' + str(int(since)), '--output=json', '--no-pager'], env=env).decode()
        rows = monitor_rows(raw, since=since, excluded=excluded)
        if rows:
            if len({row['invocation'] for row in rows}) != 1:
                raise RuntimeError('One distinct monitor phase invocation required')
            return require_notification(rows, healthy)
        if time.monotonic() >= deadline:
            raise RuntimeError('Complete monitor phase receipt not observed')
        time.sleep(1)


def invoke_monitor(name, env, *, healthy):
    """One settled phase; owned clients capture output by default."""
    wait_monitor_inactive(name, env)
    started = time.time()
    process = client_run(['systemctl', '--user', 'start', name + '.service'],
                         env=env, timeout=120, check=False)
    if (process.returncode == 0) is not healthy:
        raise RuntimeError('Monitor phase exit status differs from expected health')
    return wait_monitor_receipt(name, env, since=started, healthy=healthy)


def wait_service_health(compose, env, *, timeout=120):
    deadline = time.monotonic() + timeout
    while True:
        healthy = True
        for role in ('web', 'coordinator', 'proxy', 'db'):
            identifier = command(compose + ['ps', '-q', role], env=env).decode().strip()
            inspected = json.loads(command(['docker', 'inspect', identifier], env=env))[0]
            state = inspected['State']
            healthy &= bool(state.get('Running') and state.get('Health', {}).get('Status', 'healthy') == 'healthy')
        if healthy:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Disposable services did not regain healthy state')
        time.sleep(2)


def monitor_and_load(*, root, source, compose, env, base, token, images, daemon, config, stage, runner):
    metadata = json.loads(Path(config['source_manifest']).read_text())
    name = 'mldsafail-rehearsal-' + uuid.uuid4().hex + '-monitor'
    owner = config['operator_unit']
    proxy = command(compose + ['port', 'proxy', '8080'], env=env).decode().strip()
    if not proxy.startswith('127.0.0.1:'):
        raise RuntimeError('Disposable proxy must bind only IPv4 loopback')
    monitor_config = dict(scope='service', env_file=str(root / 'synthetic.env'),
        compose=str(root / 'compose.json'), readiness_url='http://' + proxy + '/health/ready',
        daemon_manifest=os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'], service_scheduled_units=[],
        alert_enabled=False, healthchecks=dict(enabled=False, service_endpoint_file=config['service_endpoint_file']))
    path = root / 'monitor.json'
    owned_daemon.publish(path, monitor_config)
    # Identity and complete healthy service inspection precede permanent endpoint connection.
    host_checks.validate_config(monitor_config)
    owned_daemon.verify_environment(owned_daemon.load_manifest())
    for role in ('web', 'coordinator', 'proxy', 'db'):
        identifier = command(compose + ['ps', '-q', role], env=env).decode().strip()
        inspected = json.loads(command(['docker', 'inspect', identifier], env=env))[0]
        if not inspected['State']['Running'] or inspected['Image'] != images[{'db': 'postgres', 'proxy': 'caddy'}.get(role, role)]:
            raise RuntimeError('Disposable monitored service identity differs')
    units = root / 'monitor-units'
    parent = str(Path(config['operator_parent']).parent)
    report = render(str(source), sys.executable, metadata, {'monitor': str(path)},
                    pwd.getpwuid(os.getuid()).pw_name, os.getuid(), str(units), monitor_only=True,
                    docker_socket=daemon['socket'], cgroup_root=parent, monitor_name=name, owner_unit=owner, user_manager=True)
    directory = Path.home() / '.config/systemd/user'
    if not directory.is_dir():
        raise RuntimeError('Existing user unit directory required')
    journal_path = root / 'journal.json'
    journal = json.loads(journal_path.read_text())
    journal['monitor_units'] = []
    journal['monitor_start_intent'] = False
    owned_daemon.publish(journal_path, journal)
    try:
        for unit, checksum in report['unit_sha256'].items():
            destination = directory / unit
            if destination.exists() or destination.is_symlink():
                raise RuntimeError('Disposable monitor name already occupied')
            # The durable ownership intent precedes installation and activation.
            journal['monitor_units'].append(dict(path=str(destination), sha256=checksum))
            owned_daemon.publish(journal_path, journal)
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write((units / unit).read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
        command(['systemctl', '--user', 'daemon-reload'], env=env)
        journal['monitor_start_intent'] = True
        owned_daemon.publish(journal_path, journal)
        dry_rows = invoke_monitor(name, env, healthy=True)
        owned_daemon.publish(root / 'monitor-dry-inspection.json', dry_rows)
        dry_invocations = {row['invocation'] for row in dry_rows}
        monitor_config['healthchecks']['enabled'] = True
        host_checks.validate_config(monitor_config)
        owned_daemon.publish(path, monitor_config)
        started = time.time()
        command(['systemctl', '--user', 'start', name + '.timer'], env=env)
        stage('service_monitor_scheduled', dict(period_seconds=300, grace_seconds=600,
              scope='service', backup_status='deferred', monitor=name, config_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        baseline_identity = runner.probe('identity')
        for phase in ('idle', 'evaluation'):
            allowed = None
            if phase == 'evaluation':
                payload = dict(repository_url=config['fixture_repository'], commit_sha=config['fixture_commit'],
                               solver_path='reference', benchmark_version='0.5.0', hypothesis='declared disposable reference read load')
                key = 'load-' + uuid.uuid4().hex
                owned_daemon.publish(root / 'load-intent.json', dict(payload=payload, key=key))
                allowed = runner.api('/api/v1/submissions', payload, key=key, expected=(200, 201))['submission']['id']
                runner.j['owned_attempts'].append([allowed, 1]); runner.touch()
                runner.wait(lambda: runner.probe('state', submission=allowed)['state'] == 'running', 120, allowed)
            rows = []
            def health():
                runner.guard(allowed)
                return True
            measurement = staging_read_load.run(base, token, health, duration=300, progress=rows.append)
            owned_daemon.publish(root / ('load-' + phase + '.json'), dict(measurement=measurement, requests=rows))
            if not measurement['passed'] or measurement['requests'] != 1560:
                raise RuntimeError('Declared load thresholds failed')
            if allowed:
                runner.wait(lambda: runner.probe('state', submission=allowed)['state'] in
                            {'accepted', 'rejected', 'infrastructure_failed'}, 2400, allowed)
                if runner.probe('state', submission=allowed)['state'] != 'accepted':
                    raise RuntimeError('Load reference was not accepted')
                runner.probe('audit', submission=allowed, kind='reference')
            runner.guard()
            if runner.probe('identity') != baseline_identity:
                raise RuntimeError('Epoch/worker identity changed during load')
            stage('load_' + phase, measurement)
        # Count distinct scheduled invocations before any manually induced notification.
        deadline = time.monotonic() + 360
        while True:
            raw = command(['journalctl', '--user', '-u', name + '.service', '--since', '@' + str(int(started)),
                           '--output=json', '--no-pager'], env=env).decode()
            rows = monitor_rows(raw, since=started, excluded=dry_invocations)
            invocations = {row['invocation'] for row in rows if row['invocation']}
            if len(invocations) >= 3:
                if any(not row['result']['healthy'] or row['result']['backup_status'] != 'deferred' for row in rows):
                    raise RuntimeError('Scheduled monitor observed unhealthy services')
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Three scheduled monitor invocations not observed')
            time.sleep(10)
        owned_daemon.publish(root / 'scheduled-monitor-invocations.json', rows)
        stage('three_scheduled_monitor_invocations', dict(count=len(invocations)))
        command(['systemctl', '--user', 'stop', name + '.timer'], env=env)
        wait_monitor_inactive(name, env)
        command(compose + ['stop', 'web'], env=env)
        failure_rows = invoke_monitor(name, env, healthy=False)
        owned_daemon.publish(root / 'failure-monitor-receipts.json', failure_rows)
        command(compose + ['up', '-d', '--no-deps', 'web'], env=env)
        wait_service_health(compose, env)
        runner.api('/api/v1/me')
        recovery_rows = invoke_monitor(name, env, healthy=True)
        owned_daemon.publish(root / 'failure-recovery-monitor-receipts.json', recovery_rows)
        stage('real_service_failure_and_recovery_signaled', dict(owner_email_confirmation_pending=True))
        # Five-minute period plus ten-minute grace: deliberately no heartbeat for >900 seconds.
        missed_wall = time.time()
        missed_started = time.monotonic()
        while time.monotonic() - missed_started < 960:
            time.sleep(min(30, 960 - (time.monotonic() - missed_started)))
        missed_rows = invoke_monitor(name, env, healthy=True)
        owned_daemon.publish(root / 'missed-heartbeat-receipts.json', dict(no_heartbeat_since=missed_wall, recovered_at=time.time(), receipts=missed_rows))
        stage('deliberately_missed_heartbeat_and_recovery', dict(elapsed_seconds=time.monotonic()-missed_started,
              owner_email_confirmation_pending=True, owner_pause_required=True))
    finally:
        stop_monitors(root, env)
        monitor_config['healthchecks']['enabled'] = False
        owned_daemon.publish(path, monitor_config)
