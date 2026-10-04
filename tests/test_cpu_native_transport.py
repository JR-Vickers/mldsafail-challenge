import json
import socket
import threading
from research.cpu_measurement.native_transport import drop_acknowledgement


import pytest

@pytest.mark.parametrize('chunked',[False,True])
def test_real_mutation_response_is_retained_but_not_delivered(tmp_path,chunked):
    client,proxy=socket.socketpair();server,upstream=socket.socketpair()
    errors=[]
    def fault():
        try: drop_acknowledgement(proxy,upstream,tmp_path/'receipt','create')
        except BaseException as error: errors.append(error)
    thread=threading.Thread(target=fault);thread.start()
    request=b'POST /v1.47/containers/create HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}'
    client.sendall(request)
    assert server.recv(4096)==request
    server.sendall(b'HTTP/1.1 201 Created\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n' if chunked else b'HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\n{}')
    thread.join(timeout=2)
    assert not thread.is_alive() and not errors
    assert client.recv(4096)==b''
    receipt=json.loads((tmp_path/'receipt').read_text())
    assert receipt['actual_mutation_response_observed'] and not receipt['response_delivered']
    client.close();server.close()
