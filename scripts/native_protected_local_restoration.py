"""Owned native callback for a sealed local database/epoch/evidence recovery set."""
import hashlib
import json
import os
from pathlib import Path
from deploy.recovery import private_file
from deploy.recovery_journal import Journal, atomic_json
from deploy.restore_recovery import verify
from deploy.native_recovery_powerloss import receipt


def callback(driver, config, data):
    protocol = json.loads(private_file(config['acceptance_protocol']).read_text())
    required = {'schema', 'recovery_set', 'manifest_sha256', 'epoch_id', 'result_count', 'coordinator_image'}
    if set(protocol) != required or protocol['schema'] != 'mldsafail.local-protected-restore-protocol.v1':
        raise ValueError('Exact protected local restoration protocol required')
    loaded = data.get('loaded_images')
    if not isinstance(loaded, list) or config['image'] not in loaded or protocol['coordinator_image'] not in loaded:
        raise ValueError('Both restore images require driver-bound loaded archive provenance')
    root = Path(protocol['recovery_set'])
    manifest = private_file(root / 'recovery.json')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != protocol['manifest_sha256']:
        raise ValueError('Sealed recovery manifest identity mismatch')
    if type(protocol['result_count']) is not int or protocol['result_count'] < 1:
        raise ValueError('At least one accepted result must be restored and audited')
    output = driver.path.parent / 'protected-local-restoration'
    output.mkdir(mode=0o700)
    operation = Journal(output / 'operation.json', {})
    result = {'schema': 'mldsafail.protected-local-restoration.v1', 'passed': False,
              'native_executed': False, 'offhost_verified': False, 'owner_custody_verified': False}
    original = None
    try:
        restored = verify({'owned_daemon_manifest': os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST'],
            'postgres_image': config['image'], 'coordinator_image': protocol['coordinator_image']},
            root, operation=operation, local_set=True)
        if restored['epoch_id'] != protocol['epoch_id'] or restored['result_count'] != protocol['result_count']:
            raise ValueError('Protected restoration epoch/result inventory mismatch')
        result.update(restored, native_executed=True)
    except BaseException as error:
        original = error
    finally:
        try: operation.cleanup()
        except BaseException as error:
            if original is None: original = error
            else: original.add_note('Independent cleanup: ' + type(error).__name__)
        result['cleanup_complete'] = operation.data.get('cleanup_complete') is True
        result['passed'] = original is None and result['cleanup_complete'] and result['native_executed']
        try: atomic_json(output / 'result.json', result)
        except BaseException as error:
            result['passed'] = False
            if original is None: original = error
            else: original.add_note('Publication: ' + type(error).__name__)
            try: atomic_json(output / 'result.json', result)
            except BaseException as retry: original.add_note('Negative publication: ' + type(retry).__name__)
        if original is not None: raise original
    return receipt(config, [str(output / 'result.json'), str(output / 'operation.json')])
