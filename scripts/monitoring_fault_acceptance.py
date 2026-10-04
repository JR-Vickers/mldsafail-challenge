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


def run(destination):
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {'scope': 'synthetic decisions, native Linux resource floors and loopback delivery only',
              'complete': False, 'checks': []}
    def save():
        path = destination / 'report.json'
        path.write_text(json.dumps(report, indent=2) + '\n')
        path.chmod(0o600)
    save()
    now = datetime.now(timezone.utc)
    services = dict(web=True, coordinator=True, proxy=True, db=True)
    baseline = evaluate(True, services, [], now, [], now)
    if baseline:
        raise RuntimeError('Native host resource baseline failed')
    cases = {
        'readiness': (False, services, [], now, []),
        'service': (True, {**services, 'web': False}, [], now, []),
        'lease': (True, services, [now - timedelta(seconds=1)], now, []),
        'backup-missing': (True, services, [], None, []),
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
