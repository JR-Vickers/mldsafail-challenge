"""Offline review packet. No network, Docker, database or evaluation operations."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from mldsafail.evaluator.workload import ResourcePolicy
from deploy.workload_controls import SCENARIOS
from deploy.workload_deployment import inspected_commands, REQUIRED
from deploy.workload_preparation import bootstrap_commands, installed_commands
from deploy.workload_evidence import evidence_matrix
from deploy.workload_native_protocol import DEFAULT_SEQUENCE

FILES = (
    'src/mldsafail/evaluator/workload.py',
    'src/mldsafail/evaluator/runtime_io.py',
    'src/mldsafail/evaluator/workload_socket.py',
    'src/mldsafail/evaluator/workload_service.py',
    'src/mldsafail/evaluator/queue.py',
    'deploy/workload_policy.py',
    'deploy/production_maintenance.py',
    'docs/SINGLE_WORKLOAD_DEPLOYMENT.md',
)
BLOCKERS = (
    'separate_owner_authorization_for_native_control_acceptance_absent',
    'current_host_scheduling_delegation_services_socket_and_rollback_inspection_required',
    'matching_installed_runtime_configuration_native_acceptance_receipt_required',
    'matching_changed_evaluator_release_and_configuration_review_required',
)



def prepare(root, inspection=None, *, stage="bootstrap", bootstrap=None):
    if stage not in ("bootstrap", "installed", "legacy-v1"):
        raise ValueError("unknown_deployment_stage")
    root = Path(root)
    policy = ResourcePolicy()
    files = sorted({str(p.relative_to(root)) for folder in ('src', 'deploy', 'migrations')
                    for p in (root/folder).rglob('*.py')} | {'pyproject.toml', 'README.md', 'alembic.ini'} | set(FILES) | {str(path.relative_to(root)) for path in (root/'src/mldsafail/evaluator').glob('*.py')} |
                   {'deploy/investigation_docker.py', 'deploy/workload_controls.py', 'deploy/workload_units.py',
                    'deploy/workload_deployment.py', 'deploy/workload_preparation.py', 'deploy/workload_evidence.py',
                    'deploy/workload_release.py', 'deploy/workload_schedule_v3.py', 'deploy/workload_native_protocol.py',
                    'scripts/workload_host_inspection.py', 'scripts/workload_owner_collection.py', 'deploy/privileged_scheduling.py', 'scripts/prepare_workload_packet.py', 'deploy/protected_epoch.py', 'compose.production.yaml',
                    'deploy/start-coordinator.sh', 'scripts/production_epoch_operation.py', 'deploy/workload_inert.py',
                    'deploy/workload_native_acceptance.py', 'Dockerfile.coordinator', 'uv.lock',
                    'src/mldsafail/benchmark_v050/execution.py', 'src/mldsafail/benchmark_v050/Dockerfile',
                    'deploy/worker-linux-amd64.requirements.txt', 'scripts/workload_linux_fixture.py',
                    'docs/PLAN.md', 'docs/MVP_LAUNCH_PREPARATION.md', 'docs/PROTECTED_RUNTIME_OWNER_COLLECTION.md', 'docs/PRODUCTION_EPOCH_PROCEDURE.md'})
    deployment = None
    inspection_blockers = sorted(REQUIRED | ({'uid_mapping'} if stage == 'bootstrap' else {'installed'} if stage == 'installed' else set())) if inspection is None else []
    if inspection is not None:
        try:
            if stage == 'bootstrap':
                expected = {str(Path(inspection['installation']['release'])/name): hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
                if any(inspection['release_files'].get(name) != digest for name, digest in expected.items()):
                    raise ValueError('complete_frozen_release_manifest_required')
            if stage == 'bootstrap': deployment = bootstrap_commands(inspection)
            elif stage == 'installed':
                # Installed validation is bound to the approved proposal. The
                # operator checkout may have advanced since that release froze.
                deployment = installed_commands(inspection, bootstrap)
            else: deployment = inspected_commands(inspection)
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            inspection_blockers = [str(error)]
    packet = dict(schema=('mldsafail.workload-deployment-review.v1' if stage == 'legacy-v1' else 'mldsafail.workload-deployment-review.v2'),
                stage=stage, bootstrap=bootstrap if stage == 'installed' else None,
                control_evidence_matrix=evidence_matrix(),
                proposed_operation_schema='mldsafail.production-operation.v4',
                purpose='offline_engineering_review_only', state='maintenance_proposal',
                benchmark_version='0.5.0', capacity_disposition='unmeasured_capacity',
                execution_authority=False, resource_policy=asdict(policy),
                resource_policy_sha256=policy.sha256,
                source_hashes={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
                blockers=list(BLOCKERS), missing_inspection_fields=inspection_blockers, deployment=deployment,
                native_acceptance=dict(purpose='control_only_existing_vps_no_epoch_no_capacity_no_listener_no_computational_resume',
                    requires_separate_owner_authorization=True, timeout_seconds=180, sequence=DEFAULT_SEQUENCE,
                    fixture_memory_bytes=64*1024**2, fixture_pids=32,
                    expected_cases=SCENARIOS, retained_services_must_match_before_after=True,
                    pressure_scope='disposable_fixture_cgroups_only', restoration='leave_computational_scheduling_paused'))
    packet['release'] = dict(schema='mldsafail.workload-source-release.v1', benchmark_version='0.5.0',
                             source_hashes=packet['source_hashes'], resource_policy_sha256=policy.sha256)
    if inspection is not None:
        environment = inspection.get('worker_environment')
        if environment and set(environment) == {'image_id', 'trusted_fingerprint', 'artifacts', 'host'}:
            from mldsafail.benchmark_v050 import evidence as ev
            adapter = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((root/'src/mldsafail/evaluator').glob('*.py'))}
            packet['release']['environment'] = environment
            packet['release']['evaluator_fingerprint'] = ev.sha(dict(benchmark_version='0.5.0', environment=environment, settings=ev.SETTINGS, hosted_evaluator=adapter))
        else:
            packet['deployment'] = None
            packet['missing_inspection_fields'].append('complete_frozen_worker_environment')
    packet['release_sha256'] = hashlib.sha256(json.dumps(packet['release'], sort_keys=True).encode()).hexdigest()
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release-output', type=Path, help='Optional exclusive canonical source-release artifact')
    parser.add_argument('--unit-output', type=Path, help='Optional exclusive directory for inspected unit files')
    parser.add_argument('--stage', choices=('bootstrap', 'installed', 'legacy-v1'), default='bootstrap')
    parser.add_argument('--bootstrap', type=Path, help='Exact prior v2 deployment bootstrap proposal for installed validation')
    parser.add_argument('--inspection', type=Path, help='Owner-inspected host/service/delegation/socket/rollback record')
    args = parser.parse_args()
    inspection = json.loads(args.inspection.read_bytes()) if args.inspection else None
    bootstrap = json.loads(args.bootstrap.read_bytes()) if args.bootstrap else None
    if bootstrap is not None and bootstrap.get('schema') == 'mldsafail.workload-deployment-review.v2':
        if bootstrap.get('stage') != 'bootstrap' or bootstrap.get('deployment') is None:
            parser.error('--bootstrap must contain a complete bootstrap proposal')
        bootstrap = bootstrap['deployment']
    packet = prepare(Path(__file__).resolve().parents[1], inspection, stage=args.stage, bootstrap=bootstrap)
    if args.release_output:
        with args.release_output.open('x') as stream:
            args.release_output.chmod(0o600)
            stream.write(json.dumps(packet['release'], sort_keys=True))
    if args.unit_output:
        if packet['deployment'] is None: parser.error('--unit-output requires complete inspected identities')
        args.unit_output.mkdir(mode=0o700)
        for name, contents in packet['deployment']['units'].items():
            with (args.unit_output/name).open('x') as stream:
                (args.unit_output/name).chmod(0o600); stream.write(contents)
    # Exclusive publication; never overwrite a historical packet.
    with args.output.open('x') as stream:
        args.output.chmod(0o600)
        json.dump(packet, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__': main()
