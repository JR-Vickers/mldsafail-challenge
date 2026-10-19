"""One owned phase process: cancellation and journals do not cross phase boundaries."""
import json
import os
from pathlib import Path
import sys
import threading
import time

from deploy import owned_daemon
from scripts.production_diagnostic_runtime import Client, Workload
from scripts.production_diagnostic_deadline import remaining
from scripts import production_diagnostic as diagnostic


class Health:
    def __init__(self, packet, root, deadline):
        self.packet, self.root = packet, Path(root)
        self.client = Client(self.root / 'observer-client', deadline)
        self.owner_root = str(root)
        self.rows = []

    def cancel(self):
        self.client.cancel.set()

    def __call__(self):
        from scripts.production_diagnostic_deadline import bounded
        with bounded(min(self.client.deadline,time.monotonic()+5)):
            return self.inspect()

    def inspect(self):
        import shutil
        from deploy import owned_client
        started = time.monotonic()
        passed = False
        try:
            # Kernel/provisioning checks plus API identities, in a separate owned
            # client domain. Never mutate the lifecycle evidence journal here.
            manifest = owned_daemon.load_manifest(self.packet['manifest_path'])
            owned_daemon.verify_environment(manifest)
            for entry in self.packet['protected_domains']:
                if owned_client.domain_identity(entry['path']) != entry:
                    raise RuntimeError('Protected domain changed')
            raw = self.client.run(['docker', '--host', self.packet['protected_socket'],
                'inspect', *[row['Id'] for row in self.packet['protected_containers']]], ceiling=4).stdout
            actual = json.loads(raw)
            if len(actual) != len(self.packet['protected_containers']):
                raise RuntimeError('Protected inventory changed')
            for row, expected in zip(actual, self.packet['protected_containers']):
                if row['Id'] != expected['Id'] or row['Image'] != expected['Image'] or any(
                        row['State'][field] != expected['State'][field] for field in ('Running', 'Pid', 'StartedAt')):
                    raise RuntimeError('Protected deployment changed')
            available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                if line.startswith('MemAvailable:'))) * 1024
            disk = shutil.disk_usage(self.root).free
            passed = available >= self.packet['minimum_memory_bytes'] and disk >= 5 * 1024**3
            if time.monotonic() - started > 5:
                passed = False
        finally:
            self.rows.append(dict(started=started, finished=time.monotonic(), healthy=passed))
            owned_daemon.publish(self.root / 'observations.json', dict(rows=self.rows))
        return passed and time.monotonic()-started <= 5


class Sampler:
    def __init__(self, packet, root, deadline, heavy):
        self.packet, self.root, self.deadline = packet, Path(root), deadline
        self.heavy = heavy
        self.stop = threading.Event()
        self.client = Client(self.root / 'sampler-client', deadline)
        self.rows, self.failed = [], False
        self.wait_rows = []
        self.database_thread = threading.Thread(target=self.database_waits, daemon=True) if heavy else None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            while not self.stop.is_set():
                started = time.monotonic()
                row = dict(monotonic=started, domains={})
                for name, path in self.packet['sample_domains'].items():
                    domain = Path(path)
                    row['domains'][name] = dict(cpu=(domain / 'cpu.stat').read_text(),
                        memory=int((domain / 'memory.current').read_text()))
                self.rows.append(row)
                owned_daemon.publish(self.root / 'samples.json', dict(rows=self.rows, complete=False))
                self.stop.wait(max(0, 1 - (time.monotonic() - started)))
        except BaseException:
            self.failed = True

    def database_waits(self):
        try:
            while not self.stop.is_set():
                started = time.monotonic()
                query = "SELECT coalesce(wait_event_type,'none'),count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY 1"
                raw = self.client.run(self.packet['compose'] + ['exec', '-T', 'db', 'psql', '-U', 'mldsafail',
                    '-d', 'mldsafail', '-At', '-c', query], ceiling=2).stdout
                self.wait_rows.append(dict(monotonic=started, counts=raw.decode().splitlines()))
                owned_daemon.publish(self.root / 'database-waits.json', dict(rows=self.wait_rows))
                self.stop.wait(max(0, 1-(time.monotonic()-started)))
        except BaseException:
            self.failed = True

    def start(self):
        self.thread.start()
        if self.database_thread is not None:
            self.database_thread.start()
        return self

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=remaining(self.deadline, 3))
        if self.thread.is_alive():
            self.client.cancel.set()
            self.thread.join(timeout=remaining(self.deadline, 2))
        if self.database_thread is not None:
            self.database_thread.join(timeout=remaining(self.deadline, 3))
            if self.database_thread.is_alive():
                self.client.cancel.set()
                self.database_thread.join(timeout=remaining(self.deadline, 2))
        complete = (not self.thread.is_alive() and not self.failed
                    and (self.database_thread is None or not self.database_thread.is_alive()))
        owned_daemon.publish(self.root / 'samples.json', dict(rows=self.rows, complete=complete))
        if not complete:
            raise RuntimeError('Resource/database observation failed')


def monitor(packet, root, client):
    from scripts.production_rehearsal_monitor_load import monitor_rows
    rows = []
    for index in range(3):
        wall, started = time.time(), time.monotonic()
        result = client.run(['systemctl', '--user', 'start', packet['monitor'] + '.service'],
            ceiling=120, check=False)
        # Ingestion can lag; do not mistake an empty receipt for a healthy result.
        records = []
        for _attempt in range(10):
            raw = client.run(['journalctl', '--user', '-u', packet['monitor'] + '.service',
                '--since', '@' + str(int(wall)), '--output=json', '--no-pager'], ceiling=10).stdout
            records = monitor_rows(raw.decode(), since=wall)
            if records:
                break
            time.sleep(.1)
        rows.append(dict(index=index, seconds=time.monotonic()-started,
            exit_status=result.returncode, receipts=records))
        owned_daemon.publish(root / 'monitor.json', dict(rows=rows))
        if not records:
            raise RuntimeError('Actual monitor receipt unavailable')
    return dict(complete=True, rows=rows)


