import json
from pathlib import Path

import pytest

from deploy import owned_daemon
from scripts import production_diagnostic as diagnostic
from scripts import production_diagnostic_state as state


def finish(budget, slot, tmp_path, now, *, boot='boot', complete=True):
    start = owned_daemon.read_private_json(budget.root / (slot + '-start.json'))
    path = tmp_path / (slot + '-independent.json')
    owned_daemon.publish(path, dict(budget_start_sha256=diagnostic.digest(start), independent=True, passed=True))
    return budget.finish(slot, boot_id=boot, complete=complete, cleanup_receipt=path, clock=lambda: now)


def test_interruption_consumes_slot_and_reserves_full_charge(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
    with state.locked(root) as budget:
        assert budget.inspect()['charged_seconds'] == 1200
        with pytest.raises(ValueError, match='retry'):
            budget.start('preflight', boot_id='boot')
        with pytest.raises(ValueError, match='Verified'):
            budget.start('baseline', boot_id='boot')
    with pytest.raises(FileExistsError): state.create(root)


def test_two_generations_and_cleanup_reserve(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
        finish(budget, 'preflight', tmp_path, 400)
        allowance = budget.start('baseline', boot_id='boot', clock=lambda: 400)
        allowance.admit(2100)
        with pytest.raises(TimeoutError): allowance.admit(2101)
        result = finish(budget, 'baseline', tmp_path, 3400)
        assert result['charged_seconds'] == 4200
        budget.start('post-fix', boot_id='boot', clock=lambda: 3500)
        result = finish(budget, 'post-fix', tmp_path, 6500)
        assert result['charged_seconds'] == 7200
        with pytest.raises(ValueError, match='third'):
            budget.start('post-fix', boot_id='boot')
        with pytest.raises(FileExistsError):
            finish(budget, 'post-fix', tmp_path, 6500)


def test_reboot_and_backwards_time_cannot_release_fence(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
        with pytest.raises(ValueError, match='Ambiguous'):
            finish(budget, 'preflight', tmp_path, 200, boot='new-boot')
        with pytest.raises(ValueError, match='Ambiguous'):
            finish(budget, 'preflight', tmp_path, 99)
        assert budget.inspect()['charged_seconds'] == 1200


def test_overrun_and_failed_completion_block_next_generation(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
        result = finish(budget, 'preflight', tmp_path, 401)
        assert result['charged_seconds'] == 1201
        assert not result['slots'][0]['cleanup_verified']
        with pytest.raises(ValueError, match='Verified'):
            budget.start('baseline', boot_id='boot')


def test_malformed_partial_start_is_never_reset(tmp_path):
    root = state.create(tmp_path / 'budget')
    (root / 'preflight-start.json').write_text('{')
    (root / 'preflight-start.json').chmod(0o600)
    with state.locked(root) as budget:
        with pytest.raises(json.JSONDecodeError): budget.inspect()
        with pytest.raises(json.JSONDecodeError): budget.start('preflight', boot_id='boot')


def test_no_slot_skip_or_unbound_cleanup(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        with pytest.raises(ValueError): budget.start('baseline', boot_id='boot')
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
        path = tmp_path / 'wrong.json'
        owned_daemon.publish(path, dict(independent=True, passed=True, budget_start_sha256='wrong'))
        with pytest.raises(ValueError, match='Independent'):
            budget.finish('preflight', boot_id='boot', complete=True, cleanup_receipt=path, clock=lambda: 200)


def test_actual_inventory_rejects_missing_extra_changed_and_linked_files(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    file = root / 'helper.py'
    file.write_text('original')
    expected = {'helper.py': diagnostic.file_digest(file)}
    assert diagnostic.verify_inventory(root, expected) == diagnostic.digest(expected)
    extra = root / 'unexpected.py'
    extra.write_text('extra')
    with pytest.raises(ValueError): diagnostic.verify_inventory(root, expected)
    extra.unlink()
    file.write_text('modified')
    with pytest.raises(ValueError): diagnostic.verify_inventory(root, expected)
    file.unlink()
    with pytest.raises(ValueError): diagnostic.verify_inventory(root, expected)
    file.symlink_to(Path(__file__).resolve())
    with pytest.raises(ValueError, match='links'): diagnostic.verify_inventory(root, expected)


def test_archive_hash_rejects_parent_link_and_nonregular(tmp_path):
    file = tmp_path / 'archive'
    file.write_bytes(b'archive')
    link = tmp_path / 'linked'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError): diagnostic.file_digest(link / 'archive')
    with pytest.raises(ValueError): diagnostic.file_digest(tmp_path)


def schedule(generation):
    rows = [('setup', 400), ('monitor-idle', 100), ('monitor-loaded', 100),
            ('http-idle', 100), ('http-loaded', 100)]
    rows += [('legacy', 600)] if generation == 'baseline' else [('final-idle', 350), ('final-loaded', 350)]
    return dict(generation=generation, phases=[dict(name=name, outer_seconds=ceiling) for name, ceiling in rows])


@pytest.mark.parametrize('generation', ['baseline', 'post-fix'])
def test_schedule_fits_entire_work_allowance(generation):
    protocol = schedule(generation)
    diagnostic.validate_schedule(protocol)
    protocol['phases'][0]['outer_seconds'] = 2100
    with pytest.raises(ValueError, match='exceeds'): diagnostic.validate_schedule(protocol)


def test_schedule_requires_termination_headroom_and_fixed_order():
    protocol = schedule('baseline')
    protocol['phases'][-1]['outer_seconds'] = 601
    with pytest.raises(ValueError, match='600'): diagnostic.validate_schedule(protocol)
    protocol = schedule('baseline')
    protocol['phases'].reverse()
    with pytest.raises(ValueError, match='ordered'): diagnostic.validate_schedule(protocol)


def test_cleanup_evidence_is_revalidated_before_next_start(tmp_path):
    root = state.create(tmp_path / 'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda: 100)
        finish(budget, 'preflight', tmp_path, 200)
        owned_daemon.publish(tmp_path / 'preflight-independent.json', dict(passed=False))
        with pytest.raises(ValueError, match='evidence changed'):
            budget.start('baseline', boot_id='boot')


def test_owner_authorized_preflight_resolution_preserves_failed_records(tmp_path):
    root = state.create(tmp_path/'budget')
    with state.locked(root) as budget:
        budget.start('preflight', boot_id='boot', clock=lambda:100)
        finish(budget,'preflight',tmp_path,133,complete=False)
        original=(root/'preflight-terminal.json').read_bytes()
        names=['preflight-continuation','correct-target-preflight']
        for name,seconds,limit,passed in zip(names,[32,187],[267,235],[False,True]):
            start=dict(monotonic_started=1000,limit_seconds=limit,boot_id='boot')
            state._exclusive(root/(name+'-start.json'),start)
            path=tmp_path/(name+'-receipt.json')
            owned_daemon.publish(path,dict(independent=True,passed=True,budget_start_sha256=diagnostic.digest(start)))
            state._exclusive(root/(name+'-terminal.json'),dict(start_sha256=diagnostic.digest(start),
                elapsed_seconds=seconds,charged_seconds=seconds,complete=passed,cleanup_verified=True,
                cleanup_receipt_path=str(path),cleanup_receipt_sha256=diagnostic.digest(json.loads(path.read_text()))))
        state._exclusive(root/'preflight-resolution.json',dict(authorization='Owner explicit continuation after correcting target',
            original_terminal_sha256=diagnostic.file_digest(root/'preflight-terminal.json'),continuations=names))
        result=budget.inspect()
        assert result['charged_seconds']==1152 and result['slots'][0]['complete']
        assert (root/'preflight-terminal.json').read_bytes()==original
        budget.start('baseline',boot_id='boot',clock=lambda:2000)
        with pytest.raises(ValueError,match='retry'):budget.start('baseline',boot_id='boot')


def test_unresolved_continuation_reserves_all_preflight_and_fences_baseline(tmp_path):
    root=state.create(tmp_path/'budget')
    with state.locked(root) as budget:
        budget.start('preflight',boot_id='boot',clock=lambda:100)
        finish(budget,'preflight',tmp_path,133,complete=False)
        state._exclusive(root/'preflight-continuation-start.json',dict(monotonic_started=200,limit_seconds=267,boot_id='boot'))
        assert budget.inspect()['charged_seconds']==1200
        with pytest.raises(ValueError,match='Verified'):budget.start('baseline',boot_id='boot')
        state._exclusive(root/'preflight-resolution.json',dict(authorization='resume',
            original_terminal_sha256=diagnostic.file_digest(root/'preflight-terminal.json'),continuations=['preflight-continuation']))
        assert budget.inspect()['charged_seconds']==1200
        state._exclusive(root/'artifact-preflight-start.json',dict(monotonic_started=300,limit_seconds=48,boot_id='boot'))
        with pytest.raises(ValueError,match='Ordered'):budget.inspect()


def test_orphan_continuation_cannot_create_new_preflight(tmp_path):
    root=state.create(tmp_path/'budget')
    state._exclusive(root/'correct-target-preflight-start.json',dict(monotonic_started=1,limit_seconds=235,boot_id='boot'))
    with state.locked(root) as budget:
        with pytest.raises(ValueError,match='Original'):budget.inspect()
        with pytest.raises(ValueError,match='Original'):budget.start('preflight',boot_id='boot')
