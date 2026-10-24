"""Explicit coverage inventory; scenario declarations are not passing receipts."""
from deploy.workload_controls import SCENARIOS
from deploy.workload_control_registry import HOST, NATIVE, registry


def evidence_matrix():
    rows=[]
    for entry in registry():
        row=dict(entry)
        row.update(runner_case=entry['native_case'],
            runner_status='fixture_implemented_native_not_executed' if entry['native_case'] else 'fixture_implemented_native_adapter_required',
            validator='deploy.workload_controls.validate_case',
            expected_observations=SCENARIOS[entry['control']][entry['scenario']],
            raw_required=['injection_and_observation_monotonic_trace','before_after_kernel_or_transaction_reads'],
            receipt=None,accepted=False)
        rows.append(row)
    return rows
