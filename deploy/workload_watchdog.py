"""Independent process watchdog for bounded, separately authorized packets.

The watchdog stays outside fixture cgroups. It stops on the first failed case,
runs only the bound cleanup once, and withholds success until final inspection.
It never retries a case or treats uncertain process termination as cleanup.
"""
import os
import json
import socket
from pathlib import Path
import signal
import resource
import subprocess
import time

from deploy.workload_release import canonical, digest
from deploy.workload_installation import exclusive,identity
from mldsafail.evaluator.native_workload import process_birth, require


def validate(protocol):
    require(set(protocol)=={'origin','identities','fixture_cgroup','startup','cases','cleanup','postflight','timeout_seconds'},
            'watchdog_protocol_fields')
    require(protocol['origin'] in ('synthetic','disposable_database','local_linux','installed_native') and
            type(protocol['timeout_seconds']) is int and 0<protocol['timeout_seconds']<=180,'watchdog_packet_budget')
    scope=protocol['fixture_cgroup']
    require(protocol['identities'] and type(scope) is str and scope.startswith('/sys/fs/cgroup/') and
            str(Path(scope))==scope and '..' not in Path(scope).parts,'watchdog_identities_missing')
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


def postflight_observation(raw,protocol):
    row=json.loads(raw)
    require(type(row) is dict and set(row)=={'schema','origin','identities_sha256','paused','owned_resources',
            'transactions','retained_before','retained_after'},'watchdog_postflight_observation_fields')
    require(row['schema']=='mldsafail.workload-control-postflight.v3' and row['origin']==protocol['origin'] and
            row['identities_sha256']==digest(canonical(protocol['identities'])),'watchdog_postflight_binding_changed')
    require(row['paused'] is True and type(row['owned_resources']) is int and row['owned_resources']==0 and
            row['transactions']=='resolved' and type(row['retained_before']) is dict and
            row['retained_before']==protocol['identities'].get('retained_services')==row['retained_after'] and
            (protocol['origin']=='synthetic' or bool(row['retained_before'])),'watchdog_postflight_unresolved')
    return row


def native_authority(protocol,review_path,authorization_path,root):
    """Bind separate native-test authority to exact packet bytes, host and review."""
    from deploy.workload_installation import private
    from deploy.workload_native_protocol import claim
    require(review_path is not None and authorization_path is not None,'watchdog_native_authority_required')
    review_raw,review=private(review_path);authority_raw,authority=private(authorization_path)
    binding=digest(canonical(protocol));now=time.time()
    require(review.get('decision')=='approved' and review.get('protocol_sha256')==binding and
            review.get('implemented_by') and review.get('reviewed_by') and
            review['implemented_by']!=review['reviewed_by'],'watchdog_native_review_required')
    require(authority.get('schema')=='mldsafail.workload-native-authority.v3' and
            authority.get('purpose')=='native_workload_control_only' and authority.get('authorized_by')=='owner' and
            authority.get('protocol_sha256')==binding and authority.get('review_sha256')==digest(review_raw) and
            type(authority.get('issued_at')) in (int,float) and type(authority.get('expires_at')) in (int,float) and
            authority['issued_at']<=now<authority['expires_at'] and
            protocol['timeout_seconds']<=authority['expires_at']-now<=180 and
            0<authority['expires_at']-authority['issued_at']<=180 and
            type(authority.get('nonce')) is str and len(authority['nonce'])==32,'watchdog_native_exact_authority_required')
    host=protocol['identities']
    require(host.get('hostname')==socket.gethostname() and host.get('uid')==os.getuid() and
            host.get('boot_id')==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'watchdog_native_host_changed')
    claim(authorization_path,protocol,expected_sha256=digest(authority_raw),journal_root=Path(root).parent)


def execute(protocol,root,*,birth=process_birth,review_path=None,authorization_path=None):
    started=time.monotonic()
    validate(protocol)
    if protocol['origin']=='installed_native':native_authority(protocol,review_path,authorization_path,root)
    root=Path(root);root.mkdir(mode=0o700,exist_ok=False)
    # Native evidence cannot be minted on a synthetic or non-Linux adapter.
    if protocol['origin']!='synthetic':
        path=Path(protocol['fixture_cgroup'])
        require(not any(parent.is_symlink() for parent in (path,*path.parents)),'watchdog_fixture_symlink')
        expected=protocol['identities'].get('fixture_birth',{})
        observed=identity(path)
        require(expected.get('path')==str(path) and all(type(expected.get(key)) is int and
                observed.get(key)==expected[key] for key in ('device','inode')),'watchdog_fixture_birth_changed')
        membership=Path('/proc/self/cgroup').read_text().splitlines()
        require(len(membership)==1 and membership[0].startswith('0::/'),'watchdog_unified_membership_required')
        actual=membership[0][3:]
        scope=protocol['fixture_cgroup'].removeprefix('/sys/fs/cgroup')
        require(not (actual==scope or actual.startswith(scope+'/')),'watchdog_inside_fixture_cgroup')
    exclusive(root/'intent.json',canonical(protocol))
    deadline=started+protocol['timeout_seconds'];records=[];failed=False;uncertain=False
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
        if cleanup_ok and not uncertain:
            postflight_ok=run(protocol['postflight'])
            if postflight_ok:
                postflight=postflight_observation((root/(str(len(records)-1)+'-command.log')).read_bytes(),protocol)
                exclusive(root/'postflight-observation.json',canonical(postflight))
    except BaseException as error:
        uncertain=True;postflight_ok=False
        exclusive(root/'cleanup-failure.json',canonical(dict(type=type(error).__name__,message=str(error))))
    success=not failed and cleanup_ok and postflight_ok and not uncertain and time.monotonic()<=deadline
    receipt=dict(schema='mldsafail.workload-watchdog-receipt.v3',origin=protocol['origin'],
        protocol_sha256=digest(canonical(protocol)),identities=protocol['identities'],records=records,
        passed=success,cleanup_verified=cleanup_ok and postflight_ok and not uncertain,
        ownership='released' if cleanup_ok and postflight_ok and not uncertain else 'blocked',
        paused=postflight_ok,automatic_retries=0)
    exclusive(root/'receipt.json',canonical(receipt))
    return receipt
