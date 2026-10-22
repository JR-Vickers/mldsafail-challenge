"""Scoped injections: synthetic cgroup files and a real small kernel log bound."""
import json
from pathlib import Path
import resource
import subprocess
import sys

import pytest
from deploy.workload_inert import inject_limit
from mldsafail.evaluator.native_workload import birth
from mldsafail.evaluator.workload import WorkloadBlocked


def test_limit_injection_changes_only_owned_leaf(tmp_path):
    scope=tmp_path/'scope';leaf=scope/'creators';leaf.mkdir(parents=True)
    (scope/'memory.max').write_text('retained-parent-value')
    (leaf/'memory.max').write_text(str(512*1024**2))
    output=tmp_path/'output';output.mkdir()
    record=dict(scope=birth(scope),leaf=birth(leaf))
    raw=inject_limit(record,output)
    assert (scope/'memory.max').read_text()=='retained-parent-value'
    assert (leaf/'memory.max').read_text()==str(256*1024**2)
    assert raw==json.loads((output/'injection.json').read_bytes())


def test_limit_injection_rejects_unrelated_leaf_without_mutating_it(tmp_path):
    scope=tmp_path/'scope';scope.mkdir();leaf=tmp_path/'retained';leaf.mkdir()
    target=leaf/'memory.max';target.write_text(str(512*1024**2))
    with pytest.raises(WorkloadBlocked,match='scope_changed'):
        inject_limit(dict(scope=birth(scope),leaf=birth(leaf)),tmp_path)
    assert target.read_text()==str(512*1024**2)


def test_log_injection_observes_real_kernel_limit_without_large_output(tmp_path):
    path=tmp_path/'inert.stdout'
    def limit():resource.setrlimit(resource.RLIMIT_FSIZE,(2048,2048))
    code='from deploy.workload_inert import inject_log;inject_log('+repr(str(tmp_path))+')'
    with path.open('xb') as output:
        result=subprocess.run([sys.executable,'-B','-c',code],stdout=output,stderr=subprocess.PIPE,
                              preexec_fn=limit,timeout=10)
    assert result.returncode==0,result.stderr.decode()
    assert path.stat().st_size==2048
    raw=json.loads((tmp_path/'injection.json').read_bytes())
    assert raw['log_limit']==2048 and raw['inode']==path.stat().st_ino
