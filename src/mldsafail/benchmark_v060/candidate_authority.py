"""Explicit disposable native rehearsal authority; never contract adoption."""
from dataclasses import dataclass
from pathlib import Path
from deploy import owned_daemon


@dataclass(frozen=True)
class CandidateRehearsalAuthority:
    prerequisite_path: Path
    epoch_manifest_path: Path
    source_commit: str
    supervisor_source_sha256: str
    worker_image: str
    epoch_id: str
    cohort_id: str
    contract_adopted: bool = False

    def require(self):
        if self.contract_adopted is not False:
            raise ValueError('Candidate authority cannot claim contract adoption')
        from research.mlwe_v060_preparation.native_acceptance import require_prerequisites
        epoch=owned_daemon.read_private_json(self.epoch_manifest_path,cap=4*1024*1024)
        if (epoch.get('schema')!='mldsafail.mlwe-v060-epoch-draft.v1'
                or epoch.get('benchmark_version')!='0.6.0' or epoch.get('epoch_id')!=self.epoch_id
                or epoch.get('worker_artifact',{}).get('image')!=self.worker_image
                or epoch['worker_artifact'].get('source_commit')!=self.source_commit
                or epoch.get('cohort',{}).get('evaluator_fingerprint')!=self.supervisor_source_sha256):
            raise ValueError('Candidate authority source/image/fresh epoch mismatch')
        require_prerequisites(self.prerequisite_path,supervisor_source_sha256=self.supervisor_source_sha256,
            worker_image=self.worker_image,worker_context_sha256=epoch['worker_artifact'].get('source_context_sha256'),
            worker_source_commit=self.source_commit)
        from mldsafail.benchmark_versions import Cohort
        if Cohort(**epoch['cohort']).public_id!=self.cohort_id:
            raise ValueError('Candidate authority cohort mismatch')

    def require_private(self, private_rehearsal):
        if private_rehearsal is not True:
            raise ValueError('Candidate authority requires explicit disposable rehearsal scope')
        self.require()
