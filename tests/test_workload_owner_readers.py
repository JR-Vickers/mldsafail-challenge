"""Synthetic reader/packaging tests; never privileged or installed evidence."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from deploy import workload_owner_readers as readers
from scripts.prepare_owner_collection_successor import build, ROOT, RULE, COMMAND
from scripts.prepare_owner_collection_access import ROOT as FIRST_ROOT, RULE as FIRST_RULE


def plan():
    return dict(runtime_account='mldsafail', reviewed_paths=[], reviewed_sha256={}, output_paths=[])


@pytest.mark.parametrize('change', [dict(runtime_account='root'), dict(reviewed_paths=['relative']),
    dict(reviewed_paths=['/a/../b']), dict(output_paths=['/a', '/a']), dict(output_paths=['/a']*17),
    dict(command=['sh'])])
def test_plan_rejects_unbounded_or_runtime_selected_readers(change):
    candidate = plan(); candidate.update(change)
    with pytest.raises(ValueError): readers.validate_plan(candidate)


def test_successor_is_deterministic_separate_and_fixed(tmp_path):
    source = Path(__file__).resolve().parents[1]
    candidate = plan(); candidate['reviewed_paths'] = ['/usr/local/bin/reviewed-script']; candidate['reviewed_sha256'] = {'/usr/local/bin/reviewed-script': 'a'*64}
    a = build(source, tmp_path/'a.pyz', candidate); b = build(source, tmp_path/'b.pyz', candidate)
    assert a['sha256'] == b['sha256']
    assert ROOT != FIRST_ROOT and RULE != FIRST_RULE
    assert a['command'] == COMMAND and '*' not in a['sudoers']
    assert not a['installed'] and not a['execution_authority']
    with zipfile.ZipFile(a['artifact']) as archive:
        assert set(archive.namelist()) == set(a['sources']) | {'__main__.py'}
        for name, expected in a['sources'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
        code = archive.read('__main__.py').decode()
        compile(code, '__main__.py', 'exec')
        assert "reviewed_paths=('/usr/local/bin/reviewed-script',),command_runner=scheduling_command" in code
        assert 'SupplementalDeadline' in code
    with pytest.raises(FileExistsError): build(source, tmp_path/'a.pyz', candidate)


def test_runtime_reader_cannot_measure_permissions_as_root(monkeypatch):
    monkeypatch.setattr(readers.os, 'getuid', lambda: 0)
    scope = {'__name__': 'test'}
    import sys
    monkeypatch.setattr(sys, 'argv', ['reader', '1000'])
    with pytest.raises(AssertionError): exec(readers.CGROUP_READER, scope)


def test_nonroot_supplemental_entry_refused(monkeypatch):
    monkeypatch.setattr(readers.os, 'getuid', lambda: 1000)
    with pytest.raises(ValueError, match='owner_root_console'): readers.collect(plan())


def test_supplemental_commands_are_fixed_readers_and_results_stay_unaccepted(tmp_path, monkeypatch):
    account = SimpleNamespace(pw_uid=1000, pw_name='mldsafail')
    monkeypatch.setattr(readers.os, 'getuid', lambda: 0)
    monkeypatch.setattr(readers.pwd, 'getpwnam', lambda name: account)
    monkeypatch.setattr(readers.pwd, 'getpwall', lambda: [])
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return dict(returncode=0, stdout=b'', stderr=b'', containment=dict(verified=True))
    monkeypatch.setattr(readers, 'observe_command', run)
    script = tmp_path/'script'; script.write_text('echo synthetic')
    candidate = plan(); candidate['reviewed_paths'] = [str(script)]; candidate['reviewed_sha256'] = {str(script): hashlib.sha256(script.read_bytes()).hexdigest()}
    result = readers.collect(candidate)
    assert not result['readiness'] and not result['execution_authority']
    assert result['complete'] is True
    assert result['reviewed_files'][0]['contents_hex'] == script.read_bytes().hex()
    cgroup = calls[0]
    assert cgroup[:5] == ['/usr/sbin/runuser', '-u', 'mldsafail', '--', '/usr/bin/python3']
    assert cgroup[-1] == '1000'
    assert all('install' not in argv and 'update' not in argv and 'start' not in argv for argv in calls)


def test_reviewed_script_change_is_blocked(tmp_path, monkeypatch):
    account = SimpleNamespace(pw_uid=1000, pw_name='mldsafail')
    monkeypatch.setattr(readers.os, 'getuid', lambda: 0)
    monkeypatch.setattr(readers.pwd, 'getpwnam', lambda name: account)
    monkeypatch.setattr(readers.pwd, 'getpwall', lambda: [])
    monkeypatch.setattr(readers, 'observe_command', lambda *args, **kw: dict(returncode=0, stdout=b'', stderr=b'', containment=dict(verified=True)))
    script = tmp_path/'script'; script.write_text('original')
    original = readers.inspect_path
    def raced(name):
        row = original(name)
        if row.get('sha256'): script.write_text('replacement')
        return row
    monkeypatch.setattr(readers, 'inspect_path', raced)
    candidate = plan(); candidate['reviewed_paths'] = [str(script)]; candidate['reviewed_sha256'] = {str(script): hashlib.sha256(script.read_bytes()).hexdigest()}
    result = readers.collect(candidate)
    assert result['complete'] is False
    assert result['reviewed_files'][0]['error'] == 'reviewed_path_changed'
    assert 'contents_hex' not in result['reviewed_files'][0]


def test_reviewed_script_cannot_export_a_substituted_privileged_target(tmp_path, monkeypatch):
    account = SimpleNamespace(pw_uid=1000, pw_name='mldsafail')
    monkeypatch.setattr(readers.os, 'getuid', lambda: 0)
    monkeypatch.setattr(readers.pwd, 'getpwnam', lambda name: account)
    monkeypatch.setattr(readers.pwd, 'getpwall', lambda: [])
    monkeypatch.setattr(readers, 'observe_command', lambda *a, **kw:
        dict(returncode=0, stdout=b'', stderr=b'', containment=dict(verified=True)))
    script = tmp_path/'script'; script.write_text('approved script')
    candidate = plan(); candidate['reviewed_paths'] = [str(script)]
    candidate['reviewed_sha256'] = {str(script): hashlib.sha256(script.read_bytes()).hexdigest()}
    secret = tmp_path/'root-secret'; secret.write_text('PRIVATE ROOT CONTENT')
    script.unlink(); script.symlink_to(secret)
    result = readers.collect(candidate)
    row = result['reviewed_files'][0]
    assert result['complete'] is False
    assert row == dict(path=str(script), error='reviewed_file_identity_or_content_changed')
    assert secret.read_bytes().hex() not in str(result)
    assert hashlib.sha256(secret.read_bytes()).hexdigest() not in str(result)


@pytest.mark.parametrize('hashes', [{}, {'/script': 'bad'}, {'/other': 'a'*64}])
def test_every_reviewed_content_read_requires_an_exact_frozen_hash(hashes):
    candidate = plan(); candidate['reviewed_paths'] = ['/script']; candidate['reviewed_sha256'] = hashes
    with pytest.raises(ValueError, match='hash_bindings'): readers.validate_plan(candidate)


def test_cgroup_reader_rejects_permission_change_during_measurement(tmp_path, monkeypatch):
    import sys
    root = tmp_path/'cgroup'
    manager = root/'user.slice/user-1000.slice/user@1000.service'
    manager.mkdir(parents=True)
    for path in (manager, *manager.parents):
        if not path.is_relative_to(root): break
        for name in ('cgroup.procs', 'cgroup.subtree_control', 'cgroup.controllers',
                     'memory.max', 'memory.high', 'memory.swap.max', 'pids.max', 'cpu.max', 'cpuset.cpus.effective'):
            (path/name).write_text('')
    monkeypatch.setattr(readers.os, 'getuid', lambda: 1000)
    monkeypatch.setattr(sys, 'argv', ['reader', '1000'])
    original = readers.os.access
    def raced(path, mode):
        if Path(path) == manager/'cgroup.procs': Path(path).chmod(0o400)
        return original(path, mode)
    monkeypatch.setattr(readers.os, 'access', raced)
    code = readers.CGROUP_READER.replace("'/sys/fs/cgroup'", repr(str(root)))
    with pytest.raises(AssertionError): exec(code, {'__name__': 'test'})


@pytest.mark.skipif(__import__('sys').platform != 'linux', reason='Linux subreaper')
@pytest.mark.parametrize('kind', ['timeout', 'escaped'])
def test_reader_descendants_are_reaped_and_failed_receipts_retained(kind):
    import json
    import shutil
    import sys
    if kind == 'timeout':
        code = 'import time;time.sleep(30)'
    else:
        code = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c","import os,time;os.setsid();time.sleep(30)"])'
    row = readers.observe_command([sys.executable, '-c', code], seconds=.3)
    assert not row['containment']['verified']
    report = row['containment']['report']
    assert report and not report['remaining'] and not report['errors']
    assert report['observed']
    assert report['timed_out'] if kind == 'timeout' else report['descendants']
    directory = Path(row['containment']['retained_evidence'])
    assert json.loads((directory/'report.json').read_bytes()) == report
    # The compact receipt answers this disposable check; all children are reaped.
    shutil.rmtree(directory)
