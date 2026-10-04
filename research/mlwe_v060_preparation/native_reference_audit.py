"""Independent fresh-reference audit; never trust a producer's ready flag."""
import hashlib
from collections import defaultdict
from pathlib import Path
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
from mldsafail.benchmark_v060.envelope import canonical, independently_audited_case
from .reference_authority import digest
from .references import reference_costs
from deploy import owned_daemon


def audit_reference(prepared, *, cases, directory, cohort, source_sha256,
                    worker_image, supervisor_source_sha256,
                    reference_source_commit, epoch_manifest_sha256, seal_path):
    table, producer = prepared['table'], prepared['receipt']
    producer_digest=hashlib.sha256(canonical(producer)).hexdigest()
    ids=[case['case_id'] for case in cases]
    costs=reference_costs(table,cohort,case_ids=ids,epoch_manifest_sha256=epoch_manifest_sha256,
        reference_source_commit=reference_source_commit,worker_image=worker_image,audit_receipt_sha256=producer_digest)
    if producer.get('cohort_id')!=cohort.public_id or producer.get('source_sha256')!=source_sha256:
        raise ValueError('Producer source/cohort differs from trusted reference')
    rows={row['case_id']:row['evidence'] for row in producer['cases']}
    if len(rows)!=len(producer['cases']) or set(rows)!=set(ids): raise ValueError('Exact fresh reference cases required')
    success=defaultdict(int);counts=defaultdict(int);audits=[];instance_ids=set();all_generations=set()
    for case in cases:
        public=instance_from_dict(case['public_input']);cell=(public.profile,public.eta)
        if public.instance_id in instance_ids: raise ValueError('Repeated public reference instance')
        instance_ids.add(public.instance_id)
        counts[cell]+=1
        record=rows[case['case_id']]
        generations=record.get('generations')
        # Generation identities are supplied separately by the producer record
        # wrapper; they are never inferred from mutable latest-journal state.
        if not isinstance(generations,list) or len(generations)!=3 or len(set(generations))!=3 or any(not isinstance(value,str) or not __import__('re').fullmatch('[0-9a-f]{32}',value) for value in generations):
            raise ValueError('Exactly three distinct immutable reference generations required')
        if all_generations.intersection(generations): raise ValueError('Reference generation reused across cases')
        all_generations.update(generations)
        retained=[owned_daemon.read_private_json(Path(directory)/(generation+'.json'),cap=8*1024*1024) for generation in generations]
        if any(row['public_input']!=case['public_input'] for row in retained): raise ValueError('Reference input swap')
        checked=independently_audited_case(retained,directory=directory,cohort=cohort,
            source_sha256=source_sha256,worker_image=worker_image,supervisor_source_sha256=supervisor_source_sha256)
        supplied={key:value for key,value in record.items() if key!='generations'}
        if checked!=supplied or not checked['decision']['eligible'] or checked['decision']['cost_usec']!=costs[case['case_id']]:
            raise ValueError('Independent reference cost/disposition mismatch')
        if not checked['decision']['penalized']: success[cell]+=1
        audits.append(dict(case_id=case['case_id'],generations=generations,evidence=checked))
    if set(counts)!=set(CHALLENGE_CELLS) or any(counts[cell]!=20 or success[cell]<18 for cell in CHALLENGE_CELLS):
        raise ValueError('Full tiny primitive grid below unchanged viability floor')
    epoch_seal=dict(schema='mldsafail.v060-isolated-epoch-seal.v1',epoch_id=cohort.epoch_id,
        cohort_id=cohort.public_id,epoch_manifest_sha256=epoch_manifest_sha256,
        reference_table_sha256=digest(table),production_adoption=False,audits=audits)
    if Path(seal_path).exists(): raise ValueError('Epoch seal must be new and immutable')
    owned_daemon.publish(seal_path,epoch_seal)
    return dict(schema='mldsafail.v060-native-reference-authority-audit.v1',ready=True,
        remaining_gates=[],gates=dict(independent_reference_audit=True,full_primitive_viability=True,epoch_sealing=True),
        reference_table_sha256=digest(table),epoch_seal_sha256=digest(epoch_seal),production_adoption=False)
