import json
from copy import deepcopy
import pytest
from deploy.workload_registry import observe,validate
from mldsafail.evaluator.workload import WorkloadBlocked


def source():
    owners={key:dict(manager=manager,uid=uid,account=account) for key,manager,uid,account in
            [('system:0:dbus.service','system',0,'root'),('user:1000:dbus.service','user',1000,'operator')]}
    return dict(host=dict(uid=1000),scheduling=dict(owners=owners),
        inventory=dict(manager_units={'system:0':['dbus.service'],'user:1000':['dbus.service']}))


def command(argv):
    if '/usr/bin/python3' in argv:return json.dumps([dict(uid=1000,account='operator')]).encode()
    return b'dbus.service loaded active running D-Bus\n'


def test_both_manager_names_are_observed_without_collision():
    data=source();assert observe(data,command)==data['inventory']['manager_units']


def test_new_unit_blocks_before_installation_mutations():
    def changed(argv):
        raw=command(argv)
        return raw+b'unclassified.service loaded active running Unknown\n' if 'list-units' in argv else raw
    with pytest.raises(WorkloadBlocked,match='unit_inventory_changed'):observe(source(),changed)


def test_new_manager_is_not_silently_omitted():
    def changed(argv):
        if '/usr/bin/python3' in argv:return json.dumps([dict(uid=1000,account='operator'),dict(uid=1001,account='other')]).encode()
        return command(argv)
    with pytest.raises(WorkloadBlocked,match='manager_census_changed'):observe(source(),changed)


def test_registry_requires_classification_of_every_unit():
    data=source();data['inventory']['manager_units']['system:0'].append('unknown.service')
    with pytest.raises(WorkloadBlocked,match='unclassified_units'):validate(data)


def reference_source():
    from deploy.workload_registry import REFERENCE_FIELDS
    data=source();data['inventory']['execution_references']={
        key:{field:('/usr/lib/systemd/system/dbus.service' if field=='FragmentPath' else '') for field in REFERENCE_FIELDS}
        for key in data['scheduling']['owners']}
    data['inventory'].update(original_files={'/usr/lib/systemd/system/dbus.service':'a'*64},absent_files=[])
    return data


def test_changed_fragment_target_cannot_hide_behind_unchanged_unit_name():
    from deploy.workload_registry import references
    data=reference_source()
    def changed(argv):
        row=dict(next(iter(data['inventory']['execution_references'].values())))
        row['FragmentPath']='/run/unapproved.service'
        return '\n'.join(key+'='+value for key,value in row.items()).encode()
    with pytest.raises(WorkloadBlocked,match='reference_changed'):references(data,changed)


def test_missing_optional_environment_file_has_an_explicit_absence_binding():
    from deploy.workload_registry import validate_reference_files
    data=reference_source()
    next(iter(data['inventory']['execution_references'].values()))['EnvironmentFiles']='/etc/fixture-env (ignore_errors=yes)'
    with pytest.raises(WorkloadBlocked,match='unbound_reference_file'):validate_reference_files(data)
    data['inventory']['absent_files']=['/etc/fixture-env'];validate_reference_files(data)


def test_inhibition_allows_process_accounting_but_rejects_loaded_command_changes():
    from deploy.workload_registry import references
    data=reference_source()
    identifier='user:1000:dbus.service';owner=data['scheduling']['owners'][identifier]
    for other in data['scheduling']['owners'].values():other['disposition']='retain'
    owner['disposition']='pause'
    data['unit_directories']={'user:1000':'/home/operator/.config/systemd/user'}
    before=data['inventory']['execution_references'][identifier]
    before['ExecStart']='{ path=/bin/true ; argv[]=/bin/true ; ignore_errors=no ; start_time=[n/a] ; stop_time=[n/a] ; pid=0 ; code=(null) ; status=0/0 }'
    def command(argv):
        key=identifier if '--user' in argv else 'system:0:dbus.service'
        row=dict(data['inventory']['execution_references'][key])
        if key==identifier:
            row['DropInPaths']='/home/operator/.config/systemd/user/dbus.service.d/90-mldsafail-paused.conf'
            row['ExecStart']=row['ExecStart'].replace('pid=0','pid=123').replace('stop_time=[n/a]','stop_time=[Thu 2026-10-22 07:30:17 UTC]')
        return '\n'.join(k+'='+v for k,v in row.items()).encode()
    references(data,command,inhibited=True)
    def changed(argv):return command(argv).replace(b'argv[]=/bin/true',b'argv[]=/bin/false')
    with pytest.raises(WorkloadBlocked,match='loaded_execution_changed'):references(data,changed,inhibited=True)
