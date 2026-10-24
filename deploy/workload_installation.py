"""Single V3 installation/rollback engine with durable mutation boundaries.

A compiled command is not authority. Execution requires private exact-byte owner
and independent-review artifacts. Unknown or interrupted outcomes require explicit
reconciliation; the engine never blindly repeats a mutation.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import uuid

from deploy.workload_release import canonical, digest, regular, verify, stable_stat
from mldsafail.evaluator.native_workload import require

INSTALL = ('snapshot', 'quiesce_supervisor', 'create_release', 'copy_bundle', 'tools', 'dependencies', 'images',
           'inhibit_scheduling', 'inhibit_containers', 'units', 'prerequisites', 'configurations',
           'verify_release', 'activate', 'supervisor_unit', 'enable_supervisor', 'start_paused', 'verify_paused')
ROLLBACK = ('inhibit_scheduling', 'inhibit_containers', 'stop_supervisor', 'verify_cleanup',
            'restore_activation', 'restore_units', 'verify_rollback')
SNAPSHOTS=('original-units.json','original-scheduling-files.json','original-scheduling.json','original-container-policies.json')
SCHEDULING_FILE_MAX=1024**2
SCHEDULING_SNAPSHOT_MAX=16*1024**2
RECOVERY_PROTOCOL = 4


def supervisor_enable_contents(proposal):
    return canonical(dict(proposal_sha256=digest(canonical(proposal)),manifest_sha256=proposal['manifest_sha256']))


def compile_steps(proposal):
    from deploy.workload_recovery_inventory import inventory
    inventory()
    source=proposal['identities']; recipe=source['recipe']
    steps=[]
    for phase,names in (('install',INSTALL),('rollback',ROLLBACK)):
        for name in names:
            steps.append(dict(id=phase+':'+name,phase=phase,action=name,
                precondition='fresh_bound_identity_and_previous_durable_outcome',
                acknowledgement='durable_observed_resource_identity',
                argv=['/usr/bin/env','PYTHONPATH='+recipe['bundle_root']+'/src:'+recipe['bundle_root'],
                      'PYTHONDONTWRITEBYTECODE=1','PYTHONNOUSERSITE=1',recipe.get('bootstrap_interpreter',recipe['interpreter'])['path'],'-P','-m','deploy.workload_installation',
                      '--proposal',recipe['proposal_path'],'--review',recipe['proposal_path']+'.review.json',
                      '--authorization',recipe['proposal_path']+'.authorization.json','--phase',phase]))
    return steps


def sync_directory(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def exclusive(path,data,mode=0o600):
    path=Path(path)
    for parent in (path.parent,*path.parent.parents):
        require(not parent.is_symlink(),'installation_parent_symlink')
    with path.open('xb') as stream:
        os.chmod(path,mode); stream.write(data); stream.flush(); os.fsync(stream.fileno())
    sync_directory(path.parent)


def identity(path, *, content=True):
    path=Path(path)
    try: before=path.lstat()
    except FileNotFoundError: return dict(state='absent',path=str(path))
    value=dict(state='observed',path=str(path),device=before.st_dev,inode=before.st_ino,
               uid=before.st_uid,mode=stat.S_IMODE(before.st_mode))
    if stat.S_ISLNK(before.st_mode): value['target']=os.readlink(path)
    elif stat.S_ISREG(before.st_mode):
        if content:
            descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(descriptor,'rb') as stream:
                require(stable_stat(before)==stable_stat(os.fstat(stream.fileno())),'installation_identity_race')
                value['sha256']=digest(stream.read())
                require(stable_stat(before)==stable_stat(os.fstat(stream.fileno())),'installation_identity_race')
    else: require(stat.S_ISDIR(before.st_mode) or stat.S_ISSOCK(before.st_mode),'installation_unknown_resource_kind')
    require(stable_stat(before)==stable_stat(path.lstat()),'installation_identity_race')
    return value


def read_host_regular(path):
    """Read host files, including literal systemd escaped unit names.

    Bundle-relative paths keep their stricter portable archive policy. Host
    filenames may contain backslashes; those are literal bytes, not separators.
    """
    path=Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(parent.is_symlink() for parent in (path,*path.parents)),
            'installation_host_file_path_invalid')
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=SCHEDULING_FILE_MAX,
            'installation_host_file_invalid')
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as stream:
        require(stable_stat(os.fstat(stream.fileno()))==stable_stat(before),'installation_original_file_race')
        data=stream.read(SCHEDULING_FILE_MAX+1)
        require(len(data)<=SCHEDULING_FILE_MAX and
                stable_stat(os.fstat(stream.fileno()))==stable_stat(before) and
                stable_stat(path.lstat())==stable_stat(before),'installation_original_file_race')
    return data,stat.S_IMODE(before.st_mode)


def read_owned_file(path,command,*,metadata=False):
    path=Path(path)
    try:
        before=path.lstat();data,mode=read_host_regular(path)
        record=dict(identity(path,content=False),gid=path.stat().st_gid)
        require(stable_stat(before)==stable_stat(path.lstat()),'installation_original_file_race')
    except PermissionError:
        script=('import json,os,pathlib,stat,sys; p=pathlib.Path(sys.argv[1]); '
                'assert not any(q.is_symlink() for q in (p,*p.parents)); '
                'fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW); s=os.fstat(fd); '
                'assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=1048576; '
                'f=os.fdopen(fd,"rb");f.seek(int(sys.argv[2]));data=f.read(262144);t=os.fstat(f.fileno()); '
                'keys=("st_dev","st_ino","st_mode","st_uid","st_gid","st_nlink","st_size","st_mtime_ns","st_ctime_ns"); '
                'birth=[getattr(s,k) for k in keys];assert birth==[getattr(t,k) for k in keys] and birth==[getattr(p.lstat(),k) for k in keys]; '
                'print(json.dumps(dict(hex=data.hex(),identity=birth)))')
        chunks=[];bound=None;offset=0
        while True:
            row=json.loads(command(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,str(path),str(offset)]))
            current=row['identity'];require(bound is None or bound==current,'installation_original_file_race');bound=current
            chunk=bytes.fromhex(row['hex']);chunks.append(chunk);offset+=len(chunk)
            require(offset<=bound[6]<=SCHEDULING_FILE_MAX and (chunk or offset==bound[6]),'installation_original_file_size_changed')
            if offset==bound[6]:break
        data=b''.join(chunks);mode=stat.S_IMODE(bound[2])
        record=dict(state='observed',path=str(path),device=bound[0],inode=bound[1],uid=bound[3],gid=bound[4],mode=mode)
    return (data,mode,record) if metadata else (data,mode)


def scheduling_size(source,command):
    paths=list(source['inventory']['original_files'])
    require(len(paths)<=2048,'installation_scheduling_file_count_limit')
    try:sizes=[Path(path).lstat().st_size for path in paths]
    except PermissionError:
        script='import json,pathlib,sys;print(json.dumps([pathlib.Path(p).lstat().st_size for p in sys.argv[1:]]))'
        sizes=json.loads(command(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,*paths]))
    require(len(sizes)==len(paths) and all(type(size) is int and 0<=size<=SCHEDULING_FILE_MAX for size in sizes) and
            sum(sizes)<=SCHEDULING_SNAPSHOT_MAX,'installation_scheduling_snapshot_size_limit')
    return sum(sizes)


def private(path, *, parse=True):
    path=Path(path); info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and
            info.st_nlink==1 and stat.S_IMODE(info.st_mode)&0o077==0,'installation_private_artifact_required')
    raw=path.read_bytes(); require(stable_stat(info)==stable_stat(path.lstat()),'installation_artifact_race')
    return raw,json.loads(raw) if parse else None


class Journal:
    def __init__(self,root,proposal_sha256):
        self.root=Path(root); self.binding=proposal_sha256
        require(self.root.is_dir() and not self.root.is_symlink() and self.root.stat().st_uid==os.getuid() and
                stat.S_IMODE(self.root.stat().st_mode)&0o077==0,'installation_private_journal_required')
        self.root_identity=identity(self.root)
        self.path=self.root/'installation.jsonl'; self.rows=[]
        self.reload()
    def reload(self):
        self.rows=[]
        if self.path.exists() or self.path.is_symlink():
            raw,_=private(self.path,parse=False)
            require(raw.endswith(b'\n'),'installation_partial_journal_reconcile_required')
            for line in raw.splitlines():
                row=json.loads(line)
                require(row['proposal_sha256']==self.binding and row['previous']==self.head,'installation_journal_changed')
                self.rows.append(row)
        headers=[row for row in self.rows if row['event']=='recovery_protocol']
        require(not headers or (len(headers)==1 and self.rows[0]==headers[0] and
                type(headers[0].get('version')) is int and
                headers[0]['version'] in (2, 3, RECOVERY_PROTOCOL)),'installation_recovery_protocol_invalid')
    @property
    def recovery_protocol(self):
        return self.rows[0]['version'] if self.rows and self.rows[0]['event']=='recovery_protocol' else 1
    @property
    def head(self): return digest(canonical(self.rows[-1])) if self.rows else '0'*64
    def append(self,event,**values):
        row=dict(event=event,proposal_sha256=self.binding,previous=self.head,**values)
        descriptor=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid() and
                stat.S_IMODE(info.st_mode)&0o077==0,'installation_journal_file_invalid')
        with os.fdopen(descriptor,'ab') as stream:
            stream.write(canonical(row)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        sync_directory(self.root); self.rows.append(row)
    @contextmanager
    def locked(self):
        descriptor=os.open(self.root/'installation.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid() and
                    stat.S_IMODE(info.st_mode)&0o077==0,'installation_lock_file_invalid')
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            require(identity(self.root)==self.root_identity,'installation_journal_root_replaced')
            self.reload()
            yield
        finally: os.close(descriptor)
    def outcome(self,step):
        rows=[r for r in self.rows if r.get('step')==step]
        return rows[-1] if rows else None


def authorize(proposal_raw,review_raw,authority,phase,*,now=None):
    now=time.time() if now is None else now
    review=json.loads(review_raw)
    require(review.get('decision')=='approved' and review.get('reviewed_by') and
            review.get('implemented_by') and review['reviewed_by']!=review['implemented_by'] and
            review.get('proposal_sha256')==digest(proposal_raw),'installation_independent_review_required')
    require(authority.get('schema')=='mldsafail.workload-installation-authority.v3' and
            authority.get('authorized_by')=='owner' and authority.get('proposal_sha256')==digest(proposal_raw) and
            authority.get('review_sha256')==digest(review_raw) and authority.get('phase')==phase and
            type(authority.get('issued_at')) in (int,float) and type(authority.get('expires_at')) in (int,float) and
            authority['issued_at']<=now<authority['expires_at'] and
            authority['expires_at']-authority['issued_at']<=300 and
            type(authority.get('nonce')) is str and len(authority['nonce'])==32,
            'installation_exact_owner_authority_required')


def execute(proposal,proposal_raw,review_raw,authority,backend,*,phase='install',fault=None):
    from deploy.workload_v3 import validate_proposal
    validate_proposal(proposal)
    require(json.loads(proposal_raw)==proposal,'installation_proposal_bytes_changed')
    authorize(proposal_raw,review_raw,authority,phase)
    journal=Journal(proposal['identities']['recipe']['journal_root'],digest(proposal_raw))
    with journal.locked():
        if not journal.rows:journal.append('recovery_protocol',version=RECOVERY_PROTOCOL)
        claim=digest(canonical(authority))
        require(not any(row.get('claim')==claim for row in journal.rows),'installation_authority_replay')
        journal.append('authority_claim',claim=claim,phase=phase)
        for pending_step in (s for s in proposal['steps'] if s['phase']==phase):
            pending=journal.outcome(pending_step['id'])
            require(not pending or pending['event']!='intent','installation_ambiguous_outcome_reconcile_required')
        if phase=='rollback':
            require(all(not journal.outcome('install:'+name) or journal.outcome('install:'+name)['event'] not in ('intent','reconciled_partial')
                        for name in INSTALL),'installation_ambiguous_installation_reconcile_before_rollback')
        backend.journal=journal
        backend.deadline=time.monotonic()+max(0,authority['expires_at']-time.time())
        backend.preflight(phase,journal)
        for step in (s for s in proposal['steps'] if s['phase']==phase):
            authorize(proposal_raw,review_raw,authority,phase)
            prior=journal.outcome(step['id'])
            if prior and prior['event'] not in ('reconciled_absent','reconciled_partial'):
                require(prior['event'] in ('outcome','reconciled'),'installation_ambiguous_outcome_reconcile_required')
                require(backend.observe(step,journal)==prior['observed'],'installation_completed_step_identity_changed')
                if journal.recovery_protocol == 4 and hasattr(backend,'recovery_observation'):
                    require(prior.get('operation_observation')==backend.recovery_observation(step,journal),
                            'installation_completed_operation_postconditions_changed')
                continue
            before=(backend.continuation_before(step,journal) if prior and prior['event']=='reconciled_partial'
                    else backend.before(step,journal))
            if prior:
                require(before==prior['observed'],'installation_reconciled_absence_changed')
            authorize(proposal_raw,review_raw,authority,phase)
            journal.append('intent',step=step['id'],before=before)
            if fault: fault(step['id'],'intent')
            authorize(proposal_raw,review_raw,authority,phase)
            backend.apply(step,journal)
            if fault: fault(step['id'],'unacknowledged')
            if hasattr(backend,'acknowledge_apply'):backend.acknowledge_apply(step,journal)
            if fault: fault(step['id'],'applied')
            outcome=backend.observe(step,journal)
            require(backend.valid_outcome(step,outcome,journal),'installation_outcome_not_verified')
            extra={}
            if journal.recovery_protocol == 4 and hasattr(backend,'recovery_observation'):
                extra['operation_observation']=backend.recovery_observation(step,journal)
            journal.append('outcome',step=step['id'],observed=outcome,**extra)
            if fault: fault(step['id'],'outcome')
        authorize(proposal_raw,review_raw,authority,phase)
        journal.append('phase_complete',phase=phase)
    return journal.rows


def reconcile(proposal,proposal_raw,review_raw,authority,backend,*,phase='install'):
    """Separate, fresh authority inspects a pending mutation; never replays it."""
    from deploy.workload_v3 import validate_proposal
    validate_proposal(proposal)
    require(json.loads(proposal_raw)==proposal,'installation_proposal_bytes_changed')
    authorize(proposal_raw,review_raw,authority,phase)
    require(authority.get('reconcile') is True,'installation_reconciliation_authority_required')
    journal=Journal(proposal['identities']['recipe']['journal_root'],digest(proposal_raw))
    with journal.locked():
        claim=digest(canonical(authority))
        require(not any(row.get('claim')==claim for row in journal.rows),'installation_authority_replay')
        journal.append('authority_claim',claim=claim,phase=phase,reconcile=True)
        backend.journal=journal
        backend.deadline=time.monotonic()+max(0,authority['expires_at']-time.time())
        if hasattr(backend,'reconcile_preflight'):backend.reconcile_preflight(journal)
        for step in (s for s in proposal['steps'] if s['phase']==phase):
            previous=journal.outcome(step['id'])
            if previous and previous['event']=='intent':
                authorize(proposal_raw,review_raw,authority,phase)
                substeps=backend.observe_substeps(step,journal) if hasattr(backend,'observe_substeps') else []
                if substeps:
                    journal.append('substep_reconciliation_observation',step_id=step['id'],substeps=substeps)
                try:
                    try:
                        actual=backend.observe(step,journal)
                        valid=backend.valid_outcome(step,actual,journal)
                    except BaseException:
                        if not (journal.recovery_protocol == 4 and hasattr(backend,'partial_observation') and
                                step['action'] in ('copy_bundle','tools')):raise
                        actual=backend.partial_observation(step,journal)
                        valid=False
                    if (not valid and journal.recovery_protocol == 4 and hasattr(backend,'partial_observation') and
                            step['action'] in ('copy_bundle','tools')):
                        actual=backend.partial_observation(step,journal)
                    bound=valid and backend.reconcilable(step,actual,journal)
                    absent=not valid and hasattr(backend,'absent_reconcilable') and backend.absent_reconcilable(step,actual,journal)
                    status='completed' if bound else 'ambiguous'
                    # Substep receipts are evidence, never automatic adoption.
                    if not substeps:
                        substeps=[dict(resource=row['resource'],status='observation_required')
                                  for row in journal.rows[journal.rows.index(previous)+1:]
                                  if row['event']=='mutation_intent']
                    if hasattr(backend,'reconciliation_status'):
                        status=backend.reconciliation_status(step,actual,journal,completed=bound)
                    if absent:status='absent'
                    journal.append('reconciliation_observation',step_id=step['id'],status=status,
                                   observed=actual,substeps=substeps)
                except BaseException as error:
                    journal.append('reconciliation_observation_failed',step_id=step['id'],
                                   error=dict(type=type(error).__name__,message=str(error)))
                    raise
                if absent:
                    authorize(proposal_raw,review_raw,authority,phase)
                    journal.append('reconciled_absent',step=step['id'],observed=actual)
                    continue
                if (not bound and journal.recovery_protocol in (2, 3, RECOVERY_PROTOCOL) and
                        hasattr(backend,'partial_reconcilable') and backend.partial_reconcilable(step,actual,journal)):
                    authorize(proposal_raw,review_raw,authority,phase)
                    journal.append('reconciled_partial',step=step['id'],observed=actual)
                    continue
                require(valid,'installation_ambiguous_resource_preserve_and_block')
                # Creation without an acknowledged identity cannot establish
                # ownership from its name or bytes alone.
                require(bound,'installation_creation_identity_unacknowledged')
                authorize(proposal_raw,review_raw,authority,phase)
                extra={}
                if journal.recovery_protocol == 4 and hasattr(backend,'recovery_observation'):
                    extra['operation_observation']=backend.recovery_observation(step,journal)
                journal.append('reconciled',step=step['id'],observed=actual,**extra)
    return journal.rows


def measured_by_engine(function):
    def measured(self,*args,**kwargs):
        from deploy.workload_installed import observation_runner
        with observation_runner(self.command):return function(self,*args,**kwargs)
    return measured


class LinuxBackend:
    """Concrete host adapter; all mutations come from the validated proposal."""
    def __init__(self,proposal):
        self.proposal=proposal; self.source=proposal['identities']; self.recipe=self.source['recipe']
        self.root=Path(self.source['resources']['release']['path']); self.bundle=self.root/'bundle'
        self.python=self.source['installation']['python']
        self.enable_path=self.root/'.supervisor-enabled'
    def selection_expectation(self,journal):
        for row in reversed(journal.rows):
            if row.get('step') in ('install:activate','rollback:restore_activation') and row['event'] in ('outcome','reconciled'):
                return row['observed']
        return self.source['resources']['activation']
    def installed_units_selected(self,journal):
        for row in reversed(journal.rows):
            if row.get('step') in ('install:supervisor_unit','rollback:restore_units') and row['event'] in ('outcome','reconciled'):
                return row['step']=='install:supervisor_unit'
        return False
    def unit_names(self,action):
        name='mldsafail-workload-supervisor.service'
        return [key for key in self.proposal['units'] if (key==name if action=='supervisor_unit' else key!=name)]
    def unit_records(self,journal):
        restored=journal.outcome('rollback:restore_units')
        if restored and restored['event'] in ('outcome','reconciled'):
            value=restored['observed']
            return {} if 'skipped' in value else value
        result={}
        for action in ('units','supervisor_unit'):
            row=journal.outcome('install:'+action)
            if row and row['event'] in ('outcome','reconciled'):result.update(row['observed'])
        return result
    def unit_transitions(self,journal):
        from deploy.workload_handoff import identifier
        rows=self.unit_records(journal);replacements={};overrides={}
        for name,record in rows.items():
            path=str(Path(self.source['installation']['unit_directory'])/name)
            require(identity(path)==record,'installation_unit_identity_changed')
            if self.installed_units_selected(journal) or name!='mldsafail-workload-supervisor.service' and not journal.outcome('rollback:restore_units'):
                replacements[path]=dict(contents=self.proposal['units'][name],identity=record)
                if name=='mldsafail-workload-supervisor.service' and identifier(self.source):
                    overrides[identifier(self.source)]=self.proposal['units'][name]
        return replacements,overrides
    def quiesced_units(self,journal):
        from deploy.workload_handoff import identifier
        name=identifier(self.source)
        return (name,) if name and self.acknowledged('quiesce_supervisor',journal) else ()
    def scheduling_transition(self,journal):
        from deploy.workload_installed import activation_scheduling,observation_runner
        replacements,overrides=self.unit_transitions(journal)
        with observation_runner(self.command):
            activation_scheduling(self.proposal,installed_units=self.installed_units_selected(journal),
                replacements=replacements,overrides=overrides,quiesced=self.quiesced_units(journal))
    def acknowledged(self,action,journal):
        return next((row for row in reversed(journal.rows) if row.get('step','').split(':')[-1]==action and
                     row['event'] in ('outcome','reconciled')),None)
    def owned_release(self,journal):
        require(not any(parent.is_symlink() for parent in (self.root,*self.root.parents)),
                'installation_release_parent_symlink')
        created=journal.outcome('install:create_release')
        if created and created['event'] in ('outcome','reconciled'):
            require(identity(self.root)==created['observed'],'installation_release_replaced')
    def mutation_deadline(self):
        require(time.monotonic()<getattr(self,'deadline',float('inf')),'installation_authority_deadline')
    def original_units(self,journal):
        expected=self._outcome(journal,'install:snapshot')
        require(set(expected)==set(SNAPSHOTS),'installation_snapshot_inventory_changed')
        for name in SNAPSHOTS:
            require(identity(journal.root/name)==expected[name],'installation_snapshot_changed')
        raw,_=regular(journal.root,'original-units.json')
        require(digest(raw)==expected['original-units.json']['sha256'],'installation_snapshot_changed')
        return json.loads(raw)
    def command(self,argv):
        from mldsafail.evaluator.native_workload import process_birth
        import signal,sys
        from deploy.workload_log import LogPipe
        limit=min(35,max(.001,getattr(self,'deadline',time.monotonic()+35)-time.monotonic()))
        require(sys.platform=='linux' and limit>.15,'installation_command_budget_or_platform')
        journal=getattr(self,'journal',None)
        token=uuid.uuid4().hex
        if journal: journal.append('subcommand_intent',command=token,argv_sha256=digest(canonical(argv)))
        root=journal.root if journal else Path(self.recipe['journal_root'])
        log=root/('command-'+token+'.log');report=root/('command-'+token+'-descendants.json')
        reserve=min(.25,limit/4)
        wrapped=[sys.executable,'-I',str(Path(__file__).with_name('workload_observation.py')),str(report),
                 str(limit-reserve-.05),'--cleanup-seconds',str(reserve),*argv]
        process=None;recorded=None;failure=None;cleanup_errors=[];containment=None;births=[];wrapper_timeout=False
        try:
            with log.open('xb') as stream, LogPipe(stream,1024**2) as pipe:
                os.chmod(log,0o600)
                try:
                    process=subprocess.Popen(wrapped,stdout=pipe.write_fd,stderr=subprocess.STDOUT,start_new_session=True,
                        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','UV_OFFLINE':'1','UV_NO_CACHE':'1','PIP_NO_INDEX':'1',
                             'PYTHONPATH':str(self.bundle/'src')+':'+str(self.bundle)})
                    recorded=process_birth(process.pid)
                    if journal: journal.append('subcommand_client',command=token,birth=recorded)
                    pipe.wait(process,timeout=limit)
                except subprocess.TimeoutExpired:
                    wrapper_timeout=True
                    raise
                finally:
                    if process is not None and process.poll() is None:
                        try:
                            require(process_birth(process.pid)==recorded,'installation_command_client_replaced')
                            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=.1)
                        except BaseException as error:
                            cleanup_errors.append(dict(type=type(error).__name__,message=str(error)))
                    if process is not None:
                        try:os.killpg(process.pid,0)
                        except ProcessLookupError:pass
                        except OSError as error:cleanup_errors.append(dict(type=type(error).__name__,message=str(error)))
                        else:cleanup_errors.append(dict(type='ProcessGroupRemaining',pid=process.pid))
                    stream.flush();os.fsync(stream.fileno())
        except BaseException as error:
            failure=dict(type=type(error).__name__,message=str(error))
        finally:
            try:containment=json.loads(report.read_bytes())
            except (OSError,ValueError) as error:
                cleanup_errors.append(dict(type=type(error).__name__,message=str(error)))
            progress=Path(str(report)+'.births.jsonl')
            if progress.exists():
                for line in progress.read_bytes().splitlines():
                    try:births.append(json.loads(line))
                    except ValueError:cleanup_errors.append(dict(type='PartialDescendantRecord'))
            if journal:
                journal.append('subcommand_outcome',command=token,birth=recorded,
                    returncode=process.returncode if process else None,log=identity(log),failure=failure,
                    wrapper_timeout=wrapper_timeout,containment=containment,descendant_births=births,
                    cleanup_errors=cleanup_errors)
        require(not cleanup_errors and containment is not None and not containment['remaining'] and
                not containment['errors'] and not containment['descendants'],
                'installation_subcommand_containment_unverified:'+token)
        require(failure is None and not wrapper_timeout and not containment['timed_out'] and
                process.returncode==0 and containment['returncode']==0,'installation_subcommand_failed:'+token)
        data=log.read_bytes()
        require(len(data)<1024**2,'installation_subcommand_output_limit:'+token)
        return data
    @measured_by_engine
    def reconcile_preflight(self,journal):
        import socket,sys
        require(self.source['origin'] in ('local_linux','host_observation') and sys.platform=='linux' and
                os.uname().machine=='x86_64','installation_reconcile_linux_host_required')
        host=self.source['host']
        require(os.getuid()==host['uid'] and socket.gethostname()==host['hostname'] and
                Path('/proc/sys/kernel/random/boot_id').read_text().strip()==host['boot_id'],'installation_wrong_host')
        verify(self.recipe['bundle_root'],self.source['manifest'])
        if journal.outcome('install:snapshot') and journal.outcome('install:snapshot')['event'] in ('outcome','reconciled'):
            self.original_units(journal)
        from deploy.workload_configuration import templates,verify_private_artifacts
        verify_private_artifacts(self.source)
        from mldsafail.evaluator.native_workload import NativeRuntime
        require(NativeRuntime(templates(self.source)['native']).identity()==host['runtime_identity'],
                'installation_reconcile_daemon_changed')

    @measured_by_engine
    def preflight(self,phase,journal):
        import socket,sys
        require(Path(__file__).resolve()==(Path(self.recipe['bundle_root'])/'deploy/workload_installation.py').resolve(),
                'installation_execute_frozen_engine_required')
        require(self.source['origin'] in ('local_linux','host_observation'),'installation_synthetic_origin_forbidden')
        require(sys.platform=='linux' and os.uname().machine=='x86_64','installation_linux_x86_64_required')
        host=self.source['host']
        scheduling_size(self.source,self.command)
        if journal.outcome('install:snapshot') and journal.outcome('install:snapshot')['event'] in ('outcome','reconciled'):
            self.original_units(journal)
        manager=identity(host['user_manager']['path'])
        require(all(manager[k]==host['user_manager'][k] for k in ('device','inode')),'installation_user_manager_replaced')
        manager_path=self.command(['/usr/bin/systemctl','--user','show','--property=ControlGroup','--value']).decode().strip()
        require('/sys/fs/cgroup'+manager_path==host['user_manager']['path'],'installation_user_manager_cgroup_changed')
        require(os.getuid()==host['uid'] and socket.gethostname()==host['hostname'] and
                Path('/proc/sys/kernel/random/boot_id').read_text().strip()==host['boot_id'], 'installation_wrong_host')
        keys=('bootstrap_interpreter',) if 'tools' in self.source['manifest'] else ('interpreter','installer')
        for key in keys:
            tool=self.recipe[key]; data,_=regular(Path(tool['path']).parent,Path(tool['path']).name)
            require(digest(data)==tool['sha256'] and len(data)==tool['bytes'],'installation_tool_changed')
            output=self.command([tool['path'],'--version']).decode().strip()
            require(output==('Python '+tool['version']) if key!='installer' else output.startswith('uv '+tool['version']+' '),
                    'installation_tool_version_changed')
        if journal.outcome('install:tools'):
            self.observe(dict(action='tools'),journal)
        memory=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
        output=self.source['resources']['output']
        if output['state']=='proposed':
            backing=Path(output['backing_file'])
            require(not any(parent.is_symlink() for parent in (backing,*backing.parents)), 'installation_backing_parent_symlink')
            require(backing.parent.stat().st_dev==self.root.parent.stat().st_dev,
                    'installation_separate_backing_filesystem_requires_evidence')
        allocation=output['bytes'] if output['state']=='proposed' and not journal.outcome('install:prerequisites') else 0
        from deploy.workload_release import remaining_allocation
        completed=[name for name in ('copy_bundle','tools','dependencies','images') if journal.outcome('install:'+name)]
        remaining_bytes=remaining_allocation(self.source['manifest'],self.recipe['installed_files'],completed)
        if phase=='install':
            require(memory>=1024**3 and shutil.disk_usage(self.root.parent).free-allocation-remaining_bytes>=5*1024**3,
                    'installation_admission_floor')
        from deploy.workload_installed import retained, docker,verify_ancestor_observations
        verify_ancestor_observations(self.source)
        require(retained(self.source)==self.source['retained_services'],'installation_retained_service_changed')
        daemon=json.loads(docker(self.source,['info','--format','{{json .}}']))
        require(daemon['ID']==host['daemon_id'] and any('rootless' in row for row in daemon['SecurityOptions']),
                'installation_daemon_identity_changed')
        docker_root=Path(daemon['DockerRootDir'])
        require(docker_root.is_dir() and docker_root.stat().st_dev==self.root.parent.stat().st_dev,
                'installation_docker_storage_requires_separate_admission_evidence')
        if 'images' in self.source['manifest']:
            from deploy.workload_images import tag_guard
            tag_guard(self.source['manifest']['images'],self._image_tags())
        else:
            for image in (self.source['manifest']['coordinator_image'],self.source['manifest']['worker_environment']['image_id']):
                actual=json.loads(docker(self.source,['image','inspect',image]))[0]
                require(actual['Id']==image and actual['Os']=='linux' and actual['Architecture']=='amd64','installation_image_changed')
        from deploy.workload_configuration import templates,verify_private_artifacts
        verify_private_artifacts(self.source)
        from mldsafail.evaluator.native_workload import NativeRuntime
        native=templates(self.source)['native']
        runtime=NativeRuntime(native)
        require(runtime.identity()==host['runtime_identity'],'installation_daemon_birth_changed')
        executable=Path(native['daemon_executable'])
        require(digest(regular(executable.parent,executable.name)[0])==native['daemon_sha256'],'installation_daemon_executable_changed')
        uid_map=[[int(v) for v in line.split()] for line in Path('/proc/'+str(host['runtime_identity']['daemon_birth']['pid'])+'/uid_map').read_text().splitlines()]
        require(uid_map==self.source['uid_mapping']['uid_map'],'installation_actual_uid_mapping_changed')
        activation=identity(self.recipe['activation_pointer'])
        expected=self.selection_expectation(journal)
        require(all(activation.get(k)==v for k,v in expected.items()),'installation_preflight_activation_changed')
        for kind in ('delegation','output'):
            resource=self.source['resources'][kind]
            if resource['state']=='observed':
                actual=identity(resource['path'])
                require(all(actual.get(k)==resource[k] for k in ('device','inode')),'installation_preflight_resource_changed')
        replacements,overrides=self.unit_transitions(journal)
        from deploy.workload_installed import verify_rollback,original_settings
        if self.source['origin']!='synthetic':
            from deploy.workload_registry import observe as observe_registry
            observe_registry(self.source,self.command,installed_units=self.installed_units_selected(journal))
            from deploy.workload_registry import references,bound_files
            references(self.source,self.command,inhibited=bool(self.acknowledged('inhibit_scheduling',journal)),
                       quiesced=self.quiesced_units(journal),overrides=overrides)
            bound_files(self.source,self.command,replacements=replacements)
        settings=original_settings(self.source)
        expected_settings=self.source['inventory']['manager_settings']
        inhibited=self.acknowledged('inhibit_scheduling',journal)
        for unit,actual in settings['manager_settings'].items():
            expected=dict(expected_settings[unit])
            if inhibited and inhibited.get('event') in ('outcome','reconciled') and unit in self.source['scheduling']['computational_units']:
                require(actual['ActiveState'] in ('inactive','failed'),'installation_scheduling_reactivated')
                expected['ActiveState']=actual['ActiveState']
            if unit in self.quiesced_units(journal):
                require(actual['ActiveState'] in (('active','inactive','failed') if self.installed_units_selected(journal) else ('inactive','failed')),
                        'handoff_previous_supervisor_reactivated')
                expected['ActiveState']=actual['ActiveState']
            if unit in overrides:expected.update(Restart='on-failure',Triggers='')
            require(actual==expected,'installation_original_manager_settings_drift')
        container_inhibited=self.acknowledged('inhibit_containers',journal)
        expected_containers=[dict(row) for row in self.source['containers']]
        if container_inhibited and container_inhibited.get('event') in ('outcome','reconciled'):
            for row in expected_containers:
                if row['disposition']=='pause':row.update(restart_policy='no',running=False,process_birth=None)
        require(settings['containers']==expected_containers,'installation_original_container_policy_drift')
        verify_rollback(self.source)
        from deploy.workload_handoff import observe as previous_supervisor
        if self.acknowledged('quiesce_supervisor',journal):self.observe(dict(action='quiesce_supervisor'),journal)
        else:require(previous_supervisor(self.source,self.command)==self.source['rollback'].get('supervisor'),
                     'handoff_previous_observation_changed')
        verify(self.recipe['bundle_root'],self.source['manifest'])
    def before(self,step,journal):
        action=step['action']
        if step.get('id','').startswith('install:'):self.owned_release(journal)
        if action=='create_release':
            value=identity(self.root); require(value['state']=='absent','installation_partial_destination'); return value
        if action=='quiesce_supervisor':
            from deploy.workload_handoff import observe
            actual=observe(self.source,self.command)
            require(actual==self.source['rollback'].get('supervisor'),'handoff_previous_observation_changed')
            return dict(previous_supervisor=actual)
        if action in ('activate','restore_activation'):
            if action=='activate':
                self.scheduling_transition(journal)
            actual=identity(self.recipe['activation_pointer'])
            expected=self.selection_expectation(journal)
            require(all(actual.get(k)==v for k,v in expected.items() if k!='state'),'installation_activation_identity_changed')
            return actual
        if action in ('snapshot','copy_bundle','tools','dependencies'):
            if action=='snapshot':
                before={name:identity(journal.root/name) for name in SNAPSHOTS}
                require(all(row['state']=='absent' for row in before.values()),'installation_snapshot_destination_not_absent')
                return before
            path={'snapshot':journal.root/'original-units.json','copy_bundle':self.bundle,'tools':self.root/'tools','dependencies':self.root/'.venv'}[action]
            before=identity(path);require(before['state']=='absent','installation_destination_not_absent')
            return before
        if action=='images':
            from deploy.workload_images import tag_guard
            actual=self._image_tags();tag_guard(self.source['manifest']['images'],actual);return actual
        if action=='configurations':
            rows={role:identity(row['path']) for role,row in self.source['manifest']['configurations'].items()}
            require(all(row['state']=='absent' for row in rows.values()),'installation_configuration_destination_exists')
            return rows
        if action=='inhibit_scheduling':
            if self.acknowledged(action,journal):return self.observe(step,journal)
            gate=identity(self.source['permission_root'])
            destinations={row['path']:identity(row['path']) for row in self.proposal['scheduling']['resources']}
            require(gate['state']=='absent' and all(row['state']=='absent' for row in destinations.values()),
                    'installation_inhibition_destination_exists')
            return dict(gate=gate,destinations=destinations)
        if action=='inhibit_containers':
            return {row['id']:json.loads(self.command(self._docker()+['inspect',row['id']]))[0] for row in self.source['containers']}
        if action=='prerequisites':
            observed={kind:identity(row['path']) for kind,row in self.source['resources'].items() if kind in ('delegation','output')}
            for kind in observed:
                if self.source['resources'][kind]['state']=='proposed':
                    require(observed[kind]['state']=='absent','installation_proposed_prerequisite_exists')
            return observed
        if action=='start_paused':
            require(identity(self.enable_path)==self._outcome(journal,'install:enable_supervisor'),
                    'installation_supervisor_enable_identity_changed')
            socket=identity(self.source['resources']['socket']['path'])
            require(socket['state']=='absent','installation_existing_socket_preserve')
            return dict(socket=socket)
        if action=='enable_supervisor':
            before=identity(self.enable_path)
            require(before['state']=='absent','installation_supervisor_enable_already_present')
            return before
        if action in ('units','supervisor_unit'):
            if action=='supervisor_unit':
                require(identity(self.recipe['activation_pointer'])==self._outcome(journal,'install:activate'),
                        'installation_supervisor_unit_before_activation')
                require(self.valid_outcome(dict(action='verify_release'),self.observe(dict(action='verify_release'),journal),journal),
                        'installation_release_changed_before_supervisor_unit')
            self.scheduling_transition(journal)
            return {name:identity(Path(self.source['installation']['unit_directory'])/name) for name in self.unit_names(action)}
        return self.observe(step,journal)
    def _outcome(self,journal,name):
        row=journal.outcome(name); require(row and row['event'] in ('outcome','reconciled') and 'observed' in row,
                                          'installation_required_prior_outcome_missing'); return row['observed']
    def snapshot_substeps(self,journal):
        return [row for row in journal.rows if row.get('step_id')=='install:snapshot' and
                row['event'] in ('mutation_intent','mutation_outcome','mutation_failed')]
    def observe_substeps(self,step,journal):
        """Read bound file/tree births; external effects require their own observer."""
        from deploy.workload_mutation import classify
        result=[]
        for row in journal.rows:
            if row['event']!='mutation_intent' or row.get('step_id')!=step['id']:continue
            effect=row.get('expected_effect') or {}
            record=dict(resource=row['resource'],expected_effect=effect)
            try:
                if effect.get('effect') in ('exclusive_file','exclusive_private_snapshot'):
                    actual=identity(effect['path'])
                elif step['action']=='tools' and 'inventory_sha256' in effect:
                    from deploy.workload_artifacts import verify_tree
                    role=row['resource'].removeprefix(step['id']+':')
                    target=Path(effect['path']);actual=identity(target)
                    if actual['state']!='absent':
                        actual=dict(identity=actual,inventory_sha256=digest(canonical(
                            verify_tree(target,self.source['manifest']['tools'][role]['members']))))
                elif step['action']=='prerequisites' and journal.recovery_protocol == 4:
                    from deploy.workload_recovery_inventory import observe_prerequisite
                    actual=observe_prerequisite(row['resource'],self.source,self.command)
                elif effect.get('effect')=='exclusive_directory' and journal.recovery_protocol == 4:
                    actual=identity(effect['path'])
                else:
                    result.append(dict(record,status='observation_required',
                        disposition='unacknowledged_or_incomplete_effect_preserve_and_block'));continue
                result.append(dict(record,status=classify(journal,row['resource'],actual),observed=actual))
            except BaseException as error:
                result.append(dict(record,status='ambiguous',
                    error=dict(type=type(error).__name__,message=str(error))))
        return result
    def partial_reconcilable(self,step,value,journal):
        # Protocol 2 retains snapshot-only continuation. Protocol 3 additionally
        # admits acknowledged configuration files. Neither replays external effects.
        if journal.recovery_protocol == 4 and step['id'] in ('install:copy_bundle','install:tools'):
            return self.artifact_continuable(step,value,journal)
        if journal.recovery_protocol in (3,4) and step['id']=='install:configurations':
            return self.configuration_continuable(step,value,journal)
        if journal.recovery_protocol not in (2,3,4) or step['id']!='install:snapshot':return False
        rows=self.snapshot_substeps(journal)
        if not rows or set(value)!=set(SNAPSHOTS):return False
        for name in SNAPSHOTS:
            resource='snapshot:'+name
            records=[row for row in rows if row['resource']==resource]
            intents=[row for row in records if row['event']=='mutation_intent']
            outcomes=[row for row in records if row['event']=='mutation_outcome']
            if not records:
                if value[name].get('state')!='absent':return False
                continue
            if len(records)!=2 or len(intents)!=1 or len(outcomes)!=1:return False
            if journal.recovery_protocol in (3,4):
                from deploy.workload_mutation import classify
                if classify(journal,resource,value[name])!='completed':return False
            expected=intents[0].get('expected_effect')
            if not expected or outcomes[0].get('expected_effect')!=expected:return False
            if (outcomes[0]['observed']!=value[name] or value[name].get('sha256')!=expected.get('sha256') or
                    expected.get('path')!=str(journal.root/name)):return False
        return all(row['resource'] in {'snapshot:'+name for name in SNAPSHOTS} for row in rows)
    def artifact_specs(self,step):
        """Exact construction inventory; unknown filesystem entries are blocked."""
        if step['action']=='copy_bundle':
            files={str(self.bundle/name):dict(sha256=row['sha256'],mode=row['mode'])
                   for name,row in self.source['manifest']['files'].items()}
            files[str(self.bundle/'manifest.json')]=dict(sha256=digest(canonical(self.source['manifest'])),mode=0o600)
            directories={str(self.bundle)}
            for path in files:
                directories.update(str(parent) for parent in Path(path).parents
                                   if parent==self.bundle or parent.is_relative_to(self.bundle))
            return dict(directories=sorted(directories,key=lambda path:(len(Path(path).parts),path)),files=files,tools={})
        if step['action']=='tools':
            return dict(directories=[str(self.root/'tools')],files={},
                        tools={str(self.root/'tools'/role):row for role,row in self.source['manifest'].get('tools',{}).items()})
        require(False,'installation_partial_artifact_unsupported')
    def partial_observation(self,step,journal):
        from deploy.workload_artifacts import verify_tree
        specs=self.artifact_specs(step)
        result=dict(directories={path:identity(path) for path in specs['directories']},
                    files={path:identity(path) for path in specs['files']},tools={})
        for path,row in specs['tools'].items():
            actual=identity(path)
            if actual['state']!='absent':
                try:actual=dict(identity=actual,inventory_sha256=digest(canonical(verify_tree(path,row['members']))))
                except BaseException as error:
                    actual=dict(identity=actual,unverified=type(error).__name__)
            result['tools'][path]=actual
        # Do not silently adopt extra children, including incomplete extra files.
        roots=specs['directories'][:1]
        allowed=set(specs['directories'])|set(specs['files'])|set(specs['tools'])
        if roots and Path(roots[0]).is_symlink():
            result['unexpected']=[roots[0]]
        elif step['action']=='copy_bundle' and roots and Path(roots[0]).is_dir():
            result['unexpected']=sorted(str(path) for path in Path(roots[0]).rglob('*') if str(path) not in allowed)
        elif step['action']=='tools' and roots and Path(roots[0]).is_dir():
            result['unexpected']=sorted(str(path) for path in Path(roots[0]).iterdir() if str(path) not in allowed)
        else:result['unexpected']=[]
        return result
    def artifact_continuable(self,step,value,journal):
        from deploy.workload_mutation import classify
        if value!=self.partial_observation(step,journal) or value.get('unexpected'):return False
        specs=self.artifact_specs(step);allowed={}
        for path in specs['directories']:
            allowed[step['id']+':directory:'+path]=(value['directories'][path],
                dict(path=path,effect='exclusive_directory',mode=0o700,parent_identity=identity(Path(path).parent)))
        for path,expected in specs['files'].items():
            allowed[step['id']+':'+path]=(value['files'][path],dict(path=path,effect='exclusive_file',
                parent_identity=identity(Path(path).parent),**expected))
        for path,row in specs['tools'].items():
            from pathlib import PurePosixPath
            expanded=dict(row['members'])
            for name in row['members']:
                for parent in PurePosixPath(name).parents:
                    if str(parent)!='.':expanded.setdefault(str(parent),dict(kind='directory',mode=0o700))
            allowed[step['id']+':'+Path(path).name]=(value['tools'][path],dict(path=path,
                inventory_sha256=digest(canonical(expanded))))
        rows=[row for row in journal.rows if row.get('step_id')==step['id'] and
              row['event'] in ('mutation_intent','mutation_outcome','mutation_failed')]
        if not rows or any(row['resource'] not in allowed for row in rows):return False
        for resource,(actual,effect) in allowed.items():
            records=[row for row in rows if row['resource']==resource]
            if not records:
                if actual.get('state')!='absent':return False
            else:
                if len(records)!=2 or any(row.get('expected_effect')!=effect for row in records):return False
                if classify(journal,resource,actual)!='completed':return False
        return True
    def directory_substep(self,step,journal,path):
        from deploy.workload_mutation import mutate,classify
        path=Path(path)
        require(not any(parent.is_symlink() for parent in (path,*path.parents)),
                'installation_directory_parent_symlink')
        effect=dict(path=str(path),effect='exclusive_directory',mode=0o700,parent_identity=identity(path.parent))
        resource=step['id']+':directory:'+str(path)
        records=[row for row in journal.rows if row['event']=='mutation_intent' and row.get('resource')==resource]
        if records:
            require(any(row['event']=='reconciled_partial' and row.get('step')==step['id'] for row in journal.rows) and
                    records[0].get('expected_effect')==effect and classify(journal,resource,identity(path))=='completed',
                    'installation_directory_substep_changed')
            return
        def create():
            path.mkdir(mode=0o700);sync_directory(path.parent)
        self.mutation_deadline()
        mutate(journal,resource,lambda:identity(path),create,step_id=step['id'],expected_effect=effect,
               validate=lambda actual:actual.get('state')=='observed' and actual.get('mode')==0o700)
    def configuration_continuable(self,step,value,journal):
        """Only unchanged acknowledged writes and never-attempted files continue.

        An absent attempted file is deliberately insufficient: it could have
        been removed after an unacknowledged write.
        """
        from deploy.workload_configuration import hashes,measured_resources
        from deploy.workload_mutation import classify
        expected=hashes(self.source,measured_resources(self.source))
        configurations=self.source['manifest']['configurations']
        if set(value)!=set(configurations) or set(expected)!=set(configurations):return False
        rows=[row for row in journal.rows if row.get('step_id')==step['id'] and
              row['event'] in ('mutation_intent','mutation_outcome','mutation_failed')]
        allowed=set()
        for role,configuration in configurations.items():
            path=configuration['path'];resource=step['id']+':'+path;allowed.add(resource)
            destination=Path(path)
            if any(parent.is_symlink() for parent in (destination,*destination.parents)):return False
            records=[row for row in rows if row['resource']==resource]
            if not records:
                if value[role].get('state')!='absent':return False
                continue
            if len(records)!=2:return False
            effect=dict(path=path,effect='exclusive_file',sha256=expected[role],mode=0o600,
                        parent_identity=identity(destination.parent))
            if any(row.get('expected_effect')!=effect for row in records):return False
            if classify(journal,resource,value[role])!='completed':return False
            if value[role].get('sha256')!=expected[role] or value[role].get('mode')!=0o600:return False
        return bool(rows) and all(row['resource'] in allowed for row in rows)
    def continuation_before(self,step,journal):
        value=(self.partial_observation(step,journal) if journal.recovery_protocol == 4 and
               step['action'] in ('copy_bundle','tools') else self.observe(step,journal))
        require(self.partial_reconcilable(step,value,journal),'installation_partial_resources_changed')
        return value
    def file_substep(self,step,journal,path,expected,action):
        """Record exclusive writes; v3 may skip reconciled configuration births."""
        from deploy.workload_mutation import mutate
        path=Path(path)
        effect=dict(path=str(path),effect='exclusive_file',**expected)
        if journal.recovery_protocol == 4 or (journal.recovery_protocol == 3 and step['id']=='install:configurations'):
            require(not any(parent.is_symlink() for parent in (path,*path.parents)),
                    'installation_configuration_parent_symlink')
            effect['parent_identity']=identity(path.parent)
        resource=step['id']+':'+str(path)
        records=[row for row in journal.rows if row.get('resource')==resource and
                 row['event']=='mutation_intent']
        if records and (journal.recovery_protocol == 4 or (journal.recovery_protocol == 3 and step['id']=='install:configurations')):
            from deploy.workload_mutation import classify
            require(any(row['event']=='reconciled_partial' and row.get('step')==step['id']
                        for row in journal.rows),'installation_partial_reconciliation_required')
            require(records[0].get('expected_effect')==effect and
                    classify(journal,resource,identity(path))=='completed',
                    'installation_configuration_substep_changed')
            return
        require(identity(path)['state']=='absent','installation_substep_destination_not_absent')
        self.mutation_deadline()
        mutate(journal,step['id']+':'+str(path),lambda:identity(path),action,
               step_id=step['id'],expected_effect=effect,
               validate=lambda actual:all(actual.get(key)==value for key,value in expected.items()))
    def snapshot_file(self,journal,name,data):
        from deploy.workload_mutation import mutate
        path=journal.root/name;resource='snapshot:'+name
        expected=dict(path=str(path),sha256=digest(data),effect='exclusive_private_snapshot')
        records=[row for row in self.snapshot_substeps(journal) if row['resource']==resource]
        if records:
            require(journal.recovery_protocol in (2,3,4) and
                    any(row['event']=='reconciled_partial' and row.get('step')=='install:snapshot'
                        for row in journal.rows),'installation_partial_reconciliation_required')
            if journal.recovery_protocol in (3,4):
                from deploy.workload_mutation import classify
                require(classify(journal,resource,identity(path))=='completed',
                        'installation_snapshot_substep_changed')
            outcome=next((row for row in records if row['event']=='mutation_outcome'),None)
            require(outcome and outcome.get('expected_effect')==expected and outcome['observed']==identity(path),
                    'installation_snapshot_substep_changed')
            return
        require(identity(path)['state']=='absent','installation_snapshot_destination_not_absent')
        self.mutation_deadline()
        mutate(journal,resource,lambda:identity(path),lambda:exclusive(path,data),
               step_id='install:snapshot',expected_effect=expected,
               validate=lambda actual:actual.get('sha256')==expected['sha256'] and actual.get('mode')==0o600)
    def apply(self,step,journal):
        action=step['action']
        self.mutation_deadline()
        if step.get('id','').startswith('install:'):self.owned_release(journal)
        if action in ('inhibit_scheduling','inhibit_containers') and self.acknowledged(action,journal):return
        if action=='restore_activation' and not journal.outcome('install:activate'):return
        if action=='restore_units' and not journal.outcome('install:units'):return
        if action=='quiesce_supervisor':
            from deploy.workload_handoff import stop
            stop(self.source,self.command)
        elif action=='snapshot':
            snapshot={}
            for name in [*self.proposal['units'],*[Path(r['path']).name for r in self.proposal['scheduling']['resources']]]:
                if name in self.proposal['units']:
                    path=Path(self.source['installation']['unit_directory'])/name
                    row=identity(path)
                    if row['state']=='observed':
                        row['contents_hex']=regular(path.parent,path.name)[0].hex()
                        row['gid']=path.stat().st_gid
                    snapshot[str(path)]=row
            self.snapshot_file(journal,'original-units.json',canonical(snapshot))
            originals={}
            for path,expected in self.source['inventory']['original_files'].items():
                file=Path(path);data,mode,record=read_owned_file(file,self.command,metadata=True)
                require(digest(data)==expected,'installation_original_scheduling_file_changed')
                originals[path]=dict(record,sha256=digest(data),contents_hex=data.hex())
            self.snapshot_file(journal,'original-scheduling-files.json',canonical(originals))
            from deploy.workload_installed import original_settings,observation_runner
            with observation_runner(self.command):observed_settings=original_settings(self.source)
            require(observed_settings['manager_settings']==self.source['inventory']['manager_settings'] and
                    observed_settings['containers']==self.source['containers'],'installation_original_settings_changed_before_snapshot')
            self.snapshot_file(journal,'original-scheduling.json',canonical(observed_settings['manager_settings']))
            self.snapshot_file(journal,'original-container-policies.json',canonical(observed_settings['containers']))
        elif action=='create_release':
            self.root.mkdir(mode=0o700); sync_directory(self.root.parent)
        elif action=='copy_bundle':
            # Destination is exclusively created inside an acknowledged release.
            require(identity(self.root)==self._outcome(journal,'install:create_release'),'installation_release_replaced')
            if journal.recovery_protocol == 4:
                for directory in self.artifact_specs(step)['directories']:
                    self.directory_substep(step,journal,directory)
            else:self.bundle.mkdir(mode=0o700)
            for name,row in self.source['manifest']['files'].items():
                destination=self.bundle/name
                destination.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
                from deploy.workload_release import copy_regular
                self.file_substep(step,journal,destination,dict(sha256=row['sha256'],mode=row['mode']),
                    lambda:copy_regular(self.recipe['bundle_root'],name,destination,row))
            data=canonical(self.source['manifest'])
            self.file_substep(step,journal,self.bundle/'manifest.json',dict(sha256=digest(data),mode=0o600),
                lambda:exclusive(self.bundle/'manifest.json',data))
            sync_directory(self.root)
        elif action=='tools':
            tools=self.source['manifest'].get('tools')
            if tools:
                from deploy.workload_artifacts import extract,verify_tree
                from deploy.workload_mutation import mutate
                root=self.root/'tools'
                if journal.recovery_protocol == 4:self.directory_substep(step,journal,root)
                else:root.mkdir(mode=0o700);sync_directory(root.parent)
                for role,row in tools.items():
                    data,_=regular(self.bundle,row['archive'])
                    target=root/role
                    def observe_tool():
                        actual=identity(target)
                        if actual['state']=='absent':return actual
                        return dict(identity=actual,inventory_sha256=digest(canonical(verify_tree(target,row['members']))))
                    from pathlib import PurePosixPath
                    expanded=dict(row['members'])
                    for name in row['members']:
                        for parent in PurePosixPath(name).parents:
                            if str(parent)!='.':expanded.setdefault(str(parent),dict(kind='directory',mode=0o700))
                    expected_inventory=digest(canonical(expanded))
                    resource=step['id']+':'+role
                    prior=[record for record in journal.rows if record['event']=='mutation_intent' and record.get('resource')==resource]
                    if prior and journal.recovery_protocol == 4:
                        from deploy.workload_mutation import classify
                        require(any(record['event']=='reconciled_partial' and record.get('step')==step['id'] for record in journal.rows) and
                                prior[0].get('expected_effect')==dict(path=str(target),inventory_sha256=expected_inventory) and
                                classify(journal,resource,observe_tool())=='completed',
                                'installation_tool_substep_changed')
                        continue
                    self.mutation_deadline()
                    mutate(journal,step['id']+':'+role,observe_tool,lambda:extract(data,target,row['members']),
                        step_id=step['id'],expected_effect=dict(path=str(target),inventory_sha256=expected_inventory),
                        validate=lambda actual:actual.get('inventory_sha256')==expected_inventory)
        elif action=='dependencies':
            self.command(['/usr/bin/sudo','-n','/usr/bin/unshare','--net','--setgid='+str(os.getgid()),'--setuid='+str(os.getuid()),'/usr/bin/env','PYTHONDONTWRITEBYTECODE=1',self.recipe['installer']['path'],'--no-cache','--no-config',
                          'venv','--offline','--no-project','--python',self.recipe['interpreter']['path'],str(self.root/'.venv')])
            self.command(['/usr/bin/sudo','-n','/usr/bin/unshare','--net','--setgid='+str(os.getgid()),'--setuid='+str(os.getuid()),'/usr/bin/env','PYTHONDONTWRITEBYTECODE=1',self.recipe['installer']['path'],'--no-cache','--no-config',
                          'pip','install','--offline','--no-index','--no-deps','--python',self.python,
                          *[str(self.bundle/name) for name in self.source['manifest']['dependencies']]])
            from deploy.workload_dependencies import project_entrypoints
            project_entrypoints(self.bundle,self.root/'.venv')
        elif action=='images':
            client=self.root/'offline-docker-client';client.mkdir(mode=0o700,exist_ok=False)
            exclusive(client/'config.json',canonical(dict(auths={})))
            self.command(['/usr/bin/sudo','-n','/usr/bin/unshare','--net','--setgid='+str(os.getgid()),'--setuid='+str(os.getuid()),
                          '/usr/bin/docker','--config',str(client),*self._docker()[1:],
                          'load','--input',str(self.bundle/self.source['manifest']['images']['archive'])])
        elif action=='configurations':
            from deploy.workload_configuration import materialize,measured_resources
            resources=measured_resources(self.source)
            contents=materialize(self.source,resources)
            for role,row in self.source['manifest']['configurations'].items():
                source=Path(self.recipe['configuration_sources'][role]); data,_=regular(source.parent,source.name)
                require(digest(data)==row['sha256'],'installation_private_configuration_changed')
                destination=Path(row['path']); require(destination.is_relative_to(self.root),'installation_configuration_outside_release')
                destination.parent.mkdir(mode=0o700,exist_ok=True)
                self.file_substep(step,journal,destination,dict(sha256=digest(contents[role]),mode=0o600),
                    lambda:exclusive(destination,contents[role]))
        elif action=='inhibit_scheduling':
            gate=Path(self.source['permission_root']); gate.mkdir(mode=0o700,exist_ok=False)
            for row in self.proposal['scheduling']['resources']:
                path=Path(row['path'])
                if row['owner_uid']==os.getuid():
                    if not path.parent.exists(): path.parent.mkdir(mode=0o700)
                    require(not path.parent.is_symlink() and path.parent.stat().st_uid==row['owner_uid'],
                            'installation_dropin_directory_changed')
                    exclusive(path,row['contents'].encode())
                else:
                    require(row['owner_uid']==0,'installation_unsupported_privileged_owner')
                    script=('import os,pathlib,stat,sys; p=pathlib.Path(sys.argv[1]); '
                            'p.parent.mkdir(mode=0o700,exist_ok=True); '
                            'assert not p.parent.is_symlink() and p.parent.stat().st_uid==0; '
                            'fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600); '
                            'os.write(fd,bytes.fromhex(sys.argv[2])); os.fsync(fd); os.close(fd)')
                    self.command(['/usr/bin/sudo','-n','/usr/bin/python3','-c',script,str(path),row['contents'].encode().hex()])
            for command in self.proposal['scheduling']['commands_after_exclusive_resource_creation']:
                import shlex
                self.command(shlex.split(command))
        elif action=='inhibit_containers':
            for row in self.source['containers']:
                if row['disposition']=='pause':
                    self.command(self._docker()+['update','--restart=no',row['id']])
                    self.command(self._docker()+['stop','--time','10',row['id']])
        elif action=='prerequisites':
            from deploy.workload_prerequisites import apply
            apply(self.source,self.command,journal)
        elif action in ('units','supervisor_unit','restore_units'):
            directory=Path(self.source['installation']['unit_directory'])
            if action in ('units','supervisor_unit'):
                for name in self.unit_names(action):
                    self._replace_bound(directory/name,self.proposal['units'][name].encode(),journal)
            else:
                originals=self.original_units(journal)
                for path,row in originals.items():
                    action_name='supervisor_unit' if Path(path).name=='mldsafail-workload-supervisor.service' else 'units'
                    installed=journal.outcome('install:'+action_name)
                    if not installed:continue
                    if row['state']=='absent':
                        actual=identity(path)
                        expected=self._outcome(journal,'install:'+action_name)[Path(path).name]
                        require(actual==expected,'installation_unit_replaced'); Path(path).unlink()
                        sync_directory(Path(path).parent)
                    else: self._replace_bound(Path(path),bytes.fromhex(row['contents_hex']),journal,
                                              mode=row['mode'],owner=(row['uid'],row['gid']))
            self.command(['/usr/bin/systemctl','--user','daemon-reload'])
        elif action in ('activate','restore_activation'):
            pointer=Path(self.recipe['activation_pointer']); target=str(self.root) if action=='activate' else self.source['rollback']['target']
            temporary=pointer.with_name(pointer.name+'.'+uuid.uuid4().hex+'.tmp')
            os.symlink(target,temporary); sync_directory(pointer.parent)
            candidate=identity(temporary)
            journal.append('activation_candidate',step_id=step['id'],observed=candidate)
            before=self.before(step,journal)
            self.mutation_deadline()
            import ctypes
            library=ctypes.CDLL(None,use_errno=True)
            exchange=library.renameat2
            exchange.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            exchange.restype=ctypes.c_int
            code=exchange(-100,os.fsencode(temporary),-100,os.fsencode(pointer),2)
            require(code==0,'installation_atomic_exchange_failed')
            sync_directory(pointer.parent)
            previous=identity(temporary)
            require(all(previous.get(k)==v for k,v in before.items() if k!='path'),'installation_activation_replaced_during_exchange')
            journal.append('activation_preserved',step_id=step['id'],observed=previous)
        elif action=='enable_supervisor':
            require(identity(self.recipe['activation_pointer'])==self._outcome(journal,'install:activate'),
                    'installation_activation_changed_before_enable')
            require(self.valid_outcome(dict(action='verify_release'),self.observe(dict(action='verify_release'),journal),journal),
                    'installation_release_changed_before_enable')
            self.scheduling_transition(journal)
            from deploy.workload_registry import generated_supervisor
            generated_supervisor(self.proposal,self.command)
            self.mutation_deadline()
            exclusive(self.enable_path,supervisor_enable_contents(self.proposal))
        elif action=='start_paused': self.command(['/usr/bin/systemctl','--user','start','mldsafail-workload-supervisor.service'])
        elif action=='stop_supervisor':
            if journal.outcome('install:supervisor_unit'):
                name='mldsafail-workload-supervisor.service'
                actual=identity(Path(self.source['installation']['unit_directory'])/name)
                require(actual==self._outcome(journal,'install:supervisor_unit')[name],
                        'installation_supervisor_unit_identity_changed')
                self.command(['/usr/bin/systemctl','--user','stop',name])
            enabled=journal.outcome('install:enable_supervisor')
            if enabled and enabled['event'] in ('outcome','reconciled'):
                require(identity(self.enable_path)==self._outcome(journal,'install:enable_supervisor'),
                        'installation_supervisor_enable_identity_changed')
                self.enable_path.unlink();sync_directory(self.root)
            elif enabled and enabled['event']=='reconciled_absent':
                require(identity(self.enable_path)['state']=='absent','installation_supervisor_enable_identity_changed')
        elif action in ('verify_release','verify_paused','verify_cleanup','verify_rollback'):
            require(self.valid_outcome(step,self.observe(step,journal),journal),'installation_verification_failed')
        else: require(False,'installation_unknown_step')
    def _image_tags(self):
        rows=self.command(self._docker()+['image','ls','--no-trunc','--format','{{.Repository}}:{{.Tag}} {{.ID}}']).decode().splitlines()
        return {line.rsplit(' ',1)[0]:line.rsplit(' ',1)[1] for line in rows if not line.startswith('<none>')}
    def _docker(self): return ['/usr/bin/docker','--host','unix://'+self.source['host']['runtime_identity']['socket_birth']['path']]
    def _replace_bound(self,path,data,journal,*,mode=0o600,owner=None):
        original=self.original_units(journal)[str(path)]
        actual=identity(path)
        allowed=[original]
        if path.name in self.proposal['units']:
            action_name='supervisor_unit' if path.name=='mldsafail-workload-supervisor.service' else 'units'
            installed=journal.outcome('install:'+action_name)
            if installed and 'observed' in installed:
                allowed.append(installed['observed'][path.name])
        require(any(all((path.stat().st_gid if k=='gid' else actual.get(k))==v
                        for k,v in row.items() if k not in ('contents_hex',)) for row in allowed),
                'installation_unknown_unit_preserve')
        temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        self.mutation_deadline()
        exclusive(temporary,data,mode=mode)
        if owner is not None and (temporary.stat().st_uid,temporary.stat().st_gid)!=owner:
            self.command(['/usr/bin/sudo','-n','/usr/bin/chown',str(owner[0])+':'+str(owner[1]),'--',str(temporary)])
        require(owner is None or (temporary.stat().st_uid,temporary.stat().st_gid)==owner,
                'installation_unit_owner_restore_failed')
        self.mutation_deadline()
        os.replace(temporary,path); sync_directory(path.parent)
    @measured_by_engine
    def observe(self,step,journal):
        action=step['action']
        if action=='quiesce_supervisor':
            from deploy.workload_handoff import stopped
            return stopped(self.source,self.command,replacement=self.unit_records(journal).get('mldsafail-workload-supervisor.service'))
        if action=='snapshot': return {name:identity(journal.root/name) for name in SNAPSHOTS}
        if action=='create_release': return identity(self.root)
        if action=='copy_bundle':
            if not self.bundle.exists(): return dict(state='absent')
            return dict(identity=identity(self.bundle),manifest_sha256=verify(self.bundle,self.source['manifest']))
        if action=='tools':
            from deploy.workload_artifacts import verify_tree
            tools=self.source['manifest'].get('tools')
            if not tools:return dict(legacy_external_tools=True)
            return {role:dict(identity=identity(self.root/'tools'/role),
                    inventory_sha256=digest(canonical(verify_tree(self.root/'tools'/role,row['members']))))
                    for role,row in tools.items()}
        if action=='images':
            from deploy.workload_images import installed
            return installed(self.source['manifest']['images'],lambda identifier:json.loads(self.command(self._docker()+['image','inspect',identifier]))[0])
        if action=='dependencies':
            from deploy.workload_dependencies import installed_inventory
            return installed_inventory(self.root/'.venv',interpreter=self.recipe['interpreter']['path']) if (self.root/'.venv').exists() else {}
        if action=='configurations':
            return {role:identity(row['path']) for role,row in self.source['manifest']['configurations'].items()}
        if action=='enable_supervisor':return identity(self.enable_path)
        if action in ('activate','restore_activation'): return identity(self.recipe['activation_pointer'])
        if action in ('units','supervisor_unit','restore_units'):
            if action=='restore_units' and not journal.outcome('install:units'):
                return dict(skipped='units_never_replaced')
            names=self.proposal['units'] if action=='restore_units' else self.unit_names(action)
            return {name:identity(Path(self.source['installation']['unit_directory'])/name) for name in names}
        if action in ('start_paused','verify_paused'):
            from mldsafail.evaluator.workload_client import WorkloadClient
            from mldsafail.evaluator.native_workload import private_json,process_birth
            socket_path=Path(self.source['resources']['socket']['path'])
            record=private_json(socket_path.parent/'socket.json');process=record['process']
            actual=identity(socket_path)
            require(actual.get('uid')==self.source['host']['uid'] and actual.get('mode')==0o600 and
                    all(actual.get(key)==record.get(key) for key in ('path','device','inode')),
                    'installation_supervisor_socket_birth_changed')
            require(process_birth(process['pid'])==process and Path('/proc/'+str(process['pid'])).stat().st_uid==self.source['host']['uid'],
                    'installation_supervisor_process_changed')
            main=int(self.command(['/usr/bin/systemctl','--user','show','mldsafail-workload-supervisor.service','--property=MainPID','--value']).strip())
            require(main==process['pid'],'installation_supervisor_manager_or_placement_changed')
            membership=Path('/proc/'+str(main)+'/cgroup').read_text().strip()
            require(membership.startswith('0::/') and
                    not Path('/sys/fs/cgroup'+membership[3:]).is_relative_to(self.source['installation']['heavy_path']),
                    'installation_supervisor_manager_or_placement_changed')
            state=WorkloadClient(self.source['resources']['socket']['path'],journal.root/'inspection-client').status()
            require(identity(self.enable_path)==self._outcome(journal,'install:enable_supervisor'),
                    'installation_supervisor_enable_identity_changed')
            return dict(paused=state['paused'],phase=state['phase'],process=process,socket=actual,
                        supervisor_generation=record['supervisor_generation'])
        if action=='stop_supervisor':
            if not journal.outcome('install:supervisor_unit'):
                return dict(stopped=True,enabled=identity(self.enable_path)['state']!='absent')
            result=self.command(['/usr/bin/systemctl','--user','show','mldsafail-workload-supervisor.service','--property=ActiveState','--value'])
            return dict(stopped=result.strip() in (b'inactive',b'failed'),enabled=identity(self.enable_path)['state']!='absent')
        if action in ('inhibit_scheduling','inhibit_containers','prerequisites','verify_release','verify_cleanup','verify_rollback'):
            from deploy.workload_installed import inspect_control
            return inspect_control(action,self.proposal,journal)
        return {}
    def valid_outcome(self,step,value,journal):
        action=step['action']
        if action=='snapshot':return set(value)==set(SNAPSHOTS) and all(row.get('state')=='observed' for row in value.values())
        if action=='create_release': return value.get('state')=='observed'
        if action=='enable_supervisor':
            return value.get('sha256')==digest(supervisor_enable_contents(self.proposal))
        if action=='copy_bundle': return value.get('manifest_sha256')==self.proposal['manifest_sha256']
        if action=='tools': return value==self.observe(step,journal)
        if action=='images': return value==self.observe(step,journal)
        if action=='dependencies': return value==self.recipe['installed_files']
        if action=='configurations':
            from deploy.workload_configuration import hashes,measured_resources
            resources=measured_resources(self.source)
            return all(value[role].get('sha256')==expected for role,expected in hashes(self.source,resources).items())
        if action in ('activate','restore_activation'):
            return value.get('target')==(str(self.root) if action=='activate' else self.source['rollback']['target'])
        if action in ('start_paused','verify_paused'): return value.get('paused') is True
        if action=='stop_supervisor': return value.get('stopped') is True and value.get('enabled') is False
        if action in ('units','supervisor_unit'):
            return set(value)==set(self.unit_names(action)) and all(value[name].get('sha256')==digest(self.proposal['units'][name].encode()) for name in value)
        if action=='restore_units':
            if not journal.outcome('install:units'):return value==dict(skipped='units_never_replaced')
            originals=self.original_units(journal)
            for name,actual in value.items():
                path=Path(self.source['installation']['unit_directory'])/name;original=originals[str(path)]
                if original['state']=='absent':
                    if actual['state']!='absent':return False
                elif (any(actual.get(key)!=original[key] for key in ('sha256','mode','uid')) or
                      path.stat().st_gid!=original['gid']):return False
            return set(value)==set(self.proposal['units'])
        return value.get('verified') is True
    @measured_by_engine
    def recovery_observation(self,step,journal):
        """Additional operation-specific external identities for v4 receipts.

        The ordinary observer still validates the full release, mount, container,
        socket and scheduling postconditions. These observations cover effects
        which cannot be established from desired file bytes alone.
        """
        action=step['action'];result={}
        if action in ('copy_bundle','tools','dependencies','images','configurations'):
            result['release']=identity(self.root)
        if action=='tools' and self.source['manifest'].get('tools'):
            result['tools_parent']=identity(self.root/'tools')
        if action=='dependencies':result['venv']=identity(self.root/'.venv')
        if action=='images':
            result['private_client']=identity(self.root/'offline-docker-client')
            result['client_configuration']=identity(self.root/'offline-docker-client'/'config.json')
        if action in ('images','inhibit_containers','start_paused','stop_supervisor'):
            from deploy.workload_configuration import templates
            from mldsafail.evaluator.native_workload import NativeRuntime
            result['runtime']=NativeRuntime(templates(self.source)['native']).identity()
            require(result['runtime']==self.source['host']['runtime_identity'],
                    'installation_operation_daemon_changed')
        if action in ('units','supervisor_unit','restore_units'):
            result['manager']=identity(self.source['host']['user_manager']['path'])
            names=self.proposal['units'] if action=='restore_units' else self.unit_names(action)
            loaded={};fields=('LoadState','FragmentPath','SourcePath','DropInPaths','NeedDaemonReload')
            for name in names:
                raw=self.command(['/usr/bin/systemctl','--user','show',name,'--all',
                                  '--property='+','.join(fields)]).decode()
                pairs=[line.split('=',1) for line in raw.splitlines() if '=' in line]
                require(len(pairs)==len(fields) and {key for key,value in pairs}==set(fields),
                        'installation_loaded_unit_observation_incomplete')
                row=dict(pairs)
                require(row['NeedDaemonReload']=='no','installation_unit_reload_unverified')
                expected=dict(LoadState='loaded',FragmentPath=
                    str(Path(self.source['installation']['unit_directory'])/name),SourcePath='',DropInPaths='')
                if action=='restore_units':
                    original=self.original_units(journal)[expected['FragmentPath']]
                    if original['state']=='absent':expected.update(LoadState='not-found',FragmentPath='')
                    # Preserve only previously inventoried drop-ins and the exact
                    # inhibition files this proposal deliberately leaves active.
                    from deploy.workload_schedule_v3 import unit_name
                    for identifier,owner in self.source['scheduling']['owners'].items():
                        if owner['manager']!='user' or owner['uid']!=self.source['host']['uid']:continue
                        if unit_name(identifier,owner)!=name:continue
                        reference=self.source['inventory']['execution_references'][identifier]
                        expected['FragmentPath']=reference['FragmentPath']
                        expected['LoadState']='loaded' if reference['FragmentPath'] else 'not-found'
                        expected['DropInPaths']=reference['DropInPaths']
                    inhibition=[resource['path'] for resource in self.proposal['scheduling']['resources']
                        if resource['owner_uid']==self.source['host']['uid'] and Path(resource['path']).parent.name==name+'.d']
                    expected['DropInPaths']=' '.join(sorted(set(expected['DropInPaths'].split())|set(inhibition)))
                require(all(row[key]==value for key,value in expected.items()),
                        'installation_loaded_unit_selection_changed')
                loaded[name]=row
            result['loaded_units']=loaded
        if action in ('activate','restore_activation'):
            pending=next((row for row in reversed(journal.rows) if row['event']=='intent' and row.get('step')==step['id']),None)
            require(pending is not None,'installation_activation_parent_intent_missing')
            candidates=[row['observed'] for row in journal.rows[journal.rows.index(pending)+1:]
                        if row['event']=='activation_candidate' and row.get('step_id')==step['id']]
            result['preserved_pointers']={row['path']:identity(row['path']) for row in candidates}
            for preserved in result['preserved_pointers'].values():
                require(all(preserved.get(key)==value for key,value in pending['before'].items() if key!='path'),
                        'installation_preserved_activation_changed')
        if action=='inhibit_scheduling':result['permission_gate']=identity(self.source['permission_root'])
        return result

    def apply_acknowledgements(self,step,journal):
        pending=journal.outcome(step['id'])
        if not pending or pending['event']!='intent':return []
        rows = [row for row in journal.rows[journal.rows.index(pending)+1:]
                if row['event']=='resource_acknowledgement' and row.get('step_id')==step['id']]
        if journal.recovery_protocol == 4:
            from deploy.workload_recovery_inventory import transition
            require(len(rows) <= 1, 'installation_duplicate_resource_acknowledgement')
            for row in rows:
                require(row.get('parent_intent_sha256') == digest(canonical(pending)) and
                        row.get('operation') == step['action'] and
                        row.get('resource_identity') == pending['before'] and
                        row.get('expected_transition') == transition(step),
                        'installation_resource_acknowledgement_binding_invalid')
                if hasattr(self,'recovery_observation'):
                    require(row.get('operation_observation') == self.recovery_observation(step,journal),
                            'installation_operation_postconditions_changed')
        return rows
    def acknowledge_apply(self,step,journal):
        # A whole-step resource acknowledgement is distinct from its final
        # engine outcome. Interruption after it need not discard proven births.
        observed=self.observe(step,journal)
        require(self.valid_outcome(step,observed,journal),'installation_apply_not_verified')
        binding = {}
        if journal.recovery_protocol == 4:
            from deploy.workload_recovery_inventory import transition
            pending = journal.outcome(step['id'])
            require(pending and pending['event'] == 'intent', 'installation_acknowledgement_parent_required')
            binding = dict(parent_intent_sha256=digest(canonical(pending)), operation=step['action'],
                           resource_identity=pending['before'], expected_transition=transition(step))
            if hasattr(self,'recovery_observation'):
                binding['operation_observation'] = self.recovery_observation(step,journal)
        journal.append('resource_acknowledgement',step_id=step['id'],observed=observed,**binding)
    def absent_reconcilable(self,step,value,journal):
        # Only these operations have no external effects beyond the observed
        # files. Scheduling, Docker, units and prerequisite partial progress
        # require their own reconciliation and are never replayed here.
        if self.apply_acknowledgements(step,journal):return False
        if step['action']=='snapshot' and self.snapshot_substeps(journal):return False
        pending=journal.outcome(step['id'])
        if not pending or pending['event']!='intent' or value!=pending['before']:return False
        if step['action'] in ('create_release','enable_supervisor'):
            return value.get('state')=='absent'
        if step['action']=='snapshot':
            return set(value)==set(SNAPSHOTS) and all(row.get('state')=='absent' for row in value.values())
        return False

    def reconciliation_status(self,step,value,journal,*,completed):
        if completed:return 'completed'
        acknowledgements=self.apply_acknowledgements(step,journal)
        if acknowledgements and any(row['observed']!=value for row in acknowledgements):return 'replaced'
        pending=journal.outcome(step['id'])
        if value==pending['before'] and isinstance(value,dict) and value.get('state')=='absent':
            return 'absent'
        # Distinguish acknowledged substeps from a fully reconciled operation.
        # Missing observations cannot establish replacement or safe replay.
        rows=journal.rows[journal.rows.index(pending)+1:]
        if any(row['event']=='mutation_outcome' for row in rows):return 'partially_completed'
        return 'ambiguous'

    def reconcilable(self,step,value,journal):
        acknowledgements=self.apply_acknowledgements(step,journal)
        if acknowledgements:
            return (len(acknowledgements)==1 and acknowledgements[0]['observed']==value and
                    (journal.recovery_protocol != 4 or self.valid_outcome(step,value,journal)))
        if journal.recovery_protocol == 4:
            from deploy.workload_recovery_inventory import OPERATIONS
            # Desired settings, names and bytes alone never prove ownership of
            # an unacknowledged external operation. Read-only checks can repeat.
            _, effects = OPERATIONS[step['action']]
            if all(kind == 'read_only' for _,kind in effects):
                return self.valid_outcome(step,value,journal)
            if step['action'] not in ('activate','restore_activation','restore_units'):
                return False
        # Any unacknowledged creation might belong to another operation.
        if step['action'] in ('activate','restore_activation'):
            if step['action']=='restore_activation' and not journal.outcome('install:activate'):
                return value==self.source['resources']['activation']
            candidates=[row['observed'] for row in journal.rows if row.get('event')=='activation_candidate' and row.get('step_id')==step['id']]
            pending=journal.outcome(step['id'])
            if not pending or pending.get('event')!='intent':return False
            for candidate in candidates:
                if not all(value.get(k)==candidate.get(k) for k in ('device','inode','target')):continue
                preserved=identity(candidate['path'])
                if all(preserved.get(k)==v for k,v in pending['before'].items() if k!='path'):return True
            return False
        if step['action']=='restore_units' and not journal.outcome('install:units'):
            return value==dict(skipped='units_never_replaced')
        return step['action'] in ('quiesce_supervisor','inhibit_containers','stop_supervisor','verify_release',
                                  'verify_paused','verify_cleanup','verify_rollback')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('proposal','review','authorization'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--phase',choices=('install','rollback'),required=True)
    parser.add_argument('--reconcile',action='store_true')
    args=parser.parse_args()
    raw,proposal=private(args.proposal); review,_=private(args.review); _,authority=private(args.authorization)
    backend=LinuxBackend(proposal)
    function=reconcile if args.reconcile else execute
    function(proposal,raw,review,authority,backend,phase=args.phase)


if __name__=='__main__': main()
