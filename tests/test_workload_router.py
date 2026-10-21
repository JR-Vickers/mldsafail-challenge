"""Kernel containment proof contracts for fast-exiting frozen worker commands."""
from pathlib import Path
import pytest

from mldsafail.evaluator.native_workload import birth, WorkloadBlocked
from mldsafail.evaluator.workload_router import WorkloadRouter


def test_fast_exit_requires_charges_in_its_independently_bounded_parent(tmp_path):
    route=object.__new__(WorkloadRouter)
    limits={'memory.max':str(2*1024**3),'memory.swap.max':'0','pids.max':'64','cpu.max':'100000 100000'}
    for name,value in limits.items():(tmp_path/name).write_text(value)
    (tmp_path/'cpu.stat').write_text('usage_usec 0\n')
    (tmp_path/'memory.peak').write_text('0')
    route.parent_binding=dict(path=birth(tmp_path),cpu_before=0,limits=limits)
    with pytest.raises(WorkloadBlocked,match='actual_placement_unverified'):route.admit_start({})
    (tmp_path/'cpu.stat').write_text('usage_usec 100\n');(tmp_path/'memory.peak').write_text('4096')
    proof=route.admit_start({})
    assert proof==dict(parent_cpu_usec_after=100,parent_memory_peak=4096)
    (tmp_path/'pids.max').write_text('128')
    with pytest.raises(WorkloadBlocked,match='parent_replaced'):route.admit_start({})
