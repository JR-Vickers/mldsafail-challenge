"""Deterministic sanitized launch snapshots; this tool cannot approve activation."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from scripts import launch_ledger

HEX=re.compile(r'(?:sha256:)?[0-9a-f]{7,64}$')
PRIVATE_LOCATION=re.compile(r'(?<![\w])(?:/(?:Users|home|srv|root|private|tmp|var|etc)/[^\s,;]+|[A-Za-z]:\\[^\s,;]+)')
IPV6=re.compile(r'(?<![a-zA-Z0-9])(?:[a-fA-F0-9]{0,4}:){2,}[a-fA-F0-9:.]*')
IPV4=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
URL_AUTHORITY=re.compile(r'\b(?:https?|ssh|postgresql(?:\+\w+)?|s3)://[^\s]+')
NEGATIVE=re.compile(r'fail|partial|interrupt|timeout|lost|incomplete|error',re.I)


def clean_text(value):
    if not isinstance(value,str):return ''
    value=PRIVATE_LOCATION.sub('[protected location]',value)
    value=IPV4.sub('[protected address]',value)
    value=IPV6.sub('[protected address]',value)
    return URL_AUTHORITY.sub('[protected endpoint]',value)


def reference(value):
    if not isinstance(value,str):return None
    path=value.split('#',1)[0]
    parts=Path(path).parts
    if not path.startswith('docs/') or any(part in {'.','..'} for part in parts) or '\\' in value:
        return None
    if PRIVATE_LOCATION.search(value) or IPV4.search(value) or URL_AUTHORITY.search(value):return None
    return value


def evidence_kind(root,ref):
    """Native means an explicit native attestation, never an environment name."""
    if not ref or not ref.split('#',1)[0].endswith('.json'):return 'unclassified'
    document=json.loads((root/ref.split('#',1)[0]).read_text())
    value=document;ancestors=[document]
    pointer=ref.split('#',1)[1] if '#' in ref else ''
    for part in pointer.split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if isinstance(value,list) else value[part]
        ancestors.append(value)
    dictionaries=[item for item in ancestors if isinstance(item,dict)]
    leaf=pointer.rsplit('/',1)[-1] if pointer else ''
    scope=dictionaries[-1] if dictionaries else {}
    source_outcome=lambda item:isinstance(item,str) and bool(re.search('source_review|source_and_local|isolated_source',item))
    if (leaf in {'source_review_passed','source_work_completed','make_check_passed','local_tests_passed'}
            or source_outcome(value) or source_outcome(scope.get('status'))):
        return 'source_review_or_local'
    if any(item.get('native_executed') is True for item in dictionaries) and not any(item.get('native_executed') is False for item in dictionaries):
        return 'native_attested'
    if (isinstance(value,str) and 'source' in value or
        any(any(item.get(key) is True for key in ('source_review_passed','source_work_completed','make_check_passed','local_tests_passed')) for item in dictionaries)):
        return 'source_review_or_local'
    return 'unclassified'


def safe_identities(value):
    result={}
    if not isinstance(value,dict):return result
    for key,item in sorted(value.items()):
        if not isinstance(key,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,80}',key):continue
        if 'epoch' in key.lower() and not any(word in key.lower() for word in ('sha256','fingerprint')):continue
        if not re.search(r'source|commit|sha256|fingerprint|image|worker|release|artifact',key,re.I):continue
        if isinstance(item,str) and HEX.fullmatch(item):result[key]=item
        elif isinstance(item,dict):
            nested=safe_identities(item)
            if nested:result[key]=nested
    return result


def build_packet(report,*,root,source_commit,ledger_sha256,source_tree_clean=False,state_reference=None,final=False):
    root=Path(root)
    errors=launch_ledger.validate(report,root)
    if errors:raise ValueError('Canonical ledger validation failed ('+str(len(errors))+' errors)')
    if not re.fullmatch('[0-9a-f]{40}',source_commit) or not re.fullmatch('[0-9a-f]{64}',ledger_sha256):
        raise ValueError('Full source and ledger byte identities required')
    if any(not isinstance(task['id'],str) or not re.fullmatch('[a-z][a-z0-9_-]{0,200}',task['id']) for task in report['tasks']):
        raise ValueError('Stable non-infrastructure task IDs required')
    tasks={task['id']:task for task in report['tasks']};dependants={name:[] for name in tasks}
    for name,task in tasks.items():
        for dependency in task['dependencies']:dependants[dependency].append(name)
    def descendants(name):
        found=set();pending=list(dependants[name])
        while pending:
            child=pending.pop()
            if child not in found:found.add(child);pending.extend(dependants[child])
        return sorted(found)
    root_cache={}
    def unresolved_roots(name):
        if name in root_cache:return root_cache[name]
        task=tasks[name]
        if task['status']=='passed':result=set()
        else:
            result=set().union(*(unresolved_roots(dep) for dep in task['dependencies'])) if task['dependencies'] else set()
            if task['status']=='blocked_external' or not result:result.add(name)
        root_cache[name]=result;return result
    internal_roots=set()
    for name in tasks:
        internal_roots.update(root_id for root_id in unresolved_roots(name) if tasks[root_id]['status']!='blocked_external')
    internal_roots.update(name for name,task in tasks.items() if task['status'] in {'running','failed'})
    unfinished=sorted(internal_roots)
    external=[];completed=[];attempts=[];state_refs=[];artifacts=[]
    for name,task in sorted(tasks.items()):
        refs=sorted({item for item in (reference(row.get('reference')) for row in task['evidence']) if item})
        if task['status']=='passed':
            classified=[{'reference':ref,'kind':evidence_kind(root,ref)} for ref in refs]
            kinds={row['kind'] for row in classified}
            completed.append(dict(id=name,requirement=clean_text(task['requirement']),evidence=classified,
                kind=next(iter(kinds)) if len(kinds)==1 else 'mixed' if kinds else 'unclassified',
                identities=safe_identities(task['identities'])))
            if re.search('cleanup|maintenance|staging-acceptance|health|rollback',name):
                state_refs.append(dict(task_id=name,evidence_refs=refs))
        if task['identities']:artifacts.append(dict(task_id=name,identities=safe_identities(task['identities']),evidence_refs=refs))
        if task['status']=='blocked_external':
            blocker=task['blocker']
            external.append(dict(task_id=name,input=clean_text(blocker['input']),owner=clean_text(blocker['owner']),
                requested_action=clean_text(blocker['requested_action']),blocked_descendants=descendants(name)))
        for index,row in enumerate(task['attempts']):
            text=clean_text(str(row.get('result',row.get('status','Recorded attempt; inspect referenced evidence'))))
            attempt_refs=sorted({ref for ref in (reference(row.get(key)) for key in ('evidence','reference','evidence_reference','historical_evidence_reference')) if ref})
            attempts.append(dict(task_id=name,attempt_index=index,result=text,evidence_refs=attempt_refs,
                failed_or_partial=bool(NEGATIVE.search(text)) or row.get('passed') is False,
                identities=safe_identities(row)))
    mappings=sorted(number for task in tasks.values() for number in task['checklist'])
    mapping_complete=(mappings==list(range(1,79)) and report.get('checklist_source',{}).get('status')=='available'
        and report.get('checklist_source',{}).get('expected_entries')==78)
    state_attested=False;state_identity=None
    if state_reference:
        state_ref=reference(state_reference)
        if not state_ref or '#' in state_ref or not state_ref.endswith('.json'):
            raise ValueError('Sanitized JSON state evidence reference required')
        state_bytes=(root/state_ref).read_bytes();state=json.loads(state_bytes)
        # Do not copy private telemetry into the packet. A final operator record
        # must independently attest both cleanup and live state, not source tests.
        state_errors=launch_ledger.validate(dict(tasks=[],checklist_source={'status':'blocked_external'},state_record=state))
        if state_errors:raise ValueError('State evidence must already be sanitized')
        state_refs_checked=[]
        for item in state.get('evidence_refs',[]):
            safe=reference(item)
            if safe and safe.split('#',1)[0].endswith('.json'):
                value=json.loads((root/safe.split('#',1)[0]).read_text())
                pointer=safe.split('#',1)[1] if '#' in safe else ''
                for part in pointer.split('/')[1:]:
                    part=part.replace('~1','/').replace('~0','~')
                    value=value[int(part)] if isinstance(value,list) else value[part]
                state_refs_checked.append(launch_ledger.positive_evidence(value) and evidence_kind(root,safe)=='native_attested')
            else:state_refs_checked.append(False)
        state_attested=(bool(state_refs_checked) and all(state_refs_checked) and launch_ledger.positive_evidence(state)
            and state.get('schema')=='mldsafail.launch-handoff-state.v1' and state.get('native_executed') is True
            and state.get('maintenance_reconciled') is True and state.get('live_state_verified') is True and state.get('passed') is True)
        state_identity=dict(reference=state_ref,sha256=hashlib.sha256(state_bytes).hexdigest(),native_state_attested=state_attested)
    reasons=[]
    if unfinished:reasons.append('Agent-executable work remains')
    if not mapping_complete:reasons.append('Exact original 78-item mapping is incomplete')
    if source_tree_clean is not True:reasons.append('Source tree is not attested clean')
    if not state_attested:reasons.append('Native maintenance and live-state handoff evidence is incomplete')
    packet=dict(schema='mldsafail.launch-acceptance-packet.v1',mode='final' if final else 'draft',snapshot_complete=True,
        source_identity=dict(commit=source_commit,source_tree_clean=source_tree_clean is True,
            generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            ledger_validator_sha256=hashlib.sha256(Path(launch_ledger.__file__).read_bytes()).hexdigest()),
        ledger_identity=dict(sha256=ledger_sha256,task_count=len(tasks),validated=True),
        checklist=dict(expected_entries=78,mapped_entries=len(mappings),exact_mapping_complete=mapping_complete),
        agent_work_complete=not unfinished,final_ready=not reasons,public_launch_approved=False,
        production_activation_attested=False,readiness_rejections=reasons,unfinished_executable_tasks=unfinished,
        completed_gates=completed,completed_gates_by_evidence_kind={kind:[row['id'] for row in completed if row['kind']==kind]
            for kind in ('native_attested','source_review_or_local','mixed','unclassified')},retained_artifact_references=artifacts,attempt_history=attempts,
        failed_or_partial_attempts=[row for row in attempts if row['failed_or_partial']],
        maintenance_and_state_evidence=state_refs,final_state_evidence=state_identity,
        external_inputs_and_decisions=external,
        unfinished_dependency_roots={name:sorted(unresolved_roots(name)) for name,task in sorted(tasks.items()) if task['status']!='passed'})
    # Reuse the validator's recursive secret scan on the produced envelope.
    scan_errors=launch_ledger.validate(dict(tasks=[],checklist_source={'status':'blocked_external'},packet=packet))
    if scan_errors:raise ValueError('Packet sanitization validation failed')
    return packet


def serialize(packet):return (json.dumps(packet,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode()


def write_snapshot(path,packet):
    """Never overwrite history; retract an ambiguously published positive file."""
    path=Path(path)
    with path.open('xb') as stream:
        os.fchmod(stream.fileno(),0o600)
        try:
            stream.write(serialize(packet));stream.flush();os.fsync(stream.fileno())
            parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(parent)
            finally:os.close(parent)
        except BaseException as original:
            negative=dict(packet,snapshot_complete=False,final_ready=False,publication_failed=True,
                readiness_rejections=[*packet['readiness_rejections'],'Snapshot publication failed'])
            try:
                stream.seek(0);stream.truncate();stream.write(serialize(negative));stream.flush();os.fsync(stream.fileno())
            except BaseException as retry:original.add_note('Negative snapshot publication failed: '+type(retry).__name__)
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger',type=Path);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--state-evidence');parser.add_argument('--final',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();root=args.root.resolve();ledger_bytes=args.ledger.read_bytes()
    if args.ledger.resolve().is_relative_to(root) is not True:raise ValueError('Canonical ledger must belong to selected source root')
    if hashlib.sha256((root/'scripts/launch_ledger.py').read_bytes()).digest()!=hashlib.sha256(Path(launch_ledger.__file__).read_bytes()).digest():
        raise ValueError('Authoritative ledger validator differs from packet generator validator')
    source=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,timeout=15).strip()
    clean=not subprocess.check_output(['git','-C',str(root),'status','--porcelain'],timeout=15).strip()
    packet=build_packet(json.loads(ledger_bytes),root=root,source_commit=source,ledger_sha256=hashlib.sha256(ledger_bytes).hexdigest(),
        source_tree_clean=clean,state_reference=args.state_evidence,final=args.final)
    if args.output:
        # Never overwrite a historical snapshot; failed/partial files are retained.
        write_snapshot(args.output,packet)
    else:print(serialize(packet).decode(),end='')
    raise SystemExit(2 if args.final and not packet['final_ready'] else 0)


if __name__=='__main__':main()
