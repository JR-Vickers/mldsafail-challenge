"""Disposable native fault proxy: retain a real mutating RPC response, then drop it.

This is diagnostic tooling, never an eligible measurement endpoint. A trusted
native CLI shim points only its Docker subprocess here; guardian registration
continues to verify the real dedicated daemon endpoint. No gate passes merely
because this tool runs: the test must audit its receipt and daemon barriers.
"""
import hashlib
import http.client
import socket
import time
from pathlib import Path
from research.cpu_measurement.ownership import publish

CAP=4*1024*1024


def read_message(stream):
    data=bytearray()
    while b'\r\n\r\n' not in data:
        block=stream.recv(4096)
        if not block: raise RuntimeError('HTTP connection closed' if not data else 'Incomplete HTTP headers')
        data.extend(block)
        if len(data)>CAP: raise RuntimeError('HTTP message exceeds cap')
    headers,body=bytes(data).split(b'\r\n\r\n',1)
    fields={}
    for line in headers.split(b'\r\n')[1:]:
        key,value=line.split(b':',1)
        key=key.lower().strip()
        if key in fields: raise RuntimeError('Duplicate HTTP header')
        fields[key]=value.strip()
    if b'transfer-encoding' in fields: raise RuntimeError('Chunked diagnostic messages unsupported')
    length=int(fields.get(b'content-length',b'0'))
    if length<0 or length>CAP: raise RuntimeError('HTTP body exceeds cap')
    while len(body)<length:
        block=stream.recv(min(65536,length-len(body)))
        if not block: raise RuntimeError('Incomplete HTTP body')
        body+=block
    if len(body)!=length: raise RuntimeError('Pipelined messages unsupported')
    return headers+b'\r\n\r\n'+body,headers.split(b'\r\n',1)[0]


def _drop_acknowledgement(client, upstream, receipt, operation, after_receipt=None, preludes=None):
    """Forward a single proven create/start and retain the actual HTTP response."""
    client.settimeout(15);upstream.settimeout(45)
    deadline=time.monotonic()+60
    preludes=[] if preludes is None else preludes
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0: raise RuntimeError("Diagnostic request deadline exceeded")
        client.settimeout(min(15,remaining));upstream.settimeout(min(45,remaining))
        try: request,line=read_message(client)
        except RuntimeError as error:
            if str(error)=='HTTP connection closed' and preludes: return False
            raise
        method,path,_=line.split(b' ',2)
        if method not in {b'HEAD',b'GET'} or path!=b'/_ping': break
        if len(preludes)>=4: raise RuntimeError('Diagnostic health prelude limit exceeded')
        upstream.sendall(request)
        health=http.client.HTTPResponse(upstream,method=method.decode())
        health.begin();body=health.read(CAP+1)
        if len(body)>CAP: raise RuntimeError('Health response exceeds diagnostic cap')
        headers=[(key,value) for key,value in health.getheaders() if key.lower() not in {'transfer-encoding','content-length','connection'}]
        response=('HTTP/1.1 '+str(health.status)+' '+health.reason+'\r\n').encode()
        response+=b''.join((key+': '+value+'\r\n').encode('latin1') for key,value in headers)
        if health.will_close: response+=b'Connection: close\r\n'
        response+=('Content-Length: '+str(len(body))+'\r\n\r\n').encode()+body
        client.sendall(response)
        preludes.append(dict(method=method.decode(),path=path.decode(),daemon_response_code=health.status,
            request_sha256=hashlib.sha256(request).hexdigest(),response_sha256=hashlib.sha256(response).hexdigest(),response_delivered=True))
        closes=health.will_close
        health.close()
        if closes: return False
    valid=(method==b'POST' and ((operation=='create' and path.split(b'?',1)[0].endswith(b'/containers/create')) or
           (operation=='start' and path.split(b'?',1)[0].endswith(b'/start') and b'/containers/' in path)))
    if not valid: raise RuntimeError('Only the declared mutation may be faulted')
    upstream.sendall(request)
    parsed=http.client.HTTPResponse(upstream)
    parsed.begin()
    body=parsed.read(CAP+1)
    if len(body)>CAP: raise RuntimeError('Daemon response exceeds diagnostic cap')
    code=parsed.status
    response=(str(code)+' '+parsed.reason+'\n').encode()+repr(parsed.getheaders()).encode()+b'\n'+body
    parsed.close()
    publish(Path(receipt),dict(schema='mldsafail.native-transport-loss.v1',operation=operation,
        request_sha256=hashlib.sha256(request).hexdigest(),request_bytes=len(request),
        response_sha256=hashlib.sha256(response).hexdigest(),response_bytes=len(response),
        response_digest_encoding='status_headers_decoded_body.v1',
        daemon_response_code=code,actual_mutation_response_observed=code in {201,204},
        response_delivered=False,health_preludes=preludes))
    if after_receipt is not None: after_receipt()
    # Close both sockets without ever acknowledging the mutation to Docker CLI.
    for connection in (client,upstream):
        try: connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        connection.close()
    return True


def drop_acknowledgement(client, upstream, receipt, operation, after_receipt=None, preludes=None):
    try:
        return _drop_acknowledgement(client,upstream,receipt,operation,after_receipt,preludes)
    finally:
        errors=[]
        for connection in (client,upstream):
            try: connection.close()
            except OSError as error: errors.append(repr(error))
        if errors: raise RuntimeError('Diagnostic socket cleanup failed: '+repr(errors))
