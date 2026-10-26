"""Live, owner-claimed installed-native contexts for fixed control stages.

A context manifest grants nothing. Every operation rechecks its independently
supervised stage ancestry, consumed owner claim, exact protocol and frozen source.
Historical local/VM receipts cannot be imported or promoted into this context.
"""
import copy
import json
import os
from pathlib import Path
import re
import socket
import sys
import time

from deploy.workload_acceptance_packet import load_reference,reference,validate
from deploy.workload_installation import Journal,exclusive,identity,private,sync_directory
from deploy.workload_release import canonical,digest,verify
from deploy.workload_native_supervision import SCHEMA as SUPERVISION,STAGE,BIRTH
from mldsafail.evaluator.native_workload import process_birth,require,private_json
from scripts.workload_installation_fixture import Fixture,lifecycle_lock

SCHEMA='mldsafail.workload-native-context.v1'
CAPS={'startup':30,'case':90,'cleanup':45,'postflight':15}
SETTING_FIELDS={'generation','watchdog_root','postgres_image','control','scenario','case_output','facts','global_hold','attempt_generation'}


def _path(value):
    path=Path(value)
    require(path.is_absolute() and '..' not in path.parts and
        not any(item.is_symlink() for item in (path,*path.parents)),'native_context_path_invalid')
    return path


def _ref(row):
    require(type(row) is dict and set(row)=={'path','sha256'},'native_context_reference_invalid')
    _path(row['path']);return load_reference(row)


def settings(packet):
    row=packet['protocol']['identities'].get('native_context')
    require(type(row) is dict and SETTING_FIELDS<=set(row)<=SETTING_FIELDS|{'execution_mode_fact'} and
        re.fullmatch('[a-f0-9]{32}',row.get('generation','')) and
        re.fullmatch('[a-f0-9]{32}',row.get('attempt_generation','')) and
        re.fullmatch('sha256:[a-f0-9]{64}',row.get('postgres_image','')),'native_context_settings_invalid')
    root=_path(row['watchdog_root']);output=_path(row['case_output'])
    require(output==root/'context/artifacts'/('case-'+row['generation']+'.json'),'native_context_output_outside_watchdog')
    from deploy.workload_control_registry import get_runner
    get_runner(row['control'],row['scenario'])
    require(len(packet['protocol']['cases'])==1,'native_context_one_case_required')
    return row


def _ancestry():
    result=[];pid=os.getpid()
    for _ in range(64):
        observed=process_birth(pid);result.append(observed)
        if pid<=1:break
        text=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
        require(process_birth(pid)==observed,'native_context_ancestor_replaced')
        parent=int(text[1]);require(parent!=pid,'native_context_ancestor_cycle')
        pid=parent
    return result


