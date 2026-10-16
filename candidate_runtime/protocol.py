"""Bounded private candidate gateway framing; contains no native host authority."""
import json
import socket
import struct
import time

CAP=8*1024*1024


def send(connection,value):
    block=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(block)>CAP:raise ValueError('Candidate gateway frame exceeds cap')
    connection.sendall(struct.pack('!I',len(block))+block)


def receive(connection,*,seconds=10):
    deadline=time.monotonic()+seconds
    def read(size):
        blocks=[]
        while size:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Candidate gateway absolute deadline')
            connection.settimeout(remaining);block=connection.recv(min(size,65536))
            if not block:raise RuntimeError('Candidate gateway response incomplete')
            blocks.append(block);size-=len(block)
        return b''.join(blocks)
    size=struct.unpack('!I',read(4))[0]
    if not 0<size<=CAP:raise ValueError('Candidate gateway frame exceeds cap')
    return json.loads(read(size))
