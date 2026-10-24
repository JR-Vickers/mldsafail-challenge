"""Filesystem lifecycle checks; no Linux/native installation acceptance."""
import json
import os
from pathlib import Path
import time

import pytest

from scripts import workload_installation_fixture as fixture
from deploy.workload_installation import exclusive
from deploy.workload_release import canonical
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path/'fixture'
    fixture.prepare(root)
    return root


def test_preparation_is_private_exclusive_and_records_source(prepared):
    value = fixture.Fixture(prepared)
    assert value.manifest['source_revision']
    assert value.manifest['source_hashes']['deploy/workload_installation.py']
    assert value.manifest['implementation_blockers'] == []
    assert value.manifest['root']['mode'] == 0o700
    assert not value.manifest['execution_authority']
    before = (prepared/'manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        fixture.prepare(prepared)
    assert (prepared/'manifest.json').read_bytes() == before


@pytest.mark.parametrize('path', ['relative', '/', '/a/../b'])
def test_absolute_nonroot_namespace_required(path):
    with pytest.raises(WorkloadBlocked, match='absolute_nonroot'):
        fixture.prepare(Path(path))


def test_parent_symlink_is_not_followed(tmp_path):
    real = tmp_path/'real'; real.mkdir()
    link = tmp_path/'link'; link.symlink_to(real, target_is_directory=True)
    with pytest.raises(WorkloadBlocked, match='symlink'):
        fixture.prepare(link/'fixture')
    assert not (real/'fixture').exists()


def test_overlapping_lifecycle_is_rejected(prepared):
    with fixture.lifecycle_lock(prepared):
        with pytest.raises(BlockingIOError):
            with fixture.lifecycle_lock(prepared):
                pytest.fail('second lifecycle lock admitted')


def test_shared_or_symlink_lock_is_refused(prepared, tmp_path):
    lock = prepared/'lifecycle.lock'
    os.link(lock, tmp_path/'shared')
    with pytest.raises(WorkloadBlocked, match='lock_invalid'):
        with fixture.lifecycle_lock(prepared):
            pass
    lock.unlink(); lock.symlink_to(tmp_path/'shared')
    with pytest.raises(OSError):
        with fixture.lifecycle_lock(prepared):
            pass


def test_namespace_replacement_is_preserved_and_blocks(prepared):
    renamed = prepared.with_name('original'); prepared.rename(renamed)
    prepared.mkdir(mode=0o700)
    for item in renamed.iterdir():
        item.rename(prepared/item.name)
    with pytest.raises(WorkloadBlocked, match='namespace_replaced'):
        fixture.Fixture(prepared)
    assert (prepared/'manifest.json').exists()


@pytest.mark.parametrize('name', ['inputs', 'artifacts', 'journal', 'runtime-journal'])
def test_subdirectory_symlink_and_replacement_block(prepared, name):
    saved = prepared/('saved-'+name)
    (prepared/name).rename(saved)
    (prepared/name).symlink_to(saved, target_is_directory=True)
    with pytest.raises(WorkloadBlocked):
        fixture.Fixture(prepared)
    (prepared/name).unlink(); (prepared/name).mkdir(mode=0o700)
    with pytest.raises(WorkloadBlocked, match='directory_replaced'):
        fixture.Fixture(prepared)


def test_inspection_is_exclusive_and_explicit_about_incompleteness(prepared):
    value = fixture.Fixture(prepared)
    before = value.journal.path.read_bytes()
    first = value.inspect(); second = value.inspect()
    assert first['path'] != second['path']
    observed = json.loads(Path(first['path']).read_bytes())
    assert observed['implementation_blockers'] == []
    assert not observed['runtime_suitability_verified']
    assert not observed['execution_authority']
    assert before == value.journal.path.read_bytes()


def test_failed_prepare_retains_intent_and_exact_failure(tmp_path):
    root = tmp_path/'broken'
    recipe = tmp_path/'recipe.json'
    exclusive(recipe, canonical(dict(bogus=True)))
    with pytest.raises(WorkloadBlocked, match='recipe_fields'):
        fixture.prepare(root, recipe=recipe)
    intent = json.loads((root/'prepare-intent.json').read_bytes())
    failure = json.loads((root/'prepare-failed.json').read_bytes())
    assert intent['root']['path'] == str(root)
    assert failure['error']['message'] == 'fixture_recipe_fields'
    assert failure['automatic_retry'] is False
    with pytest.raises(FileExistsError):
        fixture.prepare(root)


def test_failed_provision_is_durable_and_never_retried(prepared, monkeypatch):
    value = fixture.Fixture(prepared)
    monkeypatch.setattr(value, 'require_target', lambda: (_ for _ in ()).throw(WorkloadBlocked('unsupported')))
    with pytest.raises(WorkloadBlocked, match='unsupported'):
        value.transition('provision')
    assert value.last('provision')['event'] == 'fixture_phase_failed'
    assert value.last('provision')['ownership'] == 'unresolved_preserve'
    with pytest.raises(WorkloadBlocked, match='already_attempted'):
        value.transition('provision')
    with pytest.raises(WorkloadBlocked, match='provision_not_complete'):
        value.transition('install')


def test_builtin_plan_required_before_native_execution(prepared, monkeypatch):
    value = fixture.Fixture(prepared)
    monkeypatch.setattr(value, 'require_target', lambda: None)
    with pytest.raises(WorkloadBlocked, match='builtin_resource_plan_required'):
        value.transition('provision')


def test_expiry_does_not_reset_attempt_or_allow_cleanup_claim(prepared, monkeypatch):
    value = fixture.Fixture(prepared)
    value.journal.append('fixture_attempt_started', started_at=time.time()-1801)
    monkeypatch.setattr(value, 'require_target', lambda: None)
    with pytest.raises(WorkloadBlocked, match='expired_preserve'):
        value.transition('cleanup')
    assert value.last('cleanup')['event'] == 'fixture_phase_failed'
    assert value.last('cleanup')['ownership'] == 'unresolved_preserve'
    assert len([r for r in value.journal.rows if r['event'] == 'fixture_attempt_started']) == 1


def test_final_five_minutes_reserved(prepared):
    value = fixture.Fixture(prepared)
    value.journal.append('fixture_attempt_started', started_at=time.time()-1501)
    with pytest.raises(WorkloadBlocked, match='expired_preserve'):
        value.deadline()
    assert 0 < value.deadline(cleanup=True) < 300


def test_external_adapters_cannot_run(prepared):
    value = fixture.Fixture(prepared)
    for phase in ('provision', 'inspect', 'postflight', 'cleanup'):
        with pytest.raises(WorkloadBlocked, match='builtin_resource_plan_required'):
            value.adapter(phase)


def test_internal_worker_does_not_bypass_lock(prepared, monkeypatch):
    monkeypatch.setattr('sys.argv', ['fixture', '_engine', str(prepared)])
    with fixture.lifecycle_lock(prepared):
        with pytest.raises(RuntimeError, match='inherited_lifecycle_lock'):
            fixture.main()


def test_callable_engine_paths_are_also_fenced(prepared):
    value = fixture.Fixture(prepared)
    with pytest.raises(WorkloadBlocked, match='inherited_lock_required'):
        value.engine('install')
    with pytest.raises(WorkloadBlocked, match='inherited_lock_required'):
        fixture.fixture_engine(prepared, phase='install', review=None, authority=None)


def test_inherited_descriptor_cannot_borrow_another_worker_phase(prepared,monkeypatch):
    from types import SimpleNamespace
    from scripts.workload_fixture_worker import work
    output=prepared/'artifacts/result.json'
    request=dict(event='fixture_worker_intent',token='token',operation='engine',output=str(output),
                 phase='install',reconciliation=False,review_sha256=None,authority_sha256=None)
    fake=SimpleNamespace(root=prepared,journal=SimpleNamespace(rows=[request]),require_target=lambda:None)
    monkeypatch.setattr(fixture,'Fixture',lambda root:fake)
    with fixture.lifecycle_lock(prepared) as fd:
        with pytest.raises(WorkloadBlocked,match='worker_request_changed'):
            work(prepared,fd,'token','engine',output,phase='rollback')
    assert not output.exists()


def test_environment_collection_does_not_claim_docker_suitability():
    observed = fixture.environment()
    assert not observed['native_acceptance']
    assert 'rootless-docker' in observed['requirements']


def test_changed_driver_binding_blocks(prepared):
    path = prepared/'manifest.json'
    value = json.loads(path.read_bytes()); value['driver_sha256'] = 'a'*64
    path.unlink(); exclusive(path, canonical(value))
    with pytest.raises(WorkloadBlocked, match='driver_changed'):
        fixture.Fixture(prepared)


def test_changed_executing_module_binding_blocks_before_native_work(prepared):
    path=prepared/'manifest.json';value=json.loads(path.read_bytes())
    value['source_hashes']['deploy/workload_log.py']='0'*64
    path.unlink();exclusive(path,canonical(value))
    with pytest.raises(WorkloadBlocked,match='executing_source_changed'):fixture.Fixture(prepared)


def test_builtin_preparation_freezes_an_independent_source_snapshot(tmp_path):
    import tempfile
    with tempfile.TemporaryDirectory(prefix='fkit-',dir=Path('/tmp').resolve()) as short:
        root=Path(short)/'fixture';settings=tmp_path/'settings.json'
        exclusive(settings,canonical(dict(unit_directory=str(Path.home()/'.config/systemd/user'))))
        recipe=tmp_path/'recipe.json'
        exclusive(recipe,canonical(dict(schema=fixture.SCHEMA,fixture_only=True,
            target=dict(hostname='workload-rehearsal-test',machine_id='synthetic',uid=1000),inputs=dict(settings=str(settings)),
            adapters={phase:'builtin' for phase in ('provision','inspect','postflight','cleanup')},resources=[])))
        manifest=fixture.prepare(root,recipe=recipe)
        assert manifest['source_root']==str(root/'source')
        original=Path(fixture.__file__)
        copied=root/'source/scripts/workload_installation_fixture.py'
        assert copied.read_bytes()==original.read_bytes()
        assert copied.stat().st_nlink==1 and copied.stat().st_ino!=original.stat().st_ino
        assert (root/'source/.git').is_dir()
        fixture.Fixture(root)

def test_input_contents_and_birth_are_frozen(tmp_path):
    root = tmp_path/'fixture'
    payload = tmp_path/'adapter.py'; payload.write_bytes(b'raise RuntimeError("must not run")')
    payload.chmod(0o600)
    recipe = tmp_path/'recipe.json'
    exclusive(recipe, canonical(dict(schema=fixture.SCHEMA, fixture_only=True,
        target=dict(hostname='workload-rehearsal-test', machine_id='synthetic', uid=1000),
        inputs=dict(adapter=str(payload)),
        adapters={phase:'adapter' for phase in ('provision', 'inspect', 'postflight', 'cleanup')}, resources=[])))
    fixture.prepare(root, recipe=recipe)
    value = fixture.Fixture(root)
    path = root/'inputs/adapter'
    original = path.read_bytes()
    path.write_bytes(b'changed')
    with pytest.raises(WorkloadBlocked, match='input_changed'):
        fixture.Fixture(root)
    path.write_bytes(original)
    fixture.Fixture(root)
    replacement = root/'inputs/new'; exclusive(replacement, original)
    os.replace(replacement, path)
    with pytest.raises(WorkloadBlocked, match='input_changed'):
        fixture.Fixture(root)
    assert value.manifest['inputs']['adapter']['sha256']


@pytest.mark.parametrize('disposition', ['malformed_report', 'timeout', 'group_remaining'])
def test_command_failures_always_record_results(prepared, monkeypatch, disposition):
    value = fixture.Fixture(prepared)
    value.journal.append('fixture_attempt_started', started_at=time.time())
    monkeypatch.setattr(value, 'require_target', lambda: None)
    monkeypatch.setattr('mldsafail.evaluator.native_workload.process_birth', lambda pid: dict(pid=pid, start_ticks=1))
    class Process:
        pid = 123456789
        returncode = 0
        def poll(self): return self.returncode
        def wait(self, timeout):
            if disposition == 'timeout':
                raise RuntimeError('synthetic timeout')
            return 0
    def launch(argv, **kwargs):
        report = Path(argv[3])
        report.write_text('{' if disposition == 'malformed_report' else json.dumps(dict(
            errors=[], remaining=[], descendants=False, timed_out=False, returncode=0)))
        return Process()
    monkeypatch.setattr(fixture.subprocess, 'Popen', launch)
    def group(*args):
        if disposition != 'group_remaining': raise ProcessLookupError()
    monkeypatch.setattr(fixture.os, 'killpg', group)
    with pytest.raises(WorkloadBlocked, match='termination_unverified'):
        value.command(['inert'])
    row = value.journal.rows[-1]
    assert row['event'] == 'fixture_command_result'
    assert row['cleanup_errors'] or row['failure'] or row['group_remaining']