def verify_supervision(packet,watchdog_root,*,allowed_stage=None):
    """Observe proof only; never claim authority or launch a command."""
    # Freshness is established by startup before any hold/effect. Later stages
    # retain that exact inspection while the live claimed packet authorizes
    # identity-checked cleanup across its observation-age boundary.
    inspection=_ref(packet['inspection'])
    validate(packet,now=inspection['captured_at'])
    require(sys.platform=='linux' and packet['stage']=='installed' and
        packet['protocol']['origin']=='installed_native','native_context_installed_origin_required')
    spec=settings(packet);root=_path(watchdog_root)
    require(str(root)==spec['watchdog_root'],'native_context_watchdog_root_changed')
    source=_ref(packet['proposal'])['identities'];facts=_ref(spec['facts'])
    require(spec['global_hold']==dict(state='proposed',path=source['installation']['gate_root']+'/native-control-hold.json',
        creation='exclusive',precondition='absent',effect='deny_admission_only'),'native_context_hold_proposal_changed')
    require(facts.get('schema')=='mldsafail.native-control-packet-facts.v1' and facts.get('origin')=='host_observation' and
        facts.get('postgres_image')==spec['postgres_image'] and facts.get('authority_journal')==packet['protocol']['identities']['authority_journal'] and
        facts.get('host')=={key:source['host'][key] for key in ('hostname','uid','boot_id')},'native_context_facts_changed')
    protocol=packet['protocol'];binding=digest(canonical(protocol))
    raw,proof=private(root/'native-supervision.json')
    require(proof.get('schema')==SUPERVISION and proof.get('origin')=='installed_native' and
        proof.get('protocol_sha256')==binding and proof.get('root')==identity(root),
        'native_context_supervision_changed')
    require(type(proof.get('created_monotonic')) in (int,float) and type(proof.get('deadline_monotonic')) in (int,float) and
        0<proof['deadline_monotonic']-proof['created_monotonic']<=180 and
        proof['created_monotonic']<=time.monotonic()<proof['deadline_monotonic'],'native_context_supervision_expired')
    from deploy.workload_native_attempt import verify as verify_attempt
    require(type(proof.get('attempt')) is dict,'native_context_attempt_missing')
    attempt_deadline=verify_attempt(protocol,proof['attempt'])
    require(proof['deadline_monotonic']<=attempt_deadline,'native_context_attempt_budget_extended')
    host=protocol['identities']
    require(host.get('hostname')==socket.gethostname() and host.get('uid')==os.getuid() and
        host.get('boot_id')==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'native_context_host_changed')
    review=_ref(proof['review']);authority=_ref(proof['authorization'])
    require(review.get('decision')=='approved' and review.get('protocol_sha256')==binding and
        review.get('implemented_by') and review.get('reviewed_by') and review['implemented_by']!=review['reviewed_by'],
        'native_context_independent_review_missing')
    now=time.time()
    require(authority.get('schema')=='mldsafail.workload-native-authority.v3' and
        authority.get('purpose')=='native_workload_control_only' and authority.get('authorized_by')=='owner' and
        authority.get('protocol_sha256')==binding and authority.get('review_sha256')==proof['review']['sha256'] and
        type(authority.get('issued_at')) in (int,float) and type(authority.get('expires_at')) in (int,float) and
        authority['issued_at']<=now<authority['expires_at'] and 0<authority['expires_at']-authority['issued_at']<=180 and
        type(authority.get('nonce')) is str and re.fullmatch('[a-f0-9]{32}',authority['nonce']),
        'native_context_owner_authority_missing')
    claim=proof.get('claim',{});journal=host.get('authority_journal',{})
    require(identity(journal['path'])==journal and root.parent==Path(journal['path']) and
        claim.get('path')==str(root.parent/('native-authority-'+proof['authorization']['sha256']+'.consumed')) and
        identity(claim['path'])==claim,'native_context_consumed_claim_changed')
    consumed=private(claim['path'])[1]
    require(consumed.get('schema')=='mldsafail.native-authorization-intent.v3' and
        consumed.get('authorization_sha256')==proof['authorization']['sha256'] and consumed.get('protocol')==protocol and
        consumed.get('disposition')=='claimed_requires_final_receipt_or_reconciliation',
        'native_context_consumed_claim_missing')
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    require(all(name in source['manifest']['files'] for name in REVIEW_FILES),'native_context_review_source_missing')
    expected={name:source['manifest']['files'][name]['sha256'] for name in REVIEW_FILES}
    require(all(review.get('source_sha256',{}).get(name)==value for name,value in expected.items()) and
        proof.get('watchdog_source_sha256')==source['manifest']['files']['deploy/workload_watchdog.py']['sha256'],
        'native_context_review_source_changed')
    ancestors=_ancestry()
    require(proof['watchdog'] in ancestors and process_birth(proof['watchdog']['pid'])==proof['watchdog'],
        'native_context_watchdog_not_live_ancestor')
    rows=[protocol['startup'],*protocol['cases'],protocol['cleanup'],protocol['postflight']]
    kinds=['startup',*['case']*len(protocol['cases']),'cleanup','postflight']
    require(len(proof.get('stages',[]))==len(rows),'native_context_stage_inventory_changed')
    current=[];proof_sha=digest(raw)
    for index,(stage,row,kind) in enumerate(zip(proof['stages'],rows,kinds)):
        require(stage==dict(index=index,kind=kind,name=row['name'],intent_path=str(root/f'native-stage-{index}.json'),
            birth_path=str(root/f'native-stage-{index}-birth.json')),'native_context_stage_inventory_changed')
        if not Path(stage['intent_path']).exists():continue
        intent_raw,intent=private(stage['intent_path'])
        require(intent.get('schema')==STAGE and intent.get('supervision_sha256')==proof_sha and
            intent.get('protocol_sha256')==binding and intent.get('index')==index and intent.get('kind')==kind and
            intent.get('name')==row['name'] and intent.get('argv_sha256')==digest(canonical(row['argv'])) and
            type(intent.get('started_monotonic')) in (int,float) and type(intent.get('deadline_monotonic')) in (int,float) and
            0<intent['deadline_monotonic']-intent['started_monotonic']<=min(CAPS[kind],row['seconds']) and
            intent['deadline_monotonic']<=proof['deadline_monotonic'],'native_context_stage_binding_changed')
        # The supervisor publishes the inspected child birth immediately after
        # Popen. A bounded handoff wait never extends this stage's allowance.
        handoff=min(time.monotonic()+.25,intent['deadline_monotonic'])
        while allowed_stage==kind and not Path(stage['birth_path']).exists() and time.monotonic()<handoff:time.sleep(.005)
        if not Path(stage['birth_path']).exists():continue
        child=private(stage['birth_path'])[1]
        require(child.get('schema')==BIRTH and child.get('supervision_sha256')==proof_sha and
            child.get('intent_sha256')==digest(intent_raw),'native_context_stage_birth_changed')
        if child.get('process') not in ancestors:continue
        require(process_birth(child['process']['pid'])==child['process'],'native_context_stage_process_replaced')
        require(intent['started_monotonic']<=time.monotonic()<intent['deadline_monotonic'],'native_context_stage_expired')
        current.append((kind,intent,child))
    require(len(current)==1 and (allowed_stage is None or current[0][0]==allowed_stage),
        'native_context_current_stage_missing')
    return dict(proof=proof,proof_sha256=proof_sha,review=review,stage=current[0][0],
        intent=current[0][1],child=current[0][2],source=source)


