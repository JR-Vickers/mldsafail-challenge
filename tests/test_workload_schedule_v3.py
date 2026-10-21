import pytest

from deploy.workload_schedule_v3 import proposal
from mldsafail.evaluator.workload import WorkloadBlocked


def record():
    return dict(unclassified=0, references_open=0, receipt_sha256='a'*64,
                units=['compute.service', 'web.service'], computational_units=['compute.service'],
                owners={unit: dict(manager='user', account='operator', uid=1000, restart='always',
                                   triggers=[], disposition=disposition, active=True, enabled=True, masked=False)
                        for unit, disposition in [('compute.service', 'pause'), ('web.service', 'retain')]})


def test_persistent_inhibition_leaves_retained_units_and_original_files_alone():
    result = proposal(record(), 1000, '/srv/gate/paused', {'user:1000': '/home/operator/.config/systemd/user'})
    assert not result['execution_authority']
    assert result['resources'][0]['state'] == 'proposed'
    assert 'ConditionPathExists=!/srv/gate/paused' in result['resources'][0]['contents']
    assert '--runtime' not in str(result)
    assert all('web.service' not in command for command in result['commands_after_exclusive_resource_creation'])
    assert all(' start ' not in command for command in result['commands_after_exclusive_resource_creation'])


def test_system_owner_is_explicit():
    data = record()
    data['owners']['compute.service'].update(manager='system', account='root', uid=0)
    result = proposal(data, 1000, '/srv/gate/paused', {'system:0': '/etc/systemd/system'})
    assert result['commands_after_exclusive_resource_creation'][0].startswith('/usr/bin/sudo -n /usr/bin/systemctl')


@pytest.mark.parametrize('mutation', ['cron', 'trigger', 'other_owner'])
def test_unsupported_dispositions_block(mutation):
    data = record()
    owner = data['owners']['compute.service']
    if mutation == 'cron': owner['manager'] = 'cron'
    elif mutation == 'trigger': owner['triggers'] = ['web.service']
    else: owner.update(uid=1001, account='other')
    with pytest.raises(WorkloadBlocked):
        proposal(data, 1000, '/srv/gate/paused', {'user:1000': '/home/operator/.config/systemd/user'})
