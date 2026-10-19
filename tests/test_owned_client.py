import importlib.util
from pathlib import Path
import subprocess
import pytest

spec = importlib.util.spec_from_file_location('owned_client', Path(__file__).parents[1] / 'deploy/owned_client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


def test_domain_replacement_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    domain = tmp_path / 'client'; domain.mkdir()
    entry = {'cgroup': client.domain_identity(domain)}
    entry['cgroup']['inode'] += 1
    with pytest.raises(RuntimeError, match='identity mismatch'):
        client.stop(entry)


def test_prior_boot_does_not_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'new')
    domain = tmp_path / 'client'; domain.mkdir()
    entry = {'cgroup': {**client.domain_identity(domain), 'boot_id': 'old'}}
    client.stop(entry)
    assert domain.exists()
    assert not (domain / 'cgroup.kill').exists()


def test_delegation_required_before_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(client.sys, 'platform', 'linux')
    monkeypatch.delenv('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT', raising=False)
    monkeypatch.setattr(client.subprocess, 'Popen', lambda *a, **kw: pytest.fail('spawned'))
    with pytest.raises(RuntimeError, match='delegated'):
        client.run(['true'], [], lambda: None, tmp_path, timeout=1)


def test_cgroup_symlink_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    real = tmp_path / 'real'; real.mkdir()
    link = tmp_path / 'link'; link.symlink_to(real)
    with pytest.raises(RuntimeError, match='canonical'):
        client.domain_identity(link)


def test_full_bounded_output_sink(tmp_path):
    data = b'x' * (2 * 1024 * 1024)
    path = tmp_path / 'out'
    with path.open('wb') as stream:
        client.write_stream(stream, data)
    assert path.read_bytes() == data


def test_empty_domain_cleanup_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    domain = tmp_path / 'client'; domain.mkdir()
    (domain / 'cgroup.kill').write_text('')
    (domain / 'cgroup.events').write_text('populated 0\n')
    entry = {'cgroup': client.domain_identity(domain)}
    # Real cgroup pseudo-files disappear with rmdir; emulate that final operation.
    original = Path.rmdir
    def remove(path):
        if path == domain:
            for child in path.iterdir(): child.unlink()
        original(path)
    monkeypatch.setattr(Path, 'rmdir', remove)
    client.stop(entry); client.stop(entry)
    assert not domain.exists()


@pytest.fixture
def emulated_domain(tmp_path, monkeypatch):
    """Filesystem emulation verifies gate ordering; never native cgroup evidence."""
    monkeypatch.setattr(client.sys, 'platform', 'linux')
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    monkeypatch.setattr(client, 'prepare_domain', lambda entry, parent: tmp_path / entry['id'])
    monkeypatch.setattr(client, 'identity', lambda pid: dict(pid=pid, start_ticks=1, uid=1,
        session=pid, group=pid, boot_id='boot', cmdline_sha256='bootstrap'))
    mkdir = Path.mkdir
    rmdir = Path.rmdir
    def create(path, *args, **kwargs):
        mkdir(path, *args, **kwargs)
        if path.parent == tmp_path:
            for name, content in [('cgroup.procs', ''), ('cgroup.events', 'populated 0\n'), ('cgroup.kill', '')]:
                (path / name).write_text(content)
    def remove(path):
        if path.parent == tmp_path:
            for child in path.iterdir(): child.unlink()
        rmdir(path)
    monkeypatch.setattr(Path, 'mkdir', create)
    monkeypatch.setattr(Path, 'rmdir', remove)
    return tmp_path


def test_failed_acknowledgement_never_releases_mutation(emulated_domain):
    marker = emulated_domain / 'mutation'
    entries = []
    def save():
        if entries and entries[0].get('pid'):
            raise ValueError('ack failure')
    with pytest.raises(ValueError, match='ack failure'):
        client.run([client.sys.executable, '-c', 'from pathlib import Path;Path(__import__("sys").argv[1]).touch()', marker],
                   entries, save, emulated_domain, timeout=2)
    assert not marker.exists()
    assert entries[0]['finished']


def test_input_cwd_and_full_success_output(emulated_domain):
    import io
    output = io.BytesIO()
    entries = []
    client.run([client.sys.executable, '-c', 'import os,sys;assert os.getcwd()==sys.argv[1];assert sys.stdin.buffer.read()==b"input";sys.stdout.buffer.write(b"x"*(2*1024*1024))', emulated_domain],
               entries, lambda: None, emulated_domain, timeout=5, input=b'input', cwd=emulated_domain, stdout=output)
    assert len(output.getvalue()) == 2 * 1024 * 1024
    assert entries[0]['finished']