class NativeContext(Fixture):
    """Fixed native stages; VM lifecycle/installation methods are not authority."""
    def __init__(self,root):
        self.root=_path(root);raw,self.manifest=private(self.root/'manifest.json');self.binding=digest(raw);self.lock_fd=None
        require(self.manifest.get('schema')==SCHEMA and self.manifest.get('origin')=='installed_native' and
            self.manifest.get('root')==identity(self.root),'native_context_manifest_changed')
        self.packet=_ref(self.manifest['packet']);self.settings=settings(self.packet)
        require(self.root==Path(self.settings['watchdog_root'])/'context' and
            self.manifest.get('generation')==self.settings['generation'],'native_context_generation_changed')
        self.inspection=_ref(self.packet['inspection']);self.source=_ref(self.packet['proposal'])['identities']
        self.native_configuration=private(self.source['manifest']['configurations']['native']['path'])[1]
        self.stage=None;self._proof=None
        self.require_target()
        self.journal=self._lifecycle();self.lifecycle_journal=self.journal
        require(set(self.manifest['directories'])=={'inputs','artifacts','journal','runtime-journal'} and
            self.manifest['root'].get('uid')==os.getuid() and self.manifest['root'].get('mode')==0o700,
            'native_context_private_directories_required')
        for name,observed in self.manifest['directories'].items():
            require(identity(self.root/name)==observed and observed.get('uid')==os.getuid() and observed.get('mode')==0o700,
                'native_context_directory_changed')
        self.startup_complete=(self.root/'startup.json').exists()
        if self.stage=='case':require(self.startup_complete,'native_context_startup_missing_or_changed')
        if self.startup_complete:
            startup=private(self.root/'startup.json')[1]
            acknowledgements=[row for row in self.lifecycle_journal.rows if row['event']=='native_context_startup']
            require(len(acknowledgements)==1 and acknowledgements[0]['observed']==identity(self.root/'startup.json') and
                startup.get('supervision_sha256')==self._proof['proof_sha256'] and
                startup.get('baseline')==identity(self.root/'baseline.json'),'native_context_startup_missing_or_changed')

    def _lifecycle(self):
        if self.stage in ('cleanup','postflight'):
            from deploy.workload_fixture_control_cleanup import recovery_journal
            return recovery_journal(self.root/'journal',self.binding,self.manifest['generation'],native_lifecycle=True)
        return Journal(self.root/'journal',self.binding)

    def verify_supervisor_transition(self,record,observed):
        for name,expected_hash in self.inspection['units'].items():
            actual=identity(Path(self.source['installation']['unit_directory'])/name)
            require(actual.get('sha256')==expected_hash and actual.get('uid')==self.source['host']['uid'] and
                actual.get('mode')==0o600,'native_context_supervisor_unit_changed')
        expected={key:self.inspection['supervisor'][key] for key in ('pid','start_ticks')}
        socket_expected=self.inspection['resources']['socket']
        old_matches=record['process']==expected and all(observed.get(key)==socket_expected[key]
            for key in ('path','device','inode'))
        if old_matches:return
        require((self.settings['control'],self.settings['scenario'])==('persistent_pause','supervisor_sigkill'),
            'native_context_unexpected_supervisor_replacement')
        case=self.root/'artifacts'/('control-'+self.manifest['generation'])
        from deploy.workload_fixture_control_cleanup import _evidence
        evidence=_evidence(case,self.binding)
        rows=[row for row in evidence.rows if row['event']=='control_supervisor_replacement']
        require(evidence.complete and len(rows)==1 and rows[0]['before']['process']==expected and
            all(rows[0]['before'].get(key)==socket_expected[key] for key in ('path','device','inode')) and
            rows[0]['after']['process']==record['process'] and
            all(rows[0]['after'].get(key)==observed.get(key) for key in ('path','device','inode')),
            'native_context_supervisor_replacement_unacknowledged')
        name='mldsafail-workload-supervisor.service';unit=Path(self.source['installation']['unit_directory'])/name
        actual=identity(unit)
        require(actual.get('sha256')==self.inspection['units'][name] and actual.get('uid')==self.source['host']['uid'] and
            actual.get('mode')==0o600,'native_context_supervisor_unit_changed')

    def cleanup_barrier(self):
        self.require_target();self._held();self._global_paused()

    @property
    def baseline_capture_allowed(self):return self.stage=='startup'

    def require_target(self):
        proof=verify_supervision(self.packet,self.settings['watchdog_root'],allowed_stage=self.stage)
        self.stage=proof['stage'];self._proof=proof;self.stage_deadline=proof['intent']['deadline_monotonic']
        require(self.manifest.get('supervision_sha256')==proof['proof_sha256'],'native_context_supervision_changed')
        source_root=Path(self.manifest['source_root'])
        require(source_root==Path(self.source['resources']['release']['path'])/'bundle' and
            Path(__file__).resolve()==source_root/'deploy/workload_native_context.py','native_context_executing_source_changed')
        expected_sources={name:row['sha256'] for name,row in self.source['manifest']['files'].items()
            if name.startswith(('deploy/','scripts/','src/')) and name.endswith('.py')}
        require(self.manifest['source_hashes']==expected_sources and self.manifest.get('global_hold')==self.settings['global_hold'],
            'native_context_source_or_hold_inventory_changed')
        for name,expected in expected_sources.items():
            require(digest((source_root/name).read_bytes())==expected,'native_context_frozen_source_changed')

    def component_review(self):
        self.require_target();return self._proof['review']

    def proposal(self):
        raw,value=private(self.packet['proposal']['path'])
        require(digest(raw)==self.packet['proposal']['sha256'] and value['identities']==self.source,
            'native_context_proposal_changed')
        return raw,value

    def deadline(self,*,cleanup=False):
        self.require_target();remaining=min(self.stage_deadline,self._proof['proof']['deadline_monotonic'])-time.monotonic()
        require(remaining>0,'native_context_stage_expired');return remaining

    def _selection(self,control,scenario,output,stage):
        self.require_target()
        require(self.stage==stage and (control,scenario,str(Path(output).absolute()))==
            (self.settings['control'],self.settings['scenario'],self.settings['case_output']),
            'native_context_selection_changed')

    def command(self,argv,*,cleanup=False,seconds=300):
        self.require_target()
        if self.stage=='case':self._held()
        return super().command(argv,cleanup=cleanup,seconds=min(seconds,self.deadline(cleanup=cleanup)))

    def require_operation(self,operation,phase):
        self.require_target()
        expected={'case':('control',self.settings['control']+':'+self.settings['scenario']),
            'cleanup':('control-cleanup',self.settings['control']+':'+self.settings['scenario']+':'+self.manifest['generation']),
            'postflight':('control-postflight',self.settings['control']+':'+self.settings['scenario']+':'+self.manifest['generation'])}
        require(expected.get(self.stage)==(operation,phase),'native_context_worker_not_allowlisted')

    def worker(self,operation,**kwargs):
        self.require_target()
        self.require_operation(operation,kwargs.get('phase','install'))
        return super().worker(operation,**kwargs)

    def adapter(self,*args,**kwargs):require(False,'native_context_installation_not_authorized')
    def engine(self,*args,**kwargs):require(False,'native_context_installation_not_authorized')
    def transition(self,*args,**kwargs):require(False,'native_context_installation_not_authorized')
    def control(self,*args,**kwargs):require(False,'native_context_use_independent_native_stages')

    @classmethod
    def from_root(cls,root):return cls(root)

    @classmethod
    def open(cls,packet_path,*,stage):
        _,packet=private(packet_path);spec=settings(packet)
        proof=verify_supervision(packet,spec['watchdog_root'],allowed_stage=stage)
        context=cls(Path(spec['watchdog_root'])/'context')
        require(context.packet==packet and context.manifest['packet']==reference(packet_path) and context._proof['proof_sha256']==proof['proof_sha256'],
            'native_context_packet_changed')
        return context

    @classmethod
    def startup(cls,packet_path,watchdog_root,*,observation):
        _,packet=private(packet_path);validate(packet)
        proof=verify_supervision(packet,watchdog_root,allowed_stage='startup')
        bound=_ref(packet['inspection']);fresh=dict(observation);expected=dict(bound)
        fresh.pop('captured_at',None);expected.pop('captured_at',None)
        require(fresh==expected,'native_context_fresh_inspection_changed')
        spec=settings(packet);source=proof['source'];root=Path(watchdog_root)/'context';root.mkdir(mode=0o700)
        directories={}
        for name in ('inputs','artifacts','journal','runtime-journal'):
            (root/name).mkdir(mode=0o700);directories[name]=identity(root/name)
        files=source['manifest']['files'];source_hashes={name:row['sha256'] for name,row in files.items()
            if name.startswith(('deploy/','scripts/','src/')) and name.endswith('.py')}
        inputs={}
        if 'execution_mode_fact' in spec:
            _ref(spec['execution_mode_fact']);raw_fact=private(spec['execution_mode_fact']['path'],parse=False)[0]
            path=root/'inputs/native_execution_fact';exclusive(path,raw_fact);inputs['native_execution_fact']=identity(path)
        manifest=dict(schema=SCHEMA,origin='installed_native',fixture_only=False,generation=spec['generation'],
            root=identity(root),directories=directories,source_root=str(Path(source['resources']['release']['path'])/'bundle'),
            source_hashes=source_hashes,inputs=inputs,global_hold=spec['global_hold'],packet=reference(packet_path),supervision_sha256=proof['proof_sha256'],
            execution_authority=False,authority='live_exact_watchdog_stage_and_consumed_owner_claim_only')
        exclusive(root/'manifest.json',canonical(manifest));context=cls(root)
        from deploy.workload_native_resources import NativeResources
        resources=NativeResources(context)
        from deploy.workload_installed import observation_runner
        context._take_global_hold()
        with observation_runner(resources.run):baseline=resources.postflight(context.proposal()[1])
        startup=dict(supervision_sha256=proof['proof_sha256'],inspection=packet['inspection'],
            baseline=identity(root/'baseline.json'),global_hold=context._hold_identity())
        exclusive(root/'startup.json',canonical(startup));context.journal.append('native_context_startup',observed=identity(root/'startup.json'))
        return context

    def _hold_path(self):return Path(self.native_configuration['root'])/'native-control-hold.json'
    def _hold_identity(self):return identity(self._hold_path())

    def _take_global_hold(self):
        self.require_target();path=self._hold_path()
        value=dict(schema='mldsafail.native-control-denial-hold.v1',context=str(self.root),generation=self.manifest['generation'],
            protocol_sha256=self._proof['proof']['protocol_sha256'],supervision_sha256=self._proof['proof_sha256'])
        exclusive(path,canonical(value));observed=identity(path)
        self.journal.append('native_control_global_hold',observed=observed,binding=value)
        self._global_paused()

    def _global_paused(self):
        from mldsafail.evaluator.workload_client import WorkloadClient
        state=WorkloadClient(self.source['resources']['socket']['path'],self.root/'global-status-client').status()
        require(state and state['paused'] is True and state['phase'] in ('cleaned','complete') and
            all(type(state.get(key)) is int and state[key]==0 for key in ('inflight_launches','inflight_resumes')) and
            type(state.get('request_counts')) is dict and type(state['request_counts'].get('intent')) is int and
            state['request_counts']['intent']==0,'native_context_global_gate_not_quiescent')
        return state

    def _held(self):
        rows=[row for row in self.lifecycle_journal.rows if row['event']=='native_control_global_hold']
        require(len(rows)==1 and self._hold_identity()==rows[0]['observed'],'native_context_global_hold_changed')
        return rows[0]

    def run_case(self,control,scenario,output):
        self._selection(control,scenario,output,'case')
        with lifecycle_lock(self.root) as fd:
            self.lock_fd=fd;self.journal.reload();self._held();self._global_paused()
            require(not any(row['event']=='fixture_control_requested' for row in self.journal.rows),'native_context_case_already_attempted')
            intent=dict(schema='mldsafail.native-control-case-intent.v1',generation=self.manifest['generation'],
                control=control,scenario=scenario,supervision_sha256=self._proof['proof_sha256'],
                protocol_sha256=self._proof['proof']['protocol_sha256'],stage_intent_sha256=digest(canonical(self._proof['intent'])))
            exclusive(output,canonical(intent));self.journal.append('native_control_case_output',observed=identity(output),binding=intent)
            self.journal.append('fixture_control_requested',control=control,scenario=scenario,
                generation=self.manifest['generation'],started_monotonic=self._proof['intent']['started_monotonic'],
                packet_deadline=self._proof['proof']['deadline_monotonic'],native_stage=True)
            result=self.worker('control',seconds=min(90,self.deadline()),phase=control+':'+scenario,token=self.manifest['generation'])
            worker_path=self.root/'artifacts'/('worker-'+self.manifest['generation']+'.json')
            _,wrapped=private(worker_path)
            completed=[row for row in self.journal.rows if row['event']=='fixture_worker_complete' and row.get('token')==self.manifest['generation']]
            require(len(completed)==1 and completed[0]['observed']==identity(worker_path) and
                wrapped.get('generation')==self.manifest['generation'] and wrapped.get('token')==self.manifest['generation'] and
                wrapped.get('operation')=='control' and wrapped.get('result')==result,'native_context_fresh_worker_receipt_changed')
            self.require_target();self._held()
            receipt=dict(schema='mldsafail.native-control-case-observation.v1',origin='installed_native',case_observed=True,
                accepted=False,supervision_sha256=self._proof['proof_sha256'],generation=self.manifest['generation'],
                control=control,scenario=scenario,worker=identity(worker_path),receipt=result)
            exclusive(Path(output).with_name(Path(output).name+'.result.json'),canonical(receipt))
            return receipt

    def cleanup_case(self,control,scenario,output):
        self._selection(control,scenario,output,'cleanup')
        with lifecycle_lock(self.root) as fd:
            self.lock_fd=fd
            if hasattr(self.journal,'reload'):self.journal.reload()
            return self.worker('control-cleanup',cleanup=True,seconds=min(45,self.deadline()),
                phase=control+':'+scenario+':'+self.manifest['generation'])

    def postflight_case(self,control,scenario,output):
        self._selection(control,scenario,output,'postflight')
        with lifecycle_lock(self.root) as fd:
            self.lock_fd=fd
            if hasattr(self.journal,'reload'):self.journal.reload()
            self._held()
            result=self.worker('control-postflight',cleanup=True,seconds=min(15,self.deadline()),
                phase=control+':'+scenario+':'+self.manifest['generation'])
            require(result.get('verified') is True and result.get('transactions')=='resolved','native_context_postflight_unresolved')
            self._global_paused();hold=self._held();self.require_target()
            require(self._hold_identity()==hold['observed'],'native_context_global_hold_changed')
            self._hold_path().unlink();sync_directory(self._hold_path().parent);self.journal.append('native_control_global_hold_released',observed=hold['observed'])
            return dict(schema='mldsafail.workload-control-postflight.v3',origin='installed_native',
                identities_sha256=digest(canonical(self.packet['protocol']['identities'])),paused=True,owned_resources=0,
                transactions='resolved',retained_before=result['retained_before']['retained_services'],
                retained_after=result['retained_after']['retained_services'])
