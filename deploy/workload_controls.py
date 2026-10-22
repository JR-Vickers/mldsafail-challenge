"""Control-specific acceptance proof shapes, shared by validator and fixture runner."""
from mldsafail.evaluator.workload import ResourcePolicy

# Each case names an actual failure injection and the resulting measurable state.
# Passing a generic 'verified' checkbox does not satisfy any of these contracts.
SCENARIOS = {
    'shared_host_gate': {'cross_database_and_admin': {'callers': 3, 'acquired': 1, 'overlap': 0}},
    'coordinator_routing': {'deferred_admission': {'attempts_before': 0, 'attempts_after': 0},
                            'result_after_cleanup': {'resources_at_commit': 0, 'results': 1}},
    'administrative_routing': {'host_gate_before_fence': {'host_gate_order': 1, 'fence_order': 2},
                               'queued_blocks_admin': {'queued': 1, 'controller_launches': 0}},
    'zero_pending_fence': {'queued_claimed_running': {'blocked_states': ['queued', 'claimed', 'running'], 'launches': 0}},
    'inspected_births': {'daemon_replacement': {'replacement_kills': 0, 'paused': True},
                        'container_restart': {'results': 0, 'paused': True}},
    'durable_launch_intent': {'lost_create_ack': {'create_calls': 1, 'replay_create_calls': 0},
                              'lost_start_ack': {'start_calls': 1, 'replay_start_calls': 0}},
    'common_cgroup': {'controller_worker_descendants': {'outside_heavy': 0, 'inspected_processes': 3}},
    'ancestor_limits': {'parent_oom': {'oom_delta': 1, 'results': 0, 'paused': True},
                        'ancestor_limit_change': {'results': 0, 'paused': True}},
    'continuous_monitor': {'stuck_control_io': {'monitor_continued': True, 'results': 0},
                           'stale_sample': {'results': 0, 'paused': True}},
    'bounded_output': {'log_exhaustion': {'results': 0, 'paused': True},
                       'generation_quota_exhaustion': {'results': 0, 'paused': True}},
    'verified_cleanup': {'surviving_worker': {'ownership_released': False, 'results': 0},
                         'empty_scope_and_absent_containers': {'populated': 0, 'containers': 0}},
    'abnormal_exit': {'controller_disconnect': {'results':0,'paused':True}},
    'persistent_pause': {'supervisor_sigkill': {'restart_launches': 0, 'paused': True}},
    'explicit_resume': {'failed_preflight': {'resumed': False}, 'fresh_preflight': {'resources': 0, 'resumed': True}},
    'native_linux_acceptance': {'inert_lifecycle_and_cleanup': {'emulated': False, 'fixture_resources_after': 0,
                                                              'retained_services_unchanged': True}},
    'delegation': {'missing_controller': {'attempts': 0, 'launches': 0},
                   'inspected_limits': {'cpu_max': '100000 100000', 'pids_max': 448, 'swap_max': 0}},
    'scheduling_exclusion': {'retained_trigger_inventory': {'unclassified': 0, 'unexpected_active': 0}},
}


def validate_case(control, case, runtime, *, require):
    expected = SCENARIOS[control][case['name']]
    observations = case['observations']
    require(all(type(observations.get(key)) is type(value) and observations[key] == value
                for key, value in expected.items()))
    identities = case.get('identities', {})
    require(identities.get('boot_id') and identities.get('daemon_id'))
    require(identities.get('workload_id') and len(identities['workload_id']) == 32)
    scope = identities.get('scope', {})
    require(isinstance(scope.get('path'), str) and scope['path'].startswith(runtime['cgroup']+'/'))
    require(type(scope.get('device')) is int and type(scope.get('inode')) is int and scope['inode'] > 0)
    trace = case.get('trace', [])
    require(len(trace) >= 2 and trace[0].get('event') == 'injection' and trace[-1].get('event') == 'observation')
    require(all(type(row.get('monotonic_ns')) is int and row['monotonic_ns'] >= 0 for row in trace))
    require([row['monotonic_ns'] for row in trace] == sorted(row['monotonic_ns'] for row in trace))
    if control == 'continuous_monitor':
        require(type(observations.get('abort_latency_ms')) in (int, float) and 0 <= observations['abort_latency_ms'] <= 1100)
        require(type(observations.get('control_read_ms')) in (int, float) and 0 <= observations['control_read_ms'] <= 850)
    if control == 'bounded_output':
        require(observations.get('enforcement') == 'kernel')
        require(type(observations.get('log_rlimit_bytes')) is int and 0<observations['log_rlimit_bytes']<=ResourcePolicy().log_max//2)
        require(type(observations.get('max_log_streams')) is int and 0<observations['max_log_streams']<=8 and
                observations['max_log_streams']*observations['log_rlimit_bytes']<=ResourcePolicy().log_max)
        require(type(observations.get('generation_filesystem_bytes')) is int and
                0 < observations['generation_filesystem_bytes'] <= ResourcePolicy().generation_max)
    if control == 'common_cgroup':
        processes = identities.get('processes', [])
        require(len(processes) >= 3 and len({row.get('pid') for row in processes}) == len(processes))
        require(all(type(row.get('pid')) is int and row['pid'] > 0 and type(row.get('start_ticks')) is int and
                    row['start_ticks'] > 0 and row.get('cgroup', '').startswith(scope['path']+'/') for row in processes))
    if control == 'native_linux_acceptance':
        require(observations.get('platform') == 'linux')
        require(isinstance(observations.get('retained_before'), dict) and bool(observations['retained_before']))
        require(observations['retained_before'] == observations.get('retained_after'))
