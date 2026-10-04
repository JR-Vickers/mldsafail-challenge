import copy
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('launch_ledger', Path(__file__).parents[1] / 'scripts/launch_ledger.py')
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


def report():
    return {'checklist_source': {'status': 'available'}, 'tasks': [
        {'id': 'launch', 'requirement': 'acceptance', 'sources': ['protocol'],
         'dependencies': [], 'environment': 'disposable', 'criteria': ['native verified'],
         'status': 'passed', 'attempts': [], 'evidence': [{'reference': 'protected:run-1',
          'criteria_met': ['native verified']}], 'identities': {'source': 'abc'},
         'next_action': 'retain', 'checklist': list(range(1, 79))}]}


def test_complete_ledger():
    assert ledger.validate(report()) == []


def test_cycles_unknown_dependencies_and_pass_claims():
    data = report()
    data['tasks'][0]['dependencies'] = ['launch', 'missing']
    errors = ledger.validate(data)
    assert any('cycle' in error for error in errors)
    assert any('unknown dependency' in error for error in errors)
    assert any('incomplete prerequisite' in error for error in errors)


def test_checklist_omissions_duplicates():
    data = report()
    data['tasks'][0]['checklist'] = [1, 1]
    errors = ledger.validate(data)
    assert any('duplicate checklist' in error for error in errors)
    assert any('missing checklist' in error for error in errors)


def test_missing_source_explicitly_blocks_completion():
    data = report()
    data['checklist_source']['status'] = 'blocked_external'
    data['tasks'][0]['checklist'] = []
    assert ledger.validate(data) == []
    assert ledger.validate(data, require_complete_mapping=True)


def test_secret_fields_and_values_rejected():
    data = report()
    data['password'] = 'redacted'
    data['api_token'] = 'opaque-value'
    data['tasks'][0]['next_action'] = 'Bearer sensitive'
    assert len(ledger.validate(data)) == 3


def test_evidence_must_cover_exact_criteria():
    data = report()
    data['tasks'][0]['evidence'][0]['criteria_met'] = ['other']
    assert ledger.validate(data)
    data['tasks'][0]['evidence'] = []
    assert any('unsupported pass' in error for error in ledger.validate(data))


def test_blockers_and_readiness():
    data = report()
    parent = copy.deepcopy(data['tasks'][0])
    parent.update(id='parent', status='pending', dependencies=['launch'], checklist=[])
    data['tasks'].append(parent)
    assert ledger.readiness(data)['tasks'][1]['status'] == 'ready'
    data['tasks'][0]['status'] = 'blocked_external'
    assert any('external blocker' in error for error in ledger.validate(data))
    assert ledger.readiness(data)['tasks'][1]['status'] == 'waiting_dependency'


def test_pass_rejects_missing_or_failed_json_pointer(tmp_path):
    import json
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/evidence.json').write_text(json.dumps({'gate': {'status': 'failed'}}))
    data = report()
    evidence = data['tasks'][0]['evidence'][0]
    evidence['reference'] = 'docs/evidence.json#/gate'
    assert any('does not pass' in error for error in ledger.validate(data, tmp_path))
    evidence['reference'] = 'docs/evidence.json#/missing'
    assert any('JSON pointer' in error for error in ledger.validate(data, tmp_path))
