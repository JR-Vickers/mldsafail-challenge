"""Owner-configured secret-free webhook, inactive until local delivery validation."""
import json
from pathlib import Path
import time
import urllib.request
import fcntl
from urllib.parse import urlparse

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Webhook redirects are forbidden')


def deliver(url, token, state_file: Path, failing: set[str], now=None):
    parsed = urlparse(url)
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}):
        raise ValueError('External webhooks require HTTPS')
    if parsed.username or parsed.password:
        raise ValueError('URL credentials are forbidden')
    allowed = {'readiness', 'service', 'disk', 'ram', 'lease', 'backup', 'scheduled_job'}
    if not failing <= allowed:
        raise ValueError('Unknown alert code')
    now = time.time() if now is None else now
    state_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with state_file.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
        codes = sorted(failing)
        if previous.get('codes') == codes and now - previous.get('sent', 0) < 600:
            return False
        if not codes and not previous.get('codes'):
            return False
        body = json.dumps({'status': 'failure' if codes else 'recovered', 'checks': codes}).encode()
        request = urllib.request.Request(url, data=body, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        for attempt in range(3):
            try:
                with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
                    if not 200 <= response.status < 300:
                        raise RuntimeError('Delivery failed')
                temporary = state_file.with_suffix('.tmp')
                temporary.write_text(json.dumps({'codes': codes, 'sent': now}))
                temporary.chmod(0o600)
                temporary.replace(state_file)
                return True
            except Exception:
                if attempt == 2:
                    raise RuntimeError('Alert delivery failed') from None
                time.sleep(2 ** attempt)
