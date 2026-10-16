"""Private application config with no epochs, host paths or accounting secrets."""
import json
import os
from pathlib import Path
import stat
from mldsafail.benchmark_versions import Cohort,RegisteredBackend,VersionRegistry
from candidate_runtime.client import RemoteCandidateAuthority,evaluate


def load(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or not 0<info.st_size<=65536:
            raise ValueError('Private bounded application configuration required')
        block=os.read(descriptor,65537)
    finally:os.close(descriptor)
    value=json.loads(block)
    if set(value)!={'schema','candidate_only','database_url','gateway_socket','cohort','session_secret','signing_key_hex','work_root'} or value['schema']!='mldsafail.private-candidate-application.v1' or value['candidate_only'] is not True:
        raise ValueError('Explicit private candidate configuration required')
    if not isinstance(value['database_url'],str) or not value['database_url'].startswith('postgresql+psycopg://'):
        raise ValueError('Disposable PostgreSQL URL required')
    if not isinstance(value['session_secret'],str) or len(value['session_secret'])<32 or len(bytes.fromhex(value['signing_key_hex']))<32:
        raise ValueError('Fresh synthetic application secrets required')
    if value['gateway_socket']!='/candidate/gateway/candidate.sock' or value['work_root']!='/candidate/work':
        raise ValueError('Fixed private container mount paths required')
    cohort=Cohort(**value['cohort'])
    if cohort.benchmark_version!='0.6.0':raise ValueError('Candidate protocol0.6 only')
    authority=RemoteCandidateAuthority(value['gateway_socket'],cohort)
    registry=VersionRegistry([RegisteredBackend(cohort,lambda job:dict(benchmark_version='0.6.0',**{
        name:getattr(cohort,name) for name in ('epoch_id','evaluator_fingerprint','hidden_suite_version','worker_class')}),authority,private_rehearsal=True)])
    return value,cohort,authority,registry


def web(path):
    from mldsafail.web.app import create_app
    value,cohort,authority,registry=load(path)
    return create_app(config_name='test',config=dict(DATABASE_URL=value['database_url'],SECRET_KEY=value['session_secret'],
        BENCHMARK_VERSION='0.5.0',MLWE_EPOCH_ID='private-compatibility-only',EVALUATOR_FINGERPRINT='0'*64,
        HIDDEN_SUITE_VERSION='private-v050',WORKER_CLASS='private-v050',BENCHMARK_VERSION_REGISTRY=registry,
        V060_PRIVATE_CANDIDATE_REHEARSAL=True,V060_DEFAULT_APPROVED=False))


def coordinator(path):
    from sqlalchemy import create_engine
    from mldsafail.benchmark_v060.coordinator import Coordinator
    value,cohort,authority,_=load(path);engine=create_engine(value['database_url'])
    try:
        def run_source(source,checkpoint):
            import uuid
            from sqlalchemy import select
            from sqlalchemy.orm import Session
            from mldsafail.web.models import EvaluationJob,EvaluationAttempt
            from candidate_runtime.client import source_files,source_digest
            with Session(engine) as database:
                jobs=list(database.scalars(select(EvaluationJob).where(EvaluationJob.lease_owner==worker.worker_id,EvaluationJob.status=='running')))
                if len(jobs)!=1:raise RuntimeError('Exactly one owned running job required')
                job=jobs[0]
                attempt=database.scalar(select(EvaluationAttempt).where(EvaluationAttempt.job_id==job.id,EvaluationAttempt.number==job.attempts))
                if attempt is None:raise RuntimeError('Owned evaluation attempt missing')
                binding=dict(job_id=job.id,submission_id=job.submission_id,cohort_id=cohort.public_id,source_sha256=source_digest(source_files(source)))
                return evaluate(value['gateway_socket'],source,checkpoint,binding=binding,
                    request_directory=Path(value['work_root'])/'.gateway-requests',attempt_id=attempt.id)
        worker=Coordinator(engine=engine,cohort=cohort,gates=authority,private_rehearsal=True,
            work_root=value['work_root'],evaluate_source=run_source,
            signing_key=bytes.fromhex(value['signing_key_hex']))
        return worker.run_once()
    finally:engine.dispose()
