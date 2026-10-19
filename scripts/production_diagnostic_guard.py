"""Owned, bounded transaction fencing deployed evaluation claim commits.

Only PostgreSQL lock/connection metadata and a pending-job count are inspected.
No application row is written, no lease is created and no epoch is accessed.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time

from deploy import owned_client, owned_daemon
from scripts.production_diagnostic_runtime import Client
from scripts.production_diagnostic_deadline import remaining

KEY = 1296843841


def identity_query(tag):
    if not re.fullmatch('diagnostic-[0-9a-f]{32}',tag):
        raise ValueError('Exact owned guard correlation required')
    return ("SELECT coalesce(json_agg(json_build_object('pid',a.pid,'backend_start',a.backend_start)), '[]'::json) "
        "FROM pg_stat_activity a WHERE a.application_name='"+tag+"' "
        "AND EXISTS (SELECT 1 FROM pg_locks l WHERE l.pid=a.pid AND l.locktype='advisory' "
        "AND l.classid=0 AND l.objid="+str(KEY)+" AND l.objsubid=1 AND l.granted AND l.mode='ExclusiveLock') "
        "AND EXISTS (SELECT 1 FROM pg_locks l WHERE l.pid=a.pid AND l.locktype='relation' "
        "AND l.relation='public.evaluation_jobs'::regclass AND l.mode='ShareLock' AND l.granted)")


def holder_sql(seconds):
    if not 0 < seconds <= 3000:
        raise ValueError('Bounded SQL holder required')
    return ("BEGIN; SET LOCAL lock_timeout='2s'; SET LOCAL statement_timeout='"+str(int(seconds*1000))+"ms'; "
        "DO $$ BEGIN PERFORM pg_advisory_xact_lock("+str(KEY)+"); LOCK TABLE public.evaluation_jobs IN SHARE MODE; "
        "IF EXISTS (SELECT 1 FROM evaluation_jobs WHERE status IN ('queued','claimed','running')) "
        "THEN RAISE EXCEPTION 'pending evaluation'; END IF; PERFORM pg_sleep("+str(seconds)+"); END $$; ROLLBACK;")




def query(packet, client, sql):
    database = next(row for row in packet['protected_containers'] if row['Name']=='/mldsafail-private-db-1')
    return client.run(['docker','--host',packet['protected_socket'],'exec',database['Id'],
        'psql','-X','-A','-t','-v','ON_ERROR_STOP=1','-U','mldsafail','-d','mldsafail','-c',sql],ceiling=5).stdout.decode().strip()


def verify(packet, client):
    guard = packet['evaluation_guard']
    rows = json.loads(query(packet,client,identity_query(guard['tag'])))
    if rows != [guard['backend']]:
        raise RuntimeError('Shared evaluation admission mutex lost or changed')
    if query(packet,client,"SELECT count(*) FROM evaluation_jobs WHERE status IN ('queued','claimed','running')") != '0':
        raise RuntimeError('Protected pending evaluation appeared')


class Guard:
    def __init__(self, packet, root, deadline):
        self.packet,self.root,self.deadline=packet,Path(root),deadline
        self.root.mkdir(mode=0o700)
        self.client=Client(self.root/'control-client',deadline)
        self.clients=[]
        self.error=None
        self.failed=threading.Event()
        self.releasing=False
        self.tag='diagnostic-'+packet['run_id']
        self.started=datetime.now(timezone.utc)
        self.save()

    def save(self):
        owned_daemon.publish(self.root/'clients.json',dict(clients=self.clients))

    def acquire(self):
        database=next(row for row in self.packet['protected_containers'] if row['Name']=='/mldsafail-private-db-1')
        # Fail on contention. Server-side statement timeout bounds the holder even
        # if both controller and Docker client die. Disconnect rolls back the lock.
        seconds=remaining(self.deadline,3000)-10
        if seconds <= 0:
            raise TimeoutError('No bounded evaluation guard window remains')
        sql=holder_sql(seconds)
        argv=['docker','--host',self.packet['protected_socket'],'exec','-e','PGAPPNAME='+self.tag,database['Id'],
              'psql','-X','-A','-t','-v','ON_ERROR_STOP=1','-U','mldsafail','-d','mldsafail','-c',sql]
        owned_daemon.publish(self.root/'intent.json',dict(tag=self.tag,started=self.started.isoformat(),
            deadline=self.deadline,database_id=database['Id']))
        def run():
            try:
                with (self.root/'holder.stdout').open('xb') as out,(self.root/'holder.stderr').open('xb') as err:
                    owned_client.run(argv,self.clients,self.save,self.root,timeout=seconds,
                        absolute_deadline=self.deadline,stdout=out,stderr=err)
            except BaseException as error:
                self.error=type(error).__name__
            finally:
                if not self.releasing:
                    self.failed.set()
        self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
        until=min(self.deadline,time.monotonic()+10)
        while True:
            rows=json.loads(query(self.packet,self.client,identity_query(self.tag)))
            if len(rows)==1:
                backend=rows[0]
                if type(backend['pid']) is not int or datetime.fromisoformat(backend['backend_start']) < self.started:
                    raise RuntimeError('Guard backend birth predates owned intent')
                self.packet['evaluation_guard']=dict(tag=self.tag,backend=backend)
                owned_daemon.publish(self.root/'authority.json',self.packet['evaluation_guard'])
                verify(self.packet,self.client)
                return self
            if rows or self.error or not self.thread.is_alive():
                raise RuntimeError('Evaluation guard did not acquire the shared mutex')
            remaining(until,1);time.sleep(.05)

    def release(self):
        # Match application tag, backend PID and backend birth; never terminate
        # another connection by PID alone. Cancellation aborts the owned sleep,
        # rolling back the transaction before the Docker client is settled.
        self.releasing=True
        backend=self.packet.get('evaluation_guard',{}).get('backend')
        if backend is None:
            rows=json.loads(query(self.packet,self.client,identity_query(self.tag)))
            if len(rows)>1:
                raise RuntimeError('Ambiguous guard backend authority')
            if rows:
                backend=rows[0]
                if datetime.fromisoformat(backend['backend_start']) < self.started:
                    raise RuntimeError('Guard backend predates intent')
                owned_daemon.publish(self.root/'authority.json',dict(tag=self.tag,backend=backend,
                    recovered_from_positive_backend=True))
            else:
                raise RuntimeError('Unacknowledged guard creation remains fenced')
        if backend:
            stamp=backend['backend_start']
            if not re.fullmatch(r'[0-9T:+. -]+',stamp):
                raise ValueError('Invalid retained backend birth')
            query(self.packet,self.client,"SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE pid="+
                str(backend['pid'])+" AND backend_start='"+stamp+"'::timestamptz AND application_name='"+self.tag+"'")
        thread=getattr(self,'thread',None)
        if thread is not None:
            thread.join(timeout=remaining(self.deadline,10))
        if (thread is not None and thread.is_alive()) or json.loads(query(self.packet,self.client,identity_query(self.tag))):
            raise RuntimeError('Evaluation guard cancellation remains unverified')
        for entry in self.clients:
            if 'cgroup' not in entry:
                owned_client.stop(entry)
                continue
            if owned_client.verify_domain(entry) is not None:
                raise RuntimeError('Evaluation guard client domain remains')
        owned_daemon.publish(self.root/'cleanup.json',dict(complete=True,lock_absent=True,clients_settled=True))


def cleanup_retained(packet, root, deadline):
    """Cleanup-only: retained intent, same backend birth, no lock acquisition."""
    import uuid
    root=Path(root)
    intent=owned_daemon.read_private_json(root/'intent.json')
    if intent['tag'] != 'diagnostic-'+packet['run_id']:
        raise ValueError('Guard ownership tag differs from reviewed generation')
    database=next(row for row in packet['protected_containers'] if row['Name']=='/mldsafail-private-db-1')
    if intent['database_id'] != database['Id']:
        raise ValueError('Guard database identity differs')
    identity_query(intent['tag'])  # Validate literal before any query.
    client=Client(root/('retained-cleanup-'+uuid.uuid4().hex),deadline)
    sql=("SELECT coalesce(json_agg(json_build_object('pid',pid,'backend_start',backend_start)), '[]'::json) "
         "FROM pg_stat_activity WHERE application_name='"+intent['tag']+"'")
    rows=json.loads(query(packet,client,sql))
    if len(rows)>1:
        raise RuntimeError('Ambiguous retained guard connection')
    authority=root/'authority.json'
    if not rows and not authority.exists():
        raise RuntimeError('Unacknowledged guard creation remains fenced')
    if rows:
        backend=rows[0]
        if (type(backend['pid']) is not int or
                datetime.fromisoformat(backend['backend_start']) < datetime.fromisoformat(intent['started'])):
            raise ValueError('Guard connection predates ownership intent')
        if authority.exists() and owned_daemon.read_private_json(authority)['backend'] != backend:
            raise ValueError('Guard backend birth changed')
        stamp=backend['backend_start']
        if not re.fullmatch(r'[0-9T:+. -]+',stamp):
            raise ValueError('Invalid retained guard birth')
        if not authority.exists():
            owned_daemon.publish(authority,dict(tag=intent['tag'],backend=backend,recovered_from_positive_backend=True))
        query(packet,client,"SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE pid="+
            str(backend['pid'])+" AND backend_start='"+stamp+"'::timestamptz AND application_name='"+intent['tag']+"'")
    until=min(deadline,time.monotonic()+5)
    while json.loads(query(packet,client,sql)):
        remaining(until,1);time.sleep(.05)
    for path in root.rglob('clients.json'):
        entries=owned_daemon.read_private_json(path)['clients']
        for entry in entries:
            owned_client.stop(entry)
            if 'cgroup' in entry and owned_client.verify_domain(entry) is not None:
                raise RuntimeError('Retained guard client remains')
    receipt=dict(complete=True,lock_absent=True,clients_settled=True,retained_intent=True)
    owned_daemon.publish(root/'cleanup.json',receipt)
    return receipt
