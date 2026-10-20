import copy
import hashlib
import json
import time

import pytest

from deploy.capacity_monitor import Monitor, validate_capture, assess
from deploy.recovery_journal import atomic_json
from test_capacity_investigation import fixture


def complete(tmp_path):
    sampler, operation, retained, proc = fixture(tmp_path)
    (operation/'memory.current').write_text('100')
    (retained/'memory.current').write_text('200')
    (tmp_path/'memory-root').mkdir(mode=0o700)
    root=tmp_path/'memory-root'
    with (root/'samples.jsonl').open('wb') as stream:
        for n, name in enumerate(('setup','create','audit','cleanup')):
            for delta in (10, 20):
                row=sampler.sample(name,now=n*100+delta)
                row['live_identity_verified']=True
                row['operation_id']='a'*32
                stream.write((json.dumps(row)+'\n').encode())
    atomic_json(root/'coverage.json',dict(operation_id='a'*32,complete=True,phases=[dict(phase=name,start_ns=i*100,end_ns=i*100+30)
                            for i,name in enumerate(('setup','create','audit','cleanup'))]))
    atomic_json(root/'attempt.json',dict(state='terminated',operation_id='a'*32,capture_complete=True))
    return root


def test_complete_capture_and_compatibility_gate(tmp_path):
    root=complete(tmp_path)
    evidence=validate_capture(root)
    assert evidence['samples']==8
    assert evidence['observed_simultaneous_peak']==100
    assert evidence['retained_services_peak']==200
    with pytest.raises(ValueError,match='compatibility'):
        assess(root,{},host='host',source='source',configured_limits={},headroom={})
    compatibility=dict(source_compatible=True,reviewed_by='reviewer',measurement_sha256=evidence['measurement_sha256'],
                       coverage_sha256=evidence['coverage_sha256'],host='host',source='source',
                       production_retained_evidence={},all_host_ancestors_visible=True,
                       operation_accounting_complete=True,timer_coverage_complete=True)
    import os
    host=os.uname().nodename
    compatibility['host']=host
    retained=dict(host=host,source='source',boot_id=evidence['boot_id'],
                  measurement_sha256=evidence['measurement_sha256'],measurement_scopes=evidence['measurement_scopes'],
                  coverage_sha256=evidence['coverage_sha256'])
    atomic_json(root/'retained.json',retained)
    compatibility['production_retained_evidence']=dict(path=str(root/'retained.json'),sha256=hashlib.sha256((root/'retained.json').read_bytes()).hexdigest())
    result=assess(root,compatibility,host=host,source='source',configured_limits={'operation_memory_bytes':2684354560},
                  headroom=dict(bytes=256*1024**2,rationale='test fixture only'))
    assert result['capacity']=='supported'


@pytest.mark.parametrize('failure',['overlap','gap','birth','scope','reset','phase','boundary','ancestor','boot'])
def test_capture_validator_rejects_bad_raw_evidence(tmp_path,failure):
    root=complete(tmp_path)
    rows=[json.loads(line) for line in (root/'samples.jsonl').read_text().splitlines()]
    if failure=='overlap': rows[1]['scopes']['retained_services_excluding_operation']=rows[1]['scopes']['operation_resources']
    if failure=='gap': rows[1]['monotonic_ns']+=2_000_000_000
    if failure=='birth': next(iter(rows[1]['cgroups'].values()))['birth']['pid']=999
    if failure=='scope': rows[1]['scopes'].pop('operation_resources')
    if failure=='reset': next(iter(rows[0]['cgroups'].values()))['counters']['cpu.stat']['usage_usec']=2
    if failure=='phase': rows[1]['phase']='not-a-phase'
    if failure=='boundary': rows=rows[2:]
    if failure=='ancestor': next(iter(rows[1]['ancestors'].values()))['inode']+=1
    if failure=='boot': rows[1]['boot_id']='reboot'
    (root/'samples.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError): validate_capture(root)


def test_monitor_boundaries_and_sampling(tmp_path):
    sampler,*_=fixture(tmp_path)
    root=tmp_path/'monitor'
    root.mkdir(mode=0o700)
    monitor=Monitor(root,sampler,lambda:True,lambda:True,operation_id='a'*32).start()
    try:
        monitor.transition('create')
        time.sleep(.3)
        assert monitor.guard()
        monitor.transition('audit')
        monitor.transition('cleanup')
        monitor.finish()
    finally:
        if monitor.stream and not monitor.stream.closed: monitor.abort()
    atomic_json(root/'attempt.json',dict(state='terminated',operation_id='a'*32,capture_complete=True))
    assert validate_capture(root)['samples']>=8


def test_blackholed_monitor_fails_and_preserves_reader(tmp_path):
    import threading
    sampler,*_=fixture(tmp_path)
    root=tmp_path/'monitor'
    root.mkdir(mode=0o700)
    gate=threading.Event()
    monitor=Monitor(root,sampler,lambda:gate.wait(5),lambda:True,operation_id='a'*32)
    started=time.monotonic()
    try:
        with pytest.raises(ValueError,match='deadline'): monitor.start()
        assert time.monotonic()-started<1.5
        monitor.abort()
        assert json.loads((root/'coverage.json').read_text())['reader_remains'] is True
    finally:
        gate.set()
