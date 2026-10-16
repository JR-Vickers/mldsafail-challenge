"""Three predeclared empty/child pairs for attribution, never adoption gates."""
import argparse
import hashlib
import json
from pathlib import Path
from deploy import owned_daemon
from research.cpu_measurement import native_driver
from research.cpu_measurement.harness import run
from research.cpu_measurement.ownership import canonical_directory
from research.cpu_measurement.phase_diagnostics import Sampler
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate


def callback(driver,config,data):
    root=driver.path.parent/'phase-diagnostic';root.mkdir(mode=0o700)
    report=dict(schema='mldsafail.cpu-phase-diagnostic.v1',passed=False,native_executed=True,
                adoption_gates_passed=False,measurements=[],source_commit=config['source_commit'],
                image=config['image'],source_sha256=config['acceptance_source_sha256'],
                sampler_source_sha256=hashlib.sha256(Path(__file__).resolve().parents[1].joinpath('research/cpu_measurement/phase_diagnostics.py').read_bytes()).hexdigest(),
                protocol=dict(pairs=3,ordered_fixtures=['empty','child'],worker_timeout_seconds=60,
                              full_counter_window_unchanged=True,sandbox_unchanged=True),
                cleanup_complete=False)
    def save():owned_daemon.publish(root/'report.json',report)
    save();original=None
    try:
        inspected=json.loads(driver.command(['docker','image','inspect',config['image']],kind='read',timeout=30).stdout)
        if len(inspected)!=1 or inspected[0]['Id']!=config['image']:raise RuntimeError('Exact retained worker required')
        parent=Path(data['worker_parent'])
        instance=generate_mlwe('small',0,1).public
        for repetition in range(3):
            for fixture in ('empty','child'):
                sampler=Sampler(parent);sampler.start();error=None;row=None
                try:
                    row=run(config['image'],parent,data['worker_slice'],
                        Path(__file__).resolve().parents[1]/'research/cpu_measurement/fixtures'/fixture,
                        instance.to_dict(),lambda public,candidate:verify_candidate(instance,candidate)['verified'],
                        timeout=60,ownership_directory=canonical_directory(parent),
                        evidence_metadata=dict(fixture=fixture,repetition=repetition),epoch='isolated-phase-diagnosis')
                except BaseException as caught:error=caught
                finally:
                    try:samples=sampler.finish()
                    except BaseException as caught:
                        if error is None:error=caught
                        else:error.add_note('Independent sampler cleanup:'+type(caught).__name__)
                        samples=dict(errors=[type(caught).__name__],samples=[])
                    target=root/(str(repetition)+'-'+fixture+'.json')
                    record=dict(fixture=fixture,repetition=repetition,samples=samples,
                                authoritative_measurement=row,failed=error is not None)
                    try:owned_daemon.publish(target,record)
                    except BaseException as caught:
                        if error is None:error=caught
                        else:error.add_note('Diagnostic sample publication:'+type(caught).__name__)
                    report['measurements'].append(dict(reference=str(target),failed=error is not None))
                    try:save()
                    except BaseException as caught:
                        if error is None:error=caught
                        else:error.add_note('Diagnostic progress publication:'+type(caught).__name__)
                if error is not None:raise error
                if samples['errors']:raise RuntimeError('Diagnostic sampler failed; preserve incomplete attribution')
                if row.get('status')!='no_answer' or row.get('cleanup_complete') is not True:
                    raise RuntimeError('Exact existing no-answer fixtures and complete cleanup required')
        report['diagnostic_completed']=True
    except BaseException as caught:original=caught;report['failure_class']=type(caught).__name__
    finally:
        report.update(cleanup_complete=original is None and len(report['measurements'])==6,passed=original is None and len(report['measurements'])==6)
        try:save()
        except BaseException as caught:
            report.update(passed=False,final_publication_failed=True)
            if original is None:original=caught
            else:original.add_note('Diagnostic publication:'+type(caught).__name__)
            try:save()
            except BaseException as retry:original.add_note('Negative diagnostic publication:'+type(retry).__name__)
        if original is not None:raise original
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
                source_sha256=config['acceptance_source_sha256'],evidence_refs=[str(root/'report.json')])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')