def components(packet, root, client):
    """Supplement actual unit results; never replace their failure outcomes."""
    from deploy.host_checks import LEASE_QUERY_CODE
    commands = [('owned_client', [sys.executable, '-c', 'pass']),
        ('docker_inspect', ['docker', 'inspect', packet['coordinator_id']]),
        ('docker_exec', packet['compose'] + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', 'pass']),
        ('identical_lease_query', packet['compose'] + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', LEASE_QUERY_CODE])]
    rows = []
    for name, argv in commands:
        started = time.monotonic()
        try:
            process = client.run(argv, ceiling=10, check=False)
            row = dict(name=name, seconds=time.monotonic()-started, returncode=process.returncode,
                classification='ok' if process.returncode == 0 else 'command')
            if name == 'identical_lease_query' and process.returncode == 0:
                try:
                    from datetime import datetime
                    values = json.loads(process.stdout)
                    for value in values:
                        datetime.fromisoformat(value)
                except Exception:
                    row['classification'] = 'parsing'
        except Exception as error:
            row = dict(name=name, seconds=time.monotonic()-started,
                classification='timeout' if isinstance(error, TimeoutError) else 'command')
        rows.append(row)
        owned_daemon.publish(root / 'components.json', dict(rows=rows))
    # Individual import/connection/query timings inside the identical environment.
    code = '''import json,os,time
s=time.monotonic()
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob
imports=time.monotonic()-s
engine=create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])
s=time.monotonic()
with engine.connect() as connection:
 connection_seconds=time.monotonic()-s
 connection.execute(text('SET TRANSACTION READ ONLY'))
 s=time.monotonic()
 with Session(bind=connection) as session:
  session.scalars(select(EvaluationJob.lease_expires_at).where(EvaluationJob.status.in_(['claimed','running']))).all()
 query_seconds=time.monotonic()-s
print(json.dumps(dict(import_seconds=imports,connection_seconds=connection_seconds,query_seconds=query_seconds)))
'''
    raw = client.run(packet['compose'] + ['exec', '-T', 'coordinator', '/app/.venv/bin/python', '-c', code], ceiling=10).stdout
    owned_daemon.publish(root / 'lease-components.json', json.loads(raw))


def run(packet, phase, deadline):
    root = Path(packet['root']) / phase
    root.mkdir(mode=0o700)
    client = Client(root / 'lifecycle-client', deadline)
    health = Health(packet, root, deadline)
    loaded = phase.endswith('loaded')
    workload = None
    sampler = None
    report = dict(phase=phase, complete=False, diagnostic_only=True, private_acceptance=False, ranking=False)
    try:
        if not health():
            raise RuntimeError('Initial ownership/resource observation failed')
        if loaded:
            workload = Workload(packet, root, deadline, packet['run_id'], packet['worker_slice']).start()
        sampler = Sampler(packet, root, deadline, not phase.startswith('final-')).start()
        original_health = health
        def guarded_health():
            return (not sampler.failed and (workload is None or (workload.error is None and workload.thread.is_alive()))
                    and original_health())
        guarded_health.owner_root = str(root)
        guarded_health.cancel = original_health.cancel
        health = guarded_health
        if phase.startswith('monitor-'):
            report['measurement'] = monitor(packet, root, client)
            components(packet, root, client)
        elif phase.startswith('http-'):
            from scripts.production_diagnostic_probes import request_comparison
            report['measurement'] = request_comparison(packet['base'], packet['token'], health,
                lambda rows: owned_daemon.publish(root / 'requests.json', dict(rows=rows)), read_only_health=True)
        elif phase.startswith('final-'):
            from scripts.staging_read_load import run as load
            from scripts.production_diagnostic_service import append
            def progress(row):
                append(root/'completed-requests.jsonl', row)
            report['measurement'] = load(packet['base'], packet['token'], health,
                progress=progress, read_only_health=True,
                intent=lambda row: append(root/'request-intents.jsonl', row))
        elif phase == 'legacy':
            from scripts.production_diagnostic_probes import legacy_experiment
            report['measurement'] = legacy_experiment(packet['legacy_source'], packet['legacy_source_sha256'],
                packet['base'], packet['token'], health,
                lambda row: owned_daemon.publish(root / 'legacy.json', row))
        else:
            raise ValueError('Unknown diagnostic phase')
        measurement = report['measurement']
        report['complete'] = (measurement.get('complete') is True if not phase.startswith('final-') and phase != 'legacy'
            else measurement.get('passed') is True if phase.startswith('final-') else measurement.get('instrumentation_complete') is True)
    finally:
        errors = []
        for name, operation in [('workload', workload.finish if workload else None),
                                ('sampler', sampler.finish if sampler else None)]:
            if operation:
                try:
                    operation()
                except BaseException as error:
                    errors.append(dict(step=name, error_type=type(error).__name__))
        from scripts.read_load_observer import quiesce
        if not quiesce(root):
            errors.append(dict(step='observer', error_type='UnsettledObserver'))
        report['errors'] = errors
        report['complete'] = report['complete'] and not errors
        owned_daemon.publish(root / 'report.json', report)
    if not report['complete']:
        raise RuntimeError('Diagnostic phase incomplete')
    return report


if __name__ == '__main__':
    packet = owned_daemon.read_private_json(sys.argv[1], cap=4*1024*1024)
    run(packet, sys.argv[2], float(sys.argv[3]))
