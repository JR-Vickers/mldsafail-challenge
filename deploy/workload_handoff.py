"""Bind and quiesce a previous paused supervisor without resuming computation.

Observations remain private. This adapter is not installation authority; the
execution engine must journal its intent and enforce the frozen proposal first.
"""
import json
import re
from pathlib import Path

from deploy.workload_installation import identity
from deploy.workload_release import canonical,digest,regular
from deploy.workload_schedule_v3 import unit_name
from mldsafail.evaluator.native_workload import NativeRuntime,private_json,process_birth,require,values
from mldsafail.evaluator.workload_service import call_private
from mldsafail.evaluator.workload import HostGate


NAME='mldsafail-workload-supervisor.service'


def identifier(source):
    matches=[name for name,owner in source['scheduling']['owners'].items()
             if owner['manager']=='user' and owner['uid']==source['host']['uid'] and unit_name(name,owner)==NAME]
    require(len(matches)<=1,'handoff_previous_supervisor_ambiguous')
    return matches[0] if matches else None


def validate(source):
    name=identifier(source);proof=source['rollback'].get('supervisor')
    if name is None:
        require(proof is None,'handoff_unexpected_previous_binding')
        return
    require(type(proof) is dict and set(proof)=={'identifier','unit','active','process','socket',
            'supervisor_generation','state'} and proof['identifier']==name and type(proof['active']) is bool,
            'handoff_previous_observation_missing')
    require(source['scheduling']['owners'][name]['disposition']=='retain','handoff_supervisor_must_remain_control_service')
    refs=source['inventory'].get('execution_references',{}).get(name,{})
    require(not refs.get('DropInPaths') and not refs.get('EnvironmentFiles'),
            'handoff_previous_control_overrides_require_adapter')
    unit=proof['unit'];socket=proof['socket']
    require(unit.get('state')=='observed' and unit.get('path')==source['installation']['unit_directory']+'/'+NAME and
            unit.get('uid') in (0,source['host']['uid']) and
            all(type(unit.get(key)) is int and unit[key]>=0 for key in ('device','inode','mode')) and unit['inode']>0 and
            unit.get('sha256')==source['rollback']['manifest']['files']['generated/'+NAME]['sha256'],
            'handoff_previous_unit_binding')
    require(type(socket) is dict and type(socket.get('path')) is str and socket['path'].startswith('/') and
            socket['path']!=source['resources']['socket']['path'],'handoff_previous_socket_binding')
    if proof['active']:
        process=proof['process']
        require(type(process) is dict and set(process)=={'pid','start_ticks'} and
                all(type(value) is int and value>0 for value in process.values()) and
                type(proof['supervisor_generation']) is str and re.fullmatch('[a-f0-9]{32}',proof['supervisor_generation']) and
                socket.get('state')=='observed' and socket.get('uid')==source['host']['uid'] and socket.get('mode')==0o600 and
                all(type(socket.get(key)) is int and socket[key]>=0 for key in ('device','inode')) and socket['inode']>0 and
                proof['state'] is not None,'handoff_previous_active_binding')
    else:
        require(proof['process'] is proof['supervisor_generation'] is None and socket.get('state')=='absent',
                'handoff_previous_inactive_binding')
    state=proof['state']
    require(not proof['active'] or source['resources']['delegation']['state']=='observed',
            'handoff_active_supervisor_requires_observed_delegation')
    if state is not None:
        require(type(state) is dict and set(state)=={'workload_id','phase','paused','reference_sha256','state_sha256'} and
                re.fullmatch('[a-f0-9]{32}',state['workload_id']) and state['paused'] is True and
                state['phase'] in ('acquired','cleaned','complete') and
                all(re.fullmatch('[a-f0-9]{64}',state[key]) for key in ('reference_sha256','state_sha256')) and
                (state['phase']!='acquired' or state['reference_sha256']==digest(canonical({'bootstrap':True}))),
                'handoff_previous_state_binding')


def configuration(source):
    rollback=source['rollback'];manifest=rollback['manifest']
    row=manifest['configurations']['supervisor'];path=Path(row['path'])
    raw,_=regular(path.parent,path.name)
    require(digest(raw)==rollback['configuration_hashes']['supervisor'],'handoff_previous_configuration_changed')
    config=json.loads(raw);native_path=manifest['configurations']['native']['path']
    require(set(config)=={'root','socket','helper','roles'} and
            config['helper']==[str(Path(rollback['release'])/'.venv/bin/python'),'-m',
                               'mldsafail.evaluator.native_workload','--configuration',native_path] and
            config['socket']==config['root']+'/supervisor.sock' and
            config['root']!=source['installation']['gate_root'], 'handoff_previous_configuration_edges')
    native=private_json(native_path)
    require(digest(canonical(native))==rollback['configuration_hashes']['native'] and
            native['root']==config['root'] and native['heavy']==source['installation']['heavy_path'],
            'handoff_previous_native_configuration_changed')
    return config,native


