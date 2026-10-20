"""Real concurrency on an explicit disposable loopback database; no VPS access."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
import time

import pytest

from deploy import maintenance_fence as control

CEILINGS = dict(stop=1, create=2, audit=1, inspection=1, cleanup=1, restoration=1, margin=1)


def test_prepare_is_offline_and_budgeted(tmp_path):
    for lifetime in (0, 9, 9001, True):
        with pytest.raises(RuntimeError):
            control.prepare(tmp_path/'invalid', database={'name': 'test'}, container='local',
                            lifetime=lifetime, ceilings=CEILINGS)
    root = tmp_path/'control'
    intent = control.prepare(root, database={'name': 'test'}, container='local', lifetime=12, ceilings=CEILINGS)
    assert intent['state'] == 'prepared'
    assert set(p.name for p in root.iterdir()) == {'intent.json'}
    assert root.stat().st_mode & 0o777 == 0o700
    assert (root/'intent.json').stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        control.prepare(root, database={'name': 'test'}, container='local', lifetime=12, ceilings=CEILINGS)


@pytest.fixture
def database():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    url = os.environ.get('MLDSAFAIL_MAINTENANCE_TEST_POSTGRES')
    if not url:
        pytest.skip('explicit disposable loopback PostgreSQL required')
    parsed = conninfo_to_dict(url)
    if parsed.get('host') != '127.0.0.1' or parsed.get('dbname') != 'maintenance_fence_test':
        pytest.fail('dedicated loopback maintenance_fence_test required')
    def connect():
        return psycopg.connect(url, autocommit=True, connect_timeout=2)
    from sqlalchemy import create_engine, inspect
    from mldsafail.web.models import Base
    engine = create_engine(url.replace('postgresql://', 'postgresql+psycopg://'))
    assert not inspect(engine).get_table_names(), 'test database must initially be empty'
    Base.metadata.create_all(engine)
    try:
        yield connect, engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def make_fence(tmp_path, connect, **kwargs):
    with connect() as connection:
        identity = control.database_identity(connection)
    root = tmp_path/'fence'
    control.prepare(root, database=identity, container='local-fixture', lifetime=kwargs.get('lifetime', 12), ceilings=CEILINGS)
    return control.Fence(root, connect, lambda: 'local-fixture')


def wait_failed(fence):
    assert fence.failed.wait(2)
    with pytest.raises(RuntimeError):
        fence.verify()


def test_real_share_lock_blocks_uncooperative_writes_and_select_for_update(database, tmp_path):
    import psycopg
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    try:
        with connect() as connection:
            assert connection.execute('SELECT count(*) FROM evaluation_jobs').fetchone() == (0,)
            connection.execute("SET lock_timeout='100ms'")
            # These do not acquire the advisory mutex. SELECT FOR UPDATE obtains
            # RowShareLock, but an UPDATE/INSERT needs conflicting RowExclusive.
            connection.execute('SELECT * FROM evaluation_jobs FOR UPDATE SKIP LOCKED')
            with pytest.raises(psycopg.errors.LockNotAvailable):
                connection.execute("UPDATE evaluation_jobs SET status='claimed'")
            assert control.locks(connection, fence.backend[0])
        fence.verify()
    finally:
        fence.release()
    assert json.loads((fence.root/'state.json').read_text())['client_terminated']


@pytest.mark.parametrize('status', ['queued', 'claimed', 'running'])
def test_pending_rejected_without_mutation(database, tmp_path, status):
    connect, engine = database
    from sqlalchemy.orm import Session
    from mldsafail.web.models import User, Submission, EvaluationJob
    with Session(engine) as session:
        user = User(display_name='synthetic'); session.add(user); session.flush()
        submission = Submission(user_id=user.id, repository_url='https://github.com/example/test',
                                commit_sha='a'*40, hypothesis='synthetic', benchmark_version='0.5.0', state='queued')
        session.add(submission); session.flush()
        session.add(EvaluationJob(submission_id=submission.id, status=status)); session.commit()
    fence = make_fence(tmp_path, connect)
    with pytest.raises(RuntimeError):
        fence.acquire()
    fence.release()
    with connect() as connection:
        assert connection.execute('SELECT status FROM evaluation_jobs').fetchall() == [(status,)]


def test_contention_is_bounded_and_not_retried(database, tmp_path):
    connect, _ = database
    with connect() as blocker:
        blocker.execute('BEGIN')
        blocker.execute('SELECT pg_advisory_xact_lock(%s)', (control.KEY,))
        fence = make_fence(tmp_path, connect)
        started = time.monotonic()
        with pytest.raises(RuntimeError): fence.acquire()
        assert time.monotonic() - started < 3.5
        blocker.execute('ROLLBACK')
    fence.release()
    with pytest.raises(RuntimeError, match='reconciliation'): fence.acquire()


@pytest.mark.parametrize('loss', ['disconnect', 'identity', 'expiry', 'verification_timeout'])
def test_loss_aborts_running_phase_and_blocks_next(database, tmp_path, loss):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    terminated = threading.Event()
    try:
        with pytest.raises((RuntimeError, Exception)):
            with fence.phase('create', terminated.set):
                if loss == 'disconnect':
                    with connect() as connection:
                        connection.execute('SELECT pg_terminate_backend(%s)', (fence.backend[0],))
                elif loss == 'identity':
                    fence.identity = lambda: 'replacement'
                elif loss == 'expiry':
                    fence.deadline = time.monotonic() - 1
                else:
                    fence.verifier.close()
                assert terminated.wait(2)
                fence.verify()
        assert terminated.is_set()
        with pytest.raises(RuntimeError):
            with fence.phase('audit', lambda: None): pytest.fail('continued after loss')
    finally:
        fence.identity = lambda: 'local-fixture'
        fence.release()


def test_lost_ack_reconciliation_cannot_resume_or_reacquire(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    # Authority persists even if held-state publication/acknowledgement is lost.
    (fence.root/'state.json').unlink()
    assert control.reconcile(fence.root, connect, lambda: 'local-fixture')
    wait_failed(fence)
    fence.release()
    receipt = json.loads((fence.root/'reconciled.json').read_text())
    assert receipt['scheduling_restored'] is False
    with pytest.raises(RuntimeError): fence.acquire()


def test_backend_birth_change_refuses_termination(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    path = fence.root/'authority.json'
    original = path.read_text()
    changed = json.loads(original); changed['backend'][1] = '2000-01-01 00:00:00+00'
    path.write_text(json.dumps(changed))
    try:
        with pytest.raises(RuntimeError, match='backend_changed'):
            control.reconcile(fence.root, connect, lambda: 'local-fixture')
        fence.verify()
    finally:
        path.write_text(original)
        fence.release()


def test_phase_stop_failure_and_interrupted_restoration_never_restore(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    terminated = []
    try:
        with pytest.raises(OSError):
            with fence.phase('stop', lambda: terminated.append(True)):
                raise OSError('coordinator did not stop')
        assert terminated
        with pytest.raises(RuntimeError):
            with fence.phase('restoration', lambda: None): pytest.fail('automatic restoration')
    finally:
        fence.release()


def test_epoch_mutators_refuse_without_live_binding(tmp_path):
    from scripts import production_epoch_operation as operation
    packet = tmp_path/'packet.json'
    tmp_path.chmod(0o700)
    packet.write_text(json.dumps(dict(operation_id='a'*32, candidate='candidate', staging='staging',
        receipt='receipt', manifest='manifest', maintenance='maintenance')))
    packet.chmod(0o600)
    for action, args in ((operation.execute, (None,)), (operation.audit, ()), (operation.finalize, (None,))):
        with pytest.raises(ValueError, match='live_maintenance_fence_required'):
            action(packet, *args)


@pytest.mark.parametrize('implementation', ['current', 'retained'])
@pytest.mark.parametrize('action', ['admission', 'claim', 'recovery', 'heartbeat'])
def test_actual_application_paths_table_lock_compatibility(database, implementation, action):
    """Isolate SHARE compatibility, with no advisory lock to mask old behavior.

    Synthetic pending rows are used only in this compatibility test, not acquired
    by the zero-pending maintenance control. Read-only empty paths may proceed.
    """
    import hashlib
    import types
    import psycopg
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session
    from mldsafail.web import services
    from mldsafail.evaluator import queue
    from mldsafail.web.models import User, Submission, EvaluationJob, utcnow
    from datetime import timedelta
    if implementation == 'retained':
        root = Path('tests/fixtures/retained_maintenance')
        manifest = json.loads((root/'manifest.json').read_text())
        modules = {}
        for name in ('services', 'queue'):
            data = (root/(name+'.py')).read_bytes()
            assert hashlib.sha256(data).hexdigest() == manifest[name+'.py']['sha256']
            module = types.ModuleType('retained_' + name)
            exec(compile(data, str(root/(name+'.py')), 'exec'), module.__dict__)
            modules[name] = module
        services, queue = modules['services'], modules['queue']
        queue.transition_submission = services.transition_submission
    connect, engine = database
    with Session(engine) as session:
        user = User(display_name='synthetic'); session.add(user); session.flush()
        submission = Submission(user_id=user.id, repository_url='https://github.com/example/test',
            commit_sha='a'*40, hypothesis='compatibility', benchmark_version='0.5.0',
            state='queued' if action == 'claim' else 'validating')
        session.add(submission); session.flush()
        job = EvaluationJob(submission_id=submission.id, status='queued' if action == 'claim' else 'running',
            lease_owner='owner', lease_expires_at=utcnow()-timedelta(seconds=10), attempts=1)
        session.add(job); session.commit()
        user_id, job_id = user.id, job.id
    with connect() as holder:
        holder.execute('BEGIN'); holder.execute('LOCK TABLE evaluation_jobs IN SHARE MODE')
        with Session(engine) as session:
            session.execute(text("SET LOCAL lock_timeout='100ms'"))
            with pytest.raises(OperationalError) as error:
                if action == 'admission':
                    services.create_submission(session, session.get(User, user_id),
                        dict(repository_url='https://github.com/example/test', commit_sha='b'*40,
                             hypothesis='synthetic', benchmark_version='0.5.0'), 'new',
                        cohort=dict(epoch_id='synthetic', evaluator_fingerprint='synthetic',
                                    hidden_suite_version='synthetic', worker_class='synthetic'))
                elif action == 'claim':
                    queue.claim_job(session, 'claimant')
                elif action == 'recovery':
                    queue.recover_stale_jobs(session)
                else:
                    queue.heartbeat(session, job_id, 'owner')
            assert isinstance(error.value.orig, psycopg.errors.LockNotAvailable)
            session.rollback()
        holder.execute('ROLLBACK')
    with Session(engine) as session:
        job = session.get(EvaluationJob, job_id)
        assert job.status == ('queued' if action == 'claim' else 'running')


def test_server_lifetime_expires_without_client_cleanup(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect, lifetime=10).acquire()
    try:
        # No cancellation: PostgreSQL's statement timer must end the holder.
        assert fence.failed.wait(12)
        fence.holder.join(timeout=2)
        assert not fence.holder.is_alive()
        assert fence.holder_error == 'QueryCanceled'
        with connect() as connection:
            assert control.backends(connection, fence.intent['tag']) == []
            assert not control.locks(connection, fence.backend[0])
    finally:
        fence.release()


def test_unknown_acquisition_remains_unresolved(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect)
    with pytest.raises(RuntimeError, match='unacknowledged'):
        control.reconcile(fence.root, connect, lambda: 'local-fixture')
    assert not (fence.root/'reconciled.json').exists()


def bound_packet(tmp_path, fence):
    packet = dict(operation_id='b'*32, candidate='candidate', staging='staging', receipt='receipt',
                  manifest='manifest', maintenance='maintenance', operation=str(tmp_path/'operation'),
                  maintenance_fence_tag=fence.intent['tag'], maintenance_database_identity=fence.intent['database'],
                  maintenance_database_container=fence.intent['container'])
    path = tmp_path/'packet.json'; path.write_text(json.dumps(packet)); path.chmod(0o600)
    return path, packet


def test_loss_before_directory_creation_prevents_launch(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    path, packet = bound_packet(tmp_path, fence)
    launches = []
    @control.operation_phase('create')
    def operation(path):
        fence.failed.set()  # Loss during validation, before output creation.
        time.sleep(.2)
        Path(packet['operation']).mkdir()
        control.launch_operation(packet, lambda: launches.append(True))
    try:
        with control.bind_operation(fence, packet):
            with pytest.raises(RuntimeError): operation(path)
        assert not launches
    finally:
        # No resource was launched. Do not claim a controller existed for the
        # epoch-specific terminate_owned positive-observation requirement.
        if fence.cleanup_error:
            fence.cleanup_error = None  # fixture-only reconciled empty launch log
        fence.release()


def test_loss_during_launch_terminates_client_and_owned_resources(database, tmp_path, monkeypatch):
    from scripts import production_epoch_operation as operation
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    path, packet = bound_packet(tmp_path, fence)
    entered, finish = threading.Event(), threading.Event()
    stopped = []
    def terminate(packet):
        stopped.append('resources')
        return {'verified_stopped': True}
    monkeypatch.setattr(operation, 'terminate_owned', terminate)
    class Client:
        returncode = None
        def poll(self): return self.returncode
        def terminate(self): self.returncode = -15; stopped.append('client')
        def wait(self, timeout): return self.returncode
    client = Client()
    def spawn():
        entered.set()
        # Watchdog observes failure while an in-flight request holds the lock.
        fence.failed.set()
        time.sleep(.2)
        return client
    @control.operation_phase('create')
    def run(path):
        Path(packet['operation']).mkdir()
        control.launch_operation(packet, spawn)
    try:
        with control.bind_operation(fence, packet):
            with pytest.raises(RuntimeError): run(path)
        assert entered.is_set()
        assert stopped == ['client', 'resources']
    finally:
        fence.release()


def test_hung_cleanup_is_bounded_and_release_stays_blocked(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    unblock = threading.Event()
    try:
        started = time.monotonic()
        with pytest.raises(RuntimeError, match='cleanup_reconciliation'):
            with fence.phase('create', lambda: unblock.wait(10)):
                raise OSError('ambiguous partial launch')
        assert time.monotonic() - started < 2
        with pytest.raises(RuntimeError, match='cleanup_reconciliation'): fence.release()
    finally:
        unblock.set()
        assert fence.abort_done.wait(2)
        # Explicit test-only external reconciliation of the fake no-resource
        # callback; production reconciliation must prove actual quiescence.
        fence.cleanup_error = None
        fence.release()


def test_blackholed_verification_fails_without_waiting_for_io(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    unblock, terminated = threading.Event(), threading.Event()
    try:
        with pytest.raises(RuntimeError):
            with fence.phase('create', terminated.set):
                fence.identity = lambda: (unblock.wait(10) and 'local-fixture')
                assert terminated.wait(2)
        assert fence.failed.is_set()
    finally:
        unblock.set()
        fence.identity = lambda: 'local-fixture'
        for thread in fence.io_threads: thread.join(timeout=2)
        fence.release()


def test_release_requires_positive_operation_resource_termination(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    class Client:
        def poll(self): return 0
    try:
        with fence.phase('create', lambda: None):
            fence.launch(Client)
        with pytest.raises(RuntimeError, match='operation_cleanup_required'): fence.release()
        with pytest.raises(RuntimeError, match='not_verified_stopped'):
            fence.resources_stopped(lambda: False)
        fence.resources_stopped(lambda: True)
    finally:
        fence.release()


def test_partial_launch_without_acknowledgement_requires_reconciliation(database, tmp_path):
    connect, _ = database
    fence = make_fence(tmp_path, connect).acquire()
    def unknown_cleanup():
        raise RuntimeError('no positive daemon acknowledgement')
    try:
        with pytest.raises(RuntimeError, match='cleanup_reconciliation'):
            with fence.phase('create', unknown_cleanup):
                def spawn(): raise OSError('request may have reached daemon')
                fence.launch(spawn)
        with pytest.raises(RuntimeError, match='operation_cleanup_required'): fence.release()
        assert not (fence.root/'reconciled.json').exists()
    finally:
        fence.resources_stopped(lambda: True)  # fixture-only: no daemon exists
        fence.cleanup_error = None
        fence.release()


def test_completed_verification_readers_do_not_accumulate():
    fence=object.__new__(control.Fence)
    fence.io_threads=[]
    fence.io_registry_lock=threading.Lock()
    gate=threading.Event()
    unresolved=threading.Thread(target=gate.wait,daemon=True)
    fence._start_io(unresolved)
    try:
        for _ in range(50):
            thread=threading.Thread(target=lambda:None)
            fence._start_io(thread)
            thread.join(timeout=1)
        assert unresolved in fence.io_threads and len(fence.io_threads)<=2
    finally:
        gate.set();unresolved.join(timeout=1)
