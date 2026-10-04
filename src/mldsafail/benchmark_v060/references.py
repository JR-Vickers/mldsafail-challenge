"""Prepare fresh independently audited proposed references; never seal epochs."""
import hashlib
from collections import defaultdict
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
from .envelope import canonical, independently_audited_case


def prepare_references(*, backend, cohort, source, source_sha256,
                       supervisor_source_sha256, reference_source_commit,
                       epoch_manifest_sha256, cases, checkpoint=lambda: None):
    if cohort.benchmark_version != '0.6.0' or backend.epoch_id != cohort.epoch_id:
        raise ValueError('Fresh matching v060 reference epoch required')
    cells, identities = defaultdict(list), set()
    for case in cases:
        public = instance_from_dict(case['public_input'])
        if public.instance_id in identities:
            raise ValueError('Duplicate reference instance')
        identities.add(public.instance_id)
        cells[(public.profile,public.eta)].append(case['case_id'])
    if set(cells) != set(CHALLENGE_CELLS) or any(len(rows)!=20 for rows in cells.values()):
        raise ValueError('Complete fresh reference grid required')
    if len({case['case_id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate reference case identity')
    from mldsafail.benchmark_v050.verify import verify_candidate
    costs, receipts, successful = {}, [], defaultdict(int)
    for case in cases:
        checkpoint()
        result=backend.evaluate_case(source,case['public_input'],
                lambda public,candidate:verify_candidate(instance_from_dict(public),candidate)['verified'],
                checkpoint=checkpoint)
        if any(record['public_input']!=case['public_input'] for record in result['records']):
            raise ValueError('Reference evidence input mismatch')
        receipt=independently_audited_case(result['records'],directory=backend.directory,cohort=cohort,
                     source_sha256=source_sha256,worker_image=backend.image,
                     supervisor_source_sha256=supervisor_source_sha256)
        if not receipt['decision']['eligible']:
            raise ValueError('Invalid reference answer cannot establish costs')
        receipts.append(dict(case_id=case['case_id'], evidence=dict(receipt,generations=[row['generation'] for row in result['records']])))
        costs[case['case_id']]=receipt['decision']['cost_usec']
        public=instance_from_dict(case['public_input'])
        if not receipt['decision']['penalized']:
            successful[(public.profile,public.eta)] += 1
    if any(successful[cell]<18 for cell in CHALLENGE_CELLS):
        raise ValueError('Reference below unchanged ninety-percent per-cell viability floor')
    receipt=dict(schema='mldsafail.mlwe-v060-reference-audit.v1',cohort_id=cohort.public_id,
                 source_sha256=source_sha256, reference_source_commit=reference_source_commit,
                 epoch_manifest_sha256=epoch_manifest_sha256, cases=receipts,
                 ready=False, remaining_gates=['independent_reference_audit','full_primitive_viability','epoch_sealing'])
    receipt_sha=hashlib.sha256(canonical(receipt)).hexdigest()
    table=dict(schema='mldsafail.mlwe-v060-reference.v1',benchmark_version='0.6.0',
               measurement_method='cgroup-v2-usage-usec',units='microseconds',cohort_id=cohort.public_id,
               epoch_id=cohort.epoch_id,epoch_manifest_sha256=epoch_manifest_sha256,
               reference_source_commit=reference_source_commit,worker_image=backend.image,
               audit_receipt_sha256=receipt_sha,costs_usec=costs)
    return {'table':table,'receipt':receipt}