def state_summary(state):
    require(type(state) is dict and state.get('paused') is True and
            (state.get('phase') in ('cleaned','complete') or
             state.get('phase')=='acquired' and state.get('reference')=={'bootstrap':True}),
            'handoff_previous_ownership_not_quiescent')
    require('requests' in state or 'request_counts' in state,'handoff_previous_request_evidence_missing')
    counts=state.get('request_counts')
    require(counts is None or type(counts) is dict and set(counts)=={'intent','complete'} and
            all(type(value) is int and value>=0 for value in counts.values()) and counts['intent']==0,
            'handoff_previous_request_unresolved')
    require(type(state.get('requests',{})) is dict and
            all(type(row) is dict and row.get('phase')=='complete' for row in state.get('requests',{}).values()),
            'handoff_previous_request_unresolved')
    return dict(workload_id=state['workload_id'],phase=state['phase'],paused=True,
                reference_sha256=digest(canonical(state['reference'])),state_sha256=digest(canonical(state)))


def observe(source,command,*,replacement=None):
    """Read actual previous births and paused state; never stop or edit a unit."""
    name=identifier(source)
    if name is None:return None
    owner=source['scheduling']['owners'][name]
    require(owner['disposition']=='retain','handoff_supervisor_must_remain_control_service')
    config,native=configuration(source)
    unit=Path(source['installation']['unit_directory'])/NAME
    actual=identity(unit)
    expected=source['rollback']['manifest']['files']['generated/'+NAME]
    if replacement is None:
        require(actual.get('uid') in (0,source['host']['uid']) and actual.get('sha256')==expected['sha256'] and
                not unit.is_symlink(),'handoff_previous_unit_changed')
        raw=command(['/usr/bin/systemctl','--user','show',NAME,'--all','--property=ActiveState,SubState,MainPID']).decode()
        settings=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        require(set(settings)=={'ActiveState','SubState','MainPID'} and
                settings['ActiveState'] in ('active','inactive','failed'),'handoff_previous_unit_transitioning')
    else:
        require(actual==replacement,'handoff_replacement_unit_changed')
        previous=source['rollback']['supervisor']['process']
        if previous is not None:
            try:current=process_birth(previous['pid'])
            except FileNotFoundError:current=None
            require(current!=previous,'handoff_previous_process_survived')
        settings=dict(ActiveState='inactive',SubState='dead',MainPID='0')
    active=settings['ActiveState']=='active';pid=int(settings['MainPID'])
    socket=identity(config['socket']);process=None;generation=None;state=None
    runtime=NativeRuntime(native,run=command)
    require(runtime.identity()==source['host']['runtime_identity'],'handoff_previous_daemon_changed')
    if active:
        require(pid>0 and socket.get('uid')==source['host']['uid'] and socket.get('mode')==0o600,
                'handoff_previous_socket_missing')
        record=private_json(Path(config['root'])/'socket.json');process=process_birth(pid)
        require(record['process']==process and all(record.get(key)==socket.get(key) for key in ('path','device','inode')) and
                Path('/proc/'+str(pid)).stat().st_uid==source['host']['uid'],'handoff_previous_birth_changed')
        generation=record['supervisor_generation']
        status=call_private(config['socket'],dict(id='status',method='status',argument={}))
        state=private_json(Path(config['root'])/'workload.json')
        public={key:value for key,value in state.items() if key not in ('requests','completed_workloads','pause_actions')}
        public['request_counts']={phase:sum(row['phase']==phase for row in state.get('requests',{}).values())
                                  for phase in ('intent','complete')}
        require(status==public,'handoff_previous_memory_and_journal_changed')
    else:
        require(pid==0 and socket['state']=='absent','handoff_previous_inactive_resources_present')
        path=Path(config['root'])/'workload.json'
        if path.exists() or path.is_symlink():state=private_json(path)
    if state is not None:HostGate(config['root'],runtime)._validate(state)
    summary=state_summary(state) if state is not None else None
    if state is not None:require(runtime.stopped(state) is True,'handoff_previous_resources_present')
    heavy=Path(native['heavy'])
    if heavy.exists():require(values(heavy/'cgroup.events')['populated']==0,'handoff_previous_heavy_populated')
    else:require(not active and state is None and source['resources']['delegation']['state']=='proposed',
                 'handoff_previous_heavy_disappeared')
    return dict(identifier=name,unit=actual,active=active,process=process,socket=socket,
                supervisor_generation=generation,state=summary)


def stop(source,command):
    expected=source['rollback'].get('supervisor')
    require(observe(source,command)==expected,'handoff_previous_observation_changed')
    if expected is not None and expected['active']:
        command(['/usr/bin/systemctl','--user','stop',NAME])


def stopped(source,command,*,replacement=None):
    expected=source['rollback'].get('supervisor')
    actual=observe(source,command) if replacement is None else observe(source,command,replacement=replacement)
    if expected is None:
        require(actual is None,'handoff_unexpected_previous_supervisor')
        return dict(verified=True,previous_supervisor=None)
    require(actual is not None and actual['active'] is False and actual['process'] is None and
            actual['socket']['state']=='absent' and actual['unit']==(expected['unit'] if replacement is None else replacement),
            'handoff_previous_supervisor_not_stopped')
    if expected['state'] is None:require(actual['state'] is None,'handoff_previous_state_appeared')
    else:
        require(actual['state'] is not None and actual['state']['workload_id']==expected['state']['workload_id'] and
                actual['state']['reference_sha256']==expected['state']['reference_sha256'],
                'handoff_previous_ownership_changed')
    # Preserve the retired unit's observed identity in this historical outcome.
    # Any current replacement was independently checked against its journal.
    actual['unit']=expected['unit']
    return dict(verified=True,previous_supervisor=actual)
