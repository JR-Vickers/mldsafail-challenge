"""Heavy-subtree source preparation/evaluation/audit. Never connects to a DB."""
from __future__ import annotations

import argparse
import hashlib
import errno
import os
from pathlib import Path, PurePosixPath

from mldsafail.evaluator.envelope import sign_envelope
from mldsafail.evaluator.native_workload import private_json, publish, require
from mldsafail.web.services import DomainError


def participant(state, config, output, checkpoint):
    from mldsafail.evaluator.source import acquire_commit, validate_eligible_source, SourcePolicy
    from mldsafail.evaluator.mlwe import HostedMLWE, solver_directory
    from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
    from mldsafail.benchmark_v050.execution import solver_snapshot
    from mldsafail.benchmark_v050.models import digest
    reference = state['reference']
    require(set(reference) == {'job_id', 'attempt_id', 'submission_id', 'attempt_number',
            'repository_url', 'commit_sha', 'solver_path', 'identity', 'owner'}, 'controller_reference_fields')
    require(reference['identity'] == config['identity'], 'controller_cohort_changed')
    relative = reference['solver_path']
    if (not isinstance(relative, str) or PurePosixPath(relative).is_absolute() or
            any(part.startswith('.') or not part for part in relative.split('/'))):
        raise DomainError('invalid_solver_path', 'Invalid solver directory.')
    if not reference['repository_url'].startswith('https://github.com/'):
        raise DomainError('invalid_repository', 'Hosted MLWE requires a public GitHub repository.')
    checkpoint()
    checkout = acquire_commit(reference['repository_url'], reference['commit_sha'], output/'source', sparse_paths=(relative,))
    validate_eligible_source(checkout, SourcePolicy(max_eligible_bytes=MAX_SERIALIZED_BYTES),
                             eligible_roots=(PurePosixPath(relative),))
    source_digest = digest(solver_snapshot(solver_directory(checkout, relative), output/'snapshot'))
    checkpoint()
    hosted = HostedMLWE(Path(config['epoch_path']), config['worker_image'], config['identity']['epoch_id'])
    require(hosted.evaluator_fingerprint == config['identity']['evaluator_fingerprint'], 'controller_fingerprint_changed')
    envelope = hosted.evaluate(output/'snapshot', output/'evaluation',
                {**config['identity'], 'source_digest': source_digest},
                Path(config['signing_key']).read_bytes(), checkpoint)
    return dict(status='evaluated', envelope=envelope, source_digest=source_digest)


def administrative(role, config, output, checkpoint):
    # These functions and their worker command bytes remain frozen. Paths are
    # installation configuration, never an operator-supplied command vector.
    from mldsafail.benchmark_v050 import cli, evidence as ev
    from mldsafail.benchmark_v050.execution import environment
    checkpoint()
    epoch_path = output/'epoch' if (output/'epoch').exists() else Path(config['epoch_path'])
    if role == 'create':
        result = cli.create_epoch(output/'epoch')
    elif role == 'reference':
        epoch, reference = ev.audit_epoch(epoch_path)
        require(environment() == epoch['environment'], 'administrative_environment_changed')
        manifest, rows = cli.evaluate(output/'reference', epoch['cases'], epoch['environment'], 'primal-lll', epoch)
        result = ev.summary(manifest, rows, reference)
    elif role == 'audit':
        manifest, _ = ev.audit_epoch(epoch_path)
        result = dict(epoch_id=manifest['id'], verified=True, epoch_path=str(epoch_path), environment=manifest['environment'],
            manifest_sha256=hashlib.sha256((epoch_path/'manifest.json').read_bytes()).hexdigest(),
            reference_sha256=hashlib.sha256((epoch_path/'reference-costs.json').read_bytes()).hexdigest(),
            seal_sha256=hashlib.sha256((epoch_path/'COMPLETE.json').read_bytes()).hexdigest())
    else:
        raise ValueError('controller_role_invalid')
    checkpoint()
    return dict(status='administrative_complete', result=result)


def run(request):
    config = private_json(request['configuration'])
    require(set(config) == {'native_configuration','identity','epoch_path','worker_image','signing_key'}, 'controller_configuration_fields')
    state, role = request['state'], request['role']
    native = private_json(config['native_configuration'])
    output = Path(native['output'])/state['workload_id']
    journal = output/'router'; journal.mkdir(mode=0o700, exist_ok=True)
    router = dict(operation_id=state['workload_id'], parent='mldsafail-heavy-'+state['workload_id']+'.slice',
                  image=native['worker']['image'], configuration=native['worker']['configuration'],
                  platform_manifest=native['worker']['platform_manifest'], journal=str(journal),
                  daemon=native['daemon_id'], solver_root=str(output), label='org.mldsafail.workload',
                  native_configuration=config['native_configuration'])
    publish(output/'router.json', router)
    os.environ['MLDSAFAIL_ROUTER_CONFIG'] = str(output/'router.json')
    require(Path(native['router']).name == 'docker', 'controller_router_name')
    os.environ['PATH'] = str(Path(native['router']).parent)+':'+os.environ.get('PATH', '')
    def checkpoint():
        current = private_json(Path(native['root'])/'workload.json')
        require(current['workload_id'] == state['workload_id'] and not current['paused'] and
                current['phase'] in ('launch_intent', 'running'), 'controller_authority_lost')
    binding = dict(workload_id=state['workload_id'], role=role, reference=state['reference'])
    try:
        if role == 'inert':
            from deploy.workload_inert import exercise
            result = exercise(state, native, output, checkpoint)
        else:
            result = participant(state, config, output, checkpoint) if role == 'participant' else administrative(role, config, output, checkpoint)
    except DomainError as error:
        result = dict(status='rejected', code=error.code)
    except OSError as error:
        if error.errno in (errno.EFBIG,errno.ENOSPC,errno.EDQUOT):
            publish(Path(native['root'])/(state['workload_id']+'.violation.json'),dict(workload_id=state['workload_id'],reason='output_budget_exhausted'))
        result = dict(status='infrastructure_failed',code='controller_failure')
    except Exception:
        result = dict(status='infrastructure_failed', code='controller_failure')
    result = sign_envelope(dict(binding=binding, **result), Path(config['signing_key']).read_bytes())
    publish(output/(role+'.result.json'), result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args(argv)
    run(private_json(args.request))
    return 0


if __name__ == '__main__': raise SystemExit(main())
