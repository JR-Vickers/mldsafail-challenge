import json
import pytest
from deploy.recovery import validate_prune_state


def state(tmp_path):
    path = tmp_path / 'state.json'
    value = {'repository': 's3:https://synthetic.example/bucket/staging', 'snapshot': 'a' * 64,
             'restore_verified': True, 'cleanup_complete': True}
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
