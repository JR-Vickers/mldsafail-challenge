"""Synthetic durable-boundary tests; these cannot certify native installation."""
from copy import deepcopy
from pathlib import Path
import json
import time
import uuid

import pytest

from deploy.workload_installation import INSTALL, ROLLBACK, Journal, execute, reconcile
from deploy.workload_release import canonical,digest
from deploy.workload_v3 import bootstrap
from deploy.workload_v3_fixture import inspection
from mldsafail.evaluator.workload import WorkloadBlocked


class Backend:
    def __init__(self,root): self.root=root; self.calls=[]
    def preflight(self,phase,journal): pass
    def before(self,step,journal): return self.observe(step,journal)
    def apply(self,step,journal):
        path=self.root/step['id'].replace(':','-')
        assert not path.exists()
        path.write_text(step['id']); self.calls.append(step['id'])
    def observe(self,step,journal):
        path=self.root/step['id'].replace(':','-')
        return dict(verified=path.exists() and path.read_text()==step['id'],identity=str(path))
    def valid_outcome(self,step,value,journal): return value['verified']
    def reconcilable(self,step,value,journal): return step['action']!='create_release'


def packet(tmp_path):
    tmp_path.chmod(0o700); journal=tmp_path/'journal';journal.mkdir(mode=0o700)
    data=inspection(); data['recipe']['journal_root']=str(journal)
    proposal=bootstrap(data,now=1100); raw=canonical(proposal)
    review=canonical(dict(proposal_sha256=digest(raw),decision='approved',implemented_by='fixture',reviewed_by='independent-fixture'))
    def authority(phase='install',**extra):
        now=time.time()
        return dict(schema='mldsafail.workload-installation-authority.v3',authorized_by='owner',
            proposal_sha256=digest(raw),review_sha256=digest(review),phase=phase,issued_at=now,expires_at=now+180,
            nonce=uuid.uuid4().hex,**extra)
    return proposal,raw,review,authority


def test_complete_install_and_rollback(tmp_path):
    proposal,raw,review,authority=packet(tmp_path); backend=Backend(tmp_path)
    execute(proposal,raw,review,authority(),backend)
    execute(proposal,raw,review,authority('rollback'),backend,phase='rollback')
    assert len(backend.calls)==len(INSTALL)+len(ROLLBACK)


@pytest.mark.parametrize('boundary',['intent','applied','outcome'])
@pytest.mark.parametrize('action',INSTALL)
def test_every_mutating_boundary_stops_or_resumes_without_blind_replay(tmp_path,action,boundary):
    proposal,raw,review,authority=packet(tmp_path); backend=Backend(tmp_path)
    def interrupt(step,point):
        if step=='install:'+action and point==boundary: raise InterruptedError('injected')
    with pytest.raises(InterruptedError): execute(proposal,raw,review,authority(),backend,fault=interrupt)
    calls=list(backend.calls)
    if boundary!='outcome':
        with pytest.raises(WorkloadBlocked,match='ambiguous'): execute(proposal,raw,review,authority(),backend)
        assert backend.calls==calls
        if boundary=='applied' and action!='create_release':
            reconcile(proposal,raw,review,authority(reconcile=True),backend)
            execute(proposal,raw,review,authority(),backend)
            assert backend.calls.count('install:'+action)==1
        else:
            with pytest.raises(WorkloadBlocked): reconcile(proposal,raw,review,authority(reconcile=True),backend)
    else:
        execute(proposal,raw,review,authority(),backend)
        assert backend.calls.count('install:'+action)==1


def test_replay_and_missing_review_never_mutate(tmp_path):
    proposal,raw,review,authority=packet(tmp_path); backend=Backend(tmp_path); approved=authority()
    bad=json.loads(review);bad['reviewed_by']='fixture'
    with pytest.raises(WorkloadBlocked): execute(proposal,raw,canonical(bad),approved,backend)
    assert not backend.calls
    execute(proposal,raw,review,approved,backend)
    with pytest.raises(WorkloadBlocked,match='replay'): execute(proposal,raw,review,approved,backend)


def test_replaced_completed_resource_is_preserved_and_blocks(tmp_path):
    proposal,raw,review,authority=packet(tmp_path); backend=Backend(tmp_path)
    execute(proposal,raw,review,authority(),backend)
    unknown=tmp_path/'install-create_release';unknown.write_text('unknown owner')
    with pytest.raises(WorkloadBlocked,match='identity_changed'): execute(proposal,raw,review,authority(),backend)
    assert unknown.read_text()=='unknown owner'


def test_partial_journal_blocks_replay(tmp_path):
    proposal,raw,review,authority=packet(tmp_path)
    path=tmp_path/'journal'/'installation.jsonl';path.write_bytes(b'{');path.chmod(0o600)
    with pytest.raises(WorkloadBlocked,match='partial_journal'): execute(proposal,raw,review,authority(),Backend(tmp_path))


