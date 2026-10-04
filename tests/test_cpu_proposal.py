import pytest
from research.cpu_measurement.harness import collect


def test_authoritative_measurement_fails_closed(tmp_path):
    (tmp_path / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
    (tmp_path / 'cpu.stat').write_text('usage_usec 120\nuser_usec 100\n')
    assert collect(tmp_path, 20) == 100
    (tmp_path / 'cgroup.events').write_text('populated 1\n')
    with pytest.raises(RuntimeError):
        collect(tmp_path, 20)
    (tmp_path / 'cgroup.events').write_text('populated 0\n')
    with pytest.raises(RuntimeError):
        collect(tmp_path, 121)
    (tmp_path / 'cpu.stat').unlink()
    with pytest.raises(FileNotFoundError):
        collect(tmp_path, 20)


def test_host_membership_proof(tmp_path):
    from pathlib import Path
    from research.cpu_measurement.harness import prove_membership
    cgroups = tmp_path / 'cgroups'
    parent = cgroups / 'dedicated'
    parent.mkdir(parents=True)
    proc = tmp_path / 'proc/123'
    proc.mkdir(parents=True)
    (proc / 'cgroup').write_text('0::/dedicated/worker\n')
    prove_membership(123, parent, cgroups, proc.parent)
    (proc / 'cgroup').write_text('0::/unrelated/worker\n')
    with pytest.raises(RuntimeError):
        prove_membership(123, parent, cgroups, proc.parent)


@pytest.mark.parametrize('output,exitcode,expected', [
    (b'{"cpu_seconds":-999,"candidate":null,"verified":true}', 0, 'no_answer'),
    (b'{"cpu_seconds":0,"candidate":{"tag":"forged"},"verified":true}', 0, 'invalid'),
    (b'malformed', 0, 'malformed'),
    (b'', 0, 'malformed'),
    (b'', 1, 'crash'),
    (b'{"candidate":{"tag":"forged"}}', 1, 'invalid'),
])
def test_experimental_worker_ignores_reported_cpu_and_verification(tmp_path, monkeypatch, output, exitcode, expected):
    import json
    from types import SimpleNamespace
    from research.cpu_measurement import harness
    from mldsafail.benchmark_v050.generator import generate_mlwe
    (tmp_path / 'cpu.stat').write_text('usage_usec 20\n')
    (tmp_path / 'cgroup.events').write_text('populated 0\n')
    monkeypatch.setattr(harness.sys, 'platform', 'linux')
    monkeypatch.setattr(harness, 'validate_delegation', lambda *args: None)
    monkeypatch.setattr(harness, 'prove_membership', lambda *args: None)
    monkeypatch.setattr(harness, 'worker_cgroup', lambda *args: tmp_path / 'worker')
    monkeypatch.setattr(harness, 'prove_exclusive', lambda *args: None)
    monkeypatch.setattr(harness.subprocess, 'check_output', lambda *args, **kw: json.dumps(
        {'CgroupVersion': '2', 'SecurityOptions': ['name=rootless']}).encode())
    def command(argv, **kwargs):
        if 'rm' in argv:
            (tmp_path / 'cpu.stat').write_text('usage_usec 1020\n')
        return SimpleNamespace(returncode=0, stdout='{"Pid":123}')
    monkeypatch.setattr(harness.subprocess, 'run', command)
    import subprocess
    real_popen = subprocess.Popen
    monkeypatch.setattr(harness.subprocess, 'Popen', lambda *args, **kw: real_popen(
        [__import__('sys').executable, '-c',
         'import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(' + repr(output) + '); sys.exit(' + str(exitcode) + ')'], **kw))
    result = harness._run('sha256:' + 'a' * 64, tmp_path, 'dedicated', tmp_path,
                          generate_mlwe('small', 0, 1).public.to_dict(), lambda *args: True)
    assert result['authoritative_cpu_usec'] == 1000
    assert not result['verified'] and result['status'] == expected


def test_predeclared_cpu_adoption_gates():
    from research.cpu_measurement.native_suite import measurement_gates
    rows = [dict(fixture=name, repetition=i, authoritative_cpu_usec=cpu, wall_seconds=1.)
            for i in range(30) for name, cpu in [('empty', 200_000), ('child', 500_000)]]
    for index, row in enumerate(rows):
        row.update(schema='mldsafail.cpu-evidence.v1', status='no_answer', cleanup_complete=True,
                   suite_id='suite', source_sha256='source', image='image', host_identity='host',
                   parent_inode=1, parent_device=2, generation=str(index), boot_id='00000000-0000-0000-0000-000000000000',
                   started_monotonic=index * 2., finished_monotonic=index * 2. + 1.,
                   counter_before_usec=0, counter_after_usec=row['authoritative_cpu_usec'])
    assert measurement_gates(rows, audit_records=False)['passed']
    for row in rows:
        if row['fixture'] == 'empty':
            row['authoritative_cpu_usec'] = 100_000 if row['repetition'] % 2 else 300_000
    for row in rows: row['counter_after_usec'] = row['authoritative_cpu_usec']
    assert measurement_gates(rows, audit_records=False)['passed']  # Empty CV is deliberately not a gate.
    rows[1]['authoritative_cpu_usec'] = 2_000_000
    rows[1]['counter_after_usec'] = 2_000_000
    assert not measurement_gates(rows, audit_records=False)['gates']['deterministic_cpu_cv']
    rows[1]['authoritative_cpu_usec'] = 500_000
    rows[1]['counter_after_usec'] = 500_000
    for row in rows:
        if row['fixture'] == 'empty': row['wall_seconds'] = 6.
    assert not measurement_gates(rows, audit_records=False)['gates']['empty_wall_p95']
    with pytest.raises(ValueError, match='30'):
        measurement_gates(rows[:-1], audit_records=False)


def test_durable_generation_fences_interrupted_owner(tmp_path):
    from research.cpu_measurement.ownership import Ownership
    parent = tmp_path / 'parent'
    parent.mkdir()
    journal = tmp_path / 'private'
    with pytest.raises(ValueError):
        with Ownership(journal, parent) as owner:
            owner.mutation('container_create', name='owned-container')
            raise ValueError('injected interruption')
    with pytest.raises(RuntimeError, match='reconciliation'):
        with Ownership(journal, parent):
            pass
    import json
    record = json.loads((journal / 'journal.json').read_text())
    assert record['state'] == 'interrupted'
    assert record['mutations'][0]['name'] == 'owned-container'


def test_ownership_publishes_before_release_and_requires_cleanup(tmp_path):
    import json
    from research.cpu_measurement.ownership import Ownership
    parent = tmp_path / 'parent'
    parent.mkdir()
    with Ownership(tmp_path / 'private', parent) as owner:
        with pytest.raises(RuntimeError, match='cleanup'):
            owner.finish({'cleanup_complete': False})
        evidence = owner.finish({'cleanup_complete': True})
        journal = json.loads((tmp_path / 'private/journal.json').read_text())
        assert journal['state'] == 'complete'
        assert json.loads((tmp_path / 'private' / journal['evidence_file']).read_text()) == evidence
    with Ownership(tmp_path / 'private', parent) as owner:
        owner.finish({'cleanup_complete': True})


def test_stream_capture_caps_flood_and_preserves_crash():
    import subprocess
    import sys
    import time
    from research.cpu_measurement.harness import capture
    process = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(b"x"*1000000)'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        status, raw = capture(process, b'input', time.monotonic() + 5, cap=1024)
        assert status == 'output_limit' and len(raw) <= 1024
    finally:
        process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr): stream.close()


