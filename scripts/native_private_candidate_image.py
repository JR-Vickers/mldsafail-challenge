"""Retain an inert private application artifact; never benchmark or activate it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import os
import stat
from deploy import owned_daemon
from research.cpu_measurement import native_driver
from scripts.private_candidate_image_context import context
from scripts.native_v060_worker_preparation import retain_archive


def require_protocol(value):
    fields={'schema','package_source','wheel','wheel_manifest','base_manifest','runtime_source',
        'runtime_source_commit','runtime_review'}
    if not isinstance(value,dict) or set(value)!=fields or value['schema']!='mldsafail.private-candidate-image-protocol-build.v1':
        raise ValueError('Explicit separately bound package/runtime build protocol required')
    if not isinstance(value['runtime_source_commit'],str) or not re.fullmatch('[0-9a-f]{40}',value['runtime_source_commit']):
        raise ValueError('Full retained runtime source identity required')
    for name in fields-{'schema','runtime_source_commit'}:
        owned_daemon._canonical(Path(value[name]))
    return value


def verify_context(directory,manifest):
    directory=owned_daemon._canonical(directory)
    observed={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():raise ValueError('Image context links forbidden')
        if path.is_dir():continue
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.getuid() or before.st_mode&0o022 or before.st_size>128*1024*1024:
                raise ValueError('Bounded owned regular image context required')
            digest=hashlib.sha256()
            while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
            after=os.fstat(descriptor)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                raise ValueError('Image context changed during verification')
            observed[path.relative_to(directory).as_posix()]=digest.hexdigest()
        finally:os.close(descriptor)
    if observed!=manifest['files_sha256'] or hashlib.sha256(json.dumps(observed,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=manifest['context_sha256']:
        raise ValueError('Source-bound image context inventory changed')


def inspect_image(journal,image,manifest):
    rows=json.loads(journal.command(['docker','image','inspect',image],kind='read',timeout=30).stdout)
    if not isinstance(rows,list) or len(rows)!=1 or rows[0].get('Id')!=image or rows[0].get('Architecture')!='amd64':
        raise ValueError('One exact native amd64 application image required')
    metadata=rows[0].get('Config',{});labels=metadata.get('Labels',{})
    if (metadata.get('User')!='0:0' or metadata.get('Volumes')
            or metadata.get('Entrypoint')!=['/app/.venv/bin/python','-m','candidate_runtime']
            or labels.get('org.mldsafail.candidate')!='private-unapproved'
            or labels.get('org.mldsafail.protocol')!='0.6.0' or labels.get('org.mldsafail.default')!='0.5.0'
            or labels.get('org.mldsafail.candidate.source_commit')!=manifest['runtime_source_commit']
            or labels.get('org.mldsafail.candidate.wheel_source_commit')!=manifest['wheel_source_commit']
            or labels.get('org.mldsafail.candidate.wheel_sha256')!=manifest['wheel_sha256']):
        raise ValueError('Exact source-bound inert rootless application configuration required')
    return rows[0]


def publish_artifact(path,artifact):
    try:owned_daemon.publish(path,artifact)
    except BaseException as original:
        negative=dict(artifact,passed=False,evidence_publication_failed=True,publication_failure_class=type(original).__name__)
        try:owned_daemon.publish(path,negative)
        except BaseException as retry:original.add_note('Negative image artifact publication failed: '+repr(retry))
        raise


def callback(journal,config,data):
    protocol=require_protocol(owned_daemon.read_private_json(journal.path.parent.parent/'candidate-image-build-protocol.json'))
    review=owned_daemon.read_private_json(protocol['runtime_review'])
    if (review.get('schema')!='mldsafail.private-candidate-runtime-review.v1'
            or review.get('source_commit')!=protocol['runtime_source_commit'] or review.get('source_review_passed') is not True
            or not isinstance(review.get('evidence_refs'),list) or not review['evidence_refs']):
        raise ValueError('Independent exact runtime source review required before building')
    root=journal.path.parent/'candidate-image';root.mkdir(mode=0o700)
    artifact=dict(schema='mldsafail.private-candidate-image-build.v1',passed=False,native_executed=True,
        candidate_only=True,production_adopted=False,default_changed=False,outer_cleanup_required=True,
        native_rehearsal_passed=False,worker_built=False,epoch_created=False,reference_created=False,
        operator_source_commit=config['source_commit'],source_commit=protocol['runtime_source_commit'],
        owned_driver_journal=str(journal.path),owned_driver_id=data['id'],
        acceptance_source_sha256=config['acceptance_source_sha256'],artifact_path=str(root/'artifact.json'))
    original=None
    try:
        manifest=context(root/'context',source=Path(protocol['package_source']),wheel=Path(protocol['wheel']),
            wheel_manifest=owned_daemon.read_private_json(protocol['wheel_manifest']),
            base_manifest=owned_daemon.read_private_json(protocol['base_manifest']),
            runtime_source=Path(protocol['runtime_source']),runtime_source_commit=protocol['runtime_source_commit'],
            command=lambda argv:journal.command(argv,kind='source_read',timeout=15).stdout)
        if manifest['base_image'] not in data['loaded_images']:
            raise ValueError('Exact frozen baseline web must already be loaded from retained archive')
        verify_context(root/'context',manifest)
        image_file=root/'image.id'
        journal.command(['docker','build','--network','none','--platform','linux/amd64','--pull=false','--iidfile',str(image_file),str(root/'context')],kind='image_build',timeout=600)
        image=image_file.read_text().strip()
        if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Immutable built application image required')
        inspected=inspect_image(journal,image,manifest)
        verify_context(root/'context',manifest)
        smoke="import importlib.metadata,mldsafail,candidate_runtime.config;assert importlib.metadata.version('mldsafail-challenge')=='0.5.1';assert mldsafail.__file__.startswith('/app/.venv/');print('private-candidate-import-ok')"
        name='candidate-smoke-'+data['id']
        journal.command(['docker','run','--name',name,'--network','none','--read-only','--user','0:0',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','256m',
            '--cgroup-parent',data['worker_slice'],'--entrypoint','/app/.venv/bin/python',image,'-B','-c',smoke],
            kind='application_smoke',timeout=60)
        archive=root/'application-image.tar'
        if archive.exists():raise ValueError('Fresh application export path required')
        journal.command(['docker','image','save','--output',str(archive),image],kind='image_export',timeout=600)
        retained=retain_archive(archive)
        artifact.update(passed=True,image=image,architecture='linux/amd64',context_sha256=manifest['context_sha256'],
            context_manifest=manifest,wheel_source_commit=manifest['wheel_source_commit'],wheel_sha256=manifest['wheel_sha256'],
            base_image=manifest['base_image'],base_source_commit=manifest['base_source_commit'],
            image_archive=str(archive),image_archive_sha256=retained['sha256'],image_archive_bytes=retained['bytes'],
            image_inspection=inspected,independent_source_review=review,import_smoke_passed=True)
        publish_artifact(root/'artifact.json',artifact)
        return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
            source_sha256=config['acceptance_source_sha256'],evidence_refs=[str(root/'artifact.json')])
    except BaseException as error:
        original=error;artifact.update(passed=False,failure_class=type(error).__name__)
        try:publish_artifact(root/'artifact.json',artifact)
        except BaseException as publication:original.add_note('Negative build disposition: '+repr(publication))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args();config=owned_daemon.read_private_json(args.config)
    require_protocol(owned_daemon.read_private_json(Path(config['state_root']).parent/'candidate-image-build-protocol.json'))
    result=native_driver.execute(config,Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')
    print(json.dumps(dict(passed=result['native_acceptance_passed'],native_executed=True,candidate_only=True,
        production_adopted=False,default_changed=False)))


if __name__=='__main__':main()
