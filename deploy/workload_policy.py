"""Versioned operational evidence gate; never manufactures capacity measurements."""
from dataclasses import asdict
import hashlib
import json
import os
import stat
from pathlib import Path
import time

from mldsafail.evaluator.workload import ResourcePolicy
from deploy.workload_controls import SCENARIOS, validate_case

CONTROLS = frozenset({
    'shared_host_gate', 'coordinator_routing', 'administrative_routing',
    'zero_pending_fence', 'inspected_births', 'durable_launch_intent',
    'common_cgroup', 'ancestor_limits', 'continuous_monitor', 'bounded_output',
    'verified_cleanup', 'persistent_pause', 'explicit_resume', 'native_linux_acceptance',
    'delegation', 'scheduling_exclusion',
})


def require(value):
    if not value: raise ValueError('operational_controls_unverified')


def policy_bytes():
    return json.dumps(asdict(ResourcePolicy()), sort_keys=True).encode()


def validate_controls(packet, *, execution=False, now=None):
    now = time.time() if now is None else now
    require(type(packet) is dict and type(packet.get('supervisor_runtime')) is dict)
    require(configuration_digest(packet.get('configurations')) == packet['supervisor_runtime'].get('configuration_sha256'))
    require(packet.get('capacity_disposition') == 'unmeasured_capacity')
    require(packet.get('resource_policy_sha256') == hashlib.sha256(policy_bytes()).hexdigest())
    evidence_path = Path(packet['operational_receipt'])
    data = evidence_path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == packet['operational_receipt_sha256'])
    evidence = json.loads(data)
    require(evidence.get('schema') == 'mldsafail.operational-controls.v1')
    require(evidence.get('host') == packet['hostname'] and evidence.get('source') == packet['source'])
    require(evidence.get('operation_id') == packet['operation_id'])
    require(evidence.get('resource_policy_sha256') == packet['resource_policy_sha256'])
    require(evidence.get('runtime') == packet['supervisor_runtime'])
    require(set(evidence.get('controls', {})) == CONTROLS)
    require(all(value is True for value in evidence['controls'].values()))
    require(evidence.get('reviewed_by') and evidence.get('reviewed_by') != evidence.get('executed_by') and evidence.get('blockers') == [])
    require(0 <= now - evidence.get('prepared_at', 0) < 86400)
    if execution: require(0 <= now - evidence.get('observed_at', 0) < 300)
    runtime = evidence['runtime']
    require(set(runtime) == {'boot_id', 'daemon_id', 'supervisor_sha256', 'adapter_sha256',
                             'evaluator_fingerprint', 'cgroup', 'socket', 'configuration_sha256', 'release_sha256',
                             'worker_image', 'controller_image'})
    require(all(isinstance(value, str) and value for value in runtime.values()))
    import re
    require(all(re.fullmatch('sha256:[a-f0-9]{64}', runtime[key]) for key in ('worker_image', 'controller_image')))
    for key in ('supervisor_sha256', 'adapter_sha256', 'evaluator_fingerprint', 'configuration_sha256', 'release_sha256'):
        import re
        require(re.fullmatch('[a-f0-9]{64}', runtime[key]))
    # Every assertion is bound to retained evidence bytes, not just a checkbox.
    require(set(evidence.get('evidence', {})) == CONTROLS)
    for control, binding in evidence['evidence'].items():
        relative = Path(binding['path'])
        require(not relative.is_absolute() and '..' not in relative.parts)
        artifact_path = evidence_path.parent / relative
        require(not any(p.is_symlink() for p in (artifact_path, *artifact_path.parents)))
        artifact_bytes = artifact_path.read_bytes()
        require(hashlib.sha256(artifact_bytes).hexdigest() == binding['sha256'])
        artifact = json.loads(artifact_bytes)
        require(artifact.get('schema') == 'mldsafail.control-evidence.v1')
        require(artifact.get('control') == control and artifact.get('outcome') == 'passed')
        require(artifact.get('host') == packet['hostname'])
        require(artifact.get('source') == packet['source'])
        require(artifact.get('resource_policy_sha256') == packet['resource_policy_sha256'])
        # Native acceptance is enduring for these exact installed bytes; live
        # operation freshness remains enforced by the enclosing receipt above.
        require(artifact.get('runtime') == {
            key: runtime[key] for key in ('supervisor_sha256', 'adapter_sha256', 'evaluator_fingerprint', 'configuration_sha256', 'release_sha256', 'worker_image', 'controller_image')})
        require(isinstance(artifact.get('cases'), list) and bool(artifact['cases']))
        names = set()
        for case in artifact['cases']:
            require(type(case) is dict and isinstance(case.get('name'), str) and bool(case['name']))
            require(case['name'] not in names and case.get('outcome') == 'passed')
            names.add(case['name'])
            require(case['name'] in SCENARIOS[control])
            require(isinstance(case.get('observations'), dict) and bool(case['observations']))
            validate_case(control, case, runtime, require=require)
            if control != 'native_linux_acceptance':
                require(case['identities']['boot_id'] == runtime['boot_id'] and case['identities']['daemon_id'] == runtime['daemon_id'])
        require(names == set(SCENARIOS[control]))
        require(isinstance(artifact.get('reviewed_by'), str) and bool(artifact['reviewed_by']))
        require(isinstance(artifact.get('executed_by'), str) and bool(artifact['executed_by']))
        require(artifact['reviewed_by'] != artifact['executed_by'])


def authorize(packet_bytes, authorization, *, now=None):
    """Separate owner authority binds exact serialized operation packet bytes."""
    now = time.time() if now is None else now
    packet = json.loads(packet_bytes)
    require(packet.get('schema') == 'mldsafail.production-operation.v4')
    require(packet.get('state') == 'execution_ready')
    require(authorization.get('purpose') == 'production_unmeasured_operation_only')
    require(authorization.get('authorized_by') == 'owner')
    require(authorization.get('operation_id') == packet['operation_id'])
    native_config = json.loads(Path(packet['configurations']['native']['path']).read_bytes())
    require(authorization.get('native_configuration_sha256') == hashlib.sha256(json.dumps(native_config, sort_keys=True).encode()).hexdigest())
    require(authorization.get('roles') == packet.get('roles', []))
    require(type(authorization.get('lifetime_seconds')) is int and 0 < authorization['lifetime_seconds'] <= 9000)
    require(authorization.get('packet_sha256') == hashlib.sha256(packet_bytes).hexdigest())
    require(0 <= now - authorization.get('time', 0) < 300)
    review_data = Path(authorization['review_file']).read_bytes()
    require(hashlib.sha256(review_data).hexdigest() == authorization['review_sha256'])
    review = json.loads(review_data)
    require(review.get('packet_sha256') == authorization['packet_sha256'] and review.get('decision') == 'approved')
    require(isinstance(review.get('reviewed_by'), str) and review['reviewed_by'] not in ('', 'implementation_agent') and
            review['reviewed_by'] != review.get('implemented_by'))
    validate_controls(packet, execution=True, now=now)


def configuration_digest(configurations):
    require(type(configurations) is dict and set(configurations) == {'supervisor', 'native', 'controller'})
    require(len({binding['path'] for binding in configurations.values()}) == 3)
    for binding in configurations.values():
        require(type(binding) is dict and set(binding) == {'path', 'sha256'})
        path = Path(binding['path'])
        require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)))
        info=path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and not info.st_mode&0o077 and info.st_size<=1024**2)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == binding['sha256'])
    return hashlib.sha256(json.dumps(configurations, sort_keys=True).encode()).hexdigest()
