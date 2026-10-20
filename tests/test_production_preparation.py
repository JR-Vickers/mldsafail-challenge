import json

import pytest

from deploy.production_preflight import check
from deploy.production_preparation import FINGERPRINT, IMAGES, SOURCE, ROLLBACK, check_manifest, read_manifest
from test_production_preflight import environments


def prepared(tmp_path):
    env, staging = environments(tmp_path)
    env.pop('MLDSAFAIL_MLWE_EPOCH_ID')
    env.update({k: 'sha256:' + v for k, v in IMAGES.items()})
    env.update(MLDSAFAIL_DOMAIN='178.128.17.58', PRODUCTION_ORIGIN='https://178.128.17.58',
               MLDSAFAIL_EVALUATOR_FINGERPRINT=FINGERPRINT,
               MLDSAFAIL_HIDDEN_SUITE_VERSION='mlwe-v050', MLDSAFAIL_WORKER_CLASS='rootless-docker-v1',
               POSTGRES_PASSWORD='a'*40, MLDSAFAIL_SECRET_KEY='b'*40,
               MLDSAFAIL_OUTSTANDING_PER_ACCOUNT='1', MLDSAFAIL_SUBMISSIONS_PER_DAY='2',
               MLDSAFAIL_QUEUED_GLOBALLY='10')
    manifest = dict(schema='mldsafail.production-preparation.v1', source=SOURCE, rollback=ROLLBACK,
                    project='mldsafail-production', images_locally_resolved=True,
                    unresolved={'MLDSAFAIL_MLWE_EPOCH_ID': 'future_independently_audited_epoch'},
                    retained_roots=[str(tmp_path/'retained')])
    return env, staging, manifest


def test_only_epoch_can_be_missing(tmp_path):
    env, staging, manifest = prepared(tmp_path)
    assert check(env, staging, preparation=True) == []
    assert check_manifest(env, manifest, preparation=True) == []
    assert 'missing_or_placeholder:MLDSAFAIL_MLWE_EPOCH_ID' in check(env, staging)
    assert 'epoch_binding_not_finalized' in check_manifest(env, manifest)
    for key in ('MLDSAFAIL_HIDDEN_SUITE_VERSION', 'MLDSAFAIL_WORKER_CLASS'):
        modified = {k:v for k,v in env.items() if k != key}
        assert 'missing_or_placeholder:' + key in check(modified, staging, preparation=True)
    env['MLDSAFAIL_MLWE_EPOCH_ID'] = 'pretend'
    assert 'preparation_epoch_must_be_absent' in check_manifest(env, manifest, preparation=True)


@pytest.mark.parametrize('key,value', [('WEB_IMAGE','image:latest'), ('WORKER_IMAGE','sha256:'+'f'*64),
    ('MLDSAFAIL_BENCHMARK_VERSION','0.6.0'), ('MLDSAFAIL_QUEUED_GLOBALLY','11')])
def test_selected_bindings(tmp_path, key, value):
    env, _, manifest = prepared(tmp_path)
    env[key] = value
    assert check_manifest(env, manifest, preparation=True)


def test_blockers_secrets_and_storage(tmp_path):
    env, staging, manifest = prepared(tmp_path)
    manifest.update(images_locally_resolved=False, blockers=['private details'])
    env['MLDSAFAIL_SECRET_KEY'] = env['POSTGRES_PASSWORD']
    env['PRODUCTION_TLS_ROOT'] = manifest['retained_roots'][0] + '/tls'
    errors = check_manifest(env, manifest, preparation=True)
    assert 'private_preparation_blockers_unresolved' in errors
    assert 'separate_secrets_required' in errors
    assert 'production_storage_overlap' in errors
    assert all('private details' not in e and env['POSTGRES_PASSWORD'] not in e for e in errors)
    staging['POSTGRES_PASSWORD'] = env['POSTGRES_PASSWORD']
    assert 'staging_reuse:POSTGRES_PASSWORD' in check(env, staging, preparation=True)


def test_private_manifest(tmp_path):
    directory = tmp_path/'private'
    directory.mkdir(mode=0o700)
    path = directory/'manifest.json'
    path.write_text(json.dumps({}))
    path.chmod(0o600)
    assert read_manifest(path) == {}
    path.chmod(0o644)
    with pytest.raises(ValueError):
        read_manifest(path)


def test_cli_requires_source_and_inspection_in_both_modes(monkeypatch):
    from deploy.production_preflight import main
    for extra in ([], ['--preparation']):
        monkeypatch.setattr('sys.argv', ['preflight', '--production-env', 'absent', '--staging-env', 'absent'] + extra)
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
