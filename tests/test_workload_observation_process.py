"""Bounded disposable observation clients; no workload or benchmark runs."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from deploy.workload_installed import run
from mldsafail.evaluator.workload import WorkloadBlocked


def test_observation_budget_is_bounded_before_spawning():
    with pytest.raises(WorkloadBlocked,match='budget_invalid'):run(['/never/run'],timeout=36)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux process identity and process group checks')
def test_timed_out_observation_terminates_its_inert_descendants(tmp_path):
    marker=tmp_path/'births.json'
    code=('import json,os,pathlib,subprocess,sys,time; '
          'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]); '
          'pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(),child.pid]));time.sleep(30)')
    with pytest.raises((subprocess.TimeoutExpired,WorkloadBlocked)):
        run([sys.executable,'-c',code,str(marker)],timeout=2)
    for pid in json.loads(marker.read_bytes()):
        path=Path('/proc')/str(pid)/'stat'
        # A dead adopted zombie is waiting for PID 1 to reap it; it cannot run.
        assert not path.exists() or path.read_text().rsplit(')',1)[1].split()[0]=='Z'


@pytest.mark.skipif(sys.platform!='linux',reason='Linux observation client birth')
@pytest.mark.parametrize('escape',[False,True])
def test_exited_leader_cannot_report_success_while_a_child_survives(tmp_path,escape):
    import os,signal
    from mldsafail.evaluator.native_workload import process_birth
    marker=tmp_path/'child.json'
    code=('import json,pathlib,subprocess,sys; '
          'child=subprocess.Popen([sys.executable,"-c","import os,time;"+sys.argv[2]+"time.sleep(30)"]); '
          'ticks=int(pathlib.Path("/proc/"+str(child.pid)+"/stat").read_text().rsplit(")",1)[1].split()[19]); '
          'pathlib.Path(sys.argv[1]).write_text(json.dumps(dict(pid=child.pid,start_ticks=ticks)))')
    try:
        with pytest.raises(WorkloadBlocked,match='descendants_unverified'):
            run([sys.executable,'-c',code,str(marker),'os.setsid();' if escape else ''])
    finally:
        if marker.exists():
            record=json.loads(marker.read_bytes())
            try:current=process_birth(record['pid'])
            except FileNotFoundError:current=None
            if current is not None:
                assert current==record
                os.kill(record['pid'],signal.SIGKILL)


@pytest.mark.skipif(sys.platform!='linux',reason='Linux observation client birth')
def test_observation_output_cannot_exceed_private_log_limit():
    with pytest.raises(WorkloadBlocked,match='output_limit'):
        run([sys.executable,'-c','import sys;sys.stdout.write("x"*(2*1024**2));sys.stdout.flush()'])


def test_unsignalable_descendant_retains_reconciliation_birth(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import deploy.workload_observation as observer
    report=tmp_path/'report'
    monkeypatch.setattr(observer.sys,'argv',['wrapper',str(report),'1','inert'])
    monkeypatch.setattr(observer.ctypes,'CDLL',lambda *a,**k:SimpleNamespace(prctl=lambda *a:0))
    monkeypatch.setattr(observer.subprocess,'Popen',lambda *a:SimpleNamespace(wait=lambda **k:None,returncode=0))
    monkeypatch.setattr(observer,'children',lambda:[73])
    monkeypatch.setattr(observer,'child_birth',lambda pid:dict(pid=pid,start_ticks=99))
    monkeypatch.setattr(observer.os,'waitpid',lambda *a:(0,0))
    monkeypatch.setattr(observer.os,'kill',lambda *a:(_ for _ in ()).throw(PermissionError()))
    observer.main()
    row=json.loads(report.read_bytes())
    assert row['remaining']==[dict(pid=73,start_ticks=99)]
    assert row['errors']==[dict(pid=73,error='PermissionError')]


@pytest.mark.parametrize('failure_kind',['group','output','timeout'])
def test_process_group_blocker_preserves_wrapper_report(tmp_path,monkeypatch,failure_kind):
    from types import SimpleNamespace
    import deploy.workload_installed as installed
    import os
    monkeypatch.setattr(sys,'platform','linux')
    monkeypatch.setattr(installed,'process_birth',lambda pid:dict(pid=pid,start_ticks=12))
    def spawn(argv,**kwargs):
        Path(argv[3]).write_text(json.dumps(dict(remaining=[dict(pid=73,start_ticks=99)],errors=['PermissionError'])))
        if failure_kind=='output':kwargs['stdout'].write(b'x'*(1024**2))
        def wait(**kwargs):
            if failure_kind=='timeout':raise subprocess.TimeoutExpired(argv,11)
        return SimpleNamespace(pid=55,wait=wait,poll=lambda:0,returncode=0)
    monkeypatch.setattr(installed.subprocess,'Popen',spawn)
    monkeypatch.setattr(os,'killpg',lambda *args:None)
    with pytest.raises(WorkloadBlocked) as failure:
        installed.run(['inert'])
    assert '73' in str(failure.value) and 'PermissionError' in str(failure.value)
