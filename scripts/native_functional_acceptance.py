"""Private functional probes on an admitted disposable daemon, never staging."""
import argparse
import hashlib
from pathlib import Path

from deploy import owned_daemon
from research.cpu_measurement import native_driver
from scripts import native_recovery_rpc_loss


def callback(driver, config, data):
    review = owned_daemon.read_private_json(config['review_packet'])
    rpc_sha = hashlib.sha256(Path(native_recovery_rpc_loss.__file__).read_bytes()).hexdigest()
    if review.get('rpc_callback_source_sha256') != rpc_sha:
        raise RuntimeError('Separate exact RPC callback source review required')
    # Complement startup's synthetic admission flag with a real already-admitted
    # generation. The daemon and its socket must remain unchanged by retirement.
    manifest = owned_daemon.load_manifest(data['manifest_path'])
    identity = owned_daemon._socket_identity(Path(data['socket']))
    proof = owned_daemon.failed_startup_barrier(data, evidence_directory=driver.path.parent,
                                               attempt_id=data['id'] + '-admitted')
    if (proof['startup_shutdown_proven'] or not any('Never-admitted startup proof' in row.get('error', '')
                                                   for row in proof['errors'])):
        raise RuntimeError('Actual admitted generation retirement fence not reached')
    if owned_daemon._socket_identity(Path(data['socket'])) != identity:
        raise RuntimeError('Admitted socket changed during retirement rejection')
    owned_daemon.verify_environment(manifest, measurement_parent=Path(data['worker_parent']))
    target = driver.path.parent / 'admitted-retirement-rejection.json'
    admitted = dict(passed=True, native_executed=True, outer_cleanup_required=True,
        registered_daemon_epoch=manifest['epoch'], image_admitted=config['image'] in data['loaded_images'],
        socket_unchanged=True, proof=proof)
    try:
        owned_daemon.publish(target, admitted)
    except BaseException as original:
        admitted.update(passed=False, publication_failed=True)
        try:
            owned_daemon.publish(target, admitted)
        except BaseException as retry:
            original.add_note('Negative admitted-fence publication: ' + type(retry).__name__)
        raise
    result = native_recovery_rpc_loss.callback(driver, config, data)
    if result.get('passed') is not True:
        raise RuntimeError('RPC functional acceptance failed')
    result['evidence_refs'].append(str(target))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),
                          Path(__file__).resolve().parents[1], acceptance=callback,
                          daemon_kind='owned')