def test_cleanup_log_errors_do_not_replace_original_or_skip_save(emulated_domain, monkeypatch):
    entries = []; saved = []
    def fail_capture(process, payload, timeout, buffers, observe):
        buffers['stdout'].extend(b'partial stdout')
        buffers['stderr'].extend(b'partial stderr')
        raise ValueError('original execution failure')
    monkeypatch.setattr(client, 'capture', fail_capture)
    original_open = Path.open
    def fail_stdout_log(path, *args, **kwargs):
        if path.name.endswith('-stdout.log'):
            raise OSError('injected log failure')
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_stdout_log)
    with pytest.raises(ValueError, match='original execution failure'):
        client.run([client.sys.executable, '-c', 'import time;time.sleep(10)'], entries,
                   lambda: saved.append(bool(entries[0].get('cleanup_errors'))), emulated_domain, timeout=2)
    assert saved[-1]
    assert list(emulated_domain.glob('*-stderr.log'))[0].read_bytes() == b'partial stderr'
    assert entries[0]['cleanup_errors'][0]['step'] == 'stdout_failure_log'


def test_wait_and_final_save_failures_keep_logs_and_original(emulated_domain, monkeypatch):
    entries = []; final_save_attempts = []
    original_popen = subprocess.Popen
    def spawn(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        process.wait = lambda **kw: (_ for _ in ()).throw(TimeoutError('injected wait failure'))
        return process
    def fail_capture(process, payload, timeout, buffers, observe):
        buffers['stderr'].extend(b'failure details')
        raise ValueError('original failure')
    def save():
        if entries[0].get('cleanup_errors'):
            final_save_attempts.append(True)
            raise OSError('injected final save failure')
    monkeypatch.setattr(client.subprocess, 'Popen', spawn)
    monkeypatch.setattr(client, 'capture', fail_capture)
    with pytest.raises(ValueError, match='original failure') as raised:
        client.run([client.sys.executable, '-c', 'import time;time.sleep(10)'], entries, save,
                   emulated_domain, timeout=1)
    assert final_save_attempts
    assert list(emulated_domain.glob('*-stderr.log'))[0].read_bytes() == b'failure details'
    assert {'client_wait', 'final_ownership_save'} <= {row['step'] for row in entries[0]['cleanup_errors']}
    assert 'Independent' in raised.value.__notes__[0]


def test_large_input_file_is_streamed(emulated_domain):
    data = emulated_domain / 'input'; data.write_bytes(b'x' * (2 * 1024 * 1024))
    with data.open('rb') as stream:
        result = client.run([client.sys.executable, '-c', 'import sys;print(len(sys.stdin.buffer.read()))'],
                            [], lambda: None, emulated_domain, timeout=5, stdin=stream, text=True)
    assert result.stdout.strip() == str(2 * 1024 * 1024)


@pytest.mark.parametrize('mode,kind,error', [(0o777, 'domain', 'exclusive owner'), (0o700, 'threaded', 'must be a domain')])
def test_delegated_parent_writer_and_domain_guards(tmp_path, monkeypatch, mode, kind, error):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    tmp_path.chmod(mode)
    (tmp_path / 'cgroup.type').write_text(kind)
    with pytest.raises(RuntimeError, match=error):
        client.prepare_domain({'id': 'owned'}, tmp_path)


def test_closed_child_stdin_stops_file_reads(emulated_domain):
    class Source:
        reads = 0
        def read(self, size):
            self.reads += 1
            if self.reads > 5:
                raise AssertionError('Input drained after closed child pipe')
            return b'x' * size
    source = Source()
    result = client.run([client.sys.executable, '-c', 'import sys;sys.stdin.close()'], [],
                        lambda: None, emulated_domain, timeout=5, stdin=source)
    assert result.returncode == 0
    assert source.reads <= 5


def test_concurrent_exact_empty_domain_removal_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    domain = tmp_path / 'client'; domain.mkdir()
    (domain / 'cgroup.kill').write_text('')
    entry = {'cgroup': client.domain_identity(domain)}
    def concurrent_remove(path):
        (path / 'cgroup.kill').unlink(); path.rmdir()
        raise FileNotFoundError('concurrent kernel domain removal')
    monkeypatch.setattr(client, 'populated', concurrent_remove)
    client.stop(entry)
    assert not domain.exists()


def test_missing_control_file_in_existing_domain_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    domain = tmp_path / 'client'; domain.mkdir()
    entry = {'cgroup': client.domain_identity(domain)}
    with pytest.raises(FileNotFoundError):
        client.stop(entry)


def test_inherited_group_writable_child_secured_before_spawn(emulated_domain, monkeypatch):
    create = Path.mkdir
    def inherited(path, *args, **kwargs):
        create(path, *args, **kwargs)
        path.chmod(0o775)
    monkeypatch.setattr(Path, 'mkdir', inherited)
    spawn = client.subprocess.Popen
    entries = []
    def admitted(*args, **kwargs):
        domain = Path(entries[0]['cgroup']['path'])
        assert domain.stat().st_mode & 0o777 == 0o700
        assert entries[0]['cgroup']['mode'] == 0o700
        return spawn(*args, **kwargs)
    monkeypatch.setattr(client.subprocess, 'Popen', admitted)
    assert client.run(['true'], entries, lambda: None, emulated_domain, timeout=5).returncode == 0
    assert not Path(entries[0]['cgroup']['path']).exists()


def test_chmod_failure_retains_birth_and_never_spawns(emulated_domain, monkeypatch):
    monkeypatch.setattr(client.os, 'fchmod', lambda *args: (_ for _ in ()).throw(PermissionError('injected chmod')))
    monkeypatch.setattr(client.subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('admitted before permissions'))
    entries = []
    with pytest.raises(PermissionError, match='chmod'):
        client.run(['true'], entries, lambda: None, emulated_domain, timeout=1)
    assert entries[0]['pid'] is None
    assert entries[0]['cgroup']['uid'] == client.os.getuid()
    assert not Path(entries[0]['cgroup']['path']).exists()


def test_permission_setup_refuses_preexisting_populated_domain(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'boot_id', lambda: 'boot')
    domain = tmp_path / 'new'; domain.mkdir(mode=0o775)
    for name, content in [('cgroup.procs', '123\n'), ('cgroup.events', 'populated 1\n'), ('cgroup.kill', '')]:
        (domain / name).write_text(content)
    entry = {}
    with pytest.raises(RuntimeError, match='empty before admission'):
        client.secure_created_domain(entry, domain)
    assert entry['cgroup']['mode'] == 0o700


def test_cancelled_client_cannot_create_domain_or_spawn(tmp_path, monkeypatch):
    import threading
    cancelled = threading.Event(); cancelled.set()
    monkeypatch.setattr(client, 'prepare_domain', lambda *a: pytest.fail('Created domain after cancellation'))
    entries = []
    with pytest.raises(RuntimeError, match='cancelled'):
        client.run(['true'], entries, lambda: None, tmp_path, timeout=1, cancel=cancelled)
    assert entries == []


def test_cancel_during_capture_uses_existing_owned_cleanup(emulated_domain, monkeypatch):
    import threading
    cancelled = threading.Event()
    entries = []
    def capture(process, payload, timeout, buffers, observe):
        cancelled.set()
        observe()
        pytest.fail('Capture ignored cancellation')
    monkeypatch.setattr(client, 'capture', capture)
    with pytest.raises(RuntimeError, match='cancelled'):
        client.run([client.sys.executable, '-c', 'pass'], entries,
            lambda: None, emulated_domain, timeout=1, cancel=cancelled)
    assert entries[0]['finished']
    assert not Path(entries[0]['cgroup']['path']).exists()


def test_terminal_barrier_failure_never_falls_back_to_killing_creator(emulated_domain, monkeypatch):
    import signal
    processes=[]
    original_spawn=client.subprocess.Popen
    def spawn(*args,**kwargs):
        process=original_spawn(*args,**kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(client.subprocess,'Popen',spawn)
    def fail_capture(*args): raise TimeoutError('work allowance exhausted')
    monkeypatch.setattr(client,'capture',fail_capture)
    entries=[]
    def reject(_entry): raise RuntimeError('Unknown daemon ownership')
    try:
        with pytest.raises(TimeoutError,match='allowance'):
            client.run([client.sys.executable,'-c','import time; time.sleep(10)'],entries,
                lambda:None,emulated_domain,timeout=1,before_cancel=reject)
        assert entries[0]['cancellation_fenced']
        assert not entries[0]['finished']
        assert processes[0].poll() is None
        assert Path(entries[0]['cgroup']['path']).exists()
    finally:
        for process in processes:
            if process.poll() is None:process.kill()
            process.wait(timeout=5)
        for entry in entries:client.stop(entry)


def test_terminal_barrier_precedes_timeout_cancellation(emulated_domain, monkeypatch):
    order=[]
    original_stop=client.stop
    def stop(entry):
        order.append('cancel')
        return original_stop(entry)
    monkeypatch.setattr(client,'stop',stop)
    def fail_capture(*args):raise TimeoutError('deadline')
    monkeypatch.setattr(client,'capture',fail_capture)
    with pytest.raises(TimeoutError):
        client.run([client.sys.executable,'-c','pass'],[],lambda:None,emulated_domain,
            timeout=1,before_cancel=lambda entry:order.append('barrier'))
    assert order[0]=='barrier' and 'cancel' in order[1:]


def test_absolute_deadline_charges_slow_setup_before_gate_release(emulated_domain):
    import time
    entries=[]
    def slow_save():time.sleep(.02)
    with pytest.raises(TimeoutError,match='deadline'):
        client.run([client.sys.executable,'-c','raise RuntimeError("must never execute")'],entries,
            slow_save,emulated_domain,timeout=10,absolute_deadline=time.monotonic()+.01)
    assert entries[0]['finished']
    assert not Path(entries[0]['cgroup']['path']).exists()


def test_absolute_capture_timeout_does_not_restart_after_saves(emulated_domain,monkeypatch):
    import time
    received=[]
    def capture(process,payload,timeout,buffers,observe):
        received.append(timeout)
        process.wait(timeout=1)
    monkeypatch.setattr(client,'capture',capture)
    client.run([client.sys.executable,'-c','pass'],[],lambda:time.sleep(.01),emulated_domain,
        timeout=10,absolute_deadline=time.monotonic()+1)
    assert received and 0 < received[0] < .99
