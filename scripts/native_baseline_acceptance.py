"""Reviewed owned-daemon callbacks for frozen baseline and public reproduction.

The sole native operator supplies retained image/source inputs. This never
activates production, reuses staging epochs, or changes frozen worker files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from deploy import owned_daemon
from research.cpu_measurement import native_driver


def protocol(journal, name):
    value=owned_daemon.read_private_json(journal.path.parent.parent/(name+'-protocol.json'))
    if value.get('schema')!='mldsafail.'+name+'-native-protocol.v1':
        raise ValueError('Explicit private source-bound protocol required')
    return value


def receipt(config, refs):
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,
        native_executed=True,evidence_refs=refs,source_sha256=config['acceptance_source_sha256'])


def baseline_callback(journal, config, data):
    from scripts import baseline_production_rehearsal
    setup=protocol(journal,'baseline')
    supplied=dict(setup['rehearsal'])
    if set(supplied['images'].values())-set(data['loaded_images']):
        raise ValueError('Every baseline image must be loaded from pinned driver artifacts')
    supplied.update(run_directory=str(journal.path.parent/'baseline'),docker_socket=data['socket'])
    owned_daemon.publish(journal.path.parent/'baseline-effective-config.json',supplied)
    result=baseline_production_rehearsal.execute(supplied)
    if result.get('complete') is not True or result.get('cleanup_complete') is not True:
        raise RuntimeError('Baseline rehearsal or cleanup remains incomplete')
    return receipt(config,['baseline/report.json','baseline/journal.json'])


def build_context(root, wheel_directory, wheel_hashes, base_image):
    from mldsafail.benchmark_v050 import execution
    source=Path(execution.__file__).resolve().parent
    if not __import__('re').fullmatch('sha256:[0-9a-f]{64}',base_image):
        raise ValueError('Immutable preloaded worker base required')
    root.mkdir(mode=0o700)
    package=root/'mldsafail/benchmark_v050';package.mkdir(parents=True)
    (package.parent/'__init__.py').write_text('')
    for name in execution.WORKER_FILES:
        shutil.copyfile(source/name,package/name)
    for name in ('requirements.txt','artifacts.py'):
        shutil.copyfile(source/name,root/name)
    original=(source/'Dockerfile').read_text()
    if not original.startswith('FROM python:3.12.10-slim-bookworm@sha256:'):
        raise ValueError('Unexpected frozen worker build contract')
    (root/'Dockerfile').write_text('FROM '+base_image+'\n'+original.split('\n',1)[1])
    wheels=root/'wheels';wheels.mkdir()
    actual={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in Path(wheel_directory).glob('*.whl') if not path.is_symlink()}
    if not actual or actual!=wheel_hashes:
        raise ValueError('Exact approved offline wheel inventory required')
    for name in actual:shutil.copyfile(Path(wheel_directory)/name,wheels/name)
    files={path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}
    owned_daemon.publish(root.parent/(root.name+'-manifest.json'),dict(schema='mldsafail.frozen-worker-build.v1',
        trusted_fingerprint=execution.fingerprint(),base_image=base_image,source_files_sha256=files,
        dockerfile_original_sha256=hashlib.sha256(original.encode()).hexdigest()))
    return files


def verify_base_provenance(setup, config, journal):
    from mldsafail.benchmark_v050 import execution
    source=Path(execution.__file__).resolve().parent
    dockerfile=(source/'Dockerfile').read_bytes()
    registry=dockerfile.decode().splitlines()[0].removeprefix('FROM ')
    proof=owned_daemon.read_private_json(setup['base_provenance'])
    if (proof.get('schema')!='mldsafail.native-image-provenance.v1' or proof.get('status')!='passed'
            or proof.get('native_executed') is not True or proof.get('registry_reference')!=registry
            or proof.get('image')!=setup['base_image'] or proof.get('architecture')!='amd64'
            or proof.get('source_dockerfile_sha256')!=hashlib.sha256(dockerfile).hexdigest()
            or not isinstance(proof.get('evidence_refs'),list) or not proof['evidence_refs']):
        raise ValueError('Exact original frozen base native provenance required')
    inspection=proof.get('original_image_inspection',{})
    digest=registry.rsplit('@',1)[1]
    permitted={'python@'+digest,'docker.io/library/python@'+digest}
    if (inspection.get('Id')!=setup['base_image'] or inspection.get('Architecture')!='amd64'
            or not permitted.intersection(inspection.get('RepoDigests',[]))):
        raise ValueError('Original native registry digest/image mapping required')
    artifacts=[config]+config.get('additional_images',[])
    matches=[item for item in artifacts if item.get('image')==setup['base_image']]
    if len(matches)!=1 or matches[0].get('image_archive_sha256')!=proof.get('image_archive_sha256'):
        raise ValueError('Retained base archive differs from original native provenance')
    current=json.loads(journal.command(['docker','image','inspect',setup['base_image']],timeout=15).stdout)[0]
    if current['Id']!=setup['base_image'] or current['Architecture']!='amd64':
        raise ValueError('Loaded base image identity differs from approved artifact')
    owned_daemon.publish(journal.path.parent/'base-provenance.json',proof)


def verify_frozen_provenance(setup, config, journal):
    source=Path(__file__).resolve().parents[1]/'research/primitive_selection'
    proof=owned_daemon.read_private_json(setup['frozen_provenance'])
    expected={path.relative_to(source).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*sorted(source.glob('*.py')),source/'Dockerfile',source/'requirements.txt']}
    if (proof.get('schema')!='mldsafail.native-worker-provenance.v1' or proof.get('status')!='passed'
            or proof.get('native_executed') is not True or proof.get('source_review_passed') is not True
            or not __import__('re').fullmatch('[0-9a-f]{40}',proof.get('source_commit',''))
            or proof.get('image')!=setup['frozen_image'] or proof.get('architecture')!='amd64'
            or proof.get('source_files_sha256')!=expected
            or not isinstance(proof.get('evidence_refs'),list) or not proof['evidence_refs']):
        raise ValueError('Exact reviewed frozen primitive worker native provenance required')
    matches=[item for item in [config]+config.get('additional_images',[]) if item.get('image')==setup['frozen_image']]
    if len(matches)!=1 or matches[0].get('image_archive_sha256')!=proof.get('image_archive_sha256'):
        raise ValueError('Frozen worker archive differs from original native provenance')
    current=json.loads(journal.command(['docker','image','inspect',setup['frozen_image']],timeout=15).stdout)[0]
    if current['Id']!=setup['frozen_image'] or current['Architecture']!='amd64':
        raise ValueError('Loaded frozen primitive worker differs from approved artifact')
    owned_daemon.publish(journal.path.parent/'frozen-provenance.json',proof)


def reproduction_callback(journal, config, data):
    from scripts.reproduction_lifecycle import ReproductionRun
    from scripts.mlwe_reproduce import reproduce
    setup=protocol(journal,'reproduction')
    if {setup['base_image'],setup['frozen_image']}-set(data['loaded_images']):
        raise ValueError('Pinned base and frozen images must be loaded by the driver')
    verify_base_provenance(setup,config,journal)
    verify_frozen_provenance(setup,config,journal)
    images=[]
    for name in ('build-a','build-b'):
        context=journal.path.parent/name
        build_context(context,setup['wheel_directory'],setup['wheel_sha256'],setup['base_image'])
        output=journal.path.parent/(name+'.image-id')
        journal.command(['docker','build','--no-cache','--iidfile',str(output),str(context)],kind='worker_build',timeout=900)
        image=output.read_text().strip()
        if not __import__('re').fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Immutable built worker identity required')
        images.append(image)
    images.append(setup['frozen_image'])
    output=journal.path.parent/'reproduction'
    with ReproductionRun(output,images) as owned:
        reproduce(SimpleNamespace(image_a=images[0],image_b=images[1],frozen_image=images[2],output=output),owned)
    result=owned_daemon.read_private_json(output/'result.json')
    cleanup=owned_daemon.read_private_json(output/'journal.json')
    if result.get('cases')!=36 or any(result.get(key) is not True for key in
        ('fixture_match','normalized_output_match','dependency_artifacts_match')) or cleanup.get('cleanup_complete') is not True:
        raise RuntimeError('Frozen reproduction or cleanup remains incomplete')
    return receipt(config,['build-a-manifest.json','build-b-manifest.json','reproduction/result.json','reproduction/journal.json'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--gate',choices=['baseline','reproduction'],required=True)
    args=parser.parse_args()
    result=native_driver.execute(owned_daemon.read_private_json(args.config),Path(__file__).resolve().parents[1],
        acceptance=baseline_callback if args.gate=='baseline' else reproduction_callback,daemon_kind='owned')
    print(json.dumps(dict(passed=result['native_acceptance_passed'],production_activation=False)))


if __name__=='__main__':main()
