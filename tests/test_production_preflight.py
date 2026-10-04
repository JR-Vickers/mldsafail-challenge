import json
import os
import shutil
import subprocess

import pytest

from deploy.production_preflight import IMAGES, REQUIRED, check, read_private_env


def environments(tmp_path):
    production = {key: 'fresh-' + key for key in REQUIRED}
    production.update({key: 'registry/image@sha256:' + 'a' * 64 for key in IMAGES})
    production.update(PRODUCTION_EVALUATOR_ROOT=str(tmp_path / 'production'),
                      ROOTLESS_DOCKER_SOCKET='/run/user/1000/docker.sock',
                      MLDSAFAIL_DOMAIN='challenge.example.org')
    return production, {'EVALUATOR_WORK_DIR': str(tmp_path / 'staging')}


def test_configuration_isolation_and_failure_diagnostics(tmp_path):
    production, staging = environments(tmp_path)
    assert check(production, staging) == []
    staging['POSTGRES_PASSWORD'] = production['POSTGRES_PASSWORD']
    production['WEB_IMAGE'] = 'registry/image:latest'
    production['PRODUCTION_EVALUATOR_ROOT'] = str(tmp_path / 'staging/child')
    production['ROOTLESS_DOCKER_SOCKET'] = '/var/run/docker.sock'
    production['MLDSAFAIL_QUEUED_GLOBALLY'] = '0'
    errors = check(production, staging)
    assert 'staging_reuse:POSTGRES_PASSWORD' in errors
    assert 'immutable_image_required:WEB_IMAGE' in errors
    assert 'evaluator_storage_not_isolated' in errors
    assert 'rootless_socket_required' in errors
    assert 'positive_admission_limit_required:MLDSAFAIL_QUEUED_GLOBALLY' in errors
    assert all(production['POSTGRES_PASSWORD'] not in error for error in errors)


@pytest.mark.parametrize('domain', ['localhost', '127.0.0.1', 'https://example.org', 'bad..example.org', '-bad.example.org', 'host.invalid'])
def test_invalid_domain(tmp_path, domain):
    production, staging = environments(tmp_path)
    production['MLDSAFAIL_DOMAIN'] = domain
    assert 'production_dns_name_required' in check(production, staging)


def test_private_env_rejects_interpolation_permissions_and_duplicates(tmp_path):
    path = tmp_path / 'environment'
    path.write_text('SECRET=literal\n')
    path.chmod(0o600)
    assert read_private_env(path) == {'SECRET': 'literal'}
    for value in ('SECRET=$(touch /tmp/unwanted)\n', 'SECRET=a\nSECRET=b\n', 'SECRET= leading\n', 'SECRET=trailing \n'):
        path.write_text(value)
        with pytest.raises(ValueError):
            read_private_env(path)
    path.chmod(0o644)
    with pytest.raises(ValueError):
        read_private_env(path)


def test_switch_overlay_removes_migration_dependency(tmp_path):
    if not shutil.which('docker'):
        pytest.skip('Docker Compose unavailable')
    environment, _ = environments(tmp_path)
    result = subprocess.run(
        ['docker', 'compose', '-f', 'compose.production.yaml', '-f',
         'deploy/compose.application-switch.yaml', 'config', '--format', 'json'],
        env={**os.environ, **environment}, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)['services']
    for name in ('web', 'coordinator'):
        assert not services[name].get('depends_on')
        assert services[name]['environment']['MLDSAFAIL_SKIP_MIGRATIONS'] == '1'
    assert 'migrate' in services  # Still available for separately approved fresh setup.


@pytest.mark.parametrize('password', ['colon:password', 'user@host', 'hash#value', 'slash/value', 'query?value', 'encoded%20value'])
def test_password_url_delimiters_rejected(tmp_path, password):
    production, staging = environments(tmp_path)
    production['POSTGRES_PASSWORD'] = password
    assert 'url_safe_database_password_required' in check(production, staging)
