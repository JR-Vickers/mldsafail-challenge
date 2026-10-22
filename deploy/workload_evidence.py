"""Explicit coverage inventory; scenario declarations are not passing receipts."""
from deploy.workload_controls import SCENARIOS

# Existing tests are synthetic unless separately executed in the installed host.
NATIVE = {
    ('ancestor_limits','ancestor_limit_change'): 'ancestor_limit_change',
    ('bounded_output','log_exhaustion'): 'log_exhaustion',
    ('abnormal_exit','controller_disconnect'): 'controller_exit',
    ('ancestor_limits', 'parent_oom'): 'parent_oom',
    ('persistent_pause', 'supervisor_sigkill'): 'supervisor_death',
    ('native_linux_acceptance', 'inert_lifecycle_and_cleanup'): 'lifecycle',
}
HOST = {'abnormal_exit','common_cgroup', 'ancestor_limits', 'continuous_monitor', 'bounded_output',
        'verified_cleanup', 'persistent_pause', 'native_linux_acceptance', 'delegation',
        'inspected_births', 'scheduling_exclusion'}


def evidence_matrix():
    rows = []
    for control, cases in SCENARIOS.items():
        for name, expected in cases.items():
            case = NATIVE.get((control, name))
            runner = 'deploy.workload_native_acceptance:execute' if case else None
            rows.append(dict(control=control, scenario=name,
                required_origin='installed_native' if control in HOST else 'disposable_database_or_local_synthetic',
                runner=runner, runner_case=case, runner_status='implemented_not_executed' if runner else 'coverage_extension_required',
                validator='deploy.workload_controls.validate_case',
                expected_observations=expected,
                raw_required=['injection_and_observation_monotonic_trace', 'before_after_kernel_or_transaction_reads'],
                identity_bindings=['source_release_sha256', 'configuration_sha256', 'boot_id', 'daemon_id',
                                   'workload_id', 'scope_device_inode'],
                receipt=None, accepted=False))
    return rows
