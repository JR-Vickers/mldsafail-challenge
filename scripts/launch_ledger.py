"""Validate the sanitized operator launch ledger; no service mutations."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

STATUSES = {'pending', 'ready', 'running', 'passed', 'failed', 'blocked_external', 'waiting_dependency'}
REQUIRED = {'id', 'requirement', 'sources', 'dependencies', 'environment', 'criteria',
            'status', 'attempts', 'evidence', 'identities', 'next_action', 'checklist'}
SECRET_KEY = re.compile(r'(password|bearer|access_key|secret_value|private_key|token_value)', re.I)
SECRET_VALUE = re.compile(r'Bearer\s+\S+|-----BEGIN .*PRIVATE KEY|\bAKIA[A-Z0-9]{16}\b|https?://[^\s/@]+:[^\s/@]+@')


def validate(report, root=None, require_complete_mapping=False):
    errors = []
    def scan(value, location):
        if isinstance(value, dict):
            for key, child in value.items():
                if SECRET_KEY.search(key):
                    errors.append(f'{location}/{key}: forbidden credential field')
                scan(child, f'{location}/{key}')
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f'{location}/{index}')
        elif isinstance(value, str) and SECRET_VALUE.search(value):
            errors.append(f'{location}: credential-shaped value')
    scan(report, '')
    tasks = report.get('tasks', [])
    ids = [task.get('id') for task in tasks]
    if len(ids) != len(set(ids)):
        errors.append('duplicate task IDs')
    lookup = {task.get('id'): task for task in tasks}
    mappings = []
    for task in tasks:
        name = task.get('id')
        missing = REQUIRED - task.keys()
        if missing:
            errors.append(f'{name}: missing fields {sorted(missing)}')
        if task.get('status') not in STATUSES:
            errors.append(f'{name}: unsupported status')
        if not task.get('criteria') or not task.get('sources'):
            errors.append(f'{name}: criteria and source required')
        mappings.extend(task.get('checklist', []))
        for dependency in task.get('dependencies', []):
            if dependency not in lookup:
                errors.append(f'{name}: unknown dependency {dependency}')
        if task.get('status') == 'passed':
            if not task.get('evidence') or not task.get('identities'):
                errors.append(f'{name}: unsupported pass claim')
            if any(lookup.get(dep, {}).get('status') != 'passed' for dep in task.get('dependencies', [])):
                errors.append(f'{name}: parent passed with incomplete prerequisite')
            for evidence in task.get('evidence', []):
                if not isinstance(evidence, dict) or not evidence.get('reference') or not evidence.get('criteria_met'):
                    errors.append(f'{name}: evidence must identify satisfied criteria')
                elif not set(evidence['criteria_met']).issubset(set(task.get('criteria', []))):
                    errors.append(f'{name}: evidence claims undeclared criteria')
                elif root and evidence['reference'].startswith('docs/'):
                    path = evidence['reference'].split('#', 1)[0]
                    if not (root / path).is_file():
                        errors.append(f'{name}: evidence file absent')
            satisfied = {criterion for item in task.get('evidence', []) if isinstance(item, dict)
                         for criterion in item.get('criteria_met', [])}
            if satisfied != set(task.get('criteria', [])):
                errors.append(f'{name}: incomplete evidence coverage')
        if task.get('status') == 'blocked_external':
            blocker = task.get('blocker', {})
            if not all(blocker.get(key) for key in ('input', 'owner', 'requested_action')):
                errors.append(f'{name}: external blocker lacks exact input/owner/action')
        if task.get('status') == 'ready' and any(lookup.get(dep, {}).get('status') != 'passed' for dep in task.get('dependencies', [])):
            errors.append(f'{name}: ready with incomplete dependencies')
    if len(mappings) != len(set(mappings)):
        errors.append('duplicate checklist mappings')
    if any(type(number) is not int or not 1 <= number <= 78 for number in mappings):
        errors.append('invalid checklist number')
    absent = sorted(set(range(1, 79)) - set(mappings))
    if absent and (require_complete_mapping or report.get('checklist_source', {}).get('status') == 'available'):
        errors.append(f'missing checklist mappings: {absent}')
    if absent and report.get('checklist_source', {}).get('status') != 'blocked_external':
        errors.append('missing checklist must be explicitly externally blocked')
    visiting, visited = set(), set()
    def visit(name):
        if name in visiting:
            errors.append(f'dependency cycle at {name}')
            return
        if name in visited or name not in lookup:
            return
        visiting.add(name)
        for dep in lookup[name].get('dependencies', []):
            visit(dep)
        visiting.remove(name)
        visited.add(name)
    for name in ids:
        visit(name)
    return errors


def readiness(report):
    lookup = {task['id']: task for task in report['tasks']}
    for task in report['tasks']:
        if task['status'] in {'pending', 'ready', 'waiting_dependency'}:
            task['status'] = ('ready' if all(lookup[dep]['status'] == 'passed' for dep in task['dependencies'])
                              else 'waiting_dependency')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--require-complete-mapping', action='store_true')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    errors = validate(report, Path(__file__).resolve().parents[1], args.require_complete_mapping)
    print(json.dumps({'valid': not errors, 'errors': errors,
                      'ready': [t['id'] for t in readiness(report)['tasks'] if t['status'] == 'ready']}, indent=2))
    raise SystemExit(bool(errors))

if __name__ == '__main__':
    main()