@pytest.mark.parametrize('action',['inhibit_scheduling','inhibit_containers','prerequisites','start_paused'])
def test_concrete_preconditions_do_not_require_postconditions(tmp_path,monkeypatch,action):
    from deploy.workload_installation import LinuxBackend
    proposal,raw,review,authority=packet(tmp_path); backend=LinuxBackend(proposal)
    monkeypatch.setattr(backend,'observe',lambda *args:(_ for _ in ()).throw(AssertionError('postcondition before creation')))
    journal=Journal(tmp_path/'journal',digest(raw))
    step=next(row for row in proposal['steps'] if row['action']==action)
    if action=='start_paused':
        from deploy.workload_installation import identity
        backend.enable_path=tmp_path/'enabled';backend.enable_path.write_bytes(b'fixture')
        journal.append('outcome',step='install:enable_supervisor',observed=identity(backend.enable_path))
    assert backend.before(step,journal) is not None


def test_journal_reloads_after_acquiring_lock(tmp_path):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    first=Journal(root,'a'*64);stale=Journal(root,'a'*64)
    with first.locked():first.append('first')
    with stale.locked():
        assert stale.rows==first.rows
        stale.append('second')
    assert len(Journal(root,'a'*64).rows)==2


def test_journal_refuses_shared_file(tmp_path):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    path=root/'installation.jsonl';path.write_bytes(b'{}\n');path.chmod(0o600)
    __import__('os').link(path,tmp_path/'shared')
    with pytest.raises(WorkloadBlocked,match='private_artifact'):Journal(root,'a'*64)


def test_activation_reconciliation_requires_original_pointer_preserved(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path)
    backend=LinuxBackend(proposal);journal=Journal(tmp_path/'journal',digest(raw))
    original=tmp_path/'saved';original.symlink_to('/original');before=identity(original)
    selected=tmp_path/'selected';selected.symlink_to('/new');candidate=identity(selected)
    journal.append('intent',step='install:activate',before=before)
    # Candidate inode moved to selected; its original temporary name now holds the old pointer.
    candidate['path']=str(original)
    journal.append('activation_candidate',step_id='install:activate',observed=candidate)
    assert backend.reconcilable(dict(id='install:activate',action='activate'),identity(selected),journal)
    original.unlink();original.symlink_to('/unknown')
    assert not backend.reconcilable(dict(id='install:activate',action='activate'),identity(selected),journal)


def test_reconciliation_binds_exact_proposal_bytes(tmp_path):
    proposal,raw,review,authority=packet(tmp_path);changed=deepcopy(proposal)
    changed['identities']['recipe']['journal_root']=str(tmp_path/'other')
    # Even a separately valid proposal cannot borrow authority over other bytes.
    from deploy.workload_v3 import bootstrap
    changed=bootstrap(changed['identities'],now=1100)
    with pytest.raises(WorkloadBlocked,match='proposal_bytes_changed'):
        reconcile(changed,raw,review,authority(reconcile=True),Backend(tmp_path))


def test_final_scheduler_drift_blocks_activation_before_pointer_change(tmp_path,monkeypatch):
    from deploy.workload_installation import LinuxBackend
    import deploy.workload_installed as installed
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    pointer=tmp_path/'active';pointer.symlink_to('/original')
    backend.recipe['activation_pointer']=str(pointer)
    journal=Journal(tmp_path/'journal',digest(raw))
    def drift(proposal):raise WorkloadBlocked('registry_unit_inventory_changed')
    monkeypatch.setattr(installed,'activation_scheduling',drift)
    step=dict(id='install:activate',action='activate')
    with pytest.raises(WorkloadBlocked,match='unit_inventory_changed'):backend.before(step,journal)
    assert pointer.readlink()==__import__('pathlib').Path('/original')
    assert not list(tmp_path.glob('active.*.tmp'))


