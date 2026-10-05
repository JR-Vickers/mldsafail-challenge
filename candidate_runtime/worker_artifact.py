"""Bind an already gated worker independently of private application source."""
import re
from deploy import owned_daemon
from research.mlwe_v060_preparation.native_acceptance import require_prerequisites


def accepted_worker(artifact_path,prerequisite_path,*,expected_image,expected_archive_sha256,supervisor_source_sha256,loaded_images):
    artifact=owned_daemon.read_private_json(artifact_path,cap=4*1024*1024)
    if (not isinstance(artifact,dict) or artifact.get('schema')!='mldsafail.v060-worker-preparation.v1'
            or artifact.get('passed') is not True or artifact.get('native_executed') is not True
            or artifact.get('benchmark_version')!='0.6.0' or artifact.get('measurement_method')!='cgroup-v2-usage-usec'
            or artifact.get('architecture')!='linux/amd64' or artifact.get('image')!=expected_image
            or artifact.get('image_archive_sha256')!=expected_archive_sha256
            or expected_image not in loaded_images or artifact.get('contract_adopted') is not False
            or artifact.get('default_changed') is not False):
        raise ValueError('Exact retained independently gated worker artifact required')
    for field,length in [('image_archive_sha256',64),('source_context_sha256',64),('source_commit',40)]:
        if not isinstance(artifact.get(field),str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',artifact[field]):
            raise ValueError('Immutable worker source/archive identities required')
    source_manifest=artifact.get('source_manifest')
    if (not isinstance(source_manifest,dict) or source_manifest.get('source_commit')!=artifact['source_commit']
            or source_manifest.get('source_sha256')!=artifact['source_context_sha256']
            or source_manifest.get('source_tree_clean') is not True):
        raise ValueError('Retained worker context identity differs')
    require_prerequisites(prerequisite_path,supervisor_source_sha256=supervisor_source_sha256,
        worker_image=expected_image,worker_context_sha256=artifact['source_context_sha256'],worker_source_commit=artifact['source_commit'])
    return dict(benchmark_version='0.6.0',measurement_method='cgroup-v2-usage-usec',image=expected_image,
        source_commit=artifact['source_commit'],source_context_sha256=artifact['source_context_sha256'],
        image_archive_sha256=artifact['image_archive_sha256'])
