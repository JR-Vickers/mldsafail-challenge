"""Root-console all-account scheduling inventory; no scheduling mutations.

Stream raw output only into an exclusively created private file. Literal script
references require independent recursive review; this collector never interprets
or executes scripts. Any missed owner, command failure or bound blocks readiness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd

from deploy import privileged_scheduling as base

MAX_ACCOUNTS = 128


def inventory(accounts):
    if len(accounts) > MAX_ACCOUNTS:
        raise ValueError('account_inventory_limit')
    sections = dict(base.SECTIONS)
    roots = list(base.ROOTS)
    owners = []
    for account in accounts:
        uid, name, home = account.pw_uid, account.pw_name, account.pw_dir
        owners.append(dict(uid=uid, account=name, home=home))
        # All crontabs, including service accounts, are part of root visibility.
        sections['account_'+name+'_cron'] = ['crontab', '-l', '-u', name]
        sections['account_'+name+'_manager'] = ['systemctl', 'show', f'user@{uid}.service',
                                                '--property=Id,ActiveState,UnitFileState,ControlGroup,Delegate']
        if Path(home).is_absolute() and home != '/':
            roots.extend([str(Path(home)/'.config/systemd/user'), str(Path(home)/'.config/containers/systemd')])
        runtime = Path('/run/user')/str(uid)
        if (runtime/'bus').exists():
            prefix = ['runuser', '-u', name, '--', 'env', 'XDG_RUNTIME_DIR='+str(runtime), 'systemctl', '--user']
            for kind, args in (
                ('units', ['list-units', '--all', '--plain', '--no-pager', '--no-legend']),
                ('files', ['list-unit-files', '--no-pager', '--no-legend']),
                ('identities', ['show', '--all', '*.service', '*.timer', '*.socket', '*.path',
                               '--property=Id,Names,ActiveState,UnitFileState,ControlGroup,Delegate,Triggers,TriggeredBy,Restart,FragmentPath,DropInPaths,ExecCondition,ExecStart,ExecStartPre,ExecStartPost,ExecStop,ExecStopPost,EnvironmentFiles,Environment,WorkingDirectory'])):
                sections['account_'+name+'_'+kind] = prefix+args
    # Include vendor units and global user units, not only local overrides.
    roots.extend(['/usr/lib/systemd/system', '/usr/lib/systemd/user', '/etc/systemd/user',
                  '/etc/containers/systemd', '/etc/rc.local', '/etc/init.d'])
    sections['system_execution_references'] = ['systemctl', 'show', '--all', '*.service', '*.timer', '*.socket', '*.path',
        '--property=Id,Names,ExecCondition,ExecStart,ExecStartPre,ExecStartPost,ExecStop,ExecStopPost,EnvironmentFiles,Environment,WorkingDirectory,FragmentPath,DropInPaths,Triggers,TriggeredBy']
    return sections, tuple(dict.fromkeys(roots)), owners


def collect(raw_stream, reviewed_paths=()):
    if os.getuid() != 0:
        raise ValueError('owner_root_console_required')
    accounts = pwd.getpwall()
    sections, roots, owners = inventory(accounts)
    original_sections, original_roots = base.SECTIONS, base.ROOTS
    try:
        base.SECTIONS, base.ROOTS = sections, roots
        result = base.collect(hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), raw_stream, reviewed_paths)
    finally:
        base.SECTIONS, base.ROOTS = original_sections, original_roots
    result.update(schema='mldsafail.scheduling-collection.v3', owners=owners,
                  dependency_collector_sha256=hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest(),
                  readiness=False, execution_authority=False,
                  unresolved=['recursive_script_references_and_classification',
                              'container_daemons_and_restart_owners', 'at_job_contents',
                              'delegation_permissions_and_output_volume'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-output', type=Path, required=True)
    parser.add_argument('--reviewed-path', action='append', default=[])
    args = parser.parse_args()
    parent = args.raw_output.absolute().parent
    if any(p.is_symlink() for p in (parent, *parent.parents)) or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077:
        raise ValueError('owner_private_directory_required')
    fd = os.open(args.raw_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as raw:
        result = collect(raw, args.reviewed_path)
        raw.flush(); os.fsync(raw.fileno())
    result['raw_sha256'] = hashlib.sha256(args.raw_output.read_bytes()).hexdigest()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
