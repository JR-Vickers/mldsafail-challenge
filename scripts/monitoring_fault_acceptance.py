"""Native Linux synthetic monitoring decisions and loopback webhook acceptance.

Never stops services, changes leases, sends external alerts or activates timers.
"""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from deploy.alert_webhook import deliver
from deploy.host_checks import evaluate
from deploy.recovery import validate_verified_state
from deploy.recovery_journal import atomic_json


def backup_receipt_cases(destination, now):
    """Exercise actual receipt validation and upload freshness with synthetic data."""
    path = destination / 'synthetic-backup-state.json'
    config = {'backup_state': str(path), 'repository': 's3:https://synthetic.invalid/monitor',
              'expected_epoch_id': 'synthetic-monitor-epoch'}
    baseline = {'schema': 'mldsafail.recovery-state.v1', 'repository': config['repository'],
                'snapshot': 'a' * 64, 'epoch_id': config['expected_epoch_id'], 'result_count': 0,
                'restored_manifest_sha256': 'b' * 64, 'restore_verified': True, 'cleanup_complete': True,
                'uploaded_at': (now - timedelta(hours=1)).isoformat(), 'verified_at': now.isoformat()}
    atomic_json(path, baseline)
    assert validate_verified_state(config, now=now) == baseline
    results = [{'check': 'versioned-exact-backup-receipt', 'passed': True}]
    variants = {'repository': {'repository': 'different-synthetic-repository'},
                'epoch': {'epoch_id': 'different-synthetic-epoch'},
                'snapshot-prefix': {'snapshot': 'a' * 8},
                'truthy-restore': {'restore_verified': 'true'},
                'cleanup': {'cleanup_complete': False},
                'future-upload': {'uploaded_at': (now + timedelta(seconds=1)).isoformat()},
                'naive-upload': {'uploaded_at': now.replace(tzinfo=None).isoformat()},
                'verification-before-upload': {'verified_at': (now - timedelta(hours=2)).isoformat()},
                'manifest': {'restored_manifest_sha256': 'partial'}}
    for name, changes in variants.items():
        atomic_json(path, {**baseline, **changes})
        try:
            validate_verified_state(config, now=now)
        except ValueError:
            results.append({'check': 'backup-receipt-rejects-' + name, 'passed': True})
        else:
            raise RuntimeError('Invalid synthetic recovery receipt accepted')
    atomic_json(path, {**baseline, 'uploaded_at': (now - timedelta(hours=27)).isoformat()})
    old = validate_verified_state(config, now=now)
    age = (now - datetime.fromisoformat(old['uploaded_at'])).total_seconds()
    assert age > 26 * 3600 and old['verified_at'] == now.isoformat()
    results.append({'check': 'recent-verification-cannot-refresh-old-upload', 'passed': True})
    return results


def run(destination):
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {'scope': 'synthetic decisions, native Linux resource floors and loopback delivery only',
              'complete': False, 'checks': []}
    def save():
        path = destination / 'report.json'
        atomic_json(path, report)
    save()
    now = datetime.now(timezone.utc)
    services = dict(web=True, coordinator=True, proxy=True, db=True)
    baseline = evaluate(True, services, [], now, [], now)
    if baseline:
        raise RuntimeError('Native host resource baseline failed')
    report['checks'].extend(backup_receipt_cases(destination, now))
    save()
    cases = {
        'readiness': (False, services, [], now, []),
        'service': (True, {**services, 'web': False}, [], now, []),
        'lease': (True, services, [now - timedelta(seconds=1)], now, []),
        'backup-missing': (True, services, [], None, []),
        'backup-future': (True, services, [], now + timedelta(seconds=1), []),
        'backup-naive': (True, services, [], now.replace(tzinfo=None), []),
        'backup-stale': (True, services, [], now - timedelta(hours=26, seconds=1), []),
        'scheduled_job': (True, services, [], now, ['synthetic-failed-unit']),
    }
    for name, values in cases.items():
        expected = name.split('-')[0]
        assert evaluate(*values, now=now) == {expected}
        report['checks'].append({'check': name, 'passed': True})
        save()
    requests = []
    responses = [503, 503, 204]
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            assert self.headers['Authorization'] == 'Bearer synthetic-monitor-test'
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            self.send_response(responses.pop(0) if responses else 204)
            self.end_headers()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state = destination / 'delivery-state.json'
    url = 'http://127.0.0.1:' + str(server.server_port)
    try:
        assert deliver(url, 'synthetic-monitor-test', state, {'backup', 'lease'}, now=1000)
        assert len(requests) == 3
        assert not deliver(url, 'synthetic-monitor-test', state, {'backup', 'lease'}, now=1001)
        assert len(requests) == 3
        assert deliver(url, 'synthetic-monitor-test', state, set(), now=1002)
        assert requests[-1] == {'status': 'recovered', 'checks': []}
        assert not deliver(url, 'synthetic-monitor-test', state, set(), now=1003)
        assert len(requests) == 4
        assert all(set(body) == {'status', 'checks'} for body in requests)
        report['checks'].append({'check': 'loopback-retries-deduplication-immediate-recovery-privacy', 'passed': True})
        report.update(complete=True, requests=requests)
        save()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.destination)
        print(json.dumps({'synthetic_native_monitoring_complete': result['complete']}))
    except Exception:
        print(json.dumps({'synthetic_native_monitoring_failed': True, 'partial_evidence_retained': True}))
        raise SystemExit(1)
