"""Inherited-lock worker and subreaper shim for disposable fixtures only."""
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

from deploy.workload_installation import Journal, exclusive, identity, private
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import require, process_birth


def inherited_lock(root, fd):
    root = Path(root)
    require(type(fd) is int and fd >= 3, 'fixture_inherited_lock_required')
    before = os.fstat(fd)
    current = (root/'lifecycle.lock').lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
            stat.S_IMODE(before.st_mode) == 0o600 and
            (before.st_dev,before.st_ino) == (current.st_dev,current.st_ino), 'fixture_inherited_lock_changed')
    # An independently opened descriptor cannot take this lock while its parent
    # holds it. The inherited open-file description can.
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return fd


def wrap(root, fd, report, allowance, argv):
    """Keep the lifecycle descriptor across the existing subreaper's exec."""
    inherited_lock(root,fd)
    from deploy import workload_observation
    original = subprocess.Popen
    def launch(*args,**kwargs):
        require('pass_fds' not in kwargs,'fixture_worker_descriptor_override')
        return original(*args,pass_fds=(fd,),**kwargs)
    subprocess.Popen = launch
    try:
        sys.argv = [str(workload_observation.__file__),report,str(allowance),*argv]
        workload_observation.main()
    finally:
        subprocess.Popen = original


def work(root, fd, token, operation, output, *, phase='install',review=None,authority=None,reconciliation=False):
    inherited_lock(root,fd)
    from scripts.workload_installation_fixture import Fixture, fixture_engine
    fixture = Fixture(root)
    fixture.lock_fd = fd
    fixture.require_target()
    request = [row for row in fixture.journal.rows if row['event']=='fixture_worker_intent' and row['token']==token]
    require(len(request)==1 and request[0]['operation']==operation and request[0]['output']==str(output) and
            request[0]['phase']==phase and request[0]['reconciliation']==reconciliation and
            request[0]['review_sha256']==(digest(private(review,parse=False)[0]) if review else None) and
            request[0]['authority_sha256']==(digest(private(authority,parse=False)[0]) if authority else None),
            'fixture_worker_request_changed')
    parent = request[0]['parent']
    require(process_birth(parent['pid'])==parent,'fixture_worker_parent_replaced')
    cursor = os.getppid(); ancestors = []
    for _ in range(16):
        ancestors.append(cursor)
        if cursor==parent['pid'] or cursor<=1:break
        cursor = int(Path(f'/proc/{cursor}/stat').read_text().rsplit(')',1)[1].split()[1])
    require(parent['pid'] in ancestors,'fixture_worker_not_child_of_authorized_parent')
    require(Path(output).parent==fixture.root/'artifacts' and not Path(output).exists(),'fixture_worker_output_invalid')
    # The parent owns the lifecycle journal. Workers have a separate journal;
    # nested commands and injected faults cannot corrupt the parent's head.
    recovery_selection=None
    if operation in ('control-cleanup','control-postflight'):
        selected=phase.split(':')
        require(len(selected)==3 and not reconciliation and review is None and authority is None,
            'fixture_control_recovery_request_invalid')
        control,scenario,original_token=selected
        original=[row for row in fixture.lifecycle_journal.rows if row['event']=='fixture_worker_intent' and
            row['operation']=='control' and row['token']==original_token and row['phase']==control+':'+scenario]
        require(len(original)==1,'fixture_control_recovery_original_request_changed')
        from deploy.workload_fixture_control_cleanup import recovery_journal
        fixture.journal=recovery_journal(fixture.root/'runtime-journal',fixture.binding,original_token)
        recovery_selection=(control,scenario,original_token)
    else:
        fixture.journal = Journal(fixture.root/'runtime-journal',fixture.binding)
    require(not any(row.get('token')==token for row in fixture.journal.rows),'fixture_worker_request_replay')
    fixture.journal.append('fixture_worker_claim',token=token,operation=operation,parent=parent)
    from deploy.workload_fixture_resources import Resources
    resources = Resources(fixture)
    from deploy.workload_installed import observation_runner
    with observation_runner(resources.run):
        if operation=='provision':
            result = resources.provision()
        elif operation=='engine':
            fixture_engine(root,phase=phase,review=review,authority=authority,reconciliation=reconciliation,lock_fd=fd)
            _,proposal = fixture.proposal()
            if not reconciliation and phase=='install':
                from deploy.workload_installed import collect
                from deploy.workload_v3 import installed
                measured = collect(proposal)
                installed(measured,proposal)
                result = dict(installed=measured,postflight=resources.postflight(proposal))
            else:
                result = dict(postflight=resources.postflight(proposal))
        elif operation=='inspect':
            _,proposal = fixture.proposal()
            result = resources.observations(proposal)
            engine = Journal(proposal['identities']['recipe']['journal_root'],digest(canonical(proposal)))
            if engine.outcome('install:verify_paused') and not engine.outcome('rollback:restore_activation'):
                from deploy.workload_installed import collect
                from deploy.workload_v3 import installed
                measured = collect(proposal)
                installed(measured,proposal)
                result['installed'] = measured
        elif operation=='cleanup':
            proposal = fixture.proposal()[1] if (fixture.root/'proposal.json').exists() else None
            result = resources.cleanup(proposal)
        elif operation in ('control-cleanup','control-postflight'):
            from deploy.workload_fixture_control_cleanup import cleanup as control_cleanup,postflight as control_postflight
            require(recovery_selection is not None,'fixture_control_recovery_request_invalid')
            control,scenario,original_token=recovery_selection
            resources.cleanup_mode=True
            method=control_cleanup if operation=='control-cleanup' else control_postflight
            result=method(fixture,resources,control,scenario,original_token)
        elif operation=='control':
            from deploy.workload_fixture_controls import execute as control_execute
            selected=phase.split(':')
            require(len(selected)==2 and not reconciliation and review is None and authority is None,
                    'fixture_control_request_invalid')
            control,scenario=selected
            require(not any(row['event']=='fixture_control_case_claim' and row.get('control')==control and
                row.get('scenario')==scenario for row in fixture.journal.rows), 'fixture_control_case_already_attempted')
            fixture.journal.append('fixture_control_case_claim',control=control,scenario=scenario,
                generation=fixture.manifest['generation'],token=token)
            result=control_execute(fixture,resources,control,scenario,token)
        elif operation=='peer-probe':
            _,proposal = fixture.proposal()
            from deploy.workload_socket_probe import probe
            from deploy.workload_configuration import templates
            from mldsafail.evaluator.native_workload import NativeRuntime
            source = proposal['identities']
            native = templates(source)['native']
            def daemon_identity(*,seconds):
                return NativeRuntime(native,run=lambda argv:resources.run(argv,seconds=seconds)).identity()
            result = probe(source['manifest']['coordinator_image'],source['uid_mapping'],fixture.journal,
                           lambda argv,seconds:resources.docker(argv,seconds=seconds),daemon_identity)
        else:
            require(False,'fixture_worker_operation_invalid')
    exclusive(output,canonical(dict(fixture_only=True,generation=fixture.manifest['generation'],
                                   token=token,operation=operation,result=result)))
