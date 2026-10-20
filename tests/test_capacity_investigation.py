import io
import json
from pathlib import Path

import pytest

from deploy.capacity_sampler import Sampler, receipt, counters
from deploy.maintenance_transport import encode, serve, MAX_MESSAGE
from deploy.maintenance_supervisor import Supervisor


def fixture(tmp_path):
    root = tmp_path / 'cgroup'
    operation, retained = root / 'operation', root / 'retained'
    proc = tmp_path / 'proc'
    (proc / 'sys/kernel/random').mkdir(parents=True)
    (proc / 'sys/kernel/random/boot_id').write_text('boot')
    (proc / 'meminfo').write_text('MemAvailable: 4000000 kB\nMemTotal: 8000000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n')
    for path in (root, operation, retained):
        path.mkdir(exist_ok=True)
        for name in ('memory.max', 'memory.high', 'memory.swap.max', 'pids.max'):
            (path / name).write_text('max')
        (path / 'cpu.max').write_text('100000 100000')
        for name in ('memory.current', 'memory.peak', 'memory.swap.current', 'pids.current'):
            (path / name).write_text('0')
        (path / 'memory.events').write_text('oom 0\noom_kill 0\n')
        (path / 'memory.swap.events').write_text('max 0\nfail 0\n')
        (path / 'cpu.stat').write_text('usage_usec 0\n')
        (path / 'io.stat').write_text('8:0 rbytes=0 wbytes=0\n')
    identities = {}
    for pid, path in enumerate((operation, retained), start=100):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / 'stat').write_text(str(pid) + ' (test) ' + ' '.join(['S'] + ['0'] * 18 + ['123']))
        (proc / str(pid) / 'cgroup').write_text('0::/' + path.name + '\n')
        identities[str(path)] = dict(pid=pid, start_ticks=123, container_id='a' * 64)
    sampler = Sampler(dict(operation_resources=[operation], retained_services_excluding_operation=[retained]),
                      identities, tmp_path, cgroup=root, proc=proc)
    return sampler, operation, retained, proc


def test_capture_identity_and_ancestors(tmp_path):
    sampler, operation, retained, proc = fixture(tmp_path)
    row = sampler.sample('setup', now=1)
    assert len(row['ancestors']) == 3
    assert row['boot_id'] == 'boot'
    assert counters('8:0 rbytes=3 wbytes=4') == {'8:0:rbytes': 3, '8:0:wbytes': 4}
    sampler.sample('create', now=250000001)


@pytest.mark.parametrize('failure', ['gap', 'reset', 'ancestor', 'swap', 'oom', 'pid', 'membership', 'boot', 'missing'])
def test_rejects_incomplete_or_changed_evidence(tmp_path, failure):
    sampler, operation, retained, proc = fixture(tmp_path)
    (operation / 'cpu.stat').write_text('usage_usec 2\n')
    sampler.sample('setup', now=1)
    now = 250000001
    if failure == 'gap': now = 1000000002
    if failure == 'reset': (operation / 'cpu.stat').write_text('usage_usec 1\n')
    if failure == 'ancestor': (operation / 'cpu.max').write_text('max 100000')
    if failure == 'swap': (operation / 'memory.swap.current').write_text('1')
    if failure == 'oom': (operation / 'memory.events').write_text('oom 1\noom_kill 0\n')
    if failure == 'pid': (proc / '100/stat').write_text('100 (test) ' + ' '.join(['S'] + ['0'] * 18 + ['456']))
    if failure == 'membership': (proc / '100/cgroup').write_text('0::/elsewhere\n')
    if failure == 'boot': (proc / 'sys/kernel/random/boot_id').write_text('changed')
    if failure == 'missing': (operation / 'io.stat').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        sampler.sample('create', now=now)


def test_overlap(tmp_path):
    sampler, operation, retained, proc = fixture(tmp_path)
    with pytest.raises(ValueError, match='overlapping'):
        Sampler(dict(operation_resources=[operation], retained_services_excluding_operation=[operation]),
                sampler.identities, tmp_path, cgroup=operation.parent, proc=proc)


def test_receipt_never_certifies_incomplete_evidence(tmp_path):
    path = tmp_path / 'samples'
    path.write_text(json.dumps(dict(phase='setup', monotonic_ns=1)) + '\n')
    with pytest.raises(ValueError, match='coverage'):
        receipt(path, expected_phases=['setup', 'audit'], compatibility={})
    result = receipt(path, expected_phases=['setup'], compatibility={})
    assert result['capacity'] == 'unresolved' and result['source_compatible'] is False