def test_contamination_proof_rejects_sibling_and_direct_members(tmp_path):
    from research.cpu_measurement.harness import prove_exclusive
    worker = tmp_path / 'worker'
    sibling = tmp_path / 'sibling'
    worker.mkdir()
    sibling.mkdir()
    (tmp_path / 'cgroup.procs').write_text('')
    (worker / 'cgroup.procs').write_text('123\n')
    (sibling / 'cgroup.procs').write_text('')
    prove_exclusive(tmp_path, worker)
    (sibling / 'cgroup.procs').write_text('456\n')
    with pytest.raises(RuntimeError, match='Unauthorized'):
        prove_exclusive(tmp_path, worker)


def test_private_supervisor_request_restricts_paths():
    import socket
    from research.cpu_measurement.supervisor import read_request
    server, client = socket.socketpair()
    try:
        client.sendall(b'{"fixture":"../../secrets"}\n')
        with pytest.raises(ValueError, match='approved'):
            read_request(server)
    finally:
        server.close()
        client.close()


def test_independent_audit_rejects_cleanup_and_counter_fabrication():
    from research.cpu_measurement.audit import audit
    record = dict(schema='mldsafail.cpu-evidence.v1', generation='a'*32, boot_id='00000000-0000-0000-0000-000000000000', parent_device=1,
                  parent_inode=2, status='no_answer', execution_status='exited', verified=False, cleanup_complete=True,
                  measurement_method='cgroup-v2-usage-usec', counter_before_usec=20,
                  counter_after_usec=120, authoritative_cpu_usec=100, wall_seconds=1.,
                  binding=dict(source_sha256='a'*64, supervisor_source_sha256='e'*64, source_commit='f'*40, image='sha256:'+'b'*64, epoch='isolated',
                               host='c'*64, kernel='linux', docker={'cgroup_version': '2'}),
                  membership=[{'worker_pid':123, 'cgroup':'/sys/fs/cgroup/owned/worker'}], input_delivery='membership_proven_before_delivery',
                  termination='domain_empty', output_sha256=__import__('hashlib').sha256(b'{"candidate":null}').hexdigest(),
                  raw_stdout_base64=__import__('base64').b64encode(b'{"candidate":null}').decode(),
                  worker_returncode=0, source_artifact='generation-source',
                  accounting_parent='/sys/fs/cgroup/owned', observations=[dict(usage_usec=20, monotonic=1.)],
                  started_monotonic=1., deadline_monotonic=61., declared_timeout_seconds=60,
                  capture=dict(stopped_monotonic=2., overflow=None, cap_bytes=1024*1024, stderr_base64='',
                               stderr_sha256=__import__('hashlib').sha256(b'').hexdigest(),
                               stdout_base64=__import__('base64').b64encode(b'{"candidate":null}').decode()),
                  public_input=__import__('mldsafail.benchmark_v050.generator', fromlist=['generate_mlwe']).generate_mlwe('small',0,1).public.to_dict())
    assert audit(record)['valid']
    record['cleanup_complete'] = False
    with pytest.raises(ValueError, match='Cleanup'):
        audit(record)
    record['cleanup_complete'] = True
    record['authoritative_cpu_usec'] = 1
    with pytest.raises(ValueError, match='delta'):
        audit(record)


