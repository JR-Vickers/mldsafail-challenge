from copy import deepcopy
from pathlib import Path
import pytest
from scripts.native_repeat_activation_verification import assess_interrupted


def admitted():
    path = Path('/private/activation-root/activation-old/driver.json')
    state = dict(schema='mldsafail.cpu-native-driver-state.v1', daemon_kind='owned',
        config=dict(source_commit='a'*40, state_root=str(path.parent)),
        operator_job=dict(schema='mldsafail.operator-job-intent.v1', job='recovery-check',
                         state='running', journal_created=True),
        registered_manifest=dict(epoch='old'), provisioning=dict(operator_domain={'inode': 1}))
    rows = [dict(driver_state='/private/activation-root/activation-new/driver.json',
                 daemon_epoch='new', operator_domain={'inode': 2})]
    return state, path, rows


def test_real_admitted_job_can_be_assessed_without_claiming_native_acceptance():
    state, path, rows = admitted()
    assert assess_interrupted(state, path, rows, 'a'*40) is None


@pytest.mark.parametrize('field,value', [('job','fixture'), ('state','passed'), ('journal_created',False)])
def test_non_interrupted_or_unadmitted_job_rejected(field, value):
    state, path, rows = admitted()
    state['operator_job'][field] = value
    with pytest.raises(RuntimeError, match='Actual interrupted'):
        assess_interrupted(state, path, rows, 'a'*40)


@pytest.mark.parametrize('field,value', [('daemon_epoch','old'), ('operator_domain',{'inode':1})])
def test_reused_context_cannot_prove_reconciliation(field, value):
    state, path, rows = admitted()
    rows[0][field] = value
    with pytest.raises(RuntimeError, match='fresh'):
        assess_interrupted(state, path, rows, 'a'*40)


def test_unrelated_activation_root_rejected():
    state, path, rows = admitted()
    rows[0]['driver_state'] = '/private/unrelated/activation-new/driver.json'
    with pytest.raises(RuntimeError, match='share ownership'):
        assess_interrupted(state, path, rows, 'a'*40)


def test_reconciliation_binds_actual_job_epoch_attempt_and_replacement():
    from scripts.native_repeat_activation_verification import reconciliation_matches
    state, _, rows = admitted()
    state.update(id='attempt-old')
    state['operator_job']['journal_path'] = '/private/job/operation.json'
    rows[0].update(source_commit='a'*40, operator_unit='mldsafail-next.service',
                   operator_domain={'path':'/sys/fs/cgroup/next'})
    receipt = dict(schema='mldsafail.terminal-recovery-job.v1', cleanup_complete=True,
        journal_present=True, journal='/private/job/operation.json', terminal_daemon_epoch='old',
        reconciled_attempt_id='attempt-old', reconciling_activation=dict(source_commit='a'*40,
            operator_unit='mldsafail-next.service', operator_parent='/sys/fs/cgroup/next',
            driver_state=rows[0]['driver_state']))
    assert reconciliation_matches(receipt, state, rows)
    for field in ('journal', 'terminal_daemon_epoch', 'reconciled_attempt_id'):
        bad = deepcopy(receipt); bad[field] = 'unrelated'
        assert not reconciliation_matches(bad, state, rows)
    bad = deepcopy(receipt)
    bad['reconciling_activation']['driver_state'] = '/private/predating/driver.json'
    assert not reconciliation_matches(bad, state, rows)
    bad = deepcopy(receipt); del bad['reconciling_activation']
    assert not reconciliation_matches(bad, state, rows)
