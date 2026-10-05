from pathlib import Path
from types import SimpleNamespace
import pytest
from research.cpu_measurement.phase_diagnostics import process_sample,Sampler


def test_process_sample_binds_birth_and_kernel_cpu_ticks(tmp_path):
    process=tmp_path/'12';process.mkdir()
    fields=['S']+['0']*30
    fields[11]='17';fields[12]='3';fields[19]='1234'
    (process/'stat').write_text('12 (runc: init with ) parenthesis) '+' '.join(fields))
    row=process_sample(12,tmp_path)
    assert row['start_ticks']==1234 and row['user_ticks']==17 and row['system_ticks']==3
    assert row['comm']=='runc: init with ) parenthesis'


def test_parent_replacement_rejects_diagnostic_sample(tmp_path):
    parent=tmp_path/'parent';parent.mkdir()
    sampler=Sampler(parent)
    parent.rename(tmp_path/'retired');parent.mkdir()
    with pytest.raises(RuntimeError,match='parent replaced'):sampler.sample()


def test_protocol_cannot_be_changed_to_fish_for_better_metrics(tmp_path):
    with pytest.raises(ValueError,match='Fixed declared'):
        Sampler(tmp_path,interval=.1)


def test_sampler_keeps_attribution_explicitly_incomplete(tmp_path):
    (tmp_path/'cpu.stat').write_text('usage_usec 42\nuser_usec 20\nsystem_usec 22\n')
    (tmp_path/'cgroup.procs').write_text('')
    sampler=Sampler(tmp_path)
    row=sampler.sample()
    assert row['cpu_stat']['usage_usec']==42 and row['processes']==[]
    result=sampler.finish()
    assert result['attribution_complete'] is False
    assert result['authoritative_cpu_replacement'] is False


def diagnostic_setup(monkeypatch,tmp_path):
    from scripts import native_cpu_phase_diagnostic as module
    import json
    driver=SimpleNamespace(path=tmp_path/'driver.json',command=lambda *a,**k:SimpleNamespace(stdout=json.dumps([{'Id':'sha256:exact'}])))
    config={'source_commit':'a'*40,'image':'sha256:exact','acceptance_source_sha256':'b'*64}
    data={'worker_parent':str(tmp_path),'worker_slice':'owned.slice'}
    class FakeSampler:
        def __init__(self,*a):pass
        def start(self):pass
        def finish(self):return {'errors':[],'samples':[]}
    monkeypatch.setattr(module,'Sampler',FakeSampler)
    monkeypatch.setattr(module,'run',lambda *a,**k:{'status':'no_answer','cleanup_complete':True})
    monkeypatch.setattr(module,'canonical_directory',lambda *a:tmp_path)
    def publish(path,value):path.write_text(json.dumps(value))
    monkeypatch.setattr(module.owned_daemon,'publish',publish)
    return module,driver,config,data,publish


def test_diagnostic_never_claims_adoption(monkeypatch,tmp_path):
    import json
    module,driver,config,data,_=diagnostic_setup(monkeypatch,tmp_path)
    receipt=module.callback(driver,config,data)
    report=json.loads((tmp_path/'phase-diagnostic/report.json').read_text())
    assert receipt['passed'] and len(report['measurements'])==6
    assert report['adoption_gates_passed'] is False


def test_ambiguous_positive_publication_retries_negative(monkeypatch,tmp_path):
    import json
    module,driver,config,data,publish=diagnostic_setup(monkeypatch,tmp_path)
    failed=False
    def ambiguous(path,value):
        nonlocal failed
        publish(path,value)
        if path.name=='report.json' and value['passed'] and not failed:
            failed=True
            raise OSError('after rename fsync failed')
    monkeypatch.setattr(module.owned_daemon,'publish',ambiguous)
    with pytest.raises(OSError,match='after rename'):module.callback(driver,config,data)
    report=json.loads((tmp_path/'phase-diagnostic/report.json').read_text())
    assert report['passed'] is False and report['final_publication_failed'] is True


def test_original_failure_preserved_and_no_further_pairs(monkeypatch,tmp_path):
    import json
    module,driver,config,data,_=diagnostic_setup(monkeypatch,tmp_path)
    calls=[]
    def failed(*a,**k):
        calls.append(1)
        raise RuntimeError('original harness failure')
    monkeypatch.setattr(module,'run',failed)
    with pytest.raises(RuntimeError,match='original harness failure'):module.callback(driver,config,data)
    report=json.loads((tmp_path/'phase-diagnostic/report.json').read_text())
    assert len(calls)==1 and report['passed'] is False and report['cleanup_complete'] is False
    assert report['measurements'][0]['failed'] is True
