"""Run the disposable recovery service fault suite in the owned native driver."""
import json
from types import SimpleNamespace
from deploy import native_recovery_acceptance, owned_daemon


def callback(journal,config,data):
    """Nested same-process lease; no shared daemon or staging resources admitted."""
    image=config['image']
    inspected=json.loads(journal.command(['docker','image','inspect',image],kind='read',timeout=30).stdout)
    if not isinstance(inspected,list) or len(inspected)!=1 or inspected[0].get('Id')!=image:
        raise ValueError('Exact preloaded immutable fixture image required')
    root=journal.path.parent/'recovery-service-faults'
    native_recovery_acceptance.run(SimpleNamespace(output=root,image=image,cleanup=False))
    result=owned_daemon.read_private_json(root/'results.json')
    if result.get('native_service_suite_passed') is not True or result.get('cleanup_complete') is not True:
        raise RuntimeError('Native recovery fault suite and cleanup must both pass')
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
        source_sha256=config['acceptance_source_sha256'],evidence_refs=[str(root/'results.json')])
