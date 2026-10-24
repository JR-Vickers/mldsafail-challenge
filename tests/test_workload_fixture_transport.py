"""Real Linux subreaper + unchanged bounded native-command transport."""
from pathlib import Path
import sys

import pytest

from deploy.workload_fixture_resources import Resources
from deploy.workload_installation import Journal
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.workload_installation_fixture import Fixture


def transport(tmp_path):
    fixture=object.__new__(Fixture);fixture.root=tmp_path
    (tmp_path/'artifacts').mkdir(mode=0o700);journal=tmp_path/'journal';journal.mkdir(mode=0o700)
    fixture.journal=Journal(journal,'a'*64);fixture.lock_fd=None
    fixture.require_target=lambda:None
    fixture.deadline=lambda **kwargs:1800
    fixture.manifest={'source_root':str(Path(__file__).resolve().parents[1])}
    resources=object.__new__(Resources);resources.fixture=fixture;resources.cleanup_mode=False
    resources.check_daemon=lambda:None
    return resources,fixture


@pytest.mark.skipif(sys.platform!='linux',reason='Linux real subreaper required')
def test_inner_deadline_and_wrapper_cleanup_reserve_are_independently_enforced(tmp_path):
    resources,fixture=transport(tmp_path)
    assert resources.run([sys.executable,'-c','print("bounded")'],seconds=4.65,inner_seconds=.65)==b'bounded\n'
    with pytest.raises(WorkloadBlocked,match='fixture_command_failed'):
        resources.run([sys.executable,'-c','import time;time.sleep(2)'],seconds=4.65,inner_seconds=.65)
    receipts=[row for row in fixture.journal.rows if row['event']=='fixture_command_result']
    assert len(receipts)==2
    assert receipts[0]['containment']['returncode']==0 and receipts[1]['containment']['returncode']!=0
    for row in receipts:
        assert not row['group_remaining'] and not row['cleanup_errors']
        assert not row['containment']['remaining'] and not row['containment']['descendants']
        assert not row['containment']['timed_out']


def test_wrapper_rejects_missing_cleanup_reserve_before_command(tmp_path):
    resources,fixture=transport(tmp_path)
    with pytest.raises(WorkloadBlocked,match='wrapper_cleanup_reserve_required'):
        resources.run([sys.executable,'-c','raise RuntimeError("must not execute")'],seconds=.65,inner_seconds=.65)
    assert fixture.journal.rows==[]


@pytest.mark.parametrize('seconds',[1,True,0,-1,'0.65'])
def test_inner_deadline_cannot_be_extended_or_malformed(tmp_path,seconds):
    resources,fixture=transport(tmp_path)
    with pytest.raises(WorkloadBlocked,match='inner_command_deadline_invalid'):
        resources.run(['unused'],seconds=4.65,inner_seconds=seconds)
    assert fixture.journal.rows==[]


@pytest.mark.skipif(sys.platform!='linux',reason='Linux real subreaper required')
@pytest.mark.parametrize('interrupt',[False,True])
def test_owned_placement_parent_reaps_descendant_or_supervisor_blocks(tmp_path,interrupt):
    import threading
    import time
    from deploy.workload_fixture_controls import placement_program
    from deploy.workload_installation import exclusive
    resources,fixture=transport(tmp_path)
    marker=tmp_path/'descendant';stop=tmp_path/'stop';thread=None
    if not interrupt:
        def release():
            deadline=time.monotonic()+2
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.005)
            exclusive(stop,b'stop')
        thread=threading.Thread(target=release);thread.start()
    try:
        argv=[sys.executable,'-I','-B','-c',placement_program(marker,stop)]
        if interrupt:
            with pytest.raises(WorkloadBlocked):resources.run(argv,seconds=4.65,inner_seconds=.65)
        else:assert resources.run(argv,seconds=4.65,inner_seconds=.65)==b''
    finally:
        if thread:thread.join(3)
    row=[row for row in fixture.journal.rows if row['event']=='fixture_command_result'][-1]
    assert not row['containment']['remaining']
    assert row['containment']['descendants'] is interrupt
