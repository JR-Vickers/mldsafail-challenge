import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from deploy.alert_webhook import deliver


def test_local_delivery_deduplication_and_recovery(tmp_path):
    received = []
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            assert self.headers['Authorization'] == 'Bearer private-test-token'
            self.send_response(204)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/'
        state = tmp_path / 'state.json'
        assert deliver(url, 'private-test-token', state, {'backup'}, now=1000)
        assert not deliver(url, 'private-test-token', state, {'backup'}, now=1100)
        assert deliver(url, 'private-test-token', state, set(), now=1101)
        assert received == [{'status': 'failure', 'checks': ['backup']}, {'status': 'recovered', 'checks': []}]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
