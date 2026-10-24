"""Finite, disabled-by-default protocol-four disposable-fixture fault hooks.

A plan can interrupt an already authorized fixture operation. It supplies no
commands, grants no execution authority, and cannot extend an attempt's budget.
The marker is exclusively created and acknowledged in the installation journal;
interruption between those writes blocks later use rather than firing again.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
import time

from deploy.workload_installation import SNAPSHOTS, exclusive, identity, private
from deploy.workload_recovery_inventory import PREREQUISITE_RESOURCES, inventory
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import require

SCHEMA = 'mldsafail.fixture-recovery-fault-plan.v4'
MARKER_SCHEMA = 'mldsafail.fixture-recovery-fault-fired.v4'
FIELDS = frozenset(('schema','fixture_only','recovery_protocol','generation','step','resource','boundary'))
BOUNDARIES = frozenset(('intent','unacknowledged','applied'))
_ACTIVE = ContextVar('workload_fixture_recovery_fault',default=None)


def resources(proposal):
    """Exact finite resource closure from the frozen installation proposal."""
    source=proposal['identities'];release=Path(source['resources']['release']['path'])
    allowed={(row['step'],'operation') for row in inventory() if row['mutation']}
    base=release/'bundle';files={base/name for name in source['manifest']['files']}|{base/'manifest.json'}
    directories={base}
    for path in files:
        directories.update(parent for parent in path.parents if parent==base or parent.is_relative_to(base))
    allowed.update(('install:copy_bundle','install:copy_bundle:'+str(path)) for path in files)
    allowed.update(('install:copy_bundle','install:copy_bundle:directory:'+str(path)) for path in directories)
    if source['manifest'].get('tools'):
        allowed.add(('install:tools','install:tools:directory:'+str(release/'tools')))
        require(set(source['manifest']['tools']) <= {'interpreter','installer'},'fixture_fault_tool_role_unsupported')
        allowed.update(('install:tools','install:tools:'+role) for role in source['manifest']['tools'])
    allowed.update(('install:snapshot','snapshot:'+name) for name in SNAPSHOTS)
    allowed.update(('install:configurations','install:configurations:'+row['path'])
                   for row in source['manifest']['configurations'].values())
    allowed.update(('install:prerequisites',resource) for resource in PREREQUISITE_RESOURCES)
    return frozenset(allowed)


def _resource_shape(step,resource):
    if resource=='operation':return True
    if step=='install:snapshot':return resource in {'snapshot:'+name for name in SNAPSHOTS}
    if step=='install:prerequisites':return resource in PREREQUISITE_RESOURCES
    if step=='install:tools' and resource in ('install:tools:interpreter','install:tools:installer'):return True
    prefixes={'install:copy_bundle':('install:copy_bundle:directory:','install:copy_bundle:'),
              'install:tools':('install:tools:directory:',),
              'install:configurations':('install:configurations:',)}
    for prefix in prefixes.get(step,()):
        if not resource.startswith(prefix):continue
        value=resource.removeprefix(prefix);path=Path(value)
        if path.is_absolute() and str(path)==value and '..' not in path.parts and str(path)!='/':return True
    return False


def validate(plan,generation,proposal=None):
    require(type(generation) is str and re.fullmatch('[a-f0-9]{32}',generation) is not None,
            'fixture_fault_generation_invalid')
    require(type(plan) is dict and set(plan)==FIELDS and plan['schema']==SCHEMA and
            plan['fixture_only'] is True and type(plan['recovery_protocol']) is int and
            plan['recovery_protocol']==4,'fixture_fault_plan_fields')
    require(plan['generation']==generation,'fixture_fault_generation_changed')
    steps={row['step'] for row in inventory() if row['mutation']}
    require(type(plan['step']) is str and plan['step'] in steps and
            type(plan['resource']) is str and 0<len(plan['resource'])<=4096 and
            not any(ord(character)<32 or ord(character)==127 for character in plan['resource']) and
            _resource_shape(plan['step'],plan['resource']) and type(plan['boundary']) is str and
            plan['boundary'] in BOUNDARIES,
            'fixture_fault_point_unsupported')
    if proposal is not None:
        require((plan['step'],plan['resource']) in resources(proposal),'fixture_fault_resource_not_in_proposal')
    return plan


def bind(plan,generation):
    """Bind a preparation-only unbound plan to a freshly created generation."""
    require(type(plan) is dict and set(plan)==FIELDS-{'generation'},'fixture_fault_unbound_plan_fields')
    return validate(dict(plan,generation=generation),generation)


class FaultInjector:
    def __init__(self,root,manifest,manifest_sha256,proposal):
        self.root=Path(root);self.manifest=manifest;self.binding=manifest_sha256;self.proposal=proposal
        selected=manifest.get('recovery_fault_plan')
        self.plan=dict(selected) if type(selected) is dict else selected
        self.marker=self.root/'recovery-fault-fired.json'
        self.root_identity=None
        if self.plan is None:return
        self.generation=manifest['generation']
        validate(self.plan,self.generation,proposal)
        raw,actual=private(self.root/'manifest.json')
        require(actual==manifest and digest(raw)==manifest_sha256 and
                manifest.get('schema')=='mldsafail.installation-fixture.v1' and
                manifest.get('fixture_only') is True,'fixture_fault_manifest_changed')
        self.root_identity=identity(self.root)
        require(self.root_identity==manifest['root'] and self.root_identity['mode']==0o700,
                'fixture_fault_namespace_changed')
        self.manifest_identity=identity(self.root/'manifest.json')
        self.plan_sha256=digest(canonical(self.plan));self.proposal_sha256=digest(canonical(proposal))
    @contextmanager
    def scope(self):
        require(_ACTIVE.get() is None,'fixture_fault_scope_nested')
        token=_ACTIVE.set(self if self.plan is not None else None)
        try:yield self
        finally:_ACTIVE.reset(token)
    def _verify_scope(self,journal):
        require(journal.recovery_protocol==4,'fixture_fault_protocol_four_required')
        require(journal.binding==self.proposal_sha256,'fixture_fault_journal_proposal_changed')
        require(identity(self.root)==self.root_identity,'fixture_fault_namespace_changed')
        require(identity(self.root/'manifest.json')==self.manifest_identity,'fixture_fault_manifest_changed')
        require(digest(canonical(self.plan))==self.plan_sha256,'fixture_fault_plan_changed')
    def _verified_marker(self,journal):
        self._verify_scope(journal)
        if not self.marker.exists() and not self.marker.is_symlink():return None
        raw,value=private(self.marker)
        require(set(value)=={'schema','fixture_only','generation','manifest_sha256','proposal_sha256','plan',
                'plan_sha256','root','parent_intent_sha256','mutation_intent_sha256','monotonic_ns'} and
                type(value.get('monotonic_ns')) is int and value['monotonic_ns']>0 and
                value.get('schema')==MARKER_SCHEMA and value.get('fixture_only') is True and
                value.get('generation')==self.generation and value.get('manifest_sha256')==self.binding and
                value.get('proposal_sha256')==self.proposal_sha256 and value.get('plan')==self.plan and
                value.get('plan_sha256')==self.plan_sha256 and value.get('root')==self.root_identity and
                canonical(value)==raw,'fixture_fault_marker_changed')
        parent=next((row for row in journal.rows if row['event']=='intent' and
                     digest(canonical(row))==value['parent_intent_sha256']),None)
        require(parent is not None and parent.get('step')==self.plan['step'],'fixture_fault_marker_parent_changed')
        if self.plan['resource']=='operation':
            require(value['mutation_intent_sha256'] is None,'fixture_fault_marker_mutation_changed')
        else:
            mutation=next((row for row in journal.rows if row['event']=='mutation_intent' and
                           digest(canonical(row))==value['mutation_intent_sha256']),None)
            require(mutation is not None and mutation.get('resource')==self.plan['resource'] and
                    mutation.get('step_id')==self.plan['step'] and
                    mutation.get('parent_intent_sha256')==value['parent_intent_sha256'],
                    'fixture_fault_marker_mutation_changed')
        rows=[row for row in journal.rows if row['event']=='fixture_recovery_fault_fired']
        require(len(rows)==1 and rows[0].get('observed')==identity(self.marker) and
                rows[0].get('plan_sha256')==self.plan_sha256 and
                rows[0].get('parent_intent_sha256')==value.get('parent_intent_sha256') and
                rows[0].get('mutation_intent_sha256')==value.get('mutation_intent_sha256'),
                'fixture_fault_marker_unacknowledged_or_replaced')
        return value
    def fire(self,journal,step,resource,boundary):
        if self.plan is None:return False
        # Check consumed marker integrity even on later nonmatching callbacks.
        if self._verified_marker(journal) is not None:return False
        if (step,resource,boundary)!=(self.plan['step'],self.plan['resource'],self.plan['boundary']):return False
        pending=next((row for row in reversed(journal.rows) if row['event']=='intent' and row.get('step')==step),None)
        require(pending is not None,'fixture_fault_parent_intent_required')
        mutation=None
        if resource!='operation':
            mutation=next((row for row in reversed(journal.rows) if row['event']=='mutation_intent' and
                           row.get('step_id')==step and row.get('resource')==resource),None)
            require(mutation is not None and mutation.get('parent_intent_sha256')==digest(canonical(pending)),
                    'fixture_fault_mutation_intent_required')
        parent=digest(canonical(pending));mutation_hash=digest(canonical(mutation)) if mutation else None
        value=dict(schema=MARKER_SCHEMA,fixture_only=True,generation=self.generation,manifest_sha256=self.binding,
            proposal_sha256=self.proposal_sha256,plan=self.plan,plan_sha256=self.plan_sha256,root=self.root_identity,
            parent_intent_sha256=parent,mutation_intent_sha256=mutation_hash,monotonic_ns=time.monotonic_ns())
        exclusive(self.marker,canonical(value))
        journal.append('fixture_recovery_fault_fired',observed=identity(self.marker),plan_sha256=self.plan_sha256,
                       parent_intent_sha256=parent,mutation_intent_sha256=mutation_hash)
        raise InterruptedError('disposable_fixture_recovery_fault:'+step+':'+resource+':'+boundary)
    def operation(self,journal,step,boundary):
        if boundary not in BOUNDARIES:return False
        return self.fire(journal,step,'operation',boundary)
    def assert_fired(self,journal):
        if self.plan is None:return
        require(self._verified_marker(journal) is not None,'fixture_fault_target_not_reached')


def dispatch_mutation(journal,resource,point):
    """Called only at existing durable mutation boundaries; no active default."""
    injector=_ACTIVE.get()
    if injector is None:return
    step=next((row.get('step_id') for row in reversed(journal.rows)
               if row['event']=='mutation_intent' and row.get('resource')==resource),None)
    require(step is not None,'fixture_fault_mutation_intent_required')
    boundary={'intent':'intent','applied':'unacknowledged','outcome':'applied'}[point]
    injector.fire(journal,step,resource,boundary)
