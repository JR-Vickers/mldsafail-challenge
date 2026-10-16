"""Private Healthchecks endpoints with fixed, secret-free heartbeat bodies."""
import re
import time
import urllib.request
from urllib.parse import urlsplit

from deploy.alert_webhook import NoRedirect
from deploy.recovery import private_file

CHECKS = {'service', 'recovery'}


def ping(endpoint, check, healthy, *, opener=None, sleep=time.sleep):
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'https' or parsed.netloc != 'hc-ping.com' or
            not re.fullmatch(r'/[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', parsed.path) or
            parsed.query or parsed.fragment or check not in CHECKS or type(healthy) is not bool):
        raise ValueError('Invalid private Healthchecks configuration')
    request = urllib.request.Request(endpoint + ('' if healthy else '/fail'),
                                     data=f'{check}:{"healthy" if healthy else "failure"}'.encode(),
                                     headers={'Content-Type': 'text/plain'})
    opener = opener or urllib.request.build_opener(NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=5) as response:
                if response.status != 200 or response.read(64).strip() != b'OK':
                    raise RuntimeError('Heartbeat was not accepted')
            return True
        except Exception:
            if attempt == 2:
                raise RuntimeError('Healthchecks delivery failed') from None
            sleep(2 ** attempt)


def notify(config, check, healthy):
    """Disabled by default; URLs are credentials and never enter public reports."""
    settings = config.get('healthchecks', {})
    if not settings.get('enabled', False):
        return False
    if check not in CHECKS:
        raise ValueError('Unknown heartbeat check')
    endpoint = private_file(settings[check + '_endpoint_file']).read_text().strip()
    return ping(endpoint, check, healthy)
