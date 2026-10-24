"""Checked execution inventory. Fixture coverage never grants native acceptance."""
from deploy.workload_controls import SCENARIOS
from mldsafail.evaluator.native_workload import require

NATIVE = {
    ('ancestor_limits', 'ancestor_limit_change'): 'ancestor_limit_change',
    ('bounded_output', 'log_exhaustion'): 'log_exhaustion',
    ('abnormal_exit', 'controller_disconnect'): 'controller_exit',
    ('ancestor_limits', 'parent_oom'): 'parent_oom',
    ('persistent_pause', 'supervisor_sigkill'): 'supervisor_death',
    ('native_linux_acceptance', 'inert_lifecycle_and_cleanup'): 'lifecycle',
}
HOST = frozenset(('abnormal_exit', 'common_cgroup', 'ancestor_limits', 'continuous_monitor',
    'bounded_output', 'verified_cleanup', 'persistent_pause', 'native_linux_acceptance',
    'delegation', 'inspected_births', 'scheduling_exclusion'))

LOCAL_CASES=frozenset((
    ('inspected_births','daemon_replacement'),
    ('durable_launch_intent','lost_create_ack'),('durable_launch_intent','lost_start_ack'),
    ('verified_cleanup','surviving_worker'),('verified_cleanup','empty_scope_and_absent_containers'),
    ('explicit_resume','failed_preflight'),('explicit_resume','fresh_preflight'),
    ('abnormal_exit','controller_disconnect'),
))

# Every entry describes a concrete injection. Native adapters are deliberately
# independent: running the fixture must never upgrade its evidence origin.
INJECTIONS = {
 ('shared_host_gate','cross_database_and_admin'): 'contend_for_one_flock_from_three_callers',
 ('coordinator_routing','deferred_admission'): 'remove_preflight_headroom',
 ('coordinator_routing','result_after_cleanup'): 'commit_after_verified_termination',
 ('administrative_routing','host_gate_before_fence'): 'record_gate_before_database_fence',
 ('administrative_routing','queued_blocks_admin'): 'insert_disposable_queued_row',
 ('zero_pending_fence','queued_claimed_running'): 'insert_each_disposable_pending_state',
 ('inspected_births','daemon_replacement'): 'replace_fixture_daemon_binding',
 ('inspected_births','container_restart'): 'replace_fixture_container_birth',
 ('durable_launch_intent','lost_create_ack'): 'drop_fixture_create_acknowledgement',
 ('durable_launch_intent','lost_start_ack'): 'drop_fixture_start_acknowledgement',
 ('common_cgroup','controller_worker_descendants'): 'spawn_three_inert_descendants',
 ('ancestor_limits','parent_oom'): 'inject_fixture_oom_counter',
 ('ancestor_limits','ancestor_limit_change'): 'reduce_fixture_ancestor_allowance',
 ('continuous_monitor','stuck_control_io'): 'hold_creator_response_while_monitor_aborts',
 ('continuous_monitor','stale_sample'): 'hold_sampler_until_age_watchdog_aborts',
 ('bounded_output','log_exhaustion'): 'exceed_fixture_log_budget',
 ('bounded_output','generation_quota_exhaustion'): 'exceed_fixture_generation_budget',
 ('verified_cleanup','surviving_worker'): 'refuse_fixture_termination',
 ('verified_cleanup','empty_scope_and_absent_containers'): 'terminate_fixture_resources',
 ('abnormal_exit','controller_disconnect'): 'expire_fixture_controller_heartbeat',
 ('persistent_pause','supervisor_sigkill'): 'kill_inert_owner_after_durable_acquisition',
 ('explicit_resume','failed_preflight'): 'remove_headroom_before_explicit_resume',
 ('explicit_resume','fresh_preflight'): 'restore_headroom_before_explicit_resume',
 ('native_linux_acceptance','inert_lifecycle_and_cleanup'): 'complete_inert_fixture_lifecycle',
 ('delegation','missing_controller'): 'deny_fixture_preflight_controller',
 ('delegation','inspected_limits'): 'read_fixture_limit_files',
 ('scheduling_exclusion','retained_trigger_inventory'): 'inspect_disposable_trigger_inventory',
}


def registry(entries=None):
    expected = {(control, scenario) for control, cases in SCENARIOS.items() for scenario in cases}
    require(set(INJECTIONS) == expected, 'control_registry_injection_inventory_changed')
    authoritative = [dict(control=control, scenario=scenario,
        runner='deploy.workload_control_fixture:execute', injection=INJECTIONS[control,scenario],
        observer='durable_gate_and_raw_fixture_before_after', cleanup='generation_owned_fixture_only',
        required_origin='installed_native' if control in HOST else 'disposable_database_or_local_synthetic',
        fixture_origin='synthetic', native_runner='deploy.workload_native_acceptance:execute' if (control,scenario) in NATIVE else None,
        native_case=NATIVE.get((control,scenario)),
        local_runner='deploy.workload_control_linux:execute' if (control,scenario) in LOCAL_CASES else None,
        identity_bindings=['source_release_sha256','configuration_sha256','boot_id','daemon_id','workload_id','scope_device_inode'])
        for control,cases in SCENARIOS.items() for scenario in cases]
    rows = authoritative if entries is None else entries
    require(type(rows) is list and all(type(row) is dict and 'control' in row and 'scenario' in row for row in rows), 'control_registry_coverage_invalid')
    keys = [(row['control'],row['scenario']) for row in rows]
    require(len(keys)==len(set(keys)) and set(keys)==expected, 'control_registry_coverage_invalid')
    expected_rows={(row['control'],row['scenario']):row for row in authoritative}
    require(all(row==expected_rows[key] for row,key in zip(rows,keys)), 'control_registry_unsupported_entry')
    return rows


def get_runner(control, scenario):
    matches=[row for row in registry() if (row['control'],row['scenario'])==(control,scenario)]
    require(len(matches)==1,'control_scenario_not_allowlisted')
    return matches[0]
