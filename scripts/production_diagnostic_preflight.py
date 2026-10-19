"""Read-only fresh host admission; no images, services, epochs or dispatch."""
import json
import os
from pathlib import Path
import shutil
import time

from deploy import owned_client, owned_daemon
from scripts.production_diagnostic_runtime import Client


def inspect(packet, root, deadline):
    client = Client(Path(root)/'preflight-client', deadline)
    began = time.monotonic()
    rows = {}
    import hashlib, platform
    if hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest() != packet['host_machine_id_sha256']:
        raise RuntimeError('Diagnostic host identity differs')
    if platform.machine() != 'x86_64':
        raise RuntimeError('Native amd64 host required')
    raw = client.run(['docker','--host',packet['protected_socket'],'ps','-aq','--no-trunc'], ceiling=10).stdout
    identifiers = raw.decode().split()
    expected = packet['protected_containers']
    if set(identifiers) != {row['Id'] for row in expected}:
        raise RuntimeError('Protected container inventory differs')
    actual = json.loads(client.run(['docker','--host',packet['protected_socket'],'inspect',*identifiers], ceiling=10).stdout)
    indexed = {row['Id']:row for row in actual}
    for entry in expected:
        observed = indexed[entry['Id']]
        if observed['Image'] != entry['Image'] or any(observed['State'][field] != entry['State'][field]
            for field in ('Running','Pid','StartedAt')):
            raise RuntimeError('Protected container identity differs')
    for entry in packet.get('protected_processes', []):
        if owned_client.identity(entry['pid']) != entry:
            raise RuntimeError('Protected process birth differs')
    from scripts.production_diagnostic_bootstrap import assert_no_foreign_jobs
    assert_no_foreign_jobs(packet['protected_domains'],operator_parent=packet['operator_parent'])
    for entry in packet['protected_domains']:
        if owned_client.domain_identity(entry['path']) != entry:
            raise RuntimeError('Protected process/domain identity differs')
    jobs = client.run(['systemctl','--user','list-jobs','--no-legend'], ceiling=10).stdout.decode().strip()
    if jobs:
        raise RuntimeError('Unreconciled user manager jobs')
    units = json.loads(client.run(['systemctl','--user','list-units','--state=active','--output=json','--no-legend'], ceiling=10).stdout)
    allowed = set(packet['allowed_active_units'])
    for unit in units:
        if unit['unit'].startswith('mldsafail-') and unit['unit'] not in allowed:
            raise RuntimeError('Unreconciled active operator, build or maintenance')
    # The protected coordinator retains its ordinary environment. Query only the
    # count of pending jobs, never private scientific evidence or credentials.
    code = '''import os
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob
with Session(create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])) as session:
 session.execute(text('SET TRANSACTION READ ONLY'))
 print(session.scalar(select(func.count()).select_from(EvaluationJob).where(EvaluationJob.status.in_(['queued','claimed','running']))))
'''
    count = int(client.run(['docker','--host',packet['protected_socket'],'exec',packet['protected_coordinator'],
        '/app/.venv/bin/python','-c',code], ceiling=10).stdout)
    if count:
        raise RuntimeError('Active or queued evaluations prohibit admission')
    disk = shutil.disk_usage(packet['filesystem']).free
    memory = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
        if line.startswith('MemAvailable:'))) * 1024
    if (packet['minimum_disk_admission_bytes'] < 5*1024**3 or packet['minimum_memory_bytes'] < 128*1024**2):
        raise ValueError('Existing resource floors cannot be lowered')
    if disk < packet['minimum_disk_admission_bytes'] or memory < packet['minimum_memory_bytes']:
        raise RuntimeError('Diagnostic admission resource floor failed')
    for path in packet['retired_sockets']:
        if os.path.lexists(path):
            raise RuntimeError('Retired owned endpoint remains')
    if os.readlink('/srv/mldsafail/current') != packet['current_release']:
        raise RuntimeError('Protected current deployment changed')
    for entry in packet['retained_receipts']:
        from scripts.production_diagnostic import file_digest
        if file_digest(entry['path']) != entry['sha256']:
            raise RuntimeError('Retained protected evidence changed')
    rows.update(passed=True, elapsed_seconds=time.monotonic()-began, disk_available_bytes=disk,
        memory_available_bytes=memory, pending_jobs=count, protected_containers=expected,
        current_release=packet['current_release'], delivery=False, spending_usd=0)
    owned_daemon.publish(Path(root)/'preflight.json', rows)
    return rows
