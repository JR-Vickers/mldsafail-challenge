import copy
from pathlib import Path
import pytest
from mldsafail.benchmark_v050 import evidence as ev
from mldsafail.benchmark_v050 import execution as ex
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import RecoveredSecret, digest
from mldsafail.benchmark_v050.verify import verify_candidate
from research.primitive_selection.runner import validation_seeds


def test_seed_protocol():
    nonce = '01' * 32
    for profile in ('small', 'medium', 'large'):
        assert tuple(ev.seeds(nonce, profile)) == validation_seeds(nonce, profile)
    grid = ev.cases(nonce)
    assert len(grid) == len({c['instance_id'] for c in grid}) == 100


def test_exclusive_evidence(tmp_path):
    folder = ev.directory(tmp_path / 'evidence')
    ev.write(folder / 'a.json', {'a': 1})
    with pytest.raises((ValueError, FileExistsError)): ev.write(folder / 'a.json', {})
    with pytest.raises(FileExistsError): ev.directory(folder)
    ev.seal(folder); ev.check_seal(folder)
    (folder / 'a.json').write_text('{}')
    with pytest.raises(ValueError): ev.check_seal(folder)


def fixture_run(tmp_path):
    folder = ev.directory(tmp_path / 'run')
    ev.directory(folder / 'records')
    grid = ev.cases(smoke=True)
    m = ev.manifest('run', {'trusted_fingerprint': ex.fingerprint()}, grid, solver='primal-lll')
    ev.write(folder / 'manifest.json', m)
    rows = []
    for i, case in enumerate(grid):
        generated = generate_mlwe(case['profile'], case['seed'], case['eta'])
        candidate = __import__('json').loads(__import__('json').dumps(RecoveredSecret(generated.planted_s1, generated.planted_s2).to_dict()))
        result = {'candidate': candidate, 'verification': verify_candidate(generated.public, candidate),
                  'input_digest': case['input_digest'], 'output_digest': digest(candidate), 'status':'success',
                  'cpu_seconds': .1, 'wall_seconds': .2, 'evaluator_wall_seconds': .3, 'peak_rss_bytes': 100,
                  'limits': {'rlimits_applied': ['RLIMIT_AS'], 'cpu_affinity': 0},
                  'solver_parameters': ev.DEFAULT_PARAMETERS['primal-lll']}
        for rep in range(4):
            ev.write(folder / 'records' / f'{i:03d}-{rep}.json', {'run_id': m['id'], 'case_index': i, 'repetition': rep, 'result': result})
        rows.append(ev.aggregate(case, m['solver'], [result]*4))
    ev.write(folder / 'aggregates.json', rows)
    return folder, m


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'candidate', 'aggregate', 'settings', 'version'])
def test_audit_rejection(tmp_path, damage):
    folder, m = fixture_run(tmp_path)
    ev.audit_run(folder, check_complete=False)
    path = folder / 'records' / '000-1.json'
    if damage == 'missing': path.unlink()
    elif damage == 'duplicate': (path.parent / 'duplicate.json').write_bytes(path.read_bytes())
    elif damage == 'candidate':
        data = ev.read(path); data['result']['candidate']['s1'][0][0] += 1
        path.write_bytes(ev.encoded(data))
    elif damage == 'aggregate':
        path = folder / 'aggregates.json'; data = ev.read(path); data[0]['median_cpu_seconds'] = .0001
        path.write_bytes(ev.encoded(data))
    else:
        path = folder / 'manifest.json'; data = ev.read(path)
        if damage == 'settings': data['settings']['repetitions'] = 1
        else: data['benchmark_version'] = '0.4.0'
        path.write_bytes(ev.encoded(data))
    with pytest.raises((ValueError, FileNotFoundError)): ev.audit_run(folder, check_complete=False)


def test_failure_penalty_and_invalid():
    case = {'profile':'small','eta':1,'seed':0}
    good = {'status':'success','cpu_seconds':1}
    for status in ['timeout','memory_failure','crash','no_candidate','applicability_cap']:
        row = ev.aggregate(case, 'test', [good, good, {'status':status}, good])
        assert ev.case_cost(row) == 60
    row = ev.aggregate(case, 'test', [good, good, {'status':'invalid_answer'}, good])
    with pytest.raises(ValueError): ev.case_cost(row)
    with pytest.raises(ValueError): ev.aggregate(case, 'test', [good])
