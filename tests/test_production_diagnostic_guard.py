import json
import os
from pathlib import Path
import subprocess
import time

import pytest

from scripts.production_diagnostic_guard import holder_sql,identity_query


def test_guard_identity_and_deadline_inputs_are_bounded():
    for tag in ('wrong', "diagnostic-';DELETE",'diagnostic-'+'a'*33):
        with pytest.raises(ValueError):identity_query(tag)
    for seconds in (0,-1,3001):
        with pytest.raises(ValueError):holder_sql(seconds)


@pytest.mark.skipif(not os.environ.get('MLDSAFAIL_DIAGNOSTIC_GUARD_POSTGRES'),reason='Dedicated loopback PostgreSQL required')
def test_guard_blocks_claim_commit_and_releases_on_cancel_and_server_timeout(tmp_path,monkeypatch):
    import psycopg
    url=os.environ['MLDSAFAIL_DIAGNOSTIC_GUARD_POSTGRES']
    assert '@127.0.0.1:' in url and url.endswith('/diagnostic_guard_test')
    with psycopg.connect(url,autocommit=True) as database:
        database.execute('DROP TABLE IF EXISTS evaluation_jobs')
        database.execute('CREATE TABLE evaluation_jobs(id integer PRIMARY KEY,status text NOT NULL)')
        database.execute("INSERT INTO evaluation_jobs VALUES(1,'complete')")
        tag='diagnostic-'+'a'*32
        def start(seconds):
            process=subprocess.Popen(['/opt/homebrew/bin/psql',url,'-X','-A','-t','-v','ON_ERROR_STOP=1','-c',holder_sql(seconds)],
                env=dict(os.environ,PGAPPNAME=tag),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            until=time.monotonic()+2
            while True:
                rows=database.execute(identity_query(tag)).fetchone()[0]
                if rows:return process,rows[0]
                assert process.poll() is None
                assert time.monotonic()<until
                time.sleep(.01)
        process,backend=start(10)
        assert database.execute('SELECT count(*) FROM evaluation_jobs').fetchone()==(1,)
        with psycopg.connect(url) as contender:
            contender.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                contender.execute("UPDATE evaluation_jobs SET status='claimed' WHERE id=1")
        # Interrupted acquisition: intent survives but authority publication did not.
        from datetime import datetime,timezone,timedelta
        from scripts import production_diagnostic_guard as guard
        from deploy import owned_daemon
        owned_daemon.publish(tmp_path/'intent.json',dict(tag=tag,
            started=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat(),database_id='owned-db'))
        monkeypatch.setattr(guard,'Client',lambda *args:None)
        def local_query(packet,client,sql):
            assert 'LOCK TABLE' not in sql and 'BEGIN' not in sql  # Cleanup cannot acquire or resume.
            value=database.execute(sql).fetchone()[0]
            return json.dumps(value) if isinstance(value,list) else str(value)
        monkeypatch.setattr(guard,'query',local_query)
        receipt=guard.cleanup_retained(dict(run_id='a'*32,
            protected_containers=[dict(Name='/mldsafail-private-db-1',Id='owned-db')]),tmp_path,time.monotonic()+5)
        assert receipt['complete'] and receipt['retained_intent']
        process.communicate(timeout=2)
        assert process.returncode!=0
        assert database.execute(identity_query(tag)).fetchone()[0]==[]
        database.execute("UPDATE evaluation_jobs SET status='complete' WHERE id=1")
        process,_=start(.5)
        process.communicate(timeout=2)
        assert process.returncode!=0
        assert database.execute(identity_query(tag)).fetchone()[0]==[]
        database.execute('DROP TABLE evaluation_jobs')


def test_unacknowledged_remote_creation_cannot_claim_cleanup(tmp_path,monkeypatch):
    from scripts import production_diagnostic_guard as guard
    from deploy import owned_daemon
    owned_daemon.publish(tmp_path/'intent.json',dict(tag='diagnostic-'+'a'*32,
        started='2026-10-19T00:00:00+00:00',database_id='db'))
    monkeypatch.setattr(guard,'Client',lambda *args:None)
    monkeypatch.setattr(guard,'query',lambda *args:'[]')
    with pytest.raises(RuntimeError,match='Unacknowledged'):
        guard.cleanup_retained(dict(run_id='a'*32,protected_containers=[dict(Name='/mldsafail-private-db-1',Id='db')]),
            tmp_path,time.monotonic()+5)
    assert not (tmp_path/'cleanup.json').exists()
