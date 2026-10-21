"""Offline review packet. No network, Docker, database or evaluation operations."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from mldsafail.evaluator.workload import ResourcePolicy

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
    'native_runtime_helper_and_systemd_cleanup_integration_missing',
    'coordinator_and_administrative_launch_routing_missing',
    'native_common_cgroup_and_accounting_acceptance_missing',
    'bounded_runtime_io_and_supervisor_death_acceptance_missing',
    'postgres_and_container_contention_acceptance_missing',
    'new_hosted_fingerprint_release_and_epoch_bindings_missing',
    'deployed_scheduling_and_delegation_unverified',
    'exact_transfer_restoration_and_rollback_identities_unverified',
    'separately_scoped_owner_authorization_absent',
)


def prepare(root):
    root = Path(root)
    policy = ResourcePolicy()
    return dict(schema='mldsafail.workload-deployment-review.v1',
                proposed_operation_schema='mldsafail.production-operation.v4',
                purpose='offline_engineering_review_only', state='maintenance_proposal',
                benchmark_version='0.5.0', capacity_disposition='unmeasured_capacity',
                execution_authority=False, resource_policy=asdict(policy),
                resource_policy_sha256=policy.sha256,
                source_hashes={name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FILES},
                blockers=list(BLOCKERS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    packet = prepare(Path(__file__).resolve().parents[1])
    # Exclusive publication; never overwrite a historical packet.
    with args.output.open('x') as stream:
        args.output.chmod(0o600)
        json.dump(packet, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__': main()
