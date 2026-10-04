"""Build and retain a prospective worker before its native accounting gates.

Run only as a reviewed same-process owned native_driver callback. No epoch,
reference, score, adoption or default registry is created here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from deploy import owned_daemon
from research.cpu_measurement import native_driver
from mldsafail.benchmark_v060.build import prepare_context, wheel_protocol


def retain_archive(path):
    """Seal only a fresh regular single-link Docker export, then bind bytes."""
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_size<=0:
            raise ValueError('Owned nonempty regular worker archive required')
        digest=hashlib.sha256()
        while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
        os.fsync(descriptor)
        current=os.fstat(descriptor)
        retained=os.stat(path,follow_symlinks=False)
        if ((current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
                or (retained.st_dev,retained.st_ino)!=(info.st_dev,info.st_ino)):
            raise RuntimeError('Worker archive changed while sealing')
        os.fchmod(descriptor,0o400);os.fsync(descriptor)
        result=dict(sha256=digest.hexdigest(),bytes=info.st_size)
    finally:os.close(descriptor)
    descriptor=os.open(Path(path).parent,os.O_RDONLY|os.O_NOFOLLOW)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    return result


def callback(journal,config,data):
    root=journal.path.parent/'v060-worker';root.mkdir(mode=0o700)
    context=prepare_context(root/'context',command=lambda argv:journal.command(argv,kind='read',timeout=15).stdout,**wheel_protocol(config))
    if context['source_tree_clean'] is not True or context['source_commit']!=config['source_commit']:
        raise RuntimeError('Worker context must bind clean retained operator source')
    image_file=root/'image.id'
    journal.command(['docker','build','--iidfile',str(image_file),str(root/'context')],kind='image_build',timeout=600)
    image=image_file.read_text().strip()
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise RuntimeError('Immutable worker build ID required')
    inspected=json.loads(journal.command(['docker','image','inspect',image],kind='read',timeout=30).stdout)
    if not isinstance(inspected,list) or len(inspected)!=1 or inspected[0].get('Id')!=image:
        raise RuntimeError('Exact built worker inspection required')
    metadata=inspected[0]['Config'];labels=metadata.get('Labels',{})
    if (labels.get('org.mldsafail.benchmark.version')!='0.6.0'
            or labels.get('org.mldsafail.measurement')!='cgroup-v2-usage-usec'
            or metadata.get('Entrypoint')!=['python','-m','mldsafail.benchmark_v060.worker']
            or metadata.get('User')!='65534:65534'):
        raise RuntimeError('Version-correct minimal worker configuration required')
    archive=root/'worker-image.tar'
    if archive.exists():raise RuntimeError('New worker export path required')
    journal.command(['docker','image','save','--output',str(archive),image],kind='read',timeout=600)
    sealed=retain_archive(archive)
    artifact=dict(schema='mldsafail.v060-worker-preparation.v1',passed=True,native_executed=True,
        benchmark_version='0.6.0',measurement_method='cgroup-v2-usage-usec',image=image,
        image_archive=str(archive),image_archive_sha256=sealed['sha256'],image_archive_bytes=sealed['bytes'],
        source_commit=context['source_commit'],source_context_sha256=context['source_sha256'],
        source_manifest=context,supervisor_source_sha256=config['supervisor_source_sha256'],
        contract_adopted=False,reference_created=False,epoch_created=False,default_changed=False,
        native_faults_passed=False,native_pairs_passed=False,outer_cleanup_required=True)
    owned_daemon.publish(root/'artifact.json',artifact)
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
        evidence_refs=[str(root/'artifact.json')],source_sha256=config['acceptance_source_sha256'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    config=owned_daemon.read_private_json(args.config)
    wheel_protocol(config)  # Admission before any owned daemon/client mutation.
    native_driver.execute(config,repository=Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')

if __name__=='__main__':main()