def test_cleanup_reconciliation_is_retryable_and_preserves_failure(tmp_path, monkeypatch):
    import json
    from research.cpu_measurement.ownership import Ownership
    from research.cpu_measurement import reconcile
    parent = tmp_path / 'parent'
    parent.mkdir()
    (parent / 'cgroup.events').write_text('populated 0\n')
    (parent / 'cpu.stat').write_text('usage_usec 100\n')
    directory = tmp_path / 'private'
    with pytest.raises(ValueError):
        with Ownership(directory, parent) as owner:
            owner.mutation('container_create_intent', name='cpu-proposal-' + 'a'*32, counter_before_usec=20)
            raise ValueError('injected failure')
    def unavailable(*args, **kwargs):
        raise RuntimeError('daemon unavailable')
    monkeypatch.setattr(reconcile.subprocess, 'check_output', unavailable)
    assert not reconcile.reconcile(directory, parent)['cleanup_complete']
    with pytest.raises(RuntimeError, match='reconciliation'):
        with Ownership(directory, parent): pass
    monkeypatch.setattr(reconcile.subprocess, 'check_output', lambda *args, **kwargs: b'')
    assert reconcile.reconcile(directory, parent)['cleanup_complete']
    assert reconcile.reconcile(directory, parent)['already_complete']
    failures = [json.loads(path.read_text()) for path in directory.glob('*-cleanup-*.json')]
    assert len(failures) == 2 and any(row['errors'] for row in failures)
    with Ownership(directory, parent) as owner:
        owner.finish({'cleanup_complete': True})


