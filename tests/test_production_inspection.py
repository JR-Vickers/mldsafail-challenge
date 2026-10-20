"""Inspection helper stays bounded and read-only; no daemon is contacted."""
import json
from pathlib import Path
from types import SimpleNamespace

from deploy import production_inspection


def test_host_inspection_uses_only_readonly_bounded_commands(monkeypatch, capsys):
    monkeypatch.setenv("DOCKER_HOST", "unix:///fixture-before")
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    calls=[]
    def output(args, *, text, timeout):
        assert text and timeout == 12
        calls.append(args)
        if args == ['hostname']:return 'fixture\n'
        if args[0] == 'ps':return 'PID UID COMMAND\n'
        if args[0] == 'systemctl':return 'No jobs running.\n'
        if args[1:2] == ['info']:return json.dumps({'ID':'fixture','SecurityOptions':['rootless']})
        if 'inspect' in args:return '[]'
        return ''
    monkeypatch.setattr('subprocess.check_output',output)
    original=Path.read_text
    def read(path,*a,**kw):
        if str(path)=='/proc/self/mountinfo':return '1 2 0:1 / / rw - ext4 /dev/root rw'
        if str(path)=='/proc/meminfo':return 'MemAvailable: 1048576 kB'
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'read_text',read)
    monkeypatch.setattr('os.statvfs',lambda p:SimpleNamespace(f_bavail=1000000,f_frsize=4096))
    production_inspection.inspect_host()
    result=json.loads(capsys.readouterr().out)
    assert result['info']['ID']=='fixture'
    assert result['disk_available']==4096000000
    assert all(args[0] != 'docker' or args[1] in ('info','image','container','volume','ps') for args in calls)
    assert all('run' not in args and 'load' not in args and 'start' not in args for args in calls)
