"""Lifetime descendant evidence has a fixed bound independent of client files."""
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from deploy import workload_observation as observation


def test_lifetime_birth_limit_retains_bounded_uncertainty(tmp_path,monkeypatch):
    report=tmp_path/'report.json'
    monkeypatch.setattr(observation,'MAX_BIRTHS',2)
    monkeypatch.setattr(observation,'children',lambda:[101,102,103])
    monkeypatch.setattr(observation,'child_birth',lambda pid:dict(pid=pid,start_ticks=pid))
    monkeypatch.setattr(observation.ctypes,'CDLL',lambda *args,**kwargs:SimpleNamespace(prctl=lambda *args:0))
    monkeypatch.setattr(observation.subprocess,'Popen',lambda argv:SimpleNamespace(returncode=0,pid=0))
    original=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda path,*args,**kwargs:'' if str(path).startswith('/proc/') else original(path,*args,**kwargs))
    monkeypatch.setattr(observation.sys,'argv',['observer',str(report),'1','synthetic-command'])
    observation.main()
    result=json.loads(report.read_bytes())
    assert len(result['observed'])==2
    assert len(result['remaining'])==2
    assert any(row.get('detail')=='descendant_lifetime_evidence_limit' for row in result['errors'])
    assert any(row.get('error')=='remaining_children_evidence_limit' for row in result['errors'])
    assert report.stat().st_size<=1024**2
    assert Path(str(report)+'.births.jsonl').stat().st_size<=1024**2


@pytest.mark.skipif(sys.platform!='linux',reason='Linux subreaper')
def test_evidence_exhaustion_still_terminates_and_reaps_real_descendants(tmp_path):
    root=Path(__file__).resolve().parents[1]
    report=tmp_path/'report.json'
    code='import sys;sys.path[:0]='+repr([str(root/'src'),str(root)])+';from deploy import workload_observation as m;m.MAX_BIRTHS=1;m.main()'
    client='import subprocess,sys,time;[subprocess.Popen([sys.executable,"-I","-c","import time;time.sleep(30)"]) for _ in range(2)];time.sleep(30)'
    result=subprocess.run([sys.executable,'-I','-c',code,str(report),'2',sys.executable,'-I','-c',client],
                          capture_output=True,start_new_session=True,timeout=5)
    assert result.returncode==0,result.stderr
    observed=json.loads(report.read_bytes())
    assert not observed['remaining']
    assert observed['unrecorded_cleanup_observations']>0
    assert any(row.get('detail')=='descendant_lifetime_evidence_limit' for row in observed['errors'])
    assert len(observed['observed'])==1
    assert not any(Path('/proc/'+str(row['pid'])).exists() for row in observed['observed'])
