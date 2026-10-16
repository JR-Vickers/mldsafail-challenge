"""Independent, versioned private-record validation; never accepts worker claims."""
from __future__ import annotations
import hashlib
import json
import math
import base64
import re
from pathlib import Path

SCHEMA = 'mldsafail.cpu-evidence.v1'
STATUSES = {'verified', 'invalid', 'no_answer', 'malformed', 'crash', 'timeout', 'output_limit'}


def audit(record):
    required = {'schema', 'generation', 'boot_id', 'parent_device', 'parent_inode', 'status', 'execution_status', 'verified',
                'cleanup_complete', 'measurement_method', 'counter_before_usec', 'counter_after_usec',
                'authoritative_cpu_usec', 'wall_seconds', 'binding', 'membership', 'input_delivery',
                'termination', 'output_sha256', 'public_input', 'raw_stdout_base64', 'worker_returncode', 'source_artifact', 'accounting_parent', 'observations', 'capture', 'declared_timeout_seconds', 'started_monotonic', 'deadline_monotonic'}
    if not required <= record.keys() or record['schema'] != SCHEMA:
        raise ValueError('Incomplete or unsupported evidence schema')
    if not isinstance(record['generation'], str) or not re.fullmatch(r'[0-9a-f]{32}', record['generation']):
        raise ValueError('Invalid ownership generation identity')
    if any(type(record[key]) is not int or record[key] < 0 for key in ('parent_device', 'parent_inode')):
        raise ValueError('Invalid accounting parent identity')
    if not isinstance(record['boot_id'], str) or not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', record['boot_id']):
        raise ValueError('Missing host boot identity')
    if record['execution_status'] not in {'exited', 'crash', 'timeout', 'output_limit'}:
        raise ValueError('Invalid execution disposition')
    if record['status'] in {'verified', 'no_answer', 'malformed'} and record['execution_status'] != 'exited':
        raise ValueError('Successful output disposition requires ordinary exit')
    if record['status'] in {'crash', 'timeout', 'output_limit'} and record['execution_status'] != record['status']:
        raise ValueError('Failure execution/status disagreement')
    if record['status'] not in STATUSES or type(record['verified']) is not bool:
        raise ValueError('Invalid verifier disposition')
    if record['verified'] != (record['status'] == 'verified'):
        raise ValueError('Verifier/status disagreement')
    if record['cleanup_complete'] is not True or record['termination'] != 'domain_empty':
        raise ValueError('Cleanup was not independently established')
    if record['measurement_method'] != 'cgroup-v2-usage-usec':
        raise ValueError('Unsupported authoritative measurement method')
    for key in ('counter_before_usec', 'counter_after_usec', 'authoritative_cpu_usec'):
        if type(record[key]) is not int or record[key] < 0:
            raise ValueError('Counters must be nonnegative integers')
    if record['counter_after_usec'] - record['counter_before_usec'] != record['authoritative_cpu_usec']:
        raise ValueError('Counter delta mismatch')
    wall = record['wall_seconds']
    if type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0:
        raise ValueError('Invalid wall time')
    binding = record['binding']
    if set(binding) != {'source_sha256', 'supervisor_source_sha256', 'source_commit', 'image', 'epoch', 'host', 'kernel', 'docker'} or not all(binding.values()):
        raise ValueError('Incomplete source/environment binding')
    for key in ('source_sha256', 'supervisor_source_sha256', 'host'):
        if len(binding[key]) != 64 or any(c not in '0123456789abcdef' for c in binding[key]):
            raise ValueError('Invalid identity digest')
    if not re.fullmatch(r'[0-9a-f]{40}', binding['source_commit']):
        raise ValueError('Missing source commit identity')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', binding['image']):
        raise ValueError('Image identity is not immutable')
    memberships = record['membership']
    if not isinstance(memberships, list) or len(memberships) != 1:
        raise ValueError('Exactly one authorized worker membership required')
    member = memberships[0]
    if set(member) != {'worker_pid', 'cgroup'} or type(member['worker_pid']) is not int or member['worker_pid'] <= 0 or not member['cgroup'].startswith('/sys/fs/cgroup/'):
        raise ValueError('Invalid worker membership evidence')
    parent = Path(record['accounting_parent'])
    actual = Path(member['cgroup'])
    if not parent.is_absolute() or not parent.is_relative_to(Path('/sys/fs/cgroup')) or parent == Path('/sys/fs/cgroup'):
        raise ValueError('Invalid dedicated sysfs accounting parent')
    if '..' in parent.parts or '..' in actual.parts or actual == parent or not actual.is_relative_to(parent):
        raise ValueError('Worker is outside authorized accounting parent')
    observations = record['observations']
    if not isinstance(observations, list) or not observations or len(observations) > 10000:
        raise ValueError('Missing bounded accounting observations')
    previous_cpu = record['counter_before_usec']
    previous_time = -math.inf
    for observation in observations:
        if set(observation) != {'usage_usec', 'monotonic'} or type(observation['usage_usec']) is not int or observation['usage_usec'] < previous_cpu or observation['usage_usec'] > record['counter_after_usec']:
            raise ValueError('Invalid accounting observation counter')
        if type(observation['monotonic']) not in (int, float) or not math.isfinite(observation['monotonic']) or observation['monotonic'] < previous_time:
            raise ValueError('Invalid accounting observation time')
        previous_cpu, previous_time = observation['usage_usec'], observation['monotonic']
    if record['input_delivery'] != 'membership_proven_before_delivery':
        raise ValueError('No input-delivery evidence')
    if not re.fullmatch(r'[0-9a-f]{64}', record['output_sha256']):
        raise ValueError('Missing output digest')
    if not isinstance(record['raw_stdout_base64'], str) or len(record['raw_stdout_base64']) > 4 * ((1024 * 1024 + 2) // 3):
        raise ValueError('Encoded stdout exceeds cap')
    raw = base64.b64decode(record['raw_stdout_base64'], validate=True)
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record['output_sha256']:
        raise ValueError('Bounded raw output/digest mismatch')
    capture = record['capture']
    if set(capture) != {'stopped_monotonic', 'overflow', 'cap_bytes', 'stderr_base64', 'stderr_sha256', 'stdout_base64'} or capture['cap_bytes'] != 1024 * 1024:
        raise ValueError('Incomplete bounded stream evidence')
    if not isinstance(capture['stderr_base64'], str) or len(capture['stderr_base64']) > 4 * ((1024 * 1024 + 2) // 3):
        raise ValueError('Encoded stderr exceeds cap')
    if capture['stdout_base64'] != record['raw_stdout_base64']:
        raise ValueError('Capture/output snapshot mismatch')
    stderr = base64.b64decode(capture['stderr_base64'], validate=True)
    if len(stderr) > capture['cap_bytes'] or hashlib.sha256(stderr).hexdigest() != capture['stderr_sha256']:
        raise ValueError('Bounded stderr/digest mismatch')
    for value in (record['started_monotonic'], record['deadline_monotonic'], record['declared_timeout_seconds'], capture['stopped_monotonic']):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Invalid termination clock evidence')
    if record['declared_timeout_seconds'] <= 0 or record['deadline_monotonic'] != record['started_monotonic'] + record['declared_timeout_seconds'] or capture['stopped_monotonic'] < record['started_monotonic']:
        raise ValueError('Inconsistent declared termination deadline')
    if record['execution_status'] == 'timeout' and capture['stopped_monotonic'] < record['deadline_monotonic']:
        raise ValueError('Timeout preceded declared deadline')
    if record['execution_status'] == 'output_limit':
        overflow = capture['overflow']
        if not isinstance(overflow, dict) or set(overflow) != {'stream', 'observed_bytes'} or overflow['stream'] not in {'stdout', 'stderr'} or type(overflow['observed_bytes']) is not int or overflow['observed_bytes'] <= capture['cap_bytes']:
            raise ValueError('Output limit lacks overflow proof')
    elif capture['overflow'] is not None:
        raise ValueError('Overflow/status mismatch')
    from mldsafail.benchmark_v050.models import instance_from_dict
    from mldsafail.benchmark_v050.verify import verify_candidate
    instance = instance_from_dict(json.loads(json.dumps(record['public_input'])))
    try:
        emitted = json.loads(raw)
        candidate = emitted.get('candidate')
        invalid_candidate = candidate is not None and not verify_candidate(instance, candidate)['verified']
    except (ValueError, TypeError, AttributeError):
        invalid_candidate = False
    if invalid_candidate and record['status'] != 'invalid':
        raise ValueError('Invalid emitted candidate cannot become an ordinary penalty')
    if record['status'] in {'verified', 'invalid', 'no_answer', 'malformed'}:
        if record['status'] != 'invalid' and record['worker_returncode'] != 0:
            raise ValueError('Successful output disposition requires zero exit')
        try:
            output = json.loads(raw)
            candidate = output.get('candidate')
            valid = verify_candidate(instance, candidate)['verified']
            disposition = 'verified' if valid else ('no_answer' if candidate is None else 'invalid')
        except (ValueError, TypeError, AttributeError):
            disposition = 'malformed'
        if record['status'] != disposition:
            raise ValueError('Independent candidate disposition mismatch')
    elif record['status'] == 'crash' and record['worker_returncode'] in (None, 0):
        raise ValueError('Crash requires a nonzero worker exit')
    return dict(valid=True, status=record['status'], cpu_usec=record['authoritative_cpu_usec'])


def audit_journal(directory, generation=None):
    directory = Path(directory)
    name = 'journal.json' if generation is None else generation + '-ownership.json'
    if Path(name).name != name:
        raise ValueError('Ownership manifest path escapes private directory')
    journal = json.loads((directory / name).read_text())
    if journal.get('measurement_aborted') or (directory / (journal['generation'] + '-interrupted.json')).exists():
        raise ValueError('Interrupted/aborted generation is never a score')
    if journal.get('state') != 'complete':
        raise ValueError('Ownership generation is unfinished')
    name = journal['evidence_file']
    if Path(name).name != name:
        raise ValueError('Evidence path escapes private directory')
    evidence_path = directory / name
    if evidence_path.is_symlink() or evidence_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Invalid bounded private evidence file')
    payload = evidence_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != journal['evidence_sha256']:
        raise ValueError('Durable evidence digest mismatch')
    record = json.loads(payload)
    for key in ('generation', 'boot_id', 'parent_device', 'parent_inode'):
        if record[key] != journal[key]:
            raise ValueError('Ownership generation mismatch')
    if record['status'] in {'verified', 'no_answer', 'malformed'} or (record['status'] == 'invalid' and record['execution_status'] == 'exited'):
        expected_input = json.dumps({'instance': record['public_input'], 'solver': 'contestant'},
                                    sort_keys=True, separators=(',', ':')).encode()
        deliveries = [entry for entry in journal['mutations'] if entry['operation'] == 'input_delivered']
        if len(deliveries) != 1 or deliveries[0].get('bytes') != len(expected_input) or deliveries[0].get('sha256') != hashlib.sha256(expected_input).hexdigest():
            raise ValueError('Missing synchronized exact public-input delivery proof')
    source = record['source_artifact']
    if Path(source).name != source or not source.startswith(record['generation'] + '-source'):
        raise ValueError('Source artifact identity mismatch')
    root = directory / source
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("Source artifact path contains symlinks")
    # Reuse the frozen approved Python source validator without changing it.
    files = sorted(root.rglob('*.py'))
    if not files or len(files) > 128 or any(path.is_symlink() for path in root.rglob('*')) or sum(path.stat().st_size for path in files) > 2 * 1024 * 1024:
        raise ValueError('Invalid bounded source artifact')
    if not (root / 'solver.py').is_file() or any(path.is_file() and path.suffix != '.py' for path in root.rglob('*')):
        raise ValueError('Only approved Python source artifacts accepted')
    digest = hashlib.sha256(json.dumps({path.relative_to(root).as_posix():
        dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if digest != record['binding']['source_sha256']:
        raise ValueError('Source artifact digest mismatch')
    return audit(record)


def case_cost(records):
    """Exactly-three policy for isolated integration; never replace failures."""
    if len(records) != 3:
        raise ValueError('Exactly three measured invocations required')
    decisions = [audit(record) for record in records]
    if len({record['generation'] for record in records}) != 3:
        raise ValueError('Repeated ownership generation')
    binding_keys = ('source_sha256', 'supervisor_source_sha256', 'source_commit', 'image', 'epoch', 'host', 'kernel', 'docker')
    binding = records[0]['binding']
    if any(any(record['binding'][key] != binding[key] for key in binding_keys) or
           (record['public_input'] != records[0]['public_input'] or record['boot_id'] != records[0]['boot_id']) for record in records[1:]):
        raise ValueError('Case measurements have inconsistent provenance/input')
    if any(result['status'] == 'invalid' for result in decisions):
        return {'eligible': False, 'cost_usec': None}
    if any(result['status'] != 'verified' for result in decisions):
        return {'eligible': True, 'cost_usec': 60_000_000, 'penalized': True}
    import statistics
    return {'eligible': True, 'cost_usec': max(1, statistics.median(result['cpu_usec'] for result in decisions)),
            'penalized': False}
