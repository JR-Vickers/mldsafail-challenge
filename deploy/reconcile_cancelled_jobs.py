"""Explicit repair of stale queued jobs for already cancelled submissions.

Run inside the deployed coordinator environment. Identities remain in the private
report; stdout contains only counts. Defaults to a rolled-back preview; --apply commits repair.
No schema changes, attempts, transitions, or deletions are performed.
"""
import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mldsafail.evaluator.queue import reconcile_cancelled_queued_jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True,
                        help='New private evidence file in an existing mode-0700 directory')
    args = parser.parse_args()
    parent = args.report.absolute().parent
    if parent.resolve() != parent or parent.stat().st_mode & 0o077:
        parser.error('report directory must be private and have no symlink components')
    # Reserve evidence before any database access; never overwrite prior history.
    descriptor = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    def record(value):
        # Append durable intent/outcome records. An interrupted commit is resolved
        # by reading database state and repeating with a new evidence path.
        os.write(descriptor, (json.dumps(value) + '\n').encode())
        os.fsync(descriptor)
    engine = None
    try:
        record({'stage': 'started', 'apply': args.apply})
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)
        with Session(engine) as session:
            affected = reconcile_cancelled_queued_jobs(session)
            record({'stage': 'prepared', 'jobs': [
                {'job_id': job, 'submission_id': submission} for job, submission in affected]})
            if args.apply:
                session.commit()
            else:
                session.rollback()
            record({'stage': 'committed' if args.apply else 'preview_rolled_back'})
            print(json.dumps({'applied': args.apply, 'affected_count': len(affected)}))
    finally:
        if engine is not None:
            engine.dispose()
        os.close(descriptor)


if __name__ == '__main__':
    main()
