"""Real loopback SQL through private versioned helper pipes; no Docker/epoch."""
import os
import subprocess
import sys

from test_maintenance_fence import database, CEILINGS
from deploy.maintenance_fence import Fence, database_identity, prepare
from deploy.maintenance_transport import Connection, encode


def test_real_fence_over_separate_private_pipes(tmp_path,database):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    credentials=conninfo_to_dict(os.environ['MLDSAFAIL_MAINTENANCE_TEST_POSTGRES'])
    processes=[]
    connections=[]
    count=0
    def connect():
        nonlocal count
        index=count;count+=1
        code=('import sys,psycopg; from deploy.maintenance_transport import serve; '
              'serve(sys.stdin.buffer,sys.stdout.buffer,lambda c:psycopg.connect(**c,autocommit=True,connect_timeout=2))')
        process=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        processes.append(process)
        process.stdin.write(encode(credentials));process.stdin.flush()
        connection=Connection(process,lambda:'local','local',timeout=14 if index==1 else .5)
        connections.append(connection)
        return connection
    direct,_=database
    with direct() as connection: identity=database_identity(connection)
    root=tmp_path/'fence'
    prepare(root,database=identity,container='local',lifetime=12,ceilings=CEILINGS)
    fence=Fence(root,connect,lambda:'local')
    try:
        fence.acquire()
        with fence.phase('stop',lambda:None): assert fence.verify()
        fence.release()
        assert count==3
    finally:
        for connection in connections: connection.close()
        for process in processes:
            if process.poll() is None: process.kill();process.wait(timeout=2)
    assert all(p.poll() is not None for p in processes)
