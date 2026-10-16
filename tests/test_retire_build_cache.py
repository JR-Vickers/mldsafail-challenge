import os
from pathlib import Path

import pytest

from scripts.retire_build_cache import delete_tree, reject_mounts, root_identity


def test_only_registered_cache_removed_without_following_internal_symlink(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    protected = tmp_path / 'retained-archive'
    protected.write_bytes(b'retained')
    (cache / 'layer').mkdir()
    (cache / 'layer/file').write_bytes(b'cache')
    (cache / 'outside').symlink_to(protected)
    assert delete_tree(cache, root_identity(cache)) == 3
    assert not cache.exists() and protected.read_bytes() == b'retained'


def test_replaced_root_or_symlink_fails_before_deletion(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    expected = root_identity(cache)
    expected['inode'] += 1
    with pytest.raises(ValueError):
        delete_tree(cache, expected)
    alias = tmp_path / 'alias'
    alias.symlink_to(cache, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError)):
        delete_tree(alias, root_identity(cache))
    assert cache.is_dir()


def test_special_entry_and_mounts_reject_retirement(tmp_path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    os.mkfifo(cache / 'unexpected')
    with pytest.raises(ValueError):
        delete_tree(cache, root_identity(cache))
    assert cache.is_dir()
    for mount in (cache, cache / 'layer'):
        with pytest.raises(ValueError, match='Mounted'):
            reject_mounts(cache, [f'12 1 0:1 / {mount} rw - tmpfs tmpfs rw'])
    reject_mounts(cache, ['12 1 0:1 / /elsewhere rw - tmpfs tmpfs rw'])


@pytest.mark.parametrize('changes', [dict(cache_retirement_review_passed=False), dict(protocol_sha256='bad')])
def test_unreviewed_retirement_cannot_create_output(tmp_path, changes):
    from deploy import owned_daemon
    from scripts.retire_build_cache import retire, digest
    path = tmp_path / 'protocol.json'
    review_path = tmp_path / 'review.json'
    output = tmp_path / 'output'
    protocol = dict(schema='mldsafail.build-cache-retirement.v1', builds=[{}], source_commit='a' * 40,
                    helper_sha256='b' * 64, review_packet=str(review_path), output=str(output))
    owned_daemon.publish(path, protocol)
    review = dict(schema='mldsafail.build-cache-retirement-review.v1', cache_retirement_review_passed=True,
                  protocol_sha256=digest(path), source_commit=protocol['source_commit'], helper_sha256=protocol['helper_sha256'])
    review.update(changes)
    owned_daemon.publish(review_path, review)
    with pytest.raises(ValueError, match='review required'):
        retire(path)
    assert not output.exists()
