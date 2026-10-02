"""Sanitized host-check decisions. Queued work alone is never a failure."""
from datetime import datetime, timezone
import shutil
from pathlib import Path


def evaluate(readiness, services, leases, verified_backup, failed_jobs, now=None):
    now = now or datetime.now(timezone.utc)
    failures = set()
    if not readiness:
        failures.add('readiness')
    if not all(services.values()):
        failures.add('service')
    if any(expiry < now for expiry in leases):
        failures.add('lease')
    if verified_backup is None or (now - verified_backup).total_seconds() > 26 * 3600:
        failures.add('backup')
    if failed_jobs:
        failures.add('scheduled_job')
    if shutil.disk_usage('/srv').free < 5 * 1024**3:
        failures.add('disk')
    available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))) * 1024
    if available < 128 * 1024**2:
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
    compose = ['docker', 'compose', '--env-file', config['env_file'], '-f', config['compose']]
    def command(argv):
        return subprocess.check_output(argv, timeout=10, stderr=subprocess.DEVNULL, text=True)
    services = {}
    for role in ['web', 'coordinator', 'proxy', 'db']:
        try:
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
 values=session.scalars(select(EvaluationJob.lease_expires_at).where(EvaluationJob.status.in_(['claimed','running']),EvaluationJob.lease_expires_at.is_not(None))).all()
 print(json.dumps([value.isoformat() for value in values]))
'''
    failed_jobs = []
    try:
        leases = [datetime.fromisoformat(value) for value in json.loads(command(
            compose + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', code]))]
    except Exception:
        leases = []
        failed_jobs.append('lease_inspection')
    for unit in config.get('scheduled_units', []):
        try:
            if command(['systemctl', 'show', unit, '--property=Result', '--value']).strip() != 'success':
                failed_jobs.append(unit)
        except Exception:
            failed_jobs.append(unit)
    verified_backup = None
    try:
        backup = json.loads(Path(config['backup_state']).read_text())
        if backup['restore_verified'] and backup['repository'] == config['repository']:
            verified_backup = datetime.fromisoformat(backup['verified_at'])
    except Exception:
        pass
    failures = evaluate(readiness, services, leases, verified_backup, failed_jobs)
    if config.get('alert_enabled'):
        credential = private_file(config['alert_token_file']).read_text().strip()
        deliver(config['alert_url'], credential, Path(config['alert_state']), failures)
    print(json.dumps({'healthy': not failures, 'checks': sorted(failures)}))
    raise SystemExit(0 if not failures else 1)

if __name__ == '__main__':
    main()
