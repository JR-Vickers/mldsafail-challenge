"""Verify evidence referenced by an isolated restored database; never use live DB."""
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob, ExperimentResult
from mldsafail.benchmark_v050 import evidence as ev


def verify(database_url, epoch: Path, runs: Path):
    manifest, reference = ev.audit_epoch(epoch)
    count = 0
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            for result in session.scalars(select(ExperimentResult)):
                if result.benchmark_version != '0.5.0':
                    raise ValueError('Recovery cohort contains historical evidence; separate verifier required')
                job = session.scalar(select(EvaluationJob).where(EvaluationJob.submission_id == result.submission_id))
                if not job or result.epoch_id != manifest['id']:
                    raise ValueError('Restored database epoch/attempt mismatch')
                run_manifest, rows = ev.audit_run(runs / result.submission_id / str(job.attempts), epoch)
                summary = ev.summary(run_manifest, rows, reference)
                if not result.verified or result.diagnostics != summary or result.mlwe_score != summary['score']:
                    raise ValueError('Restored evidence/result mismatch')
                count += 1
    finally:
        engine.dispose()
    return {'database_evidence_verified': True, 'result_count': count, 'epoch_id': manifest['id']}
