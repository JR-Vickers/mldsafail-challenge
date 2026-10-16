"""Trusted-host contestant path, disabled unless explicitly instantiated.

The caller owns the dedicated delegated parent and private evidence directory.
Infrastructure exceptions propagate without a score or replacement invocation.
"""
from pathlib import Path
from mldsafail.benchmark_versions import IntegrationGates
from research.cpu_measurement import audit, harness
from research.cpu_measurement.ownership import canonical_directory


class HostBackend:
    def __init__(self, *, image, parent, cgroup_parent, epoch_id, gates, private_rehearsal=False):
        from .candidate_authority import CandidateRehearsalAuthority
        if isinstance(gates,CandidateRehearsalAuthority):
            gates.require_private(private_rehearsal)
            if gates.worker_image!=image or gates.epoch_id!=epoch_id: raise ValueError('Candidate backend authority mismatch')
        elif not isinstance(gates, IntegrationGates):
            raise ValueError('Explicit integration gates required')
        gates.require()
        self.image, self.parent = image, Path(parent)
        self.cgroup_parent, self.epoch_id = cgroup_parent, epoch_id
        self.directory = canonical_directory(self.parent)

    def evaluate_case(self, source, public_input, verify, checkpoint=lambda: None):
        records = []
        # Each invocation snapshots approved Python independently. The warmup
        # remains durable evidence but contributes no measured cost.
        for number in range(4):
            checkpoint()
            record = harness.run(self.image, self.parent, self.cgroup_parent,
                                 source, public_input, verify, timeout=60,
                                 ownership_directory=self.directory, epoch=self.epoch_id)
            audit.audit_journal(self.directory, record['generation'])
            if number:
                records.append(record)
        checkpoint()
        return {'decision': audit.case_cost(records), 'records': records}