def test_transport_limits_and_redaction():
    with pytest.raises(ValueError): encode({'x': 'a' * MAX_MESSAGE})
    class DB:
        def execute(self, *args): raise ValueError('secret password')
        def close(self): pass
    stream = io.BytesIO()
    request = encode(dict(version=1, request='r', sql='secret', params=[]))
    serve(io.BytesIO(b'{"password":"secret"}\n' + request), stream, lambda credentials: DB())
    assert b'secret' not in stream.getvalue()
    assert json.loads(stream.getvalue())['error'] == 'query_failed'


def test_supervisor_rejects_wrong_purpose_and_resume(tmp_path):
    supervisor = Supervisor(tmp_path, None, dict(state='maintenance_proposal'), {})
    with pytest.raises(ValueError): supervisor.run(dict(purpose='capacity_investigation', state='execution_ready'))
    assert not (tmp_path / 'supervisor.json').exists()
    (tmp_path / 'supervisor.json').write_text('{}')
    with pytest.raises(RuntimeError): Supervisor(tmp_path, None, {}, {})


def test_transport_roundtrip_and_blackhole():
    import subprocess
    import sys
    from deploy.maintenance_transport import Connection
    code = '''import sys,json
for line in sys.stdin.buffer:
 v=json.loads(line); print(json.dumps(dict(version=1,request=v['request'],rows=[[True]])),flush=True)
'''
    process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    connection = Connection(process, lambda: 'same', 'same')
    try:
        assert connection.execute('SELECT true').fetchone() == (True,)
    finally:
        connection.close()
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    connection = Connection(process, lambda: 'same', 'same', timeout=.05)
    try:
        with pytest.raises(RuntimeError, match='reconciliation'):
            connection.execute('SELECT true')
    finally:
        connection.close()
    assert process.poll() is not None


def test_supervisor_cleanup_after_ownership_loss(tmp_path):
    class Fence:
        def acquire(self): pass
        def verify(self): raise RuntimeError('lost')
    stopped = []
    actions = dict(terminate=lambda: stopped.append(True) or True, resources_stopped=lambda: True)
    supervisor = Supervisor(tmp_path, Fence(), dict(operation_id='o', state='execution_ready'), actions)
    with pytest.raises(RuntimeError, match='lost'):
        supervisor.run(dict(purpose='production_maintenance', state='execution_ready'))
    assert stopped == [True]
    state = json.loads((tmp_path / 'supervisor.json').read_text())
    assert state['phase'] == 'reconciliation_required' and state['resources_stopped'] is True
    assert state['scheduling_restored'] is False


def test_investigation_authorization_cannot_reuse_production():
    from deploy.capacity_investigation import admission, worker_wrapper
    for purpose in ('production_epoch_only', 'production_maintenance', 'capacity_investigation_only'):
        with pytest.raises(ValueError):
            admission(dict(state='maintenance_proposal'), dict(purpose=purpose))
    wrapper = worker_wrapper('a' * 32, 'isolated.slice', 'sha256:' + 'b' * 64)
    compile(wrapper, 'docker', 'exec')
    assert 'org.mldsafail.capacity-investigation=' in wrapper


def test_packet_relocation_and_tamper(tmp_path):
    import os
    import shutil
    from scripts.prepare_capacity_packet import build, validate
    from deploy.production_preparation import IMAGES
    prior = tmp_path / 'v8'
    prior.mkdir(mode=0o700)
    protocol = dict(commands=[], operation_id='a' * 32, operation='/opt/old', epoch='/srv/old/epoch',
                    source='s', controller=dict(index='sha256:' + IMAGES['COORDINATOR_IMAGE']),
                    worker=dict(index='sha256:' + IMAGES['WORKER_IMAGE']), ceilings={})
    for name, value in (('capacity-protocol.json', protocol), ('transfer-dependencies.json', {}), ('scheduling-semantic-review.json', {})):
        path = prior / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
    dest = build(prior, tmp_path / 'v9')
    moved = tmp_path / 'relocated'
    shutil.copytree(dest, moved)
    assert validate(moved)['executable'] is False
    (moved / 'packet.json').write_text('{}')
    with pytest.raises(ValueError, match='hash'):
        validate(moved)
