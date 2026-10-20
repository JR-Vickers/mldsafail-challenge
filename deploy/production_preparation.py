"""Source-bound retained-preview preparation checks. Diagnostics contain no values."""
import json
import os
import stat
from pathlib import Path

from deploy.recovery_journal import safe_path

SOURCE = '1c9ca9eff3a1133aa8b508a35f6b174a587a4f01'
ROLLBACK = '26c5f2f4bc771b319ffccc2cdcb1c735eaab4176'
IMAGES = dict(zip(
    ('WEB_IMAGE', 'COORDINATOR_IMAGE', 'WORKER_IMAGE', 'CADDY_IMAGE', 'POSTGRES_IMAGE'),
    ('31383f86703dcc8b4ba4c36acd8933ed5bf306ee98fa129e50d4625dd4c12a4b',
     'b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4',
     '6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe',
     '6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b',
     '639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652')))
FINGERPRINT = 'b6f92231843fcb90695669108f0cc02d747ae0614eb9b3d25cddae602e092eee'


def read_manifest(path):
    path = safe_path(path)
    if (not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.parent.stat().st_uid != os.getuid()
            or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
            or path.stat().st_nlink != 1 or path.parent.stat().st_mode & 0o077):
        raise ValueError('private_manifest_required')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_private_record_field')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def check_manifest(environment, manifest, *, preparation=False):
    if not isinstance(manifest, dict):
        return ['invalid_preparation_manifest']
    errors = []
    expected = {'schema': ('mldsafail.production-preparation.v1' if preparation else 'mldsafail.production-final.v1'), 'source': SOURCE,
                'rollback': ROLLBACK, 'project': 'mldsafail-production'}
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append('preparation_binding_mismatch:' + key)
    fields = {'MLDSAFAIL_BENCHMARK_VERSION': '0.5.0',
              'MLDSAFAIL_DOMAIN': '178.128.17.58',
              'PRODUCTION_ORIGIN': 'https://178.128.17.58',
              'MLDSAFAIL_EVALUATOR_FINGERPRINT': FINGERPRINT,
              'MLDSAFAIL_HIDDEN_SUITE_VERSION': 'mlwe-v050',
              'MLDSAFAIL_WORKER_CLASS': 'rootless-docker-v1',
              'MLDSAFAIL_OUTSTANDING_PER_ACCOUNT': '1',
              'MLDSAFAIL_SUBMISSIONS_PER_DAY': '2', 'MLDSAFAIL_QUEUED_GLOBALLY': '10'}
    for key, value in fields.items():
        if environment.get(key) != value:
            errors.append('preview_binding_mismatch:' + key)
    for key, digest in IMAGES.items():
        if environment.get(key) not in ('sha256:' + digest,
                {'CADDY_IMAGE': 'caddy', 'POSTGRES_IMAGE': 'postgres'}.get(key, '') + '@sha256:' + digest):
            errors.append('selected_image_mismatch:' + key)
    if manifest.get('blockers'):
        errors.append('private_preparation_blockers_unresolved')
    if preparation and manifest.get('unresolved') != {'MLDSAFAIL_MLWE_EPOCH_ID': 'future_independently_audited_epoch'}:
        errors.append('invalid_unresolved_dependencies')
    if preparation and 'MLDSAFAIL_MLWE_EPOCH_ID' in environment:
        errors.append('preparation_epoch_must_be_absent')
    if not preparation and manifest.get('unresolved'):
        errors.append('epoch_binding_not_finalized')
    for key in ('POSTGRES_PASSWORD', 'MLDSAFAIL_SECRET_KEY'):
        if len(environment.get(key, '')) < 32:
            errors.append('secret_strength_required:' + key)
    if environment.get('POSTGRES_PASSWORD') == environment.get('MLDSAFAIL_SECRET_KEY'):
        errors.append('separate_secrets_required')
    paths = [environment.get(key, '') for key in
             ('PRODUCTION_EVALUATOR_ROOT', 'PRODUCTION_TLS_ROOT', 'PRODUCTION_ACME_WEBROOT')]
    try:
        def remote_path(value):
            path = Path(value)
            if not path.is_absolute() or '..' in path.parts:
                raise ValueError('absolute_inspected_host_path_required')
            return path
        # Host paths are reconciled against remote mount/symlink evidence by the receipt validator.
        paths = [remote_path(p) for p in paths]
        retained = [remote_path(p) for p in manifest['retained_roots']]
        if not retained:
            raise ValueError('retained roots required')
        for i, path in enumerate(paths):
            if any(path.is_relative_to(other) or other.is_relative_to(path)
                   for other in paths[i+1:] + retained):
                errors.append('production_storage_overlap')
    except (KeyError, TypeError, ValueError):
        errors.append('production_storage_inventory_required')
    return errors
