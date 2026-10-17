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


def test_special_nodes_require_exact_separately_declared_inventory(tmp_path):
    from scripts.retire_build_cache import inspect_tree
    cache = tmp_path / 'cache'
    cache.mkdir()
    os.mkfifo(cache / 'fifo')
    expected = root_identity(cache)
    inventory = inspect_tree(cache, expected)
    assert (cache / 'fifo').exists()  # Inspection alone never removes it.
    assert len(inventory['special_entries']) == 1
    with pytest.raises(ValueError, match='review required'):
        delete_tree(cache, expected)
    changed = [dict(inventory['special_entries'][0], inode=-1)]
    with pytest.raises(ValueError, match='review required'):
        delete_tree(cache, expected, special_entries=changed)
    assert cache.exists()
    assert delete_tree(cache, expected, special_entries=inventory['special_entries']) == 1
    assert not cache.exists()


@pytest.mark.parametrize('path', ['/outside', '../outside', '.', 'layer/../outside'])
def test_special_node_declarations_cannot_escape_root(tmp_path, path):
    cache = tmp_path / 'cache'
    cache.mkdir()
    with pytest.raises(ValueError):
        delete_tree(cache, root_identity(cache), special_entries=[dict(path=path, device=1, inode=1, mode=1, rdev=0)])
    assert cache.exists()


def test_negative_native_cleanup_never_accepts_a_positive_or_unsettled_run(monkeypatch):
    from scripts import retire_build_cache as cache
    driver = dict(state='complete', native_acceptance_passed=False,
        cleanup=dict(cleanup_complete=True, daemon_barrier=dict(shutdown_proven=False)))
    operator = dict(cleanup_complete=True, complete=False)
    with pytest.raises(ValueError, match='negative native result'):
        cache.terminal_proof(driver, operator, failed_native=True)
    driver['cleanup']['daemon_barrier']['shutdown_proven'] = True
    driver['native_acceptance_passed'] = True
    with pytest.raises(ValueError, match='negative native result'):
        cache.terminal_proof(driver, operator, failed_native=True)
    driver['native_acceptance_passed'] = False
    with pytest.raises(ValueError, match='Positive completed build'):
        cache.terminal_proof(driver, operator)


def test_failed_native_inspection_retains_separate_operation_and_application_reports(tmp_path, monkeypatch):
    import json
    from deploy import owned_daemon
    from scripts import retire_build_cache as cache
    base = tmp_path / 'daemon'
    base.mkdir(mode=0o700)
    root = base / 'root_dir'
    root.mkdir(mode=0o700)
    seed = tmp_path / 'image.tar'
    seed.write_bytes(b'immutable image archive')
    seed.chmod(0o600)
    config = dict(image_archive=str(seed), image_archive_sha256=cache.digest(seed), additional_images=[])
    application = dict(complete=False, cleanup_complete=True, retained_failure_volumes=[])
    paths = {name: tmp_path / (name + '.json') for name in ['config', 'application', 'driver', 'operator', 'protocol', 'review']}
    owned_daemon.publish(paths['config'], config)
    owned_daemon.publish(paths['application'], application)
    driver = dict(config=config, provisioning=dict(base=dict(path=str(base)), roots=dict(root_dir=dict(path=str(root), **cache.root_identity(root)))))
    owned_daemon.publish(paths['driver'], driver)
    owned_daemon.publish(paths['operator'], {})
    rootless = tmp_path / 'rootlesskit'
    rootless.write_text('reviewed executable')
    rootless.chmod(0o700)
    output = tmp_path / 'inspection'
    item = dict(driver=str(paths['driver']), driver_sha256=cache.digest(paths['driver']),
        operator=str(paths['operator']), operator_sha256=cache.digest(paths['operator']),
        driver_config=str(paths['config']), driver_config_sha256=cache.digest(paths['config']),
        application_report=str(paths['application']), offline_volume_names=[],
        evidence=[dict(path=str(paths['application']), sha256=cache.digest(paths['application']))])
    protocol = dict(schema='mldsafail.failed-native-cache-retirement.v1', builds=[item],
        source_commit='a' * 40, helper_sha256=cache.digest(cache.__file__),
        offline_helper_sha256=cache.digest(Path(cache.__file__).with_name('offline_volume_evidence.py')),
        rootlesskit=str(rootless), rootlesskit_sha256=cache.digest(rootless),
        review_packet=str(paths['review']), output=str(output), action='inspect')
    owned_daemon.publish(paths['protocol'], protocol)
    owned_daemon.publish(paths['review'], dict(schema='mldsafail.build-cache-retirement-review.v1',
        cache_retirement_review_passed=True, failed_native_retirement_review_passed=True,
        protocol_sha256=cache.digest(paths['protocol']), source_commit=protocol['source_commit'],
        helper_sha256=protocol['helper_sha256'], offline_helper_sha256=protocol['offline_helper_sha256']))
    monkeypatch.setattr(cache.subprocess, 'check_output', lambda argv, **kw: 'a' * 40 if 'rev-parse' in argv else b'')
    monkeypatch.setattr(cache, 'terminal_proof', lambda *a, **kw: dict(socket_absent=True))
    from contextlib import nullcontext
    monkeypatch.setattr(cache, 'provision_lock', lambda *a: nullcontext())
    monkeypatch.setattr(cache, 'mount_inspection', lambda *a: {})
    original_readlink = cache.os.readlink
    monkeypatch.setattr(cache.os, 'readlink', lambda path, **kw: 'user:[owned]' if str(path) == '/proc/self/ns/user' else original_readlink(path, **kw))
    def child(argv, *args, **kwargs):
        intent = Path(argv[-1])
        owned_daemon.publish(intent.with_suffix('.complete.json'), dict(complete=True, action='inspect'))
    monkeypatch.setattr(cache.owned_client, 'run', child)
    cache.retire(paths['protocol'])
    operation = json.loads((output / 'report.json').read_text())
    assert operation['complete'] is True and len(operation['builds']) == 1
    assert json.loads(paths['application'].read_text()) == application
    assert root.is_dir() and not (base / 'CACHE_RETIRED.json').exists()
