"""Prepare pinned native prerequisite images; never execute a benchmark epoch.

Reviewed same-process owned native_driver callback. Scientific files remain
byte-identical; original Docker/requirements identities are retained separately
from the explicit native assembly and offline-wheel substitutions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from deploy import owned_daemon
from research.cpu_measurement import native_driver
from mldsafail.benchmark_v060.build import wheel_protocol,approved_wheels
from scripts.native_v060_worker_preparation import retain_archive


def source_files(repository):
    study=Path(repository)/'research/primitive_selection'
    return {path.relative_to(study).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*sorted(study.glob('*.py')),study/'Dockerfile',study/'requirements.txt']}


def require_source_review(config):
    repository=Path(__file__).resolve().parents[1]
    protocol=owned_daemon.read_private_json(Path(config['state_root']).parent/'reproduction-artifacts-protocol.json')
    if set(protocol)!={'schema','source_review'} or protocol['schema']!='mldsafail.reproduction-artifacts-protocol.v1':
        raise ValueError('Strict scientific artifact source review protocol required')
    review=owned_daemon.read_private_json(protocol['source_review'])
    if (review.get('schema')!='mldsafail.native-artifact-source-review.v1' or review.get('passed') is not True
            or review.get('source_commit')!=config['source_commit']
            or review.get('primitive_source_files_sha256')!=source_files(repository)
            or not isinstance(review.get('reviewer'),str) or not review['reviewer']
            or not isinstance(review.get('evidence_refs'),list) or not review['evidence_refs']):
        raise ValueError('Independently reviewed exact frozen scientific source required')
    return review


def export_image(journal,image,path):
    if path.exists():raise ValueError('New private artifact archive required')
    journal.command(['docker','image','save','--output',str(path),image],kind='read',timeout=600)
    return retain_archive(path)


def inspect_image(journal,image):
    rows=json.loads(journal.command(['docker','image','inspect',image],kind='read',timeout=30).stdout)
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict) or not re.fullmatch('sha256:[0-9a-f]{64}',rows[0].get('Id','')) or rows[0].get('Architecture')!='amd64':
        raise RuntimeError('Immutable native amd64 image inspection required')
    return rows[0]


def study_context(output,repository,base_image,options,source_commit):
    source=Path(repository)/'research/primitive_selection'
    wheels=approved_wheels(options['wheel_directory'],options['wheel_inventory'])
    output.mkdir(mode=0o700)
    files=[*sorted(source.glob('*.py')),*sorted((source/'schemas').glob('*.json')),
           *[source/name for name in ('Dockerfile','requirements.txt','primitive-study','rebuild-check.sh')],
           *sorted((Path(repository)/'tests').glob('test_primitive*.py'))]
    for path in files:
        if path.is_symlink() or not path.is_file():raise ValueError('Regular frozen scientific source required')
        target=output/path.relative_to(repository);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
    lock=Path(repository)/'deploy/worker-linux-amd64.requirements.txt'
    if hashlib.sha256(lock.read_bytes()).hexdigest()!='35890cf7c5ed544124dc4cc86269009f11d029a5388d1627b6899e986650c1f0':
        raise ValueError('Exact approved native dependency lock required')
    shutil.copyfile(lock,output/'native-requirements.txt')
    (output/'wheels').mkdir()
    for name,path in wheels.items():
        target=output/'wheels'/name;shutil.copyfile(path,target,follow_symlinks=False)
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=options['wheel_inventory'][name]:
            raise ValueError('Retained approved wheel changed during context copy')
    original=(source/'Dockerfile').read_text()
    expected='FROM python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db'
    if original.splitlines()[0]!=expected:raise ValueError('Frozen study base contract changed')
    body=original.split('\n',1)[1]
    old='RUN pip install --no-cache-dir --requirement /tmp/requirements.txt'
    if body.count(old)!=1:raise ValueError('Frozen scientific installation contract changed')
    body=body.replace(old,'COPY wheels /wheels\nCOPY native-requirements.txt /native-requirements.txt\nRUN pip install --no-index --find-links=/wheels --requirement /native-requirements.txt\n'+old)
    body=body.replace('libgmp10 libmpfr6','libgmp10=2:6.2.1+dfsg1-1.1 libmpfr6=4.2.0-1')
    (output/'Dockerfile').write_text('FROM '+base_image+'\n'+body)
    (output/'wheel-provenance.json').write_text(json.dumps(options['wheel_provenance'],sort_keys=True,separators=(',',':')))
    manifest={path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob('*')) if path.is_file()}
    owned_daemon.publish(output.parent/'study-context.json',dict(schema='mldsafail.native-study-context.v1',
        source_commit=source_commit,source_files_sha256=source_files(repository),context_files_sha256=manifest,
        context_sha256=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        base_image=base_image,architecture='amd64',scientific_source_changed=False,
        native_lock_sha256=manifest['native-requirements.txt'],native_acceptance_passed=False))
    return manifest


def callback(journal,config,data):
    repository=Path(__file__).resolve().parents[1]
    review=require_source_review(config);options=wheel_protocol(config)
    if not options:raise ValueError('Approved retained native offline wheels required')
    actual=journal.command(['git','-C',str(repository),'rev-parse','HEAD'],kind='read',timeout=15).stdout
    dirty=journal.command(['git','-C',str(repository),'status','--porcelain'],kind='read',timeout=15).stdout
    if actual.decode().strip()!=config['source_commit'] or dirty.strip():raise RuntimeError('Exact clean retained artifact source required')
    root=journal.path.parent/'reproduction-artifacts';root.mkdir(mode=0o700)
    dockerfile=(repository/'src/mldsafail/benchmark_v050/Dockerfile').read_bytes()
    registry=dockerfile.decode().splitlines()[0].removeprefix('FROM ')
    if registry!='python:3.12.10-slim-bookworm@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db':
        raise ValueError('Exact frozen pinned Python registry reference required')
    journal.command(['docker','pull','--platform','linux/amd64',registry],kind='image_pull',timeout=600)
    original=inspect_image(journal,registry);base=original['Id'];digest=registry.rsplit('@',1)[1]
    if not {'python@'+digest,'docker.io/library/python@'+digest}.intersection(original.get('RepoDigests',[])):
        raise RuntimeError('Actual pinned official registry image mapping required')
    if 'PYTHON_VERSION=3.12.10' not in original.get('Config',{}).get('Env',[]):raise RuntimeError('Pinned Python version metadata required')
    exported=export_image(journal,base,root/'python-base.tar')
    base_proof=dict(schema='mldsafail.native-image-provenance.v1',status='passed',native_executed=True,
        registry_reference=registry,image=base,architecture='amd64',source_dockerfile_sha256=hashlib.sha256(dockerfile).hexdigest(),
        image_archive=str(root/'python-base.tar'),image_archive_sha256=exported['sha256'],image_archive_bytes=exported['bytes'],
        original_image_inspection=original,evidence_refs=['python-base.tar','artifact-operator-journal'],outer_cleanup_required=True)
    owned_daemon.publish(root/'python-base-provenance.json',base_proof)
    context=root/'study-context';study_context(context,repository,base,options,config['source_commit'])
    image_file=root/'primitive-image.id'
    journal.command(['docker','build','--platform','linux/amd64','--iidfile',str(image_file),
        '--build-arg','RESEARCH_GIT_REVISION='+config['source_commit'],'--build-arg','RESEARCH_GIT_DIRTY=false',str(context)],kind='study_image_build',timeout=900)
    image=image_file.read_text().strip()
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise RuntimeError('Immutable built primitive image required')
    built=inspect_image(journal,image)
    if built['Id']!=image or built.get('Config',{}).get('Entrypoint')!=['python','-m','research.primitive_selection']:
        raise RuntimeError('Exact frozen scientific entrypoint required')
    exported=export_image(journal,image,root/'primitive-study.tar')
    proof=dict(schema='mldsafail.native-worker-provenance.v1',status='passed',native_executed=True,
        source_review_passed=review['passed'],source_commit=config['source_commit'],image=image,architecture='amd64',
        source_files_sha256=source_files(repository),source_review_evidence_refs=review['evidence_refs'],
        image_archive=str(root/'primitive-study.tar'),image_archive_sha256=exported['sha256'],image_archive_bytes=exported['bytes'],
        original_image_inspection=built,evidence_refs=['study-context.json','primitive-study.tar','artifact-operator-journal'],
        scientific_source_changed=False,benchmark_acceptance_passed=False,outer_cleanup_required=True)
    owned_daemon.publish(root/'primitive-study-provenance.json',proof)
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
        evidence_refs=[str(root/'python-base-provenance.json'),str(root/'primitive-study-provenance.json')],source_sha256=config['acceptance_source_sha256'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args();config=owned_daemon.read_private_json(args.config)
    if not wheel_protocol(config):raise ValueError('Approved offline wheel protocol required')
    require_source_review(config)
    native_driver.execute(config,Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')

if __name__=='__main__':main()
