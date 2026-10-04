"""Verify two completed, separately provisioned native operator activations.

The operator invokes the fixed lifecycle fixture in two actual delegated user
units before this read-only gate. This verifier never activates a service and
does not accept two calls within one surviving controller domain as two units.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from deploy import owned_client, owned_daemon
from deploy.operator_activation import activation_lock


def assess(rows, source_commit, source_sha256):
    if len(rows) != 2:
        raise ValueError('Exactly two predeclared activation receipts required')
    domains = []
    epochs = []
    for row in rows:
        if (row.get('schema') != 'mldsafail.operator-activation-receipt.v1' or
            row.get('passed') is not True or row.get('cleanup_complete') is not True or
            row.get('job') != 'fixture' or row.get('native_cpu_gates_passed') is not False or
            row.get('source_commit') != source_commit or row.get('source_sha256') != source_sha256):
            raise RuntimeError('Exact source-bound completed fixture receipts required')
        domain = row['operator_domain']
        domains.append((domain['boot_id'], domain['device'], domain['inode']))
        epochs.append(row['daemon_epoch'])
    if domains[0] == domains[1] or epochs[0] == epochs[1] or rows[0]['driver_state'] == rows[1]['driver_state']:
        raise RuntimeError('Each actual activation needs a fresh controller and daemon epoch')
    if Path(rows[0]['driver_state']).parent.parent != Path(rows[1]['driver_state']).parent.parent:
        raise RuntimeError('Repeat activations must share the same serialized activation root')


def verify(paths, output):
    if sys.platform != 'linux':
        raise RuntimeError('Native Linux verification required')
    repository = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', '-C', str(repository), 'status', '--porcelain'], timeout=15):
        raise RuntimeError('Clean retained verifier source required')
    source = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], timeout=15).decode().strip()
    digest = hashlib.sha256((repository/'deploy/operator_activation.py').read_bytes()).hexdigest()
    rows = [owned_daemon.read_private_json(path) for path in paths]
    assess(rows, source, digest)
    root = owned_daemon._canonical(output)
    owned_daemon._private_directory(root.parent)
    root.mkdir(mode=0o700)
    clients = []
    report = dict(schema='mldsafail.repeat-activation-native.v1', passed=False,
                  native_executed=True, source_commit=source, source_sha256=digest,
                  receipts=[str(path) for path in paths], observations=[], cleanup_complete=False)
    def save():
        owned_daemon.publish(root/'ownership.json', dict(clients=clients, report=report))
    save()
    original = None
    errors = []
    try:
        activation_root = Path(rows[0]['driver_state']).parent.parent
        program = ('import sys,json\nsys.path.insert(0,sys.argv[1])\n'
                   'from deploy.operator_activation import activation_lock,ActivationContended\n'
                   'try:\n context=activation_lock(sys.argv[2]);context.__enter__()\n'
                   'except ActivationContended:\n print(json.dumps({"ownership_rejected":"activation_lock_contended"}));sys.exit(73)\n')
        with activation_lock(activation_root):
            rival = owned_client.run([sys.executable, '-c', program, str(repository), str(activation_root)],
                clients, save, root, timeout=15, capture_output=True, check=False)
            if rival.returncode != 73 or json.loads(rival.stdout) != {'ownership_rejected': 'activation_lock_contended'}:
                raise RuntimeError('Native independent process did not prove activation flock exclusivity')
        report['native_serialization_passed'] = True
        for row in rows:
            state = owned_daemon.read_private_json(row['driver_state'], cap=4*1024*1024)
            if (state.get('native_acceptance_passed') is not True or
                state.get('cleanup', {}).get('cleanup_complete') is not True or
                state['config']['source_commit'] != source or
                state['config']['acceptance_source_sha256'] != digest or
                state['registered_manifest']['epoch'] != row['daemon_epoch'] or
                state['registered_manifest']['worker_domain'] != row['worker_domain'] or
                state['provisioning']['operator_domain'] != row['operator_domain']):
                raise RuntimeError('Activation does not match completed immutable driver evidence')
            result = owned_client.run(['systemctl', '--user', 'show', row['operator_unit'],
                '--property=ActiveState', '--property=ControlGroup'], clients, save, root,
                timeout=15, capture_output=True)
            unit = dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line)
            if unit.get('ActiveState') not in {'inactive', 'failed'}:
                raise RuntimeError('An activation unit remains active')
            for domain in (row['operator_domain'], row['worker_domain'], state['registered_manifest']['domain']):
                if owned_client.verify_domain({'cgroup': domain}) is not None:
                    raise RuntimeError('An exact owned activation domain remains present')
            for client in state['clients']:
                if owned_client.verify_domain(client) is not None:
                    raise RuntimeError('An activation command client domain remains present')
            report['observations'].append(dict(operator_unit=row['operator_unit'], terminal=True,
                controller_absent=True, daemon_and_worker_absent=True, clients_absent=True))
            save()
    except BaseException as error:
        original = error
        report['failure_class'] = type(error).__name__
    finally:
        for client in clients:
            try:
                owned_client.stop(client)
            except BaseException as error:
                errors.append(type(error).__name__)
        report.update(cleanup_complete=not errors, cleanup_errors=errors,
                      passed=original is None and not errors and len(report['observations']) == 2)
        try:
            owned_daemon.publish(root/'report.json', report)
        except BaseException as error:
            if original is None:
                original = error
            else:
                original.add_note('Independent verification publication failed: '+type(error).__name__)
    if original is not None:
        raise original
    if not report['passed']:
        raise RuntimeError('Repeat activation verification cleanup incomplete')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify(args.receipt, args.output)
