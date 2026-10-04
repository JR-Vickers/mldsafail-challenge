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
