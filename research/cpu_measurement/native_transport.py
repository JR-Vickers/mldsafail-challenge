"""Disposable native fault proxy: retain a real mutating RPC response, then drop it.

This is diagnostic tooling, never an eligible measurement endpoint. A trusted
native CLI shim points only its Docker subprocess here; guardian registration
continues to verify the real dedicated daemon endpoint. No gate passes merely
because this tool runs: the test must audit its receipt and daemon barriers.
"""
import hashlib
import socket
from pathlib import Path
from research.cpu_measurement.ownership import publish

CAP=4*1024*1024


def read_message(stream):
    data=bytearray()
    while b'\r\n\r\n' not in data:
        block=stream.recv(4096)
        if not block: raise RuntimeError('Incomplete HTTP headers')
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


def _drop_acknowledgement(client, upstream, receipt, operation):
    """Forward a single proven create/start and retain the actual HTTP response."""
    client.settimeout(15);upstream.settimeout(45)
    request,line=read_message(client)
    method,path,_=line.split(b' ',2)
    valid=(method==b'POST' and ((operation=='create' and path.split(b'?',1)[0].endswith(b'/containers/create')) or
           (operation=='start' and path.split(b'?',1)[0].endswith(b'/start') and b'/containers/' in path)))
    if not valid: raise RuntimeError('Only the declared mutation may be faulted')
    upstream.sendall(request)
    response,status=read_message(upstream)
    code=int(status.split(b' ',2)[1])
    publish(Path(receipt),dict(schema='mldsafail.native-transport-loss.v1',operation=operation,
        request_sha256=hashlib.sha256(request).hexdigest(),request_bytes=len(request),
        response_sha256=hashlib.sha256(response).hexdigest(),response_bytes=len(response),
        daemon_response_code=code,actual_mutation_response_observed=code in {201,204},
        response_delivered=False))
    # Close both sockets without ever acknowledging the mutation to Docker CLI.
    for connection in (client,upstream):
        try: connection.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        connection.close()


def drop_acknowledgement(client, upstream, receipt, operation):
    try:
        return _drop_acknowledgement(client,upstream,receipt,operation)
    finally:
        errors=[]
        for connection in (client,upstream):
            try: connection.close()
            except OSError as error: errors.append(repr(error))
        if errors: raise RuntimeError('Diagnostic socket cleanup failed: '+repr(errors))
