"""Native-only fault-injection gate on an isolated delegated accounting parent.

Never invoke on staging's worker/epoch parent. Read/cleanup faults are injected at
trusted host interfaces while Docker execution and domain cleanup remain native.
All failed and partial generations are retained; every case explicitly reconciles
before the next. This supplements, and does not replace, the 30-pair suite.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from research.cpu_measurement import harness
from research.cpu_measurement.ownership import Ownership, canonical_directory, publish
from research.cpu_measurement.reconcile import reconcile
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.verify import verify_candidate


def execute(args):
    directory = canonical_directory(args.parent)
    instance = generate_mlwe('small', 0, 1).public
    source = Path(__file__).parent / 'fixtures' / 'child'
    results = []
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    original_fields = harness.fields
    original_run = harness.subprocess.run
    baseline = harness.run(args.image, args.parent, args.cgroup_parent, source, instance.to_dict(),
                           lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                           ownership_directory=directory)
    publish(args.output / 'baseline.json', baseline)
    if baseline['status'] != 'no_answer' or baseline['cleanup_complete'] is not True or baseline['authoritative_cpu_usec'] <= 0:
        raise RuntimeError('Native baseline did not establish expected execution/membership/cleanup')
    cases = ('missing_counter', 'regressing_counter', 'membership_failure', 'cleanup_failure', 'competing_owner', 'delegation', 'contamination')
    for fault in cases:
        calls = 0
        injected = False
        def faulty_fields(path):
            nonlocal calls, injected
            value = original_fields(path)
            if path.name == 'cpu.stat':
                calls += 1
                if fault == 'missing_counter' and calls > 1:
                    injected = True
                    raise OSError('Injected native counter read failure')
                if fault == 'regressing_counter' and calls > 1:
                    injected = True
                    value['usage_usec'] = -1
            return value
        def faulty_command(argv, **kwargs):
            nonlocal injected
            if fault == 'cleanup_failure' and argv[:3] == ['docker', 'rm', '-f']:
                injected = True
                raise OSError('Injected native container cleanup failure')
            return original_run(argv, **kwargs)
        holder = None
        intruder = None
        cleanup_errors = []
        foreign = args.parent / "cpu-native-contamination"
        try:
            if fault == 'competing_owner':
                holder = Ownership(directory, args.parent)
                holder.__enter__()
                injected = True
            with patch.object(harness, 'fields', faulty_fields), patch.object(harness.subprocess, 'run', faulty_command):
                if fault in {'membership_failure', 'delegation', 'contamination'}:
                    def mismatch(*values):
                        nonlocal injected, intruder
                        if fault == 'delegation':
                            original_delegation(*values)
                            injected = True
                            raise RuntimeError('Injected native delegation rejection')
                        original_membership(*values)
                        if fault == 'contamination':
                            foreign.mkdir()
                            intruder = subprocess.Popen(['sleep', '60'])
                            (foreign / 'cgroup.procs').write_text(str(intruder.pid))
                            injected = True
                        else:
                            injected = True
                            raise RuntimeError('Injected membership mismatch')
                    original_membership = harness.prove_membership
                    original_delegation = harness.validate_delegation
                    target = 'validate_delegation' if fault == 'delegation' else 'prove_membership'
                    with patch.object(harness, target, side_effect=mismatch):
                        harness.run(args.image, args.parent, args.cgroup_parent, source, instance.to_dict(),
                                    lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                                    ownership_directory=directory)
                else:
                    harness.run(args.image, args.parent, args.cgroup_parent, source, instance.to_dict(),
                                lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                                ownership_directory=directory)
            result = dict(fault=fault, passed=False, error='Fault unexpectedly produced measurement')
        except Exception as error:
            marker = {'missing_counter': 'Injected native counter read failure',
                      'regressing_counter': 'Accounting counter regressed',
                      'membership_failure': 'Injected membership mismatch',
                      'cleanup_failure': 'Injected native container cleanup failure',
                      'delegation': 'Injected native delegation rejection',
                      'contamination': 'Unauthorized accounting domain member'}
            expected = isinstance(error, BlockingIOError) if fault == 'competing_owner' else marker[fault] in str(error)
            result = dict(fault=fault, passed=injected and expected, injection_reached=injected,
                          expected_failure=expected, error_type=type(error).__name__, error=str(error))
        finally:
            if intruder is not None:
                for step, action in [('intruder_kill', lambda: intruder.kill() if intruder.poll() is None else None),
                                     ('intruder_wait', lambda: intruder.wait(timeout=10)),
                                     ('foreign_cgroup_remove', foreign.rmdir)]:
                    try:
                        action()
                    except Exception as error:
                        cleanup_errors.append(dict(step=step, error=repr(error)))
            if holder is not None:
                try:
                    holder.__exit__(RuntimeError, RuntimeError('Competing-owner probe complete'), None)
                except Exception as error:
                    cleanup_errors.append(dict(step='competing_owner_release', error=repr(error)))
        # Preserve the probe receipt even if independent reconciliation fails.
        result['independent_cleanup_errors'] = cleanup_errors
        publish(args.output / (fault + '.json'), result)
        try:
            cleanup = reconcile(directory, args.parent)
        except Exception as error:
            cleanup = dict(cleanup_complete=False, error_type=type(error).__name__, error=str(error))
        result['cleanup'] = cleanup
        result['passed'] = result['passed'] and cleanup['cleanup_complete'] and not cleanup_errors
        publish(args.output / (fault + '.json'), result)
        results.append(result)
        if cleanup_errors or not cleanup['cleanup_complete']:
            break  # Conflicting work is prohibited until explicit repair.
    if all(row['passed'] for row in results):
        from research.cpu_measurement.native_lifecycle import lifecycle
        try:
            from research.cpu_measurement.native_birth import probe
            results.append(probe(args, args.output / 'birth_gap.json'))
            results.extend(lifecycle(args, args.output / 'lifecycle'))
            from research.cpu_measurement.native_loss import probe as lost_mutation
            for operation in ('create','start'):
                results.append(lost_mutation(args,args.output/('lost_'+operation+'_ack.json'),operation=operation,api_version=args.api_version))
            results.append(grandchild_probe(args, directory, instance))
            publish(args.output / 'grandchild_membership.json', results[-1])
        except Exception as error:
            failure = dict(fault='lifecycle_or_descendant_probe', passed=False, error_type=type(error).__name__, error=str(error))
            publish(args.output / 'lifecycle_failure.json', failure)
            results.append(failure)
    summary = dict(schema='mldsafail.cpu-native-fault.v1', native_executed=True,
                   passed=len(results) == len(cases) + 6 and all(row['passed'] for row in results),
                   cases=results, remaining_native_faults=[])

    summary['contract_fault_gate_passed'] = summary['passed']
    publish(args.output / 'report.json', summary)
    return summary


def grandchild_probe(args, directory, instance):
    original = harness.prove_exclusive
    witnesses = {}
    def observe(parent, authorized):
        original(parent, authorized)
        for path in [authorized / 'cgroup.procs', *authorized.rglob('cgroup.procs')]:
            try:
                members = path.read_text().split()
            except FileNotFoundError:
                if not path.parent.exists():
                    continue
                raise
            for text in members:
                pid = int(text)
                try:
                    harness.prove_membership(pid, parent)
                    fields = (Path('/proc') / text / 'stat').read_text().rpartition(')')[2].split()
                    witness = dict(pid=pid, parent_pid=int(fields[1]), start_ticks=int(fields[19]),
                                   cpu_ticks=int(fields[11]) + int(fields[12]))
                    key = (pid, witness['start_ticks'])
                    if key not in witnesses or witness['cpu_ticks'] > witnesses[key]['cpu_ticks']:
                        witnesses[key] = witness
                except FileNotFoundError:
                    pass  # An exited process is not descendant accounting proof.
    with patch.object(harness, 'prove_exclusive', side_effect=observe):
        result = harness.run(args.image, args.parent, args.cgroup_parent,
                             Path(__file__).parent / 'fixtures' / 'grandchild', instance.to_dict(),
                             lambda public, candidate: verify_candidate(instance, candidate)['verified'],
                             ownership_directory=directory)
    worker = result['membership'][0]['worker_pid']
    children = {row['pid'] for row in witnesses.values() if row['parent_pid'] == worker}
    grandchildren = [row for row in witnesses.values() if row['parent_pid'] in children]
    ticks = sum(row['cpu_ticks'] for row in witnesses.values() if row['pid'] != worker)
    accounted = result['authoritative_cpu_usec'] >= ticks * 1_000_000 / os.sysconf('SC_CLK_TCK')
    return dict(fault='grandchild_membership', passed=result['status'] == 'no_answer' and
                any(row['cpu_ticks'] > 0 for row in grandchildren) and accounted,
                generation=result['generation'], witnesses=list(witnesses.values()),
                cpu_lower_bound_usec=ticks * 1_000_000 / os.sysconf('SC_CLK_TCK'),
                authoritative_cpu_usec=result['authoritative_cpu_usec'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--cgroup-parent', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--api-version', required=True, help='Predeclared supported dedicated Docker API version for fault-only CLI shim')
    args = parser.parse_args()
    report = execute(args)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
