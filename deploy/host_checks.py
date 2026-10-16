"""Sanitized host-check decisions. Queued work alone is never a failure."""
from datetime import datetime, timezone
import shutil
import re
import os
from urllib.parse import urlsplit
from pathlib import Path


def validate_config(config):
    """Validate structure before inspecting services or delivering any heartbeat."""
    if not isinstance(config, dict) or config.get('scope', 'full') not in {'full', 'service'}:
        raise ValueError('Unknown monitoring scope')
    for key in ('env_file', 'compose'):
        value = config.get(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ValueError('Absolute monitoring configuration paths required')
    url = urlsplit(config.get('readiness_url', ''))
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
        raise ValueError('Invalid readiness URL')
    if 'daemon_manifest' in config and (not isinstance(config['daemon_manifest'], str) or not Path(config['daemon_manifest']).is_absolute()):
        raise ValueError('Absolute daemon manifest required')
    for key in ('scheduled_units', 'service_scheduled_units'):
        units = config.get(key, [])
        if not isinstance(units, list) or any(not isinstance(unit, str) or not re.fullmatch(
                r'[A-Za-z0-9_@.-]+\.service', unit) for unit in units):
            raise ValueError('Invalid scheduled units')
    settings = config.get('healthchecks', {})
    if not isinstance(settings, dict) or type(settings.get('enabled', False)) is not bool:
        raise ValueError('Invalid heartbeat settings')
    if settings.get('enabled'):
        from deploy.recovery import private_file
        from deploy.healthchecks import validate_endpoint
        validate_endpoint(private_file(settings['service_endpoint_file']).read_text().strip(), 'service', True)
    if type(config.get('alert_enabled', False)) is not bool:
        raise ValueError('Invalid alert settings')
    if config.get('alert_enabled'):
        from deploy.recovery import private_file
        alert = urlsplit(config.get('alert_url', ''))
        if (alert.scheme != 'https' and not (alert.scheme == 'http' and alert.hostname in {'127.0.0.1', 'localhost', '::1'})) or not alert.hostname or alert.username or alert.password:
            raise ValueError('Invalid alert URL')
        private_file(config['alert_token_file'])
        if not Path(config['alert_state']).is_absolute():
            raise ValueError('Absolute alert state required')
    return config.get('scope', 'full')


def evaluate(readiness, services, leases, verified_backup, failed_jobs, now=None, *, scope='full'):
    if scope not in {'full', 'service'}:
        raise ValueError('Unknown monitoring scope')
    now = now or datetime.now(timezone.utc)
    failures = set()
    if not readiness:
        failures.add('readiness')
    if not services or not all(services.values()):
        failures.add('service')
    try:
        if any(expiry.tzinfo is None or expiry < now for expiry in leases):
            failures.add('lease')
    except Exception:
        failures.add('lease')
    if scope == 'full' and (verified_backup is None or verified_backup.tzinfo is None or not 0 <= (now - verified_backup).total_seconds() <= 26 * 3600):
        failures.add('backup')
    if failed_jobs:
        failures.add('scheduled_job')
    try:
        if shutil.disk_usage('/srv').free < 5 * 1024**3:
            failures.add('disk')
    except Exception:
        failures.add('disk')
    try:
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        if available < 128 * 1024**2:
            failures.add('ram')
    except Exception:
        failures.add('ram')
    return failures


def main():
    import argparse
    import json
    import subprocess
    import urllib.request
    from deploy.recovery import private_file
    from deploy.alert_webhook import deliver
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(private_file(args.config).read_text())
    scope = validate_config(config)
    compose = ['docker', 'compose', '--env-file', config['env_file'], '-f', config['compose']]
    def command(argv):
        return subprocess.check_output(argv, timeout=10, stderr=subprocess.DEVNULL, text=True)
    daemon_ok = True
    if config.get('daemon_manifest'):
        try:
            from deploy import owned_daemon
            manifest = owned_daemon.load_manifest(config['daemon_manifest'])
            if os.environ.get('DOCKER_HOST') != 'unix://' + manifest['socket']:
                raise ValueError('Monitor socket differs from owned daemon')
            owned_daemon.verify_environment(manifest)
        except Exception:
            daemon_ok = False
    services = {}
    for role in ['web', 'coordinator', 'proxy', 'db']:
        try:
            if not daemon_ok:
                raise RuntimeError('Dedicated daemon identity inspection failed')
            identifier = command(compose + ['ps', '-q', role]).strip()
            state = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', identifier]))
            services[role] = state.get('Running') and state.get('Health', {}).get('Status', 'healthy') == 'healthy'
        except Exception:
            services[role] = False
    try:
        with urllib.request.urlopen(config['readiness_url'], timeout=3) as response:
            readiness = response.status == 200
    except Exception:
        readiness = False
    # Read-only lease inspection from the deployed coordinator environment.
    code = '''import json,os
from datetime import datetime,timezone
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob
engine=create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])
with Session(engine) as session:
 if engine.dialect.name == 'postgresql': session.execute(text('SET TRANSACTION READ ONLY'))
 values=session.scalars(select(EvaluationJob.lease_expires_at).where(EvaluationJob.status.in_(['claimed','running']))).all()
 print(json.dumps([value.isoformat() if value is not None else None for value in values]))
'''
    failed_jobs = []
    try:
        if not daemon_ok:
            raise RuntimeError('Dedicated daemon identity inspection failed')
        leases = [datetime.fromisoformat(value) for value in json.loads(command(
            compose + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', code]))]
    except Exception:
        leases = []
        failed_jobs.append('lease_inspection')
    for unit in config.get('service_scheduled_units' if scope == 'service' else 'scheduled_units', []):
        try:
            if command(['systemctl', 'show', unit, '--property=Result', '--value']).strip() != 'success':
                failed_jobs.append(unit)
        except Exception:
            failed_jobs.append(unit)
    verified_backup = None
    if scope == 'full':
        try:
            from deploy.recovery import validate_verified_state
            if not config.get('expected_epoch_id'):
                raise ValueError('Monitoring requires exact expected epoch identity')
            backup = validate_verified_state(config)
            verified_backup = datetime.fromisoformat(backup['uploaded_at'])
        except Exception:
            pass
    failures = evaluate(readiness, services, leases, verified_backup, failed_jobs, scope=scope)
    from deploy.healthchecks import notify
    notify(config, 'service', not failures)
    if config.get('alert_enabled'):
        credential = private_file(config['alert_token_file']).read_text().strip()
        deliver(config['alert_url'], credential, Path(config['alert_state']), failures)
    print(json.dumps({'healthy': not failures, 'checks': sorted(failures), 'scope': scope,
                      'backup_status': 'deferred' if scope == 'service' else ('failed' if 'backup' in failures else 'verified')}))
    raise SystemExit(0 if not failures else 1)

if __name__ == '__main__':
    main()
