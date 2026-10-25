"""Actual cleanup-worker dispatch must survive only a proven runtime prefix."""
import json
import os

import pytest

from deploy.workload_installation import Journal,private
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_fixture_control_cleanup import (
    owned,native_fixture,add_compute,CONTROL,SCENARIO,TOKEN,
)


def test_cleanup_worker_uses_preserved_prefix_for_safety_stop_then_blocks(owned,monkeypatch):
    import scripts.workload_fixture_worker as worker
    import scripts.workload_installation_fixture as driver
    import deploy.workload_fixture_resources as resources
    add_compute(owned)
    runtime_path=owned.fixture.root/'runtime-journal/installation.jsonl'
    with runtime_path.open('ab') as stream:stream.write(b'{"event":"interrupted')
    original=runtime_path.read_bytes()
    parent_root=owned.fixture.root/'journal';parent_root.mkdir(mode=0o700)
    parent=Journal(parent_root,owned.fixture.binding)
    parent_process=dict(pid=os.getppid(),start_ticks=1)
    output=owned.fixture.root/'artifacts/cleanup-worker-result.json'
    phase=CONTROL+':'+SCENARIO+':'+TOKEN;cleanup_token='f'*32
    parent.append('fixture_worker_intent',operation='control',token=TOKEN,phase=CONTROL+':'+SCENARIO)
    parent.append('fixture_worker_intent',operation='control-cleanup',token=cleanup_token,phase=phase,
        output=str(output),reconciliation=False,review_sha256=None,authority_sha256=None,parent=parent_process)
    owned.fixture.journal=parent;owned.fixture.lifecycle_journal=parent
    monkeypatch.setattr(driver,'Fixture',lambda root:owned.fixture)
    monkeypatch.setattr(worker,'process_birth',lambda pid:parent_process)
    monkeypatch.setattr(resources,'Resources',lambda fixture:owned.resources)
    owned.calls.clear()
    with pytest.raises(WorkloadBlocked,match='partial_runtime_journal_preserve'):
        worker.work(owned.fixture.root,9,cleanup_token,'control-cleanup',output,phase=phase)
    assert (owned.scope/'cgroup.kill').read_text()=='1'
    assert private(owned.root/'runtime/workload.json')[1]['paused'] is True
    assert runtime_path.read_bytes()==original and owned.calls==[]
    assert not output.exists() and not (owned.root/'independent-cleanup.json').exists()
    sidecar=owned.fixture.root/('control-recovery-'+TOKEN)
    assert sidecar.is_dir()
    events=[json.loads(line)['event'] for line in (sidecar/'installation.jsonl').read_text().splitlines()]
    assert 'fixture_worker_claim' in events and 'fixture_control_cleanup_scope_kill_acknowledged' in events


def test_normal_worker_keeps_strict_runtime_journal_interpretation(owned,monkeypatch):
    import scripts.workload_fixture_worker as worker
    import scripts.workload_installation_fixture as driver
    runtime_path=owned.fixture.root/'runtime-journal/installation.jsonl'
    with runtime_path.open('ab') as stream:stream.write(b'{"partial":')
    original=runtime_path.read_bytes()
    parent_root=owned.fixture.root/'journal';parent_root.mkdir(mode=0o700);parent=Journal(parent_root,owned.fixture.binding)
    parent_process=dict(pid=os.getppid(),start_ticks=1);token='f'*32;output=owned.fixture.root/'artifacts/inspect-worker.json'
    parent.append('fixture_worker_intent',operation='inspect',token=token,phase='install',output=str(output),
        reconciliation=False,review_sha256=None,authority_sha256=None,parent=parent_process)
    owned.fixture.journal=owned.fixture.lifecycle_journal=parent
    monkeypatch.setattr(driver,'Fixture',lambda root:owned.fixture)
    monkeypatch.setattr(worker,'process_birth',lambda pid:parent_process)
    with pytest.raises(WorkloadBlocked,match='partial_journal'):
        worker.work(owned.fixture.root,9,token,'inspect',output)
    assert runtime_path.read_bytes()==original and (owned.scope/'cgroup.kill').read_text()=='0'
    assert not (owned.fixture.root/('control-recovery-'+TOKEN)).exists()
