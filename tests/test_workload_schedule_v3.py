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
    assert 'ConditionPathExists=/srv/gate/paused/user-1000.allow' in result['resources'][0]['contents']
    assert result['gate']['permission_files'] == 'must_remain_absent_no_creation_authorized'
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


def test_same_named_units_in_distinct_managers_keep_distinct_owners():
    data=record();owner=data['owners']['compute.service']
    data['units']=['user:1000:compute.service','system:0:compute.service']
    data['computational_units']=list(data['units'])
    data['owners']={'user:1000:compute.service':dict(owner),
                    'system:0:compute.service':dict(owner,manager='system',uid=0,account='root')}
    result=proposal(data,1000,'/srv/gate/paused',{'user:1000':'/home/operator/.config/systemd/user','system:0':'/etc/systemd/system'})
    assert len(result['resources'])==2
    assert {row['path'] for row in result['resources']}=={
        '/home/operator/.config/systemd/user/compute.service.d/90-mldsafail-paused.conf',
        '/etc/systemd/system/compute.service.d/90-mldsafail-paused.conf'}
    assert all('user:1000:compute.service' not in row and 'system:0:compute.service' not in row
               for row in result['commands_after_exclusive_resource_creation'])


def test_qualified_owner_identifier_cannot_redirect_to_another_manager():
    data=record();data['units'][0]='system:0:compute.service';data['computational_units']=['system:0:compute.service']
    data['owners']['system:0:compute.service']=data['owners'].pop('compute.service')
    with pytest.raises(WorkloadBlocked,match='owner_identifier_changed'):
        proposal(data,1000,'/srv/gate/paused',{'user:1000':'/home/operator/.config/systemd/user'})
