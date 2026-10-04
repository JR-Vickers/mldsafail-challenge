"""Isolated proposed cohort evaluation; no queue/default registration."""
import math
import statistics
from collections import defaultdict
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
from research.mlwe_v060_preparation.references import reference_costs
from research.mlwe_v060_preparation.reference_authority import require as require_reference_authority
from .envelope import SCHEMA, independently_audited_case, sign


def _evaluate(*, backend, source, source_sha256, supervisor_source_sha256, cohort,
             cases, references, epoch_manifest_sha256, reference_source_commit,
             reference_worker_image, reference_audit_sha256, signing_key,
             checkpoint=lambda: None, reference_authority=None, reference_authority_key=None):
    """Complete exact fresh paired cohort or raise; never infer historical costs."""
    if cohort.benchmark_version != '0.6.0' or backend.epoch_id != cohort.epoch_id:
        raise ValueError('Explicit matching v060 backend/cohort required')
    require_reference_authority(references,reference_authority,key=reference_authority_key)
    ids = [case['case_id'] for case in cases]
    costs = reference_costs(references, cohort, case_ids=ids,
                            epoch_manifest_sha256=epoch_manifest_sha256,
                            reference_source_commit=reference_source_commit,
                            worker_image=reference_worker_image,
                            audit_receipt_sha256=reference_audit_sha256)
    cells = defaultdict(list)
    instance_ids = set()
    for case in cases:
        public = instance_from_dict(case['public_input'])
        if public.instance_id in instance_ids:
            raise ValueError('Repeated public instance in fresh cohort')
        instance_ids.add(public.instance_id)
        cell = (public.profile, public.eta)
        if cell not in CHALLENGE_CELLS:
            raise ValueError('Case outside tiny challenge grid')
        cells[cell].append(case['case_id'])
    if set(cells) != set(CHALLENGE_CELLS) or any(len(values) != 20 for values in cells.values()):
        raise ValueError('Exactly twenty fresh cases per challenge cell required')
    receipts, ratios = [], defaultdict(list)
    eligible = True
    from mldsafail.benchmark_v050.verify import verify_candidate
    for case in cases:
        checkpoint()
        result = backend.evaluate_case(source, case['public_input'],
                    lambda public, candidate: verify_candidate(instance_from_dict(public), candidate)['verified'],
                    checkpoint=checkpoint)
        if any(record['public_input'] != case['public_input'] for record in result['records']):
            raise ValueError('Evidence differs from declared fresh case')
        receipt = independently_audited_case(result['records'], directory=backend.directory,
                        cohort=cohort, source_sha256=source_sha256, worker_image=backend.image,
                        supervisor_source_sha256=supervisor_source_sha256)
        receipts.append(receipt)
        decision = receipt['decision']
        eligible = eligible and decision['eligible']
        if decision['eligible']:
            public = instance_from_dict(case['public_input'])
            ratios[(public.profile, public.eta)].append(math.log(decision['cost_usec']/costs[case['case_id']]))
    score = math.exp(statistics.mean(statistics.mean(values) for values in ratios.values())) if eligible else None
    payload = dict(schema=SCHEMA, benchmark_version='0.6.0', cohort_id=cohort.public_id,
                   source_sha256=source_sha256, epoch_id=cohort.epoch_id,
                   verified=eligible, score=score, cases=receipts,
                   reference_audit_sha256=reference_audit_sha256)
    checkpoint()
    return sign(payload, signing_key)


def evaluate(**kwargs):
    """No authoritative result survives a fixed twenty-minute platform expiry.

    The deadline interrupts blocking host measurement into its existing durable
    infrastructure-failure cleanup. Ordinary per-worker timeouts remain sixty
    seconds; an incomplete three-invocation case never receives a replacement
    or a synthetic ordinary-failure score. Cleanup may retain a fence afterward.
    """
    from .deadline import COMPLETE_EVALUATION_SECONDS, deadline
    checkpoint=kwargs.get('checkpoint',lambda:None)
    with deadline(COMPLETE_EVALUATION_SECONDS) as check:
        def guarded_checkpoint():
            check()
            checkpoint()
            check()
        return _evaluate(**dict(kwargs,checkpoint=guarded_checkpoint))
