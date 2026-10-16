from scripts.production_compatibility import compare


def manifests():
    files = {key: 'a' * 64 for key in ('uv.lock', 'deploy/worker-linux-amd64.requirements.txt',
        'src/mldsafail/benchmark_v050/worker.py', 'src/mldsafail/evaluator/coordinator.py',
        'src/mldsafail/evaluator/mlwe.py', 'migrations/schema.py')}
    return dict(source_commit='a' * 40, source_files_sha256=dict(files)), dict(
        source_commit='b' * 40, source_files_sha256=dict(files))


def test_same_worker_and_schema_do_not_hide_evaluator_cohort_drift():
    candidate, rollback = manifests()
    assert compare(candidate, rollback)['compatible']
    rollback['source_files_sha256']['src/mldsafail/evaluator/coordinator.py'] = 'b' * 64
    report = compare(candidate, rollback)
    assert not report['compatible']
    assert report['checks']['frozen_benchmark'] and report['checks']['schema']
    assert not report['checks']['hosted_evaluator']
    assert report['inventories']['hosted_evaluator']['changed_files'] == ['src/mldsafail/evaluator/coordinator.py']


def test_missing_or_extra_evaluator_modules_block_compatibility():
    candidate, rollback = manifests()
    del rollback['source_files_sha256']['src/mldsafail/evaluator/mlwe.py']
    assert not compare(candidate, rollback)['compatible']
    candidate, rollback = manifests()
    rollback['source_files_sha256']['src/mldsafail/evaluator/extra.py'] = 'b' * 64
    assert not compare(candidate, rollback)['compatible']


def test_non_python_schema_or_worker_inputs_are_bound():
    candidate, rollback = manifests()
    candidate['source_files_sha256']['migrations/schema.sql'] = 'c' * 64
    rollback['source_files_sha256']['migrations/schema.sql'] = 'd' * 64
    assert not compare(candidate, rollback)['compatible']
    candidate, rollback = manifests()
    candidate['source_files_sha256']['src/mldsafail/benchmark_v050/Dockerfile'] = 'c' * 64
    assert not compare(candidate, rollback)['compatible']
