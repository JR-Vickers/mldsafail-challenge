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


@pytest.mark.parametrize('method',[b'HEAD',b'GET'])
@pytest.mark.parametrize('reconnect',[False,True])
def test_actual_health_response_relay_before_exact_mutation(tmp_path,method,reconnect):
    preludes=[];errors=[]
    def exchange(health_only):
        client,proxy=socket.socketpair();server,upstream=socket.socketpair()
        result=[]
        def fault():
            try: result.append(drop_acknowledgement(proxy,upstream,tmp_path/'receipt','create',preludes=preludes))
            except BaseException as error: errors.append(error)
        thread=threading.Thread(target=fault);thread.start()
        if not preludes:
            request=method+b' /_ping HTTP/1.1\r\n\r\n'
            client.sendall(request);assert server.recv(4096)==request
            server.sendall(b'HTTP/1.1 200 OK\r\nAPI-Version: 1.56\r\nContent-Length: 2\r\n\r\n'+(b'OK' if method==b'GET' else b''))
            response=client.recv(4096)
            assert b'API-Version: 1.56' in response and response.startswith(b'HTTP/1.1 200 OK')
            if method==b'GET': assert response.endswith(b'OK')
        if health_only:
            client.close()
        else:
            request=b'POST /v1.56/containers/create HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}'
            client.sendall(request);assert server.recv(4096)==request
            server.sendall(b'HTTP/1.1 201 Created\r\nContent-Length: 2\r\n\r\n{}')
        thread.join(timeout=2)
        assert not thread.is_alive() and not errors
        assert result==[not health_only]
        client.close();server.close()
    if reconnect: exchange(True)
    exchange(False)
    receipt=json.loads((tmp_path/'receipt').read_text())
    assert receipt['health_preludes']==preludes and len(preludes)==1
    assert receipt['actual_mutation_response_observed'] is True
    assert receipt['response_delivered'] is False


def test_other_read_or_mutation_is_not_a_health_prelude(tmp_path):
    client,proxy=socket.socketpair();server,upstream=socket.socketpair()
    errors=[]
    def fault():
        try: drop_acknowledgement(proxy,upstream,tmp_path/'receipt','create')
        except RuntimeError as error: errors.append(str(error))
    thread=threading.Thread(target=fault);thread.start()
    client.sendall(b'GET /version HTTP/1.1\r\n\r\n')
    thread.join(timeout=2)
    assert errors==['Only the declared mutation may be faulted']
    assert not (tmp_path/'receipt').exists()
    client.close();server.close()
