"""Read-only production configuration checks; never emit configuration values."""
import argparse
import ipaddress
import os
import re
from urllib.parse import urlsplit
from pathlib import Path

from deploy.validate_production import validate

IMAGES = ('WEB_IMAGE', 'COORDINATOR_IMAGE', 'WORKER_IMAGE', 'CADDY_IMAGE', 'POSTGRES_IMAGE')
SECRETS = ('POSTGRES_PASSWORD', 'MLDSAFAIL_SECRET_KEY', 'GITHUB_CLIENT_SECRET')
IDENTITIES = ('MLDSAFAIL_MLWE_EPOCH_ID', 'MLDSAFAIL_HIDDEN_SUITE_VERSION')
REQUIRED = IMAGES + SECRETS + IDENTITIES + (
    'GITHUB_CLIENT_ID', 'MLDSAFAIL_DOMAIN', 'ROOTLESS_DOCKER_SOCKET', 'WORKLOAD_SUPERVISOR_ROOT',
    'PRODUCTION_TLS_ROOT', 'PRODUCTION_ACME_WEBROOT',
    'PRODUCTION_EVALUATOR_ROOT', 'MLDSAFAIL_EVALUATOR_FINGERPRINT', 'MLDSAFAIL_WORKER_CLASS',
)


def check(environment, staging, *, preparation=False):
    """Return fixed diagnostic codes. A passing result is not activation approval."""
    errors = []
    for key in REQUIRED:
        if preparation and key == 'MLDSAFAIL_MLWE_EPOCH_ID' and key not in environment:
            continue
        value = environment.get(key, '')
        if not value or any(marker in value.upper() for marker in ('CHANGE_ME', 'PLACEHOLDER')):
            errors.append('missing_or_placeholder:' + key)
    for key in IMAGES:
        if not re.fullmatch(r'(?:sha256:[a-f0-9]{64}|[^\s@]+@sha256:[a-f0-9]{64})', environment.get(key, '')):
            errors.append('immutable_image_required:' + key)
    # Compose embeds the password directly in a PostgreSQL URL. Require
    # unreserved ASCII rather than allowing delimiter/interpolation ambiguity.
    if not re.fullmatch(r'[A-Za-z0-9._~-]+', environment.get('POSTGRES_PASSWORD', '')):
        errors.append('url_safe_database_password_required')
    for key in SECRETS + IDENTITIES:
        if environment.get(key) and environment.get(key) == staging.get(key):
            errors.append('staging_reuse:' + key)
    domain = environment.get('MLDSAFAIL_DOMAIN', '')
    try:
        address = ipaddress.ip_address(domain)
        valid_domain = (address.version == 4 and address.is_global
                        and not address.is_multicast and not address.is_reserved)
    except ValueError:
        valid_domain = bool(re.fullmatch(r'(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', domain))
        valid_domain = valid_domain and '.' in domain and all(
            re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
            for label in domain.split('.')
        ) and not domain.endswith(('.localhost', '.invalid', '.example'))
    if not valid_domain:
        errors.append('production_origin_host_required')
    origin = environment.get('PRODUCTION_ORIGIN', 'https://' + domain)
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or parsed.netloc != domain or
            parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
        errors.append('trusted_https_origin_required')
    if environment.get('MLDSAFAIL_BENCHMARK_VERSION') not in {'0.5.0', '0.6.0'}:
        errors.append('explicit_supported_benchmark_required')
    try:
        validate(environment.get('PRODUCTION_EVALUATOR_ROOT', ''),
                 staging.get('EVALUATOR_WORK_DIR', '/srv/mldsafail-evaluator'))
    except ValueError:
        errors.append('evaluator_storage_not_isolated')
    socket = environment.get('ROOTLESS_DOCKER_SOCKET', '')
    if not re.fullmatch(r'/run/user/[1-9][0-9]*/docker.sock', socket):
        errors.append('rootless_socket_required')
    supervisor_root = Path(environment.get('WORKLOAD_SUPERVISOR_ROOT', ''))
    if not supervisor_root.is_absolute() or '..' in supervisor_root.parts or len(str(supervisor_root/'supervisor.sock')) >= 108:
        errors.append('private_workload_supervisor_root_required')
    for key in ('MLDSAFAIL_OUTSTANDING_PER_ACCOUNT', 'MLDSAFAIL_SUBMISSIONS_PER_DAY', 'MLDSAFAIL_QUEUED_GLOBALLY'):
        value = environment.get(key, {'MLDSAFAIL_OUTSTANDING_PER_ACCOUNT': '1', 'MLDSAFAIL_SUBMISSIONS_PER_DAY': '2', 'MLDSAFAIL_QUEUED_GLOBALLY': '10'}[key])
        if not re.fullmatch(r'[1-9][0-9]*', value):
            errors.append('positive_admission_limit_required:' + key)
    return errors


def read_private_env(path):
    path = Path(path)
    if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
            or path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid()
            or path.stat().st_nlink != 1 or path.parent.stat().st_mode & 0o077
            or path.parent.stat().st_uid != os.getuid()):
        raise ValueError('private_env_permissions_required')
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in result:
            raise ValueError('invalid_private_env_format')
        # Plain values only: do not execute, interpolate, or silently reinterpret.
        if value != value.strip() or any(character in value for character in ('$', '`', '"', "'")):
            raise ValueError('literal_private_env_values_required')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production-env', required=True)
    parser.add_argument('--staging-env', required=True)
    parser.add_argument('--preparation', action='store_true')
    parser.add_argument('--preparation-manifest', type=Path, required=True)
    parser.add_argument('--inspection-receipt', type=Path, required=True)
    args = parser.parse_args()
    try:
        environment = read_private_env(args.production_env)
        errors = check(environment, read_private_env(args.staging_env), preparation=args.preparation)
        if args.preparation_manifest:
            from deploy.production_preparation import check_manifest, read_manifest
            errors += check_manifest(environment, read_manifest(args.preparation_manifest), preparation=args.preparation)
        from deploy.production_receipts import validate_receipt, render
        errors += validate_receipt(environment, args.production_env, args.inspection_receipt, preparation=args.preparation)
        if not errors:
            errors += render(environment, preparation=args.preparation)
    except (ValueError, OSError, TypeError, KeyError):
        errors = ['private_configuration_unreadable_or_invalid']
    for error in errors:
        print(error)
    if not errors:
        if args.preparation:
            print('unresolved_dependency:MLDSAFAIL_MLWE_EPOCH_ID')
            print('preparation_checks_passed_full_readiness_pending_epoch')
        else:
            print('configuration_preflight_passed_activation_not_authorized')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
