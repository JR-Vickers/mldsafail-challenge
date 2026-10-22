"""Fresh complete systemd manager/unit name closure, with owner-qualified IDs."""
import json
import re
from deploy.workload_preparation import manager_prefix
from deploy.workload_schedule_v3 import unit_name
from mldsafail.evaluator.native_workload import require


def expected(record):
    groups={}
    for identifier,owner in record['owners'].items():
        key=owner['manager']+':'+str(owner['uid'])
        groups.setdefault(key,[]).append(unit_name(identifier,owner))
    return {key:sorted(names) for key,names in groups.items()}


def validate(source):
    registry=source['inventory']['manager_units']
    require(type(registry) is dict and {'system:0','user:'+str(source['host']['uid'])}<=set(registry),
            'registry_required_managers_missing')
    for key,units in registry.items():
        require(re.fullmatch(r'(system:0|user:\d+)',key) and type(units) is list and
                units==sorted(set(units)),'registry_manager_units_invalid')
    classified=expected(source['scheduling'])
    require(all(registry.get(key)==names for key,names in classified.items()) and
            all(classified.get(key,[])==names for key,names in registry.items()),'registry_unclassified_units')


def observe(source,command,*,installed_units=False):
    validate(source)
    # Root visibility distinguishes inactive accounts from inaccessible managers.
    script=('import json,pwd,pathlib,stat; rows=pwd.getpwall();assert len(rows)<=128;out=[];'
            '\nfor account in rows:\n p=pathlib.Path("/run/user")/str(account.pw_uid)/"bus"\n'
            ' if p.exists():\n  s=p.lstat();assert stat.S_ISSOCK(s.st_mode) and s.st_uid==account.pw_uid;out.append(dict(uid=account.pw_uid,account=account.pw_name))\n'
            'print(json.dumps(out))')
    accounts=json.loads(command(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script]))
    owners={'system:0':dict(manager='system',uid=0,account='root')}
    for account in accounts:owners['user:'+str(account['uid'])]=dict(manager='user',**account)
    require(set(owners)==set(source['inventory']['manager_units']),'registry_manager_census_changed')
    for owner in source['scheduling']['owners'].values():
        key=owner['manager']+':'+str(owner['uid'])
        require(key in owners and owner['account']==owners[key]['account'],'registry_owner_account_changed')
    actual={}
    for key,owner in owners.items():
        units=set();prefix=manager_prefix(owner,source['host']['uid'])
        for action in ('list-units','list-unit-files'):
            raw=command([*prefix,action,'--all','--type=service,timer,socket,path','--full','--plain','--no-legend','--no-pager']).decode()
            for line in raw.splitlines():
                if not line.strip():continue
                name=line.split()[0];unit_name(name,owner);units.add(name)
        actual[key]=sorted(units)
    wanted={key:list(value) for key,value in source['inventory']['manager_units'].items()}
    if installed_units:
        key='user:'+str(source['host']['uid'])
        wanted[key]=sorted(set(wanted[key])|{'mldsafail-workload-supervisor.service'})
    require(actual==wanted,'registry_unit_inventory_changed')
    return actual


EXECUTION_FIELDS=('ExecCondition','ExecStart','ExecStartPre','ExecStartPost','ExecStop','ExecStopPost')
REFERENCE_FIELDS=('FragmentPath','DropInPaths','EnvironmentFiles','Names','TriggeredBy',*EXECUTION_FIELDS)


def stable_execution(value):
    """Discard only systemd's terminal per-command process accounting fields."""
    if not value:return value
    pattern=re.compile(r'\{ (path=.*? ; argv\[\]=.*? ; ignore_errors=(?:yes|no)) ; '
        r'start_time=\[[^\]\n]*\] ; stop_time=\[[^\]\n]*\] ; pid=\d+ ; '
        r'code=[^;{}\n]+ ; status=[^;{}\n]+ \}')
    rows=list(pattern.finditer(value))
    require(rows and ' '.join(row[0] for row in rows)==value,'registry_execution_status_syntax')
    return tuple(row[1] for row in rows)


def references(source,command,*,inhibited=False):
    expected=source['inventory'].get('execution_references',{})
    require(set(expected)==set(source['scheduling']['owners']),'registry_execution_references_missing')
    actual={}
    for identifier,owner in source['scheduling']['owners'].items():
        before=expected[identifier]
        require(set(before)==set(REFERENCE_FIELDS) and all(type(value) is str for value in before.values()),
                'registry_execution_reference_fields')
        raw=command([*manager_prefix(owner,source['host']['uid']),'show',unit_name(identifier,owner),
                     '--all','--property='+','.join(REFERENCE_FIELDS)]).decode()
        row=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
        require(set(row)==set(REFERENCE_FIELDS),'registry_reference_collection_incomplete')
        wanted=dict(before)
        if inhibited and owner['disposition']=='pause':
            key=owner['manager']+':'+str(owner['uid'])
            path=source['unit_directories'][key]+'/'+unit_name(identifier,owner)+'.d/90-mldsafail-paused.conf'
            wanted['DropInPaths']=' '.join(sorted(set(before['DropInPaths'].split())|{path}))
            require(bool(before['FragmentPath']),'registry_transient_computation_requires_adapter')
            # Stopping a file-backed unit changes execution timestamps/status.
            # Approved fragment/drop-in bytes and all reference paths stay bound.
            for field in EXECUTION_FIELDS:
                require(stable_execution(before[field])==stable_execution(row[field]),
                        'registry_loaded_execution_changed')
                wanted[field]=row[field]
        for key in ('DropInPaths','Names','TriggeredBy'):
            row[key]=' '.join(sorted(row[key].split()));wanted[key]=' '.join(sorted(wanted[key].split()))
        require(row==wanted,'registry_execution_reference_changed')
        actual[identifier]=row
    return actual


def validate_reference_files(source):
    existing=set(source['inventory']['original_files']);absent=set(source['inventory']['absent_files'])
    require(not existing&absent,'registry_reference_file_state_conflict')
    for row in source['inventory']['execution_references'].values():
        paths=set(row['DropInPaths'].split())
        if row['FragmentPath']:paths.add(row['FragmentPath'])
        environment=row['EnvironmentFiles']
        matches=list(re.finditer(r'(\S+) \(ignore_errors=(?:yes|no)\)',environment))
        require(not environment or ' '.join(match[0] for match in matches)==environment,'registry_environment_reference_syntax')
        paths.update(match[1] for match in matches)
        require(paths<=existing|absent,'registry_unbound_reference_file')
