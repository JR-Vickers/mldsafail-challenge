"""Reject legacy/cross-cohort reference costs before future 0.6.0 scoring."""
from __future__ import annotations
import math
import re
from .contracts import Cohort


def reference_costs(table, cohort, *, case_ids, epoch_manifest_sha256, reference_source_commit, worker_image, audit_receipt_sha256):
    if not isinstance(cohort, Cohort) or cohort.benchmark_version != '0.6.0':
        raise ValueError('0.6.0 reference cohort required')
    fields = {'schema', 'benchmark_version', 'measurement_method', 'units', 'cohort_id',
              'epoch_id', 'epoch_manifest_sha256', 'reference_source_commit', 'worker_image',
              'audit_receipt_sha256', 'costs_usec'}
    if not isinstance(table, dict) or set(table) != fields:
        raise ValueError('Strict versioned independently audited reference table required')
    expected = dict(schema='mldsafail.mlwe-v060-reference.v1', benchmark_version='0.6.0',
                    measurement_method='cgroup-v2-usage-usec', units='microseconds',
                    cohort_id=cohort.public_id, epoch_id=cohort.epoch_id,
                    epoch_manifest_sha256=epoch_manifest_sha256,
                    reference_source_commit=reference_source_commit, worker_image=worker_image,
                    audit_receipt_sha256=audit_receipt_sha256)
    if any(table[key] != value for key, value in expected.items()):
        raise ValueError('Reference table belongs to a different contract/cohort/epoch')
    for key in ('epoch_manifest_sha256', 'audit_receipt_sha256'):
        if not isinstance(table[key], str) or not re.fullmatch('[0-9a-f]{64}', table[key]):
            raise ValueError('Audited reference digest required')
    if not isinstance(table['reference_source_commit'], str) or not re.fullmatch('[0-9a-f]{40}', table['reference_source_commit']):
        raise ValueError('Reference source identity required')
    if not isinstance(table['worker_image'], str) or not re.fullmatch('sha256:[0-9a-f]{64}', table['worker_image']):
        raise ValueError('Immutable reference worker identity required')
    costs = table['costs_usec']
    if not isinstance(costs, dict) or set(costs) != set(case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError('Exactly one fresh cost per declared case required')
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 1 for value in costs.values()):
        raise ValueError('Finite floored authoritative microsecond costs required')
    return dict(costs)
