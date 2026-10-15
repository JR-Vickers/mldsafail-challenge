"""Read load for a reviewed disposable application callback, never staging.

The caller provisions/audits fresh synthetic application state and supplies its
phase guard. This adapter reuses the existing 300-second request schedule, does
not submit work, and leaves all lifecycle cleanup to the enclosing owned driver.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import urllib.request

from deploy import owned_daemon
from scripts import staging_read_load
from scripts.hosted_vps_failure_acceptance import private_token


def origin(server):
    parsed = urlsplit(server)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment
            or parsed.port is None or not 1 <= parsed.port <= 65535):
        raise ValueError('Explicit disposable IPv4 loopback HTTP origin required')
    return parsed.port


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise RuntimeError('Disposable load redirects are prohibited')


def isolated_request_open():
    # A private opener avoids environment proxies and process-global mutations.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open


def run(journal, config, data, protocol, *, phase_guard):
    """Run exactly one idle/evaluation phase under an audited operator callback.

    phase_guard must independently verify the disposable database/epoch/queue
    and worker identities, including idle versus evaluation activity. It is part
    of the reviewed caller, not a participant-supplied hook.
    """
    if set(protocol) != {'schema', 'phase', 'server', 'container_id', 'image',
                         'bearer_file', 'setup_receipt'} or protocol['schema'] != 'mldsafail.disposable-load.v1':
        raise ValueError('Exact private disposable load protocol required')
    if protocol['phase'] not in {'idle', 'evaluation'} or not callable(phase_guard):
        raise ValueError('Declared phase and reviewed application phase guard required')
    review = owned_daemon.read_private_json(config['review_packet'])
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if review.get('disposable_load_source_sha256') != source:
        raise RuntimeError('Disposable load adapter absent from callback review')
    port = origin(protocol['server'])
    identifier = protocol['container_id']
    if not re.fullmatch('[a-f0-9]{64}', identifier) or protocol['image'] not in data['loaded_images']:
        raise ValueError('Exact freshly loaded application and container identities required')
    # The private caller's setup receipt binds fresh database, epoch and fixture
    # provenance. Revalidate it through phase_guard on every host-floor check.
    setup_path = owned_daemon._canonical(protocol['setup_receipt'])
    setup = owned_daemon.read_private_json(setup_path, cap=4 * 1024 * 1024)
    if setup.get('passed') is not True or setup.get('synthetic_disposable') is not True:
        raise RuntimeError('Audited disposable synthetic setup required')
    output = journal.path.parent / ('load-' + protocol['phase'])
    output.mkdir(mode=0o700)
    report = dict(schema='mldsafail.disposable-load-result.v1', passed=False,
                  phase=protocol['phase'], source_sha256=source,
                  setup_sha256=hashlib.sha256(setup_path.read_bytes()).hexdigest(),
                  source_commit=config['source_commit'], container_id=identifier,
                  image=protocol['image'], requests=[], duration_seconds=300,
                  outer_cleanup_required=True)
    owned_daemon.publish(output / 'report.json', report)

    def health():
        owned_daemon.verify_environment(owned_daemon.load_manifest(),
                                        measurement_parent=Path(data['worker_parent']))
        inspected = json.loads(journal.command(['docker', 'inspect', identifier]).stdout)
        if len(inspected) != 1:
            raise RuntimeError('Disposable application container disappeared')
        container = inspected[0]
        bindings = [entry for entries in container['NetworkSettings']['Ports'].values()
                    for entry in (entries or [])]
        if (container['Id'] != identifier or container['Image'] != protocol['image']
                or container['State']['Running'] is not True
                or container['HostConfig']['CgroupParent'] != data['worker_slice']
                or not bindings or any(row['HostIp'] != '127.0.0.1' for row in bindings)
                or not any(key.endswith('/tcp') and row['HostPort'] == str(port)
                           for key, entries in container['NetworkSettings']['Ports'].items()
                           for row in (entries or []))):
            raise RuntimeError('Exact isolated application binding changed')
        if phase_guard(protocol['phase'], setup) is not True:
            raise RuntimeError('Disposable application phase/identity guard failed')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        owned_daemon.publish(output / 'report.json', report)
        return available >= 134217728 and shutil.disk_usage('/srv').free >= 5368709120

    try:
        if not health():
            raise RuntimeError('Initial host resource floor failed')
        result = staging_read_load.run(protocol['server'], private_token(Path(protocol['bearer_file'])),
                                       health, duration=300, progress=report['requests'].append,
                                       request_open=isolated_request_open())
        report['result'] = result
        report['passed'] = result['passed'] and health()
    except BaseException as error:
        report['passed'] = False
        report['failure_class'] = type(error).__name__
        raise
    finally:
        try:
            owned_daemon.publish(output / 'report.json', report)
        except BaseException as error:
            report.update(passed=False, publication_failed=True)
            try:
                owned_daemon.publish(output / 'report.json', report)
            except BaseException as retry:
                error.add_note('Negative load publication failed: ' + repr(retry))
            raise
    return report
