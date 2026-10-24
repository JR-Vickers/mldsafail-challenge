"""Concrete LinuxBackend recovery using generation-owned inert command adapters.

Real archives/files/units/sockets are inspected by production observers. Docker,
service managers and kernel/proc visibility are fixture-specific stand-ins; these
cases do not establish installed-native interruption acceptance.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest

from deploy.workload_installation import Journal, identity, supervisor_enable_contents
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.workload import WorkloadBlocked
from tests.test_workload_installation_substeps import backend
from tests.test_workload_installation import seal_snapshots
from tests.test_native_workload import fixture as native_fixture

BOUNDARIES=('intent','unacknowledged','acknowledged')


def begin(instance,journal,step):
    if not journal.rows:journal.append('recovery_protocol',version=4)
    before=instance.before(step,journal)
    journal.append('intent',step=step['id'],before=before)
    return before


def acknowledged(instance,journal,step,boundary):
    if boundary!='intent':instance.apply(step,journal)
    if boundary=='acknowledged':instance.acknowledge_apply(step,journal)


def bind_runtime(instance,tmp_path,monkeypatch,native_fixture):
    """Keep NativeRuntime configuration checks; replace only owned daemon I/O."""
    from mldsafail.evaluator.native_workload import NativeRuntime
    raw=canonical(native_fixture[0].config)
    instance.source['recipe']['configuration_templates']['native']=raw.hex()
    instance.source['manifest']['configurations']['native']['sha256']=digest(raw)
    daemon=tmp_path/'daemon-birth.json';daemon.write_bytes(canonical(instance.source['host']['runtime_identity']))
    monkeypatch.setattr(NativeRuntime,'identity',lambda self:json.loads(daemon.read_bytes()))
    return daemon


def image_fixture(tmp_path,monkeypatch,native_fixture):
    from tests.test_workload_images import fixture as image_archive
    from deploy.workload_images import inspect_archive,without_tags
    instance,journal=backend(tmp_path)
    raw=tmp_path/'source-images.tar';selected=image_archive(raw)
    offline=instance.bundle/'offline';offline.mkdir()
    frozen=offline/'images.tar';binding=without_tags(raw,frozen,selected)
    instance.source['manifest']['images']=binding
    daemon=bind_runtime(instance,tmp_path,monkeypatch,native_fixture)
    retained='sha256:'+'e'*64
    initial={retained:dict(Id=retained,Os='linux',Architecture='amd64',Config=dict(Labels=dict(retained='yes')))}
    store=tmp_path/'image-store.json';store.write_bytes(canonical(initial));calls=[]
    def command(argv):
        calls.append(argv);current=json.loads(store.read_bytes())
        if argv[-5:]==['image','ls','--no-trunc','--format','{{.Repository}}:{{.Tag}} {{.ID}}']:
            return ('retained:current '+retained+'\n').encode()
        if 'inspect' in argv:return canonical([current[argv[-1]]])
        assert 'load' in argv and argv[-2:]==['--input',str(frozen)] and '--net' in argv
        checked=inspect_archive(frozen,selected)
        for identifier,configuration in checked['configurations'].items():
            current[identifier]=dict(Id=identifier,Os=configuration['os'],Architecture=configuration['architecture'],
                                     Config=configuration.get('config',{}))
        store.write_bytes(canonical(current));return b'loaded inert images'
    instance.command=command
    return instance,journal,store,initial,calls,daemon


@pytest.mark.parametrize('boundary',BOUNDARIES)
@pytest.mark.parametrize('replacement',[None,'configuration','daemon'])
def test_image_load_real_archive_observer_and_acknowledgement_boundaries(tmp_path,monkeypatch,native_fixture,boundary,replacement):
    instance,journal,store,retained,calls,daemon=image_fixture(tmp_path,monkeypatch,native_fixture)
    step=dict(id='install:images',action='images');begin(instance,journal,step)
    acknowledged(instance,journal,step,boundary)
    current=json.loads(store.read_bytes())
    assert all(current[key]==value for key,value in retained.items())
    if boundary=='intent':
        with pytest.raises(KeyError):instance.observe(step,journal)
        assert not instance.reconcilable(step,{},journal)
    else:
        observed=instance.observe(step,journal);assert instance.valid_outcome(step,observed,journal)
        assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
        if replacement=='configuration':
            identifier=instance.source['manifest']['images']['selected']['coordinator']
            current[identifier]['Config']['Labels']['role']='unreviewed';store.write_bytes(canonical(current))
            with pytest.raises(WorkloadBlocked,match='image_configuration_changed'):instance.observe(step,journal)
        if replacement=='daemon':
            changed=json.loads(daemon.read_bytes());changed['daemon_birth']['start_ticks']+=1;daemon.write_bytes(canonical(changed))
            if boundary=='acknowledged':
                with pytest.raises(WorkloadBlocked,match='daemon_changed'):instance.reconcilable(step,observed,journal)
    assert len([argv for argv in calls if 'load' in argv])==(boundary!='intent')
    assert not instance.partial_reconcilable(step,{},journal)


def dependency_fixture(tmp_path):
    from deploy.workload_dependencies import entrypoint_code
    instance,journal=backend(tmp_path);instance.python=str(instance.root/'.venv/bin/python')
    instance.recipe['interpreter']['path']=sys.executable
    (instance.bundle/'pyproject.toml').write_bytes(b'[project.scripts]\nfixture-tool = "fixture_module:main"\n')
    wheel=instance.bundle/'offline';wheel.mkdir();(wheel/'fixture.whl').write_bytes(b'inert wheel bytes')
    instance.source['manifest']['dependencies']=['offline/fixture.whl']
    expected={'pyvenv.cfg':(b'fixture interpreter configuration',0o600),
              'lib/fixture_module.py':(b'def main():\n    return 0\n',0o600),
              'bin/fixture-tool':(entrypoint_code(instance.bundle,instance.root/'.venv/bin/python','fixture_module','main'),0o700)}
    instance.recipe['installed_files']={name:dict(sha256=digest(data),bytes=len(data),mode=mode)
                                       for name,(data,mode) in expected.items()}
    calls=[];fail_after=[None]
    def command(argv):
        calls.append(argv)
        assert '--net' in argv and '--offline' in argv and '--no-cache' in argv
        venv=instance.root/'.venv'
        if 'venv' in argv:
            assert argv[-1]==str(venv);venv.mkdir(mode=0o700);(venv/'bin').mkdir()
            (venv/'bin/python').symlink_to(sys.executable)
            (venv/'pyvenv.cfg').write_bytes(expected['pyvenv.cfg'][0]);(venv/'pyvenv.cfg').chmod(0o600)
            if fail_after[0]=='venv':raise InterruptedError('after venv external effect')
        else:
            assert 'pip' in argv and 'install' in argv and '--no-index' in argv and '--no-deps' in argv
            (venv/'lib').mkdir();(venv/'lib/fixture_module.py').write_bytes(expected['lib/fixture_module.py'][0])
            (venv/'lib/fixture_module.py').chmod(0o600)
            if fail_after[0]=='wheel':raise InterruptedError('after wheel external effect')
        return b''
    instance.command=command
    return instance,journal,calls,fail_after


@pytest.mark.parametrize('boundary',BOUNDARIES)
def test_dependency_construction_inventory_and_entrypoints_boundaries(tmp_path,boundary):
    instance,journal,calls,_=dependency_fixture(tmp_path)
    step=dict(id='install:dependencies',action='dependencies');begin(instance,journal,step)
    acknowledged(instance,journal,step,boundary)
    observed=instance.observe(step,journal)
    assert instance.valid_outcome(step,observed,journal)==(boundary!='intent')
    assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
    if boundary!='intent':
        file=instance.root/'.venv/lib/fixture_module.py';file.write_bytes(b'substituted')
        changed=instance.observe(step,journal)
        assert not instance.valid_outcome(step,changed,journal)
        assert not instance.reconcilable(step,changed,journal)
        assert file.read_bytes()==b'substituted'
    assert len(calls)==(0 if boundary=='intent' else 2)


@pytest.mark.parametrize('effect',['venv','wheel'])
def test_dependency_internal_partial_construction_is_preserved_and_not_replayed(tmp_path,effect):
    instance,journal,calls,fail_after=dependency_fixture(tmp_path);fail_after[0]=effect
    step=dict(id='install:dependencies',action='dependencies');begin(instance,journal,step)
    with pytest.raises(InterruptedError):instance.apply(step,journal)
    observed=instance.observe(step,journal)
    assert observed and not instance.valid_outcome(step,observed,journal)
    assert not instance.partial_reconcilable(step,observed,journal)
    assert not instance.reconcilable(step,observed,journal)
    saved=deepcopy(observed);attempts=len(calls)
    with pytest.raises(WorkloadBlocked,match='destination_not_absent'):instance.before(step,journal)
    assert instance.observe(step,journal)==saved and len(calls)==attempts


def unit_fixture(tmp_path,monkeypatch):
    instance,journal=backend(tmp_path)
    units=tmp_path/'units';units.mkdir();manager=tmp_path/'manager';manager.mkdir()
    instance.source['installation']['unit_directory']=str(units)
    instance.source['host']['user_manager']['path']=str(manager)
    originals={}
    for name in instance.proposal['units']:
        path=units/name;path.write_bytes(b'[Unit]\nDescription=Original inert fixture\n');path.chmod(0o644)
        originals[str(path)]=dict(identity(path),gid=path.stat().st_gid,contents_hex=path.read_bytes().hex())
    journal.append('recovery_protocol',version=4);seal_snapshots(journal,originals)
    loaded=tmp_path/'loaded-unit-hashes.json'
    loaded.write_bytes(canonical({name:digest((units/name).read_bytes()) for name in instance.proposal['units']}))
    calls=[];interrupt=[None]
    def command(argv):
        calls.append(argv)
        if 'daemon-reload' in argv:
            if interrupt[0]=='before_reload':raise InterruptedError('after replacement before reload')
            loaded.write_bytes(canonical({name:digest((units/name).read_bytes()) for name in instance.proposal['units']}))
            if interrupt[0]=='after_reload':raise InterruptedError('after reload before acknowledgement')
            return b''
        assert argv[2]=='show';name=argv[3];selected=json.loads(loaded.read_bytes())
        row=dict(LoadState='loaded',FragmentPath=str(units/name),SourcePath='',DropInPaths='',
                 NeedDaemonReload='no' if selected[name]==digest((units/name).read_bytes()) else 'yes')
        return '\n'.join(key+'='+value for key,value in row.items()).encode()
    instance.command=command
    # This adapter has no host scheduling managers; preserve its inert retained
    # sentinel while exercising the concrete unit replacement/observer methods.
    retained=tmp_path/'retained';retained.write_bytes(b'retained')
    def scheduling_admission(journal):assert retained.read_bytes()==b'retained'
    monkeypatch.setattr(instance,'scheduling_transition',scheduling_admission)
    return instance,journal,originals,calls,interrupt,retained


@pytest.mark.parametrize('action',['units','restore_units'])
@pytest.mark.parametrize('boundary',BOUNDARIES)
def test_real_unit_replacement_reload_and_restore_boundaries(tmp_path,monkeypatch,action,boundary):
    instance,journal,originals,calls,_,retained=unit_fixture(tmp_path,monkeypatch)
    install=dict(id='install:units',action='units')
    if action=='restore_units':
        begin(instance,journal,install);instance.apply(install,journal);instance.acknowledge_apply(install,journal)
        journal.append('outcome',step=install['id'],observed=instance.observe(install,journal))
    step=dict(id=('rollback:' if action=='restore_units' else 'install:')+action,action=action)
    begin(instance,journal,step);count=len(calls);acknowledged(instance,journal,step,boundary)
    observed=instance.observe(step,journal)
    assert instance.valid_outcome(step,observed,journal)==(boundary!='intent')
    assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
    assert retained.read_bytes()==b'retained'
    assert len([argv for argv in calls[count:] if 'daemon-reload' in argv])==(boundary!='intent')
    if boundary=='acknowledged':
        loaded=tmp_path/'loaded-unit-hashes.json';loaded.write_bytes(canonical({name:'unloaded' for name in instance.proposal['units']}))
        with pytest.raises(WorkloadBlocked,match='unit_reload_unverified'):instance.reconcilable(step,observed,journal)


@pytest.mark.parametrize('point',['before_reload','after_reload'])
def test_unit_replacement_internal_reload_interruption_blocks_adoption(tmp_path,monkeypatch,point):
    instance,journal,_,calls,interrupt,retained=unit_fixture(tmp_path,monkeypatch)
    step=dict(id='install:units',action='units');begin(instance,journal,step);interrupt[0]=point
    with pytest.raises(InterruptedError):instance.apply(step,journal)
    observed=instance.observe(step,journal);assert instance.valid_outcome(step,observed,journal)
    assert not instance.reconcilable(step,observed,journal)
    assert not instance.partial_reconcilable(step,observed,journal)
    before=deepcopy(observed)
    assert instance.observe(step,journal)==before and retained.read_bytes()==b'retained'


@pytest.fixture
def supervisor_adapter(tmp_path,monkeypatch,native_fixture):
    import socket,tempfile
    import deploy.workload_installation as installation
    from mldsafail.evaluator.workload_client import WorkloadClient
    instance,journal=backend(tmp_path);bind_runtime(instance,tmp_path,monkeypatch,native_fixture)
    instance.source['host']['uid']=os.getuid()
    instance.source['installation']['heavy_path']=str(native_fixture[3])
    proc=native_fixture[2];cgroup=native_fixture[4]
    def fixture_path(value):
        text=str(value)
        if text.startswith('/proc/'):return proc/text.removeprefix('/proc/')
        if text.startswith('/sys/fs/cgroup/'):return cgroup/text.removeprefix('/sys/fs/cgroup/')
        return Path(value)
    monkeypatch.setattr(installation,'Path',fixture_path)
    temporary=tempfile.TemporaryDirectory(prefix='recovery-socket-',dir='/tmp');socket_path=Path(temporary.name).resolve()/'supervisor.sock'
    instance.source['resources']['socket']['path']=str(socket_path)
    instance.enable_path=instance.root/'.supervisor-enabled'
    instance.enable_path.write_bytes(supervisor_enable_contents(instance.proposal));instance.enable_path.chmod(0o600)
    units=tmp_path/'supervisor-units';units.mkdir();name='mldsafail-workload-supervisor.service'
    instance.source['installation']['unit_directory']=str(units)
    (units/name).write_text(instance.proposal['units'][name]);(units/name).chmod(0o600)
    journal.append('recovery_protocol',version=4)
    journal.append('outcome',step='install:enable_supervisor',observed=identity(instance.enable_path))
    journal.append('outcome',step='install:supervisor_unit',observed={name:identity(units/name)})
    state=tmp_path/'service-state.json';state.write_bytes(canonical(dict(active=False,paused=True,phase='complete')))
    endpoints=[];calls=[];pid=77777
    def command(argv):
        calls.append(argv);current=json.loads(state.read_bytes())
        if 'start' in argv:
            endpoint=socket.socket(socket.AF_UNIX);endpoint.bind(str(socket_path));socket_path.chmod(0o600);endpoints.append(endpoint)
            (proc/str(pid)).mkdir();(proc/str(pid)/'stat').write_text(str(pid)+' (inert fixture) '+' '.join(['S']+['0']*18+['1234']+['0']*20))
            (proc/str(pid)/'cgroup').write_text('0::/control')
            born=identity(socket_path)
            record=dict(path=born['path'],device=born['device'],inode=born['inode'],
                        process=dict(pid=pid,start_ticks=1234),supervisor_generation='a'*32)
            installation.exclusive(socket_path.parent/'socket.json',canonical(record));current['active']=True
        elif 'stop' in argv:
            for endpoint in endpoints:endpoint.close()
            socket_path.unlink();current['active']=False
        elif 'show' in argv:
            if '--property=MainPID' in argv:return str(pid if current['active'] else 0).encode()
            if '--property=ActiveState' in argv:return b'active' if current['active'] else b'inactive'
            raise AssertionError(argv)
        else:raise AssertionError(argv)
        state.write_bytes(canonical(current));return b''
    instance.command=command
    monkeypatch.setattr(WorkloadClient,'status',lambda self:{key:value for key,value in json.loads(state.read_bytes()).items() if key!='active'})
    try:yield instance,journal,calls,state,proc,socket_path
    finally:
        for endpoint in endpoints:endpoint.close()
        temporary.cleanup()


@pytest.mark.parametrize('action',['start_paused','stop_supervisor'])
@pytest.mark.parametrize('boundary',BOUNDARIES)
def test_supervisor_start_stop_real_socket_and_process_observation_boundaries(supervisor_adapter,action,boundary):
    instance,journal,calls,state,proc,socket_path=supervisor_adapter
    start=dict(id='install:start_paused',action='start_paused')
    if action=='stop_supervisor':
        begin(instance,journal,start);instance.apply(start,journal);instance.acknowledge_apply(start,journal)
        journal.append('outcome',step=start['id'],observed=instance.observe(start,journal))
    step=dict(id=('rollback:' if action=='stop_supervisor' else 'install:')+action,action=action)
    begin(instance,journal,step);count=len(calls);acknowledged(instance,journal,step,boundary)
    if action=='start_paused' and boundary=='intent':
        with pytest.raises(FileNotFoundError):instance.observe(step,journal)
        assert not instance.reconcilable(step,{},journal)
    else:
        observed=instance.observe(step,journal)
        assert instance.valid_outcome(step,observed,journal)==(boundary!='intent')
        assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
    assert len([argv for argv in calls[count:] if ('start' if action=='start_paused' else 'stop') in argv])==(boundary!='intent')
    assert socket_path.exists()==(action=='start_paused' and boundary!='intent' or action=='stop_supervisor' and boundary=='intent')


@pytest.mark.parametrize('replacement',['process','placement','paused_state'])
def test_started_supervisor_receipt_rejects_observed_process_or_paused_drift(supervisor_adapter,replacement):
    instance,journal,_,state,proc,_=supervisor_adapter
    step=dict(id='install:start_paused',action='start_paused');begin(instance,journal,step)
    instance.apply(step,journal);instance.acknowledge_apply(step,journal)
    if replacement=='process':
        path=proc/'77777/stat';path.write_text(path.read_text().replace('1234','5678'))
    elif replacement=='placement':(proc/'77777/cgroup').write_text('0::/mldsafail-heavy.slice/unauthorized')
    else:
        row=json.loads(state.read_bytes());row['paused']=False;state.write_bytes(canonical(row))
    if replacement!='paused_state':
        with pytest.raises(WorkloadBlocked,match='process_changed|placement_changed'):instance.observe(step,journal)
    else:
        observed=instance.observe(step,journal);assert not instance.valid_outcome(step,observed,journal)
        assert not instance.reconcilable(step,observed,journal)


def scheduling_fixture(tmp_path):
    import shlex
    instance,journal=backend(tmp_path);uid=os.getuid();instance.source['host']['uid']=uid
    directory=tmp_path/'account/.config/systemd/user';directory.mkdir(mode=0o700,parents=True)
    name='fixture-compute.service';original=directory/(name+'.d')/'10-original.conf'
    original.parent.mkdir(mode=0o700);original.write_bytes(b'[Service]\nRestart=always\n');original.chmod(0o600)
    retained=directory/'retained.service';retained.write_bytes(b'[Unit]\nDescription=Retained\n')
    gate=tmp_path/'paused';instance.source['permission_root']=str(gate)
    owner=dict(manager='user',account='fixture',uid=uid,disposition='pause',triggers=[])
    instance.source['scheduling']=dict(owners={name:owner},computational_units=[name])
    instance.source['inventory']['execution_references']={name:dict(DropInPaths=str(original))}
    instance.source['unit_directories']={'user:'+str(uid):str(directory)}
    dropin=original.parent/'90-mldsafail-paused.conf';contents='[Unit]\nConditionPathExists='+str(gate/('user-'+str(uid)+'.allow'))+'\n'
    commands=[['/usr/bin/systemctl','--user','daemon-reload'],['/usr/bin/systemctl','--user','stop',name]]
    instance.proposal['scheduling']=dict(resources=[dict(path=str(dropin),owner_uid=uid,contents=contents)],
        commands_after_exclusive_resource_creation=[shlex.join(argv) for argv in commands])
    manager=tmp_path/'scheduling-manager.json';manager.write_bytes(canonical(dict(active='active',paths=[str(original)],
        hashes={str(original):digest(original.read_bytes())})))
    calls=[];interrupt=[None]
    def command(argv):
        calls.append(argv);row=json.loads(manager.read_bytes())
        if 'daemon-reload' in argv:
            if interrupt[0]=='before_reload':raise InterruptedError('before manager reload effect')
            row.update(paths=[str(original),str(dropin)],hashes={str(path):digest(path.read_bytes()) for path in (original,dropin)})
            manager.write_bytes(canonical(row))
            if interrupt[0]=='after_reload':raise InterruptedError('after reload effect before return')
            return b''
        if 'stop' in argv:
            assert argv[-1]==name;row['active']='inactive';manager.write_bytes(canonical(row))
            if interrupt[0]=='after_stop':raise InterruptedError('after stop before return')
            return b''
        assert argv[2:4]==['show',name]
        if '--property=ActiveState' in argv:return row['active'].encode()
        assert argv[-1]=='--property=DropInPaths,NeedDaemonReload'
        changed=any(not Path(path).exists() or digest(Path(path).read_bytes())!=value for path,value in row['hashes'].items())
        return ('DropInPaths='+' '.join(row['paths'])+'\nNeedDaemonReload='+('yes' if changed else 'no')).encode()
    instance.command=command
    return instance,journal,manager,dropin,original,retained,calls,interrupt


@pytest.mark.parametrize('boundary',BOUNDARIES)
def test_scheduling_inhibition_real_dropins_and_loaded_manager_boundaries(tmp_path,boundary):
    instance,journal,manager,dropin,original,retained,calls,_=scheduling_fixture(tmp_path)
    step=dict(id='install:inhibit_scheduling',action='inhibit_scheduling');begin(instance,journal,step)
    acknowledged(instance,journal,step,boundary)
    if boundary=='intent':
        with pytest.raises(FileNotFoundError):instance.observe(step,journal)
        assert not instance.reconcilable(step,{},journal)
    else:
        observed=instance.observe(step,journal);assert instance.valid_outcome(step,observed,journal)
        assert instance.reconcilable(step,observed,journal)==(boundary=='acknowledged')
        assert dropin.read_text()==instance.proposal['scheduling']['resources'][0]['contents']
        if boundary=='acknowledged':
            row=json.loads(manager.read_bytes());row['paths']=['/unreviewed/override'];manager.write_bytes(canonical(row))
            with pytest.raises(WorkloadBlocked,match='loaded_inhibition_changed'):instance.reconcilable(step,observed,journal)
    assert original.read_bytes()==b'[Service]\nRestart=always\n'
    assert retained.read_bytes()==b'[Unit]\nDescription=Retained\n'
    assert len([argv for argv in calls if 'daemon-reload' in argv])==(boundary!='intent')
    assert len([argv for argv in calls if 'stop' in argv])==(boundary!='intent')


@pytest.mark.parametrize('point',['before_reload','after_reload','after_stop'])
def test_scheduling_internal_external_effects_preserve_partial_state_and_block(tmp_path,point):
    instance,journal,_,dropin,original,retained,calls,interrupt=scheduling_fixture(tmp_path)
    step=dict(id='install:inhibit_scheduling',action='inhibit_scheduling');begin(instance,journal,step);interrupt[0]=point
    with pytest.raises(InterruptedError):instance.apply(step,journal)
    assert dropin.exists()
    if point=='after_stop':
        observed=instance.observe(step,journal);assert instance.valid_outcome(step,observed,journal)
        assert not instance.reconcilable(step,observed,journal)
    else:
        with pytest.raises(WorkloadBlocked,match='computational_unit_active'):instance.observe(step,journal)
    assert not instance.partial_reconcilable(step,{},journal)
    before=identity(dropin);attempts=len(calls)
    with pytest.raises(WorkloadBlocked,match='inhibition_destination_exists'):instance.before(step,journal)
    assert identity(dropin)==before and len(calls)==attempts
    assert original.read_bytes()==b'[Service]\nRestart=always\n' and retained.read_bytes()==b'[Unit]\nDescription=Retained\n'


@pytest.mark.parametrize('loaded',['missing_path','unreviewed_path','needs_reload','incomplete'])
def test_initial_scheduling_acknowledgement_requires_complete_loaded_inhibition(tmp_path,loaded):
    instance,journal,manager,_,_,_,_,_=scheduling_fixture(tmp_path)
    step=dict(id='install:inhibit_scheduling',action='inhibit_scheduling');begin(instance,journal,step);instance.apply(step,journal)
    row=json.loads(manager.read_bytes())
    if loaded=='missing_path':row['paths']=row['paths'][:1]
    elif loaded=='unreviewed_path':row['paths'].append('/unknown.conf')
    elif loaded=='needs_reload':row['hashes'][row['paths'][0]]='not-the-loaded-hash'
    else:
        original=instance.command
        def command(argv):
            if argv[-1]=='--property=DropInPaths,NeedDaemonReload':return b'NeedDaemonReload=no\n'
            return original(argv)
        instance.command=command
    manager.write_bytes(canonical(row))
    observed=instance.observe(step,journal);assert instance.valid_outcome(step,observed,journal)
    with pytest.raises(WorkloadBlocked,match='loaded_inhibition_'):instance.acknowledge_apply(step,journal)
    assert not any(row['event']=='resource_acknowledgement' for row in journal.rows)


@pytest.mark.parametrize('action',['activate','restore_activation'])
@pytest.mark.parametrize('boundary',BOUNDARIES)
def test_activation_apply_uses_proven_candidate_and_preserved_original_births(tmp_path,monkeypatch,action,boundary):
    """Exercise concrete adapter with an inert file exchange, not kernel renameat2."""
    import ctypes
    from types import SimpleNamespace
    instance,journal=backend(tmp_path)
    pointer=tmp_path/'selected';pointer.symlink_to('/previous-inert-release')
    instance.recipe['activation_pointer']=str(pointer)
    instance.source['resources']['activation']=identity(pointer)
    instance.source['rollback']['target']='/previous-inert-release'
    retained=tmp_path/'retained';retained.write_bytes(b'unchanged')
    def scheduling_admission(journal):assert retained.read_bytes()==b'unchanged'
    monkeypatch.setattr(instance,'scheduling_transition',scheduling_admission)
    exchanges=[]
    def exchange(oldfd,old,newfd,new,flags):
        old,new=Path(os.fsdecode(old)),Path(os.fsdecode(new))
        assert old.parent==new.parent==tmp_path and flags==2 and oldfd==newfd==-100
        temporary=tmp_path/'inert-exchange';old.rename(temporary);new.rename(old);temporary.rename(new)
        exchanges.append((old,new));return 0
    monkeypatch.setattr(ctypes,'CDLL',lambda *args,**kwargs:SimpleNamespace(renameat2=exchange))
    journal.append('recovery_protocol',version=4)
    install=dict(id='install:activate',action='activate')
    if action=='restore_activation':
        begin(instance,journal,install);instance.apply(install,journal);instance.acknowledge_apply(install,journal)
        journal.append('outcome',step=install['id'],observed=instance.observe(install,journal))
    step=dict(id=('rollback:' if action=='restore_activation' else 'install:')+action,action=action)
    before=begin(instance,journal,step);count=len(exchanges);acknowledged(instance,journal,step,boundary)
    observed=instance.observe(step,journal)
    assert instance.valid_outcome(step,observed,journal)==(boundary!='intent')
    # This operation has a narrow ownership proof even if the exchange lost its
    # acknowledgement: both candidate and preserved prior inode must still match.
    assert instance.reconcilable(step,observed,journal)==(boundary!='intent')
    assert len(exchanges)-count==(boundary!='intent')
    if boundary!='intent':
        record=next(row for row in reversed(journal.rows) if row['event']=='activation_candidate' and row['step_id']==step['id'])
        preserved=identity(record['observed']['path'])
        assert all(preserved[key]==value for key,value in before.items() if key!='path')
        assert observed['inode']==record['observed']['inode']
    assert retained.read_bytes()==b'unchanged'
