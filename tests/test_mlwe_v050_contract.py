import copy
import json
import pytest
from mldsafail.benchmark_v050 import generator, models, verify, scoring
from research.primitive_selection import generator as frozen, decision


def wire(x):
    return json.loads(json.dumps(x))


@pytest.mark.parametrize('profile', ['small', 'medium', 'large'])
@pytest.mark.parametrize('eta', [1, 2])
def test_sampler_and_contract(profile, eta):
    for seed in range(10):
        a, b = generator.generate_mlwe(profile, seed, eta), frozen.generate_mlwe(profile, seed, eta)
        assert a.public.to_dict() == b.public.to_dict()
        assert a.planted_s1 == b.planted_s1 and a.planted_s2 == b.planted_s2
        assert models.instance_from_dict(wire(a.public.to_dict())) == a.public
        candidate = wire(models.RecoveredSecret(a.planted_s1, a.planted_s2).to_dict())
        assert verify.verify_candidate(a.public, candidate)['verified']
        for bad in [dict(candidate, seed=seed), {'tag': 'reconstructed', 's1': candidate['s1'], 's2': candidate['s2']}, [], True]:
            assert not verify.verify_candidate(a.public, bad)['verified']
        for bad_value in [True, 0.5, eta + 1, '1']:
            bad = copy.deepcopy(candidate)
            bad['s1'][0][0] = bad_value
            assert not verify.verify_candidate(a.public, bad)['verified']
        invalid = wire(a.public.to_dict()); invalid['seed'] = seed
        with pytest.raises(ValueError): models.instance_from_dict(invalid)


def test_score_equivalence():
    rows = []
    for p, e in scoring.CHALLENGE_CELLS:
        for seed in range(4):
            for solver in ['primal-lll', 'hybrid-bdd']:
                rows.append(dict(track='mlwe', profile=p, eta=e, seed=seed, solver=solver,
                                 verification_result=True, median_cpu_seconds=(seed + e) * (1 if solver == 'primal-lll' else 1.5),
                                 repetitions=[{'status':'success'}]*3))
    assert scoring.ranking(rows, 'primal-lll') == 1
    assert scoring.ranking_interval(rows, 'primal-lll') == (1, 1)
    assert scoring.ranking(rows, 'hybrid-bdd') == decision.ranking(rows, 'hybrid-bdd')
    assert scoring.ranking_interval(rows, 'hybrid-bdd') == decision.ranking_interval(rows, 'hybrid-bdd')
    scores = {'a':1, 'b':1.009, 'c':1.018, 'd':1.03}
    assert scoring.ranked_groups(scores) == decision.ranked_groups(scores)


def test_zero_and_equation_rejection():
    generated = generator.generate_mlwe('small', 0, 1)
    zero = {'tag': 'recovered_secret', 's1': [[0]*4], 's2': [[0]*4]*2}
    assert not verify.verify_candidate(generated.public, zero)['verified']
    payload = wire(generated.public.to_dict())
    payload['t'] = [[0]*4]*2
    del payload['instance_id']
    payload['instance_id'] = models.digest(payload)
    assert verify.verify_candidate(models.instance_from_dict(payload), zero)['verified']
    valid = wire(models.RecoveredSecret(generated.planted_s1, generated.planted_s2).to_dict())
    for field in ('s1','s2'):
        bad = copy.deepcopy(valid); bad[field][0].pop()
        assert not verify.verify_candidate(generated.public, bad)['verified']
    bad = copy.deepcopy(valid)
    bad['s2'][0][0] = -1 if bad['s2'][0][0] != -1 else 1
    assert not verify.verify_candidate(generated.public, bad)['verified']
