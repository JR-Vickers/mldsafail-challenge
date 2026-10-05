"""Private operator controls; never confer administrator access on participants."""
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from mldsafail.admin import moderate
from mldsafail.web.models import Base, User, GithubIdentity, AuditEvent, EvaluationJob
from mldsafail.web.services import create_api_token, create_submission, verify_api_token, DomainError


def exercise(engine):
    with Session(engine) as db:
        prior_users=db.scalar(select(func.count()).select_from(User))
        actor=User(display_name='synthetic operator',is_admin=True)
        participant=User(display_name='synthetic participant')
        db.add_all([actor,participant]);db.flush()
        db.add_all([GithubIdentity(user_id=actor.id,github_subject='900001',login='operator'),
            GithubIdentity(user_id=participant.id,github_subject='900002',login='participant')]);db.commit()
        credential,secret=create_api_token(db,participant,'synthetic administrative test')
        submission,_=create_submission(db,participant,dict(repository_url='https://github.com/example/synthetic',
            commit_sha='a'*40,hypothesis='disposable control test',benchmark_version='0.4.0'),'admin-test')
        with pytest.raises(DomainError) as denied:moderate(db,'900002','revoke-token',credential.id)
        assert denied.value.status==403;db.rollback()
        assert verify_api_token(db,secret) is not None
        assert moderate(db,'900001','revoke-token',credential.id)
        assert not moderate(db,'900001','revoke-token',credential.id)
        db.commit();assert verify_api_token(db,secret) is None
        assert moderate(db,'900001','cancel-submission',submission.id)
        assert not moderate(db,'900001','cancel-submission',submission.id)
        db.commit()
        job=db.scalar(select(EvaluationJob).where(EvaluationJob.submission_id==submission.id))
        assert job.status=='complete'
        events=list(db.scalars(select(AuditEvent).where(AuditEvent.event_type.like('admin.%'))))
        assert len(events)==2 and all(event.user_id==actor.id for event in events)
        assert db.scalar(select(func.count()).select_from(User))==prior_users+2


def test_existing_administrator_can_revoke_and_cancel_with_idempotent_actor_audit(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'operator.db'));Base.metadata.create_all(engine)
    try:exercise(engine)
    finally:engine.dispose()
