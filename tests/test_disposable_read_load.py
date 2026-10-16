import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy import owned_daemon
from scripts import disposable_read_load


@pytest.mark.parametrize('server', ['https://example.com', 'http://localhost:8080',
                                   'http://127.0.0.1', 'http://127.0.0.1:8000/path',
                                   'http://user@127.0.0.1:8000', 'http://127.0.0.1:8000?x=1',
                                   'http://0.0.0.0:8000', 'http://[::1]:8000'])
def test_load_origin_rejects_ambiguous_or_non_disposable_routes(server):
    with pytest.raises(ValueError):
        disposable_read_load.origin(server)


@pytest.mark.parametrize('damage', ['identity', 'image', 'worker', 'wildcard', 'port', 'stopped', 'udp'])
def test_foreign_container_binding_prevents_any_load(tmp_path, monkeypatch, damage):
    identifier = 'a' * 64
    image = 'sha256:' + 'b' * 64
    setup = tmp_path / 'setup.json'
    review = tmp_path / 'review.json'
    owned_daemon.publish(setup, dict(passed=True, synthetic_disposable=True))
    owned_daemon.publish(review, dict(disposable_load_source_sha256=hashlib.sha256(
        Path(disposable_read_load.__file__).read_bytes()).hexdigest()))
    container = dict(Id=identifier, Image=image, State=dict(Running=True),
                     HostConfig=dict(CgroupParent='owned.slice'),
                     NetworkSettings=dict(Ports={'8080/tcp': [dict(HostIp='127.0.0.1', HostPort='8123')]}))
    if damage == 'identity': container['Id'] = 'c' * 64
    if damage == 'image': container['Image'] = 'sha256:' + 'c' * 64
    if damage == 'worker': container['HostConfig']['CgroupParent'] = 'foreign.slice'
    if damage == 'wildcard': container['NetworkSettings']['Ports']['8080/tcp'][0]['HostIp'] = '0.0.0.0'
    if damage == 'port': container['NetworkSettings']['Ports']['8080/tcp'][0]['HostPort'] = '8124'
    if damage == 'stopped': container['State']['Running'] = False
    if damage == 'udp': container['NetworkSettings']['Ports'] = {'8080/udp': [dict(HostIp='127.0.0.1', HostPort='8123')]}
    journal = SimpleNamespace(path=tmp_path / 'driver.json', command=lambda argv:
                              SimpleNamespace(stdout=json.dumps([container]).encode()))
    monkeypatch.setattr(owned_daemon, 'load_manifest', lambda: {})
    monkeypatch.setattr(owned_daemon, 'verify_environment', lambda *a, **kw: None)
    monkeypatch.setattr(disposable_read_load.staging_read_load, 'run', lambda *a, **kw:
                        pytest.fail('No HTTP load may run against a foreign binding'))
    config = dict(review_packet=str(review), source_commit='d' * 40)
    data = dict(loaded_images=[image], worker_parent='/owned', worker_slice='owned.slice')
    protocol = dict(schema='mldsafail.disposable-load.v1', phase='idle',
                    server='http://127.0.0.1:8123', container_id=identifier, image=image,
                    bearer_file=str(tmp_path / 'unused'), setup_receipt=str(setup))
    with pytest.raises(RuntimeError, match='binding changed'):
        disposable_read_load.run(journal, config, data, protocol, phase_guard=lambda *a: True)
    report = json.loads((tmp_path / 'load-idle/report.json').read_text())
    assert report['passed'] is False and not report['requests']


def test_disposable_requests_never_forward_redirect_or_authorization(monkeypatch):
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, HTTPServer
    observed = []
    class Sink(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            observed.append(self.headers.get('Authorization'))
            self.send_response(200); self.end_headers()
    sink = HTTPServer(('127.0.0.1', 0), Sink)
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', 'http://127.0.0.1:' + str(sink.server_port) + '/sink')
            self.end_headers()
    redirect = HTTPServer(('127.0.0.1', 0), Redirect)
    servers = (sink, redirect)
    threads = [threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}) for server in servers]
    for thread in threads: thread.start()
    try:
        # Even a configured proxy must not capture or redirect the private probe.
        monkeypatch.setenv('http_proxy', 'http://127.0.0.1:' + str(sink.server_port))
        monkeypatch.setenv('no_proxy', '')
        request = urllib.request.Request('http://127.0.0.1:' + str(redirect.server_port),
                                         headers={'Authorization': 'Bearer synthetic-test-only'})
        with pytest.raises(RuntimeError, match='redirects are prohibited'):
            disposable_read_load.isolated_request_open()(request, timeout=2)
        assert observed == []
    finally:
        for server in servers: server.shutdown(); server.server_close()
        for thread in threads: thread.join(2); assert not thread.is_alive()
