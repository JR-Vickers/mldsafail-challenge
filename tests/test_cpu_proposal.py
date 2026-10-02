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
])
def test_experimental_worker_ignores_reported_cpu_and_verification(tmp_path, monkeypatch, output, exitcode, expected):
    import json
    from types import SimpleNamespace
    from research.cpu_measurement import harness
    from mldsafail.benchmark_v050.generator import generate_mlwe
    (tmp_path / 'cpu.stat').write_text('usage_usec 20\n')
    (tmp_path / 'cgroup.events').write_text('populated 0\n')
    monkeypatch.setattr(harness.sys, 'platform', 'linux')
    monkeypatch.setattr(harness, 'prove_membership', lambda *args: None)
    monkeypatch.setattr(harness.subprocess, 'check_output', lambda *args, **kw: json.dumps(
        {'CgroupVersion': '2', 'SecurityOptions': ['name=rootless']}).encode())
    def command(argv, **kwargs):
        if 'rm' in argv:
            (tmp_path / 'cpu.stat').write_text('usage_usec 1020\n')
        return SimpleNamespace(returncode=0, stdout='{"Pid":123}')
    monkeypatch.setattr(harness.subprocess, 'run', command)
    class Worker:
        def __init__(self, argv, **kwargs):
            self.stdout = kwargs['stdout']
            self.returncode = None
        def communicate(self, payload, timeout):
            self.stdout.write(output)
            self.stdout.flush()
            self.returncode = exitcode
        def poll(self):
            return self.returncode
        def wait(self, **kwargs):
            return exitcode
    monkeypatch.setattr(harness.subprocess, 'Popen', Worker)
    result = harness._run('sha256:' + 'a' * 64, tmp_path, 'dedicated', tmp_path,
                          generate_mlwe('small', 0, 1).public.to_dict(), lambda *args: True)
    assert result['authoritative_cpu_usec'] == 1000
    assert not result['verified'] and result['status'] == expected
