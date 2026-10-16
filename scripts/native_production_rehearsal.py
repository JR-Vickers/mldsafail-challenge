"""Reviewed combined fresh-epoch/service-only disposable production protocol.

All callbacks share one owned daemon, preserving frozen 0.5.0 host identity.
No staging evidence, production OAuth, public listeners, backups or 0.6.0 adoption.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

from deploy import owned_daemon
from research.cpu_measurement import native_driver
from scripts import native_production_epoch, production_rehearsal


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_sources(repository, manifest):
    """Bind actual source/import closure, rejecting unexpected executable inputs."""
    repository = owned_daemon._canonical(repository)
    if subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True, timeout=15).strip() != manifest['source_commit']:
        raise ValueError('Exact frozen operator source required')
    actual = {}
    for path in repository.rglob('*'):
        relative = path.relative_to(repository)
        if relative.parts[0] == '.git':
            continue
        if path.is_symlink():
            raise ValueError('Operator source links forbidden')
        if path.is_file():
            actual[relative.as_posix()] = digest(path)
    if actual != manifest['source_files_sha256']:
        raise ValueError('Complete operator source/configuration inventory changed')
    for name in ('scripts.production_rehearsal_exercises', 'scripts.production_rehearsal_monitor_load',
                 'scripts.hosted_vps_failure_driver', 'scripts.hosted_vps_failure_probe',
                 'scripts.staging_read_load', 'deploy.host_checks', 'deploy.render_operator_units'):
        importlib.import_module(name)
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] not in {'deploy', 'scripts', 'research', 'mldsafail'} or module is None:
            continue
        path = getattr(module, '__file__', None)
        if path:
            resolved = Path(path).resolve()
            if not resolved.is_relative_to(repository) or str(resolved.relative_to(repository)) not in actual:
                raise ValueError('Operator imports unexpected helper source')
        elif hasattr(module, '__path__') and any(not Path(value).resolve().is_relative_to(repository) for value in module.__path__):
            raise ValueError('Operator namespace resolves outside frozen source')


def preflight(config, repository):
    path = Path(config['state_root']).parent / 'production-rehearsal-protocol.json'
    protocol = owned_daemon.read_private_json(path)
    review = owned_daemon.read_private_json(config['review_packet'])
    if (protocol.get('schema') != 'mldsafail.production-rehearsal-native.v1'
            or protocol.get('benchmark_version') != '0.5.0'
            or review.get('production_rehearsal_protocol_sha256') != digest(path)):
        raise ValueError('Exact independently reviewed rehearsal protocol required')
    epoch_path = path.with_name('production-epoch-protocol.json')
    epoch_protocol = owned_daemon.read_private_json(epoch_path)
    if (set(epoch_protocol) != {'schema', 'benchmark_version', 'worker', 'coordinator', 'purpose'}
            or epoch_protocol.get('schema') != 'mldsafail.production-epoch.v1'
            or epoch_protocol.get('benchmark_version') != '0.5.0'
            or epoch_protocol.get('purpose') != 'disposable_rehearsal_only'
            or epoch_protocol.get('worker') != protocol['rehearsal']['images']['worker']
            or epoch_protocol.get('coordinator') != protocol['rehearsal']['images']['coordinator']
            or review.get('production_epoch_protocol_sha256') != digest(epoch_path)):
        raise ValueError('Exact coherent epoch protocol required before provisioning')
    for field in ('source_manifest', 'release_manifest', 'rollback_manifest'):
        file = Path(protocol['rehearsal'][field])
        owned_daemon.read_private_json(file, cap=4*1024*1024)
        if digest(file) != protocol[field + '_sha256']:
            raise ValueError('Private rehearsal manifest identity changed')
    manifest = owned_daemon.read_private_json(protocol['rehearsal']['source_manifest'], cap=4*1024*1024)
    verify_sources(repository, manifest)
    if manifest['source_commit'] != config['source_commit']:
        raise ValueError('Operator source differs from driver source')
    supplied = dict(protocol['rehearsal'], run_directory=str(Path(config['state_root']) / 'production'),
                    evaluator_root=str(Path(config['state_root']) / 'rehearsal-epoch/evaluator'),
                    docker_socket='/PLACEHOLDER_NOT_USED_BEFORE_NATIVE_ADMISSION',
                    operator_unit=config['operator_unit'], operator_parent=config['operator_parent'])
    production_rehearsal.validate(supplied)
    return protocol, supplied


def callback(journal, config, data):
    repository = Path(__file__).resolve().parents[1]
    protocol, supplied = preflight(config, repository)
    if set(supplied['images'].values()) - set(data['loaded_images']):
        raise ValueError('All exact rehearsal images must be imported from retained archives')
    supplied['docker_socket'] = data['socket']
    production_rehearsal.validate(supplied)
    # Fetch only the repository-controlled reviewed tiny fixture commit, then
    # compare every tracked byte before any scientific epoch or submission.
    fixture = journal.path.parent / 'reviewed-fixture'
    journal.command(['git', 'init', str(fixture)], kind='fixture_initialization')
    journal.command(['git', '-C', str(fixture), '-c', 'credential.helper=', 'fetch', '--depth=1',
                     supplied['fixture_repository'], supplied['fixture_commit']], kind='fixture_acquisition', timeout=60)
    journal.command(['git', '-C', str(fixture), 'checkout', '--detach', 'FETCH_HEAD'], kind='fixture_checkout')
    names = journal.command(['git', '-C', str(fixture), 'ls-files']).stdout.decode().splitlines()
    hashes = {}
    for name in names:
        path = fixture / name
        if path.is_symlink() or not path.is_file() or path.suffix != '.py':
            raise ValueError('Only reviewed Python tiny fixtures permitted')
        hashes[name] = digest(path)
    if hashes != protocol['fixture_files_sha256']:
        raise ValueError('Repository-controlled fixture bytes differ')
    owned_daemon.publish(journal.path.parent / 'fixture-source-audit.json', dict(passed=True, files_sha256=hashes))
    # No retry, fallback epoch or seed selection. Failure stops dependent execution.
    native_production_epoch.callback(journal, config, data)
    owned_daemon.publish(journal.path.parent / 'production-effective-config.json', supplied)
    result = production_rehearsal.execute(supplied)
    if result.get('complete') is not True or result.get('cleanup_complete') is not True:
        raise RuntimeError('Production rehearsal or cleanup remains incomplete')
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
        source_sha256=config['acceptance_source_sha256'], evidence_refs=[
            'fixture-source-audit.json', 'rehearsal-epoch/report.json', 'production/report.json',
            'production/journal.json'],)


def terminal_cleanup(path, controller_config, repository):
    """Retire interrupted nested monitoring/clients without restarting the daemon."""
    from deploy import owned_client
    from deploy.recovery_daemon import provision_lock
    from scripts.production_rehearsal_monitor_load import stop_monitors
    review = owned_daemon.read_private_json(controller_config['review_packet'])
    metadata_path = Path(review['operator_source_manifest'])
    if (review.get('production_terminal_cleanup_review_passed') is not True
            or review.get('acceptance_source_sha256') != digest(__file__)
            or digest(metadata_path) != review.get('operator_source_manifest_sha256')):
        raise ValueError('Exact independently reviewed terminal controller required')
    verify_sources(repository, owned_daemon.read_private_json(metadata_path, cap=4*1024*1024))
    native_driver.validate(controller_config, repository)
    path = owned_daemon._canonical(path)
    data = owned_daemon.read_private_json(path, cap=4*1024*1024)
    if data.get('schema') != 'mldsafail.cpu-native-driver-state.v1':
        raise ValueError('Exact retained native driver journal required')
    root = path.parent / 'production'
    receipt = dict(schema='mldsafail.production-terminal-cleanup.v1', complete=False,
                   authoritative_result_available=False, resources_preserved_offline=True, errors=[])
    output = path.parent / ('production-terminal-' + __import__('uuid').uuid4().hex + '.json')
    owned_daemon.publish(output, receipt)
    with provision_lock(data['provisioning']):
        if owned_daemon.read_private_json(path, cap=4*1024*1024) != data:
            raise RuntimeError('Interrupted driver changed during terminal locking')
        nested = None
        env = dict(os.environ, DOCKER_HOST='unix://' + data['socket'],
                   MLDSAFAIL_OWNED_CLIENT_ROOT=str(root))
        if root.exists():
            try:
                production_rehearsal.cleanup_authority(dict(run_directory=str(root), docker_socket=data['socket']))
                nested = owned_daemon.read_private_json(root / 'journal.json', cap=4*1024*1024)
                if nested['dedicated_daemon']['provisioning'] != data['provisioning']:
                    raise RuntimeError('Nested application daemon authority differs')
                stop_monitors(root, env)
            except Exception as error:
                receipt['errors'].append(dict(step='nested_monitor_authority', error_type=type(error).__name__))
    try:
        daemon_receipt = native_driver.cleanup_state(path, controller_config=controller_config, repository=repository)
        receipt['daemon_cleanup'] = daemon_receipt
        if not daemon_receipt.get('cleanup_complete') or not daemon_receipt.get('daemon_barrier', {}).get('shutdown_proven'):
            raise RuntimeError('Positive terminal daemon/worker barrier required')
        if nested is not None:
            for client_path in [root / 'clients.json', *root.glob('cleanup-clients-*.json')]:
                if not client_path.exists(): continue
                from deploy.recovery import private_file
                clients = json.loads(private_file(client_path).read_text())
                if not isinstance(clients, list):
                    raise ValueError('Nested client authority is malformed')
                for entry in clients: owned_client.stop(entry)
            if receipt['errors']:
                raise RuntimeError('Nested monitor cleanup remains unresolved')
            nested = owned_daemon.read_private_json(root / 'journal.json', cap=4*1024*1024)
            nested.update(cleanup_complete=True, terminal_cleanup=True, resources_preserved_offline=True)
            owned_daemon.publish(root / 'journal.json', nested)
        receipt['complete'] = not receipt['errors']
    except Exception as error:
        receipt['errors'].append(dict(step='terminal_settlement', error_type=type(error).__name__))
    finally:
        owned_daemon.publish(output, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--config', type=Path)
    group.add_argument('--cleanup-state', type=Path)
    parser.add_argument('--controller-config', type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    if args.cleanup_state:
        if args.controller_config is None: parser.error('Terminal cleanup requires a new controller configuration')
        receipt = terminal_cleanup(args.cleanup_state, owned_daemon.read_private_json(args.controller_config), repository)
        raise SystemExit(0 if receipt['complete'] else 1)
    config = owned_daemon.read_private_json(args.config)
    preflight(config, repository)  # Validate complete imported/configuration closure before provisioning.
    native_driver.execute(config, repository, acceptance=callback, daemon_kind='owned')


if __name__ == '__main__':
    main()
