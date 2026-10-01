"""Read-only in-container inspection. Output contains no raw private evidence."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from mldsafail.web.models import (ApiToken, EvaluationAttempt, EvaluationJob,
    ExperimentResult, GithubIdentity, IdempotencyKey, Submission, SubmissionTransition, User)
from mldsafail.benchmark_v050 import evidence as ev


def inspect(request):
    engine = create_engine(os.environ["MLDSAFAIL_DATABASE_URL"])
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        action = request["action"]
        if action == "lookup":
            item = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == request['key'],
                                                          IdempotencyKey.user_id == request['user']))
            return {'submission': item.submission_id if item else None}
        if action == "snapshot":
            rows = {}
            for model in (User, GithubIdentity, ApiToken, ExperimentResult):
                columns = [c for c in model.__table__.columns if c.name not in {"last_used_at", "updated_at"}]
                rows[model.__tablename__] = sorted(
                    [list(map(str, row)) for row in db.execute(select(*columns))])
            return {"digest": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
        if action == "identity":
            from mldsafail.evaluator.mlwe import HostedMLWE
            hosted = HostedMLWE(Path(os.environ['MLDSAFAIL_MLWE_EPOCH_PATH']),
                                os.environ['MLDSAFAIL_WORKER_IMAGE'], os.environ['MLDSAFAIL_MLWE_EPOCH_ID'])
            assert hosted.evaluator_fingerprint == os.environ['MLDSAFAIL_EVALUATOR_FINGERPRINT']
            return {"epoch_id": hosted.manifest['id'], "fingerprint": hosted.evaluator_fingerprint,
                    "worker": hosted.manifest['environment']['image_id']}
        if action == "active":
            active = db.scalars(select(EvaluationJob).where(
                EvaluationJob.status.in_(['queued', 'claimed', 'running']))).all()
            return {"active": [j.submission_id for j in active]}
        identifier = request.get('submission')
        if action == "state":
            submission = db.get(Submission, identifier)
            job = db.scalar(select(EvaluationJob).where(EvaluationJob.submission_id == identifier))
            attempts = db.scalars(select(EvaluationAttempt).where(EvaluationAttempt.job_id == job.id)
                                  .order_by(EvaluationAttempt.number)).all()
            transitions = db.scalars(select(SubmissionTransition).where(
                SubmissionTransition.submission_id == identifier).order_by(SubmissionTransition.created_at)).all()
            results = db.scalars(select(ExperimentResult).where(ExperimentResult.submission_id == identifier)).all()
            return {'state': submission.state, 'rejection_code': submission.rejection_code,
                    'job_status': job.status, 'attempt_count': job.attempts, 'max_attempts': job.max_attempts,
                    'available_at': job.available_at.isoformat(),
                    'lease_expires_at': job.lease_expires_at.isoformat() if job.lease_expires_at else None,
                    'attempts': [{'number': a.number, 'status': a.status, 'failure_class': a.failure_class,
                                  'started': a.started_at.isoformat(),
                                  'finished': a.finished_at.isoformat() if a.finished_at else None} for a in attempts],
                    'transitions': [t.to_state for t in transitions],
                    'results': [r.id for r in results]}
        if action in {'audit', 'timeout'}:
            epoch = Path(os.environ['MLDSAFAIL_MLWE_EPOCH_PATH'])
            em, reference = ev.audit_epoch(epoch)
            job = db.scalar(select(EvaluationJob).where(EvaluationJob.submission_id == identifier))
            run = Path(os.environ['MLDSAFAIL_EVALUATOR_WORK_ROOT']) / 'runs' / identifier / str(job.attempts)
            if action == 'timeout':
                if not (run / 'manifest.json').exists():
                    return {'timeout': False}
                partial = ev.partial_diagnostics(run, em)
                timed = [ev.read(p)['result'] for p in (run / 'records').glob('*.json')
                         if ev.read(p)['result']['status'] == 'timeout']
                assert all(r.get('timeout') and 60 <= r['evaluator_wall_seconds'] < 75 for r in timed)
                return {'timeout': bool(timed), 'partial_verified': partial['verified_records']}
            m, rows = ev.audit_run(run, epoch)
            summary = ev.summary(m, rows, reference)
            result = db.scalar(select(ExperimentResult).where(ExperimentResult.submission_id == identifier))
            if result:
                assert result.verified and result.diagnostics == summary and result.mlwe_score == summary['score']
            kind = request['kind']
            expected = {'crash': 'crash', 'invalid': 'invalid_answer', 'reference': 'success'}[kind]
            assert all(r['status'] == expected for row in rows for r in row['warmups'] + row['repetitions'])
            if kind == 'crash':
                from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS, case_cost
                import statistics
                costs = {r['instance_id']: case_cost(r) for r in reference}
                score = math.exp(statistics.mean(statistics.mean(math.log(60.0 / costs[r['instance_id']])
                        for r in rows if (r['profile'], r['eta']) == cell) for cell in CHALLENGE_CELLS))
                assert math.isclose(score, result.mlwe_score, rel_tol=1e-12)
            return {'evidence_verified': True, 'penalties_recomputed': kind == 'crash'}
        if action == 'privacy':
            epoch = Path(os.environ['MLDSAFAIL_MLWE_EPOCH_PATH'])
            em = ev.read(epoch / 'manifest.json')
            secret = ev.read(epoch / 'secret.json')
            text = request['text']
            assert secret['nonce'] not in text
            assert '/srv/mldsafail-evaluator' not in text
            assert not re.search(r'"(?:seed|nonce|candidate|s1|s2)"\s*:', text)
            assert all(not re.search(r'(?<![0-9])' + str(c['seed']) + r'(?![0-9])', text) for c in em['cases'])
            return {'private_material_absent': True}
        raise ValueError('Unknown read-only probe')


if __name__ == '__main__':
    try:
        print(json.dumps(inspect(json.load(sys.stdin))))
    except Exception:
        print('{"probe_failed":true}')
        sys.exit(1)