def test_closed_output_streams_still_receive_ordinary_timeout():
    import subprocess
    import sys
    import time
    from research.cpu_measurement.harness import capture
    process = subprocess.Popen([sys.executable, '-c', 'import os,time; os.close(1); os.close(2); time.sleep(10)'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    evidence = {}
    deadline = time.monotonic() + .1
    try:
        assert capture(process, b'input', deadline, evidence=evidence)[0] == 'timeout'
        assert evidence['stopped_monotonic'] >= deadline
    finally:
        process.kill()
        process.wait()
        for stream in (process.stdin, process.stdout, process.stderr): stream.close()


def test_parent_lock_serializes_distinct_journal_directories(tmp_path):
    from research.cpu_measurement.ownership import Ownership
    parent = tmp_path / 'parent'
    parent.mkdir()
    with Ownership(tmp_path / 'first', parent) as first:
        with pytest.raises(BlockingIOError):
            with Ownership(tmp_path / 'second', parent): pass
        first.finish({'cleanup_complete': True})


def test_private_supervisor_enforces_total_request_deadline(monkeypatch):
    from research.cpu_measurement import supervisor
    clock = iter((0., .1, .6, 1.1))
    monkeypatch.setattr(supervisor.time, 'monotonic', lambda: next(clock))
    class Dribble:
        def __init__(self): self.timeouts = []
        def settimeout(self, value): self.timeouts.append(value)
        def recv(self, count): return b' '
    connection = Dribble()
    with pytest.raises(TimeoutError, match='Absolute'):
        supervisor.read_request(connection)
    assert connection.timeouts == [.9, .4]


def test_failed_invocation_retains_preexecution_source_and_public_input(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from research.cpu_measurement import harness
    from mldsafail.benchmark_v050.generator import generate_mlwe
    parent = tmp_path / 'accounting'
    parent.mkdir()
    private = tmp_path / 'private'
    source = tmp_path / 'contestant'
    source.mkdir()
    (source / 'solver.py').write_text('def solve(instance): return None\n')
    (source / 'nested').mkdir()
    (source / 'nested/helper.py').write_text('VALUE = 1\n')
    monkeypatch.setattr(harness, 'canonical_directory', lambda _: private)
    original_read = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda path: b'host-identity' if str(path) == '/etc/machine-id' else original_read(path))
    monkeypatch.setattr(harness.subprocess, 'check_output', lambda *args, **kwargs: b'a'*40)
    def interrupted(*args, owner, **kwargs):
        snapshot = args[3]
        assert snapshot.stat().st_mode & 0o777 == 0o755
        assert (snapshot / 'nested').stat().st_mode & 0o777 == 0o755
        intent = owner.record['mutations'][0]
        assert (private / intent['source_artifact']).stat().st_mode & 0o777 == 0o700
        assert intent['operation'] == 'invocation_intent'
        assert (private / intent['source_artifact'] / 'solver.py').read_text() == (source / 'solver.py').read_text()
        raise RuntimeError('Injected failure after durable provenance')
    monkeypatch.setattr(harness, '_run', interrupted)
    public = generate_mlwe('small', 0, 1).public.to_dict()
    import os
    previous_umask = os.umask(0o077)
    try:
        with pytest.raises(RuntimeError, match='durable provenance'):
            harness.run('sha256:'+'b'*64, parent, 'native-slice', source, public, lambda *args: False,
                        ownership_directory=private)
    finally:
        os.umask(previous_umask)
    journal = json.loads((private / 'journal.json').read_text())
    assert journal['state'] == 'interrupted'
    assert journal['mutations'][0]['public_input'] == json.loads(json.dumps(public))
    assert len(list(private.glob('*-interrupted.json'))) == 1


def test_reboot_cleanup_never_signals_reused_host_client_pid(tmp_path, monkeypatch):
    from research.cpu_measurement.ownership import Ownership
    from research.cpu_measurement import reconcile
    parent = tmp_path / 'parent'
    parent.mkdir()
    (parent / 'cgroup.events').write_text('populated 0\n')
    (parent / 'cpu.stat').write_text('usage_usec 1\n')
    directory = tmp_path / 'private'
    with pytest.raises(ValueError):
        with Ownership(directory, parent) as owner:
            owner.mutation('host_client_spawned', pid=123, start_ticks=1, uid=1, cmdline_sha256='a'*64)
            raise ValueError('interrupted')
    monkeypatch.setattr(reconcile, 'boot_id', lambda: 'different-boot')
    def forbidden(*args): raise AssertionError('Rebooted host client PID must never be signaled')
    monkeypatch.setattr(reconcile.os, 'pidfd_open', forbidden, raising=False)
    receipt = reconcile.reconcile(directory, parent)
    assert receipt['cleanup_complete'] and receipt['changed_boot']
