"""Independent process watchdog for bounded, separately authorized packets.

The watchdog stays outside fixture cgroups. It stops on the first failed case,
runs only the bound cleanup once, and withholds success until final inspection.
It never retries a case or treats uncertain process termination as cleanup.
"""
import os
from pathlib import Path
import signal
import resource
import subprocess
import time

from deploy.workload_release import canonical, digest
from deploy.workload_installation import exclusive
from mldsafail.evaluator.native_workload import process_birth, require


def validate(protocol):
    require(set(protocol)=={'origin','identities','fixture_cgroup','startup','cases','cleanup','postflight','timeout_seconds'},
            'watchdog_protocol_fields')
    require(protocol['origin'] in ('synthetic','disposable_database','local_linux','installed_native') and
            type(protocol['timeout_seconds']) is int and 0<protocol['timeout_seconds']<=180,'watchdog_packet_budget')
    require(protocol['identities'] and protocol['fixture_cgroup'].startswith('/sys/fs/cgroup/'),'watchdog_identities_missing')
    require(type(protocol['cases']) is list and protocol['cases'] and
            len({row['name'] for row in protocol['cases']})==len(protocol['cases']),'watchdog_case_order_invalid')
    rows=[protocol['startup'],*protocol['cases'],protocol['cleanup'],protocol['postflight']]
    for row in rows:
        require(set(row)=={'name','argv','seconds'} and type(row['seconds']) in (int,float) and
                0<row['seconds']<=protocol['timeout_seconds'] and type(row['argv']) is list and row['argv'] and
                all(type(v) is str and v and '\0' not in v for v in row['argv']) and
                Path(row['argv'][0]).is_absolute(),'watchdog_command_invalid')
    require(sum(row['seconds'] for row in rows)<=protocol['timeout_seconds'],'watchdog_cleanup_budget_not_reserved')
    return protocol


def execute(protocol,root,*,birth=process_birth):
    validate(protocol)
    root=Path(root);root.mkdir(mode=0o700,exist_ok=False)
    # Native evidence cannot be minted on a synthetic or non-Linux adapter.
    if protocol['origin']!='synthetic':
        actual=Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
        scope=protocol['fixture_cgroup'].removeprefix('/sys/fs/cgroup')
        require(not (actual==scope or actual.startswith(scope+'/')),'watchdog_inside_fixture_cgroup')
    exclusive(root/'intent.json',canonical(protocol))
    deadline=time.monotonic()+protocol['timeout_seconds'];records=[];failed=False;uncertain=False
    def run(row):
        nonlocal uncertain
        path=root/(str(len(records))+'-command.log')
        process=None;identity=None;timed_out=False
        start=time.monotonic()
        with path.open('xb') as output:
            try:
                def limit_output(): resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
                process=subprocess.Popen(row['argv'],stdout=output,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit_output)
                identity=birth(process.pid)
                exclusive(root/(str(len(records))+'-birth.json'),canonical(identity))
                process.wait(timeout=min(row['seconds'],max(.001,deadline-time.monotonic())))
            except subprocess.TimeoutExpired:
                timed_out=True
            finally:
                if process is not None and process.poll() is None:
                    try:
                        require(birth(process.pid)==identity,'watchdog_client_birth_changed')
                        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=min(2,max(.001,deadline-time.monotonic())))
                    except BaseException:
                        uncertain=True
                if process is not None and process.poll() is not None:
                    try: os.killpg(process.pid,0)
                    except ProcessLookupError: pass
                    else: uncertain=True
                output.flush();os.fsync(output.fileno())
        record=dict(name=row['name'],argv_sha256=digest(canonical(row['argv'])),birth=identity,
                    returncode=process.returncode if process else None,timed_out=timed_out,
                    elapsed_seconds=time.monotonic()-start,log_sha256=digest(path.read_bytes()),
                    termination_verified=process is not None and process.poll() is not None and not uncertain)
        records.append(record);exclusive(root/(str(len(records)-1)+'-outcome.json'),canonical(record))
        return record['returncode']==0 and not timed_out and record['termination_verified']
    try:
        failed=not run(protocol['startup'])
        if not failed:
            for row in protocol['cases']:
                if not run(row): failed=True;break
    except BaseException as error:
        failed=True
        exclusive(root/'failure.json',canonical(dict(type=type(error).__name__,message=str(error))))
    cleanup_ok=False;postflight_ok=False
    try:
        cleanup_ok=run(protocol['cleanup'])
        # Even after case failure, postflight records resource/transaction state.
        if cleanup_ok and not uncertain: postflight_ok=run(protocol['postflight'])
    except BaseException as error:
        uncertain=True
        exclusive(root/'cleanup-failure.json',canonical(dict(type=type(error).__name__,message=str(error))))
    success=not failed and cleanup_ok and postflight_ok and not uncertain and time.monotonic()<=deadline
    receipt=dict(schema='mldsafail.workload-watchdog-receipt.v3',origin=protocol['origin'],
        protocol_sha256=digest(canonical(protocol)),identities=protocol['identities'],records=records,
        passed=success,cleanup_verified=cleanup_ok and postflight_ok and not uncertain,
        ownership='released' if cleanup_ok and postflight_ok and not uncertain else 'blocked',
        paused=postflight_ok,automatic_retries=0)
    exclusive(root/'receipt.json',canonical(receipt))
    return receipt
