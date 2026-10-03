"""Read-only production storage isolation preflight."""
import argparse
import os
from deploy.recovery_journal import safe_path


def validate(production, staging='/srv/mldsafail-evaluator'):
    production, staging = safe_path(production), safe_path(staging)
    if production.is_relative_to(staging) or staging.is_relative_to(production):
        raise ValueError('Production and staging evaluator roots overlap')
    return production


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-root', default=os.environ.get('PRODUCTION_EVALUATOR_ROOT'))
    parser.add_argument('--staging-root', default='/srv/mldsafail-evaluator')
    args = parser.parse_args()
    if not args.production_root:
        parser.error('PRODUCTION_EVALUATOR_ROOT required')
    validate(args.production_root, args.staging_root)
