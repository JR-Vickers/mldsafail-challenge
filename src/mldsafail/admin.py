"""Restricted operational administration commands."""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mldsafail.web.models import GithubIdentity, User


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-admin",))
    parser.add_argument("--github-subject", required=True, help="stable numeric GitHub user ID")
    parser.add_argument("--login", required=True)
    args = parser.parse_args(argv)
    if not args.github_subject.isdigit():
        parser.error("--github-subject must be GitHub's stable numeric user ID")
    with Session(create_engine(os.environ["MLDSAFAIL_DATABASE_URL"])) as database:
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
