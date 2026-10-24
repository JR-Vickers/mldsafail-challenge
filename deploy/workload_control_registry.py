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

OWNED_INJECTIONS={
 ('shared_host_gate','cross_database_and_admin'):'production_dispatcher_two_disposable_databases_and_admin_contend',
 ('coordinator_routing','deferred_admission'):'production_dispatcher_fixture_admission_denial_before_attempt',
 ('coordinator_routing','result_after_cleanup'):'production_dispatcher_SQL_commit_observer_after_real_child_termination',
 ('administrative_routing','host_gate_before_fence'):'production_administration_route_and_disposable_PostgreSQL_fence',
 ('administrative_routing','queued_blocks_admin'):'disposable_PostgreSQL_queued_row_blocks_real_fence',
 ('zero_pending_fence','queued_claimed_running'):'disposable_PostgreSQL_pending_states_block_real_fence',
 ('inspected_births','daemon_replacement'):'replace_fixture_identity_binding_without_shared_daemon_mutation',
 ('inspected_births','container_restart'):'restart_exact_generation_owned_inert_container',
 ('durable_launch_intent','lost_create_ack'):'withhold_router_create_ack_after_actual_owned_Docker_create',
 ('durable_launch_intent','lost_start_ack'):'withhold_router_start_ack_after_actual_owned_Docker_start',
 ('common_cgroup','controller_worker_descendants'):'place_inert_controller_descendant_and_container_in_owned_cgroups',
 ('ancestor_limits','parent_oom'):'kernel_OOM_in_exclusive_64MiB_32PID_child_cgroup',
 ('ancestor_limits','ancestor_limit_change'):'reduce_only_owned_creator_leaf_memory_limit',
 ('continuous_monitor','stuck_control_io'):'withhold_bounded_native_command_response_on_control_channel',
 ('continuous_monitor','stale_sample'):'hold_sample_callback_until_independent_age_watchdog',
 ('bounded_output','log_exhaustion'):'kernel_RLIMIT_FSIZE_sparse_write_and_observed_EFBIG',
 ('bounded_output','generation_quota_exhaustion'):'allocate_only_exclusive_quota_file_until_kernel_ENOSPC',
 ('verified_cleanup','surviving_worker'):'inert_worker_survives_normal_leaf_cleanup_in_owned_scope',
 ('verified_cleanup','empty_scope_and_absent_containers'):'production_cleanup_of_actual_owned_container_and_cgroup',
 ('abnormal_exit','controller_disconnect'):'actual_inert_native_controller_exit_23_without_result',
 ('persistent_pause','supervisor_sigkill'):'SIGKILL_only_owned_fixture_supervisor_then_observe_restart_pause',
 ('explicit_resume','failed_preflight'):'fixture_admission_denial_after_verified_native_cleanup',
 ('explicit_resume','fresh_preflight'):'explicit_resume_after_actual_native_stopped_and_fresh_preflight',
 ('native_linux_acceptance','inert_lifecycle_and_cleanup'):'actual_inert_lifecycle_with_separately_reviewed_execution_mode_fact',
 ('delegation','missing_controller'):'actual_preflight_against_exclusive_child_with_disabled_subtree_controllers',
 ('delegation','inspected_limits'):'read_actual_admitted_heavy_cgroup_limits',
 ('scheduling_exclusion','retained_trigger_inventory'):'fresh_owner_census_and_computational_ActiveState_observations',
}
OWNED_FIXTURE_CASES=frozenset(OWNED_INJECTIONS)


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
    require(set(INJECTIONS) == expected and set(OWNED_INJECTIONS)==expected, 'control_registry_injection_inventory_changed')
    authoritative = [dict(control=control, scenario=scenario,
        runner='deploy.workload_control_fixture:execute', injection=INJECTIONS[control,scenario],
        observer='durable_gate_and_raw_fixture_before_after', cleanup='generation_owned_fixture_only',
        required_origin='installed_native' if control in HOST else 'disposable_database_or_local_synthetic',
        fixture_origin='synthetic', native_runner='deploy.workload_native_acceptance:execute' if (control,scenario) in NATIVE else None,
        native_case=NATIVE.get((control,scenario)),
        local_runner='deploy.workload_control_linux:execute' if (control,scenario) in LOCAL_CASES else None,
        owned_fixture_runner='deploy.workload_fixture_controls:execute',
        owned_fixture_context=dict(origin='local_linux',installed_native_eligible=False,
            injection=OWNED_INJECTIONS[control,scenario],
            observer='raw_native_kernel_container_and_transaction_reads_with_intended_rejection_causality',
            cleanup='exact_recorded_births_resolved_router_and_gate_empty_owned_cgroups_retained_fingerprints',
            authority='existing_generation_inherited_lock_target_marker_component_review_and_remaining_attempt_budget'),
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
