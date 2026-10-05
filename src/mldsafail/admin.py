"""Restricted operational administration commands."""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mldsafail.web.models import ApiToken, GithubIdentity, Submission, SubmissionState, User
from mldsafail.web.services import DomainError, audit, cancel_submission, evaluation_transaction_lock, revoke_token


def moderate(database: Session, subject: str, command: str, identifier: str) -> bool:
    """Privileged local DB operation, attributed to an existing administrator.

    Database access is the operator authentication boundary. The subject is an
    audit attribution, never a substitute for that access or a public API.
    """
    identity = database.scalar(select(GithubIdentity).where(
        GithubIdentity.github_subject == subject).with_for_update())
    if identity is None or not identity.user.is_admin:
        raise DomainError('administrator_required', 'Existing administrator required.', 403)
    actor = identity.user
    if command == 'revoke-token':
        item = database.get(ApiToken, identifier, with_for_update=True)
        if item is None:
            raise DomainError('not_found', 'Token not found.', 404)
        if item.revoked_at is not None:
            return False
        audit(database, 'admin.api_token.revoked', actor.id, token_id=item.id,
              affected_user_id=item.user_id)
        revoke_token(database, item, database.get(User, item.user_id))
    elif command == 'cancel-submission':
        evaluation_transaction_lock(database)
        item = database.get(Submission, identifier, with_for_update=True)
        if item is None:
            raise DomainError('not_found', 'Submission not found.', 404)
        if item.state == SubmissionState.CANCELLED.value or item.cancel_requested:
            return False
        audit(database, 'admin.submission.cancellation_requested', actor.id,
              submission_id=item.id, affected_user_id=item.user_id)
        cancel_submission(database, item)
    else:
        raise ValueError('Fixed administrative operation required')
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-admin", "revoke-token", "cancel-submission"))
    parser.add_argument("--github-subject", required=True, help="stable numeric GitHub user ID")
    parser.add_argument("--login")
    parser.add_argument("--id", help="exact database record identifier for moderation")
    args = parser.parse_args(argv)
    if not args.github_subject.isdigit():
        parser.error("--github-subject must be GitHub's stable numeric user ID")
    if args.command == 'bootstrap-admin' and not args.login:
        parser.error('--login is required for bootstrap-admin')
    if args.command != 'bootstrap-admin' and not args.id:
        parser.error('--id is required for moderation')
    with Session(create_engine(os.environ["MLDSAFAIL_DATABASE_URL"])) as database:
        if args.command != 'bootstrap-admin':
            changed = moderate(database, args.github_subject, args.command, args.id)
            database.commit()
            print('Administrative operation completed.' if changed else 'Already reconciled.')
            return 0
        identity = database.scalar(select(GithubIdentity).where(GithubIdentity.github_subject == args.github_subject))
        if identity:
            user = identity.user
        else:
            user = User(display_name=args.login, is_admin=True)
            database.add(user); database.flush()
            database.add(GithubIdentity(user_id=user.id, github_subject=args.github_subject, login=args.login))
        user.is_admin = True; database.commit()
        print(f"Administrator enabled for GitHub subject {args.github_subject}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
