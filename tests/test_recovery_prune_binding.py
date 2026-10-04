import json
from datetime import datetime, timezone
import pytest
from deploy.recovery import validate_prune_state


def state(tmp_path):
    path = tmp_path / 'state.json'
    value = {'repository': 's3:https://synthetic.example/bucket/staging', 'snapshot': 'a' * 64,
             'restore_verified': True, 'cleanup_complete': True, 'schema': 'mldsafail.recovery-state.v1',
             'epoch_id': 'synthetic', 'result_count': 0, 'restored_manifest_sha256': 'b' * 64,
             'uploaded_at': datetime.now(timezone.utc).isoformat(), 'verified_at': datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(value)); path.chmod(0o600)
    return path, value, {'backup_state': str(path), 'repository': value['repository'],
                        'restore_verified_snapshot': value['snapshot']}


@pytest.mark.parametrize('field,bad', [('repository', 'other'), ('snapshot', 'b' * 64),
                                     ('restore_verified', False), ('cleanup_complete', False)])
def test_prune_refuses_unbound_or_incomplete_verification(tmp_path, field, bad):
    path, value, config = state(tmp_path)
    value[field] = bad; path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='exact repository/snapshot'):
        validate_prune_state(config)


def test_prune_requires_full_immutable_identity_and_private_state(tmp_path):
    path, value, config = state(tmp_path)
    assert validate_prune_state(config) == value
    config['restore_verified_snapshot'] = 'latest'
    with pytest.raises(ValueError): validate_prune_state(config)
    config['restore_verified_snapshot'] = value['snapshot']; path.chmod(0o644)
    with pytest.raises(ValueError, match='private regular'): validate_prune_state(config)


@pytest.mark.parametrize('field,bad', [
    ('schema', 'old'), ('epoch_id', ''), ('result_count', True),
    ('restored_manifest_sha256', 'missing'), ('uploaded_at', '2099-01-01T00:00:00+00:00'),
    ('verified_at', '2026-01-01T00:00:00'), ('restore_verified', 'true')])
def test_verified_receipt_rejects_untrusted_identity_and_time(tmp_path, field, bad):
    path, value, config = state(tmp_path)
    value[field] = bad; path.write_text(json.dumps(value))
    with pytest.raises(ValueError): validate_prune_state(config)


def test_monitoring_state_requires_matching_epoch_and_valid_json(tmp_path):
    from deploy.recovery import validate_verified_state
    path, value, config = state(tmp_path)
    config['expected_epoch_id'] = 'other'
    with pytest.raises(ValueError): validate_verified_state(config)
    path.write_text('{corrupt')
    with pytest.raises(ValueError): validate_verified_state(config)