def test_rollback_resume_uses_latest_acknowledged_selection_and_units(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    journal=Journal(tmp_path/'journal',digest(raw))
    pointer=tmp_path/'active';pointer.symlink_to('/new');selected=identity(pointer)
    journal.append('outcome',step='install:activate',observed=selected)
    journal.append('outcome',step='install:units',observed={})
    assert backend.selection_expectation(journal)==selected and backend.installed_units_selected(journal)
    pointer.unlink();pointer.symlink_to('/previous');restored=identity(pointer)
    journal.append('outcome',step='rollback:restore_activation',observed=restored)
    journal.append('outcome',step='rollback:restore_units',observed={})
    assert backend.selection_expectation(journal)==identity(pointer)
    assert not backend.installed_units_selected(journal)


def test_rollback_refuses_unreconciled_installation_before_backend_calls(tmp_path):
    proposal,raw,review,authority=packet(tmp_path);backend=Backend(tmp_path)
    journal=Journal(tmp_path/'journal',digest(raw));journal.append('intent',step='install:create_release',before={})
    with pytest.raises(WorkloadBlocked,match='reconcile_before_rollback'):
        execute(proposal,raw,review,authority('rollback'),backend,phase='rollback')
    assert not backend.calls


def test_partial_rollback_leaves_unmodified_selection_and_unknown_units_untouched(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    pointer=tmp_path/'active';pointer.symlink_to('/previous');bound=identity(pointer)
    backend.recipe['activation_pointer']=str(pointer);backend.source['resources']['activation']=bound
    backend.source['rollback']['target']='/previous'
    unknown=tmp_path/'unknown.service';unknown.write_text('unrelated')
    journal=Journal(tmp_path/'journal',digest(raw))
    backend.command=lambda argv:(_ for _ in ()).throw(AssertionError('unexpected mutation'))
    backend.enable_path=tmp_path/'absent-marker'
    for action in ('stop_supervisor','restore_activation','restore_units'):
        step=dict(id='rollback:'+action,action=action)
        backend.apply(step,journal)
        assert backend.valid_outcome(step,backend.observe(step,journal),journal)
    assert identity(pointer)==bound and unknown.read_text()=='unrelated'
    assert not list(tmp_path.glob('active.*.tmp'))


def test_rollback_never_removes_replaced_supervisor_enable_file(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    journal=Journal(tmp_path/'journal',digest(raw))
    marker=tmp_path/'marker';marker.write_bytes(b'approved');backend.enable_path=marker
    journal.append('outcome',step='install:enable_supervisor',observed=identity(marker))
    replacement=tmp_path/'other';replacement.write_bytes(b'unknown');replacement.replace(marker)
    with pytest.raises(WorkloadBlocked,match='enable_identity_changed'):
        backend.apply(dict(id='rollback:stop_supervisor',action='stop_supervisor'),journal)
    assert marker.read_bytes()==b'unknown'


def test_rollback_keeps_existing_acknowledged_inhibition_without_reapplying(tmp_path):
    from deploy.workload_installation import LinuxBackend
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    journal=Journal(tmp_path/'journal',digest(raw))
    backend.command=lambda argv:(_ for _ in ()).throw(AssertionError('inhibition replay'))
    for action in ('inhibit_scheduling','inhibit_containers'):
        journal.append('outcome',step='install:'+action,observed=dict(verified=True))
        backend.apply(dict(id='rollback:'+action,action=action),journal)


@pytest.mark.parametrize('boundary',['intent','applied','outcome'])
@pytest.mark.parametrize('action',ROLLBACK)
def test_rollback_boundaries_require_reconciliation_without_automatic_retries(tmp_path,action,boundary):
    proposal,raw,review,authority=packet(tmp_path);backend=Backend(tmp_path)
    execute(proposal,raw,review,authority(),backend)
    def interrupt(step,point):
        if step=='rollback:'+action and point==boundary:raise InterruptedError('injected rollback interruption')
    with pytest.raises(InterruptedError):execute(proposal,raw,review,authority('rollback'),backend,phase='rollback',fault=interrupt)
    calls=list(backend.calls)
    if boundary!='outcome':
        with pytest.raises(WorkloadBlocked,match='ambiguous'):
            execute(proposal,raw,review,authority('rollback'),backend,phase='rollback')
        assert backend.calls==calls
        if boundary=='intent':
            with pytest.raises(WorkloadBlocked):reconcile(proposal,raw,review,authority('rollback',reconcile=True),backend,phase='rollback')
            return
        reconcile(proposal,raw,review,authority('rollback',reconcile=True),backend,phase='rollback')
    execute(proposal,raw,review,authority('rollback'),backend,phase='rollback')
    assert backend.calls.count('rollback:'+action)==1


def test_restore_units_preserves_identical_bytes_with_unknown_birth(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    directory=tmp_path/'units';directory.mkdir()
    backend.source['installation']['unit_directory']=str(directory)
    original={};installed={}
    for name,contents in proposal['units'].items():
        path=directory/name;original[str(path)]=dict(state='absent',path=str(path))
        path.write_bytes(contents.encode());installed[name]=identity(path)
    journal=Journal(tmp_path/'journal',digest(raw));journal.append('outcome',step='install:units',observed=installed)
    (journal.root/'original-units.json').write_bytes(canonical(original))
    name=next(iter(proposal['units']));path=directory/name
    replacement=directory/'replacement';replacement.write_bytes(path.read_bytes());replacement.replace(path)
    with pytest.raises(WorkloadBlocked,match='unit_replaced'):backend.apply(dict(id='rollback:restore_units',action='restore_units'),journal)
    assert path.read_bytes()==proposal['units'][name].encode()


def test_installed_marker_requires_acknowledged_birth_and_contents(tmp_path):
    import os
    from deploy.workload_installation import identity,supervisor_enable_contents
    from deploy.workload_installed import verify_supervisor_enable
    proposal,_,_,_=packet(tmp_path);source=proposal['identities']
    root=tmp_path/'release';root.mkdir(mode=0o700)
    source['resources']['release']['path']=str(root);source['host']['uid']=os.getuid()
    source['recipe']['proposal_path']=str(tmp_path/'proposal.json');raw=canonical(proposal)
    path=tmp_path/'proposal.json';path.write_bytes(raw);path.chmod(0o600)
    marker=root/'.supervisor-enabled';marker.write_bytes(supervisor_enable_contents(proposal));marker.chmod(0o600)
    journal=Journal(tmp_path/'journal',digest(raw));journal.append('outcome',step='install:enable_supervisor',observed=identity(marker))
    assert verify_supervisor_enable(proposal)==identity(marker)
    replacement=root/'other';replacement.write_bytes(marker.read_bytes());replacement.chmod(0o600);replacement.replace(marker)
    with pytest.raises(WorkloadBlocked,match='enable_changed'):verify_supervisor_enable(proposal)
    marker.unlink()
    with pytest.raises((FileNotFoundError,WorkloadBlocked)):verify_supervisor_enable(proposal)


def test_existing_unit_mode_owner_and_group_survive_round_trip(tmp_path):
    from deploy.workload_installation import LinuxBackend,identity
    proposal,raw,review,authority=packet(tmp_path);backend=LinuxBackend(proposal)
    directory=tmp_path/'units';directory.mkdir();backend.source['installation']['unit_directory']=str(directory)
    originals={}
    for name in proposal['units']:
        path=directory/name;path.write_bytes(b'original unit bytes');path.chmod(0o644)
        originals[str(path)]=dict(identity(path),gid=path.stat().st_gid,contents_hex=path.read_bytes().hex())
    journal=Journal(tmp_path/'journal',digest(raw));(journal.root/'original-units.json').write_bytes(canonical(originals))
    backend.command=lambda argv:b''
    install=dict(id='install:units',action='units');backend.apply(install,journal)
    journal.append('outcome',step='install:units',observed=backend.observe(install,journal))
    restore=dict(id='rollback:restore_units',action='restore_units');backend.apply(restore,journal)
    assert backend.valid_outcome(restore,backend.observe(restore,journal),journal)
    for path,row in originals.items():
        actual=Path(path).stat()
        assert Path(path).read_bytes()==b'original unit bytes'
        assert actual.st_mode&0o777==0o644 and (actual.st_uid,actual.st_gid)==(row['uid'],row['gid'])


def test_partial_cleanup_without_supervisor_rejects_unacknowledged_state(tmp_path,monkeypatch):
    import deploy.workload_installed as installed
    proposal,raw,review,authority=packet(tmp_path);source=proposal['identities']
    gate=tmp_path/'gate';gate.mkdir();source['installation']['gate_root']=str(gate)
    source['installation']['heavy_path']=str(tmp_path/'absent-heavy')
    monkeypatch.setattr(installed,'scheduling',lambda proposal:dict(verified=True))
    journal=Journal(tmp_path/'journal',digest(raw))
    assert installed.inspect_control('verify_cleanup',proposal,journal)['supervisor_never_started']
    path=gate/'workload.json';path.write_bytes(b'unknown runtime ownership')
    with pytest.raises(WorkloadBlocked,match='unacknowledged_runtime_state'):
        installed.inspect_control('verify_cleanup',proposal,journal)
    assert path.read_bytes()==b'unknown runtime ownership'


def test_expired_final_verification_cannot_publish_completed_phase(tmp_path,monkeypatch):
    import deploy.workload_installation as engine
    proposal,raw,review,authority=packet(tmp_path);backend=Backend(tmp_path);approved=authority()
    initial=time.time();clock=[initial]
    monkeypatch.setattr(engine.time,'time',lambda:clock[0])
    def expire(step,point):
        if step=='install:verify_paused' and point=='outcome':clock[0]=approved['expires_at']+1
    with pytest.raises(WorkloadBlocked,match='exact_owner_authority'):
        execute(proposal,raw,review,approved,backend,fault=expire)
    journal=Journal(tmp_path/'journal',digest(raw))
    assert journal.outcome('install:verify_paused')['event']=='outcome'
    assert not any(row['event']=='phase_complete' for row in journal.rows)
