"""Source-bound isolated native candidate callback; no production adoption.

Executed only as a reviewed same-process owned native_driver consumer, after
source-bound accounting fault and thirty-pair receipts have passed. Every output
is private; the callback never changes a deployed registry or existing epoch.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid
from deploy import owned_daemon
from research.cpu_measurement import native_driver
from research.mlwe_v060_preparation.contracts import Cohort
from research.mlwe_v060_preparation.epochs import prepare_epoch
from research.mlwe_v060_preparation.native_reference_audit import audit_reference
from research.mlwe_v060_preparation.reference_authority import seal
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import digest as instance_digest
from mldsafail.benchmark_v060.build import prepare_context
from mldsafail.benchmark_v060.deadline import deadline, COMPLETE_EVALUATION_SECONDS
from mldsafail.benchmark_v060.references import prepare_references


def python_identity(source):
    files={path.relative_to(source).as_posix():dict(bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(source.rglob('*.py'))}
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def require_prerequisites(path, *, supervisor_source_sha256, worker_image, worker_context_sha256, worker_source_commit):
    import re
    if (not isinstance(worker_image,str) or not re.fullmatch('sha256:[0-9a-f]{64}',worker_image)
            or not isinstance(worker_context_sha256,str) or not re.fullmatch('[0-9a-f]{64}',worker_context_sha256)
            or not isinstance(worker_source_commit,str) or not re.fullmatch('[0-9a-f]{40}',worker_source_commit)):
        raise RuntimeError('Explicit gated worker artifact identities required')
    receipt=owned_daemon.read_private_json(path,cap=4*1024*1024)
    if (receipt.get('schema')!='mldsafail.v060-native-prerequisites.v1'
            or receipt.get('supervisor_source_sha256')!=supervisor_source_sha256
            or receipt.get('worker_image')!=worker_image or receipt.get('worker_context_sha256')!=worker_context_sha256
            or receipt.get('worker_source_commit')!=worker_source_commit
            or receipt.get('native_faults_passed') is not True or receipt.get('native_pairs_passed') is not True
            or receipt.get('supervisor_review_passed') is not True or receipt.get('auditor_review_passed') is not True
            or not isinstance(receipt.get('evidence_refs'),list) or not receipt['evidence_refs']):
        raise RuntimeError('Exact independently accepted native prerequisites required')
    return receipt


def restore_environment(values):
    errors=[]
    for name,value in values.items():
        try:
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value
        except BaseException as error:errors.append(name+': '+repr(error))
    return errors


def callback(journal, config, data):
    """Reuse the exactly gated worker and prepare fresh audited references."""
    root=journal.path.parent/'v060';root.mkdir(mode=0o700)
    original=None;result=dict(schema='mldsafail.v060-native-acceptance.v1',passed=False,
        native_executed=False,production_adopted=False,default_changed=False)
    try:
        protocol=owned_daemon.read_private_json(journal.path.parent.parent/'v060-protocol.json')
        if protocol.get('schema')!='mldsafail.v060-native-protocol.v1': raise ValueError('Explicit private candidate protocol required')
        source=Path(__file__).resolve().parents[2]
        context=prepare_context(root/'worker-context',command=lambda argv:journal.command(argv,kind='read',timeout=15).stdout)
        if not context['source_tree_clean'] or context['source_commit']!=config['source_commit']:
            raise RuntimeError('Worker context must bind exact retained clean source')
        image=config['image']
        require_prerequisites(protocol['prerequisites'],supervisor_source_sha256=config['supervisor_source_sha256'],
            worker_image=image,worker_context_sha256=context['source_sha256'],worker_source_commit=context['source_commit'])
        result['native_executed']=True
        inspected=json.loads(journal.command(['docker','image','inspect',image]).stdout)[0]
        if inspected.get('Id')!=image: raise RuntimeError('Exact previously gated worker image required')
        labels=inspected['Config']['Labels']
        if labels.get('org.mldsafail.benchmark.version')!='0.6.0' or labels.get('org.mldsafail.measurement')!='cgroup-v2-usage-usec':
            raise RuntimeError('Version-specific worker artifact labels required')
        artifact=dict(benchmark_version='0.6.0',measurement_method='cgroup-v2-usage-usec',image=image,
            source_context_sha256=context['source_sha256'],source_commit=config['source_commit'])
        owned_daemon.publish(root/'worker-artifact.json',artifact)
        manifest=owned_daemon.load_manifest(data['manifest_path'])
        owned_daemon.verify_environment(manifest,measurement_parent=data['worker_parent'])
        cohort=Cohort('0.6.0',uuid.uuid4().hex,config['supervisor_source_sha256'],'v060-fresh-native',
            image,hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'cgroup-v2-usage-usec')
        epoch=prepare_epoch(root/'epoch',cohort,worker_artifact=artifact,forbidden_epoch_ids=protocol['forbidden_epoch_ids'])
        epoch_hash=hashlib.sha256(json.dumps(epoch,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        cases=[]
        for index,row in enumerate(epoch['cases']):
            public=json.loads(json.dumps(generate_mlwe(row['profile'],row['seed'],row['eta']).public.to_dict()))
            if instance_digest(public)!=row['input_digest']: raise RuntimeError('Fresh epoch regenerated input mismatch')
            cases.append(dict(case_id=str(index),public_input=public))
        reference=source/'examples/mlwe/primal-lll'
        source_hash=python_identity(reference)
        from mldsafail.benchmark_v060.candidate_authority import CandidateRehearsalAuthority
        from mldsafail.benchmark_v060.backend import HostBackend
        candidate_authority=CandidateRehearsalAuthority(Path(protocol['prerequisites']),root/'epoch/manifest.json',
            config['source_commit'],config['supervisor_source_sha256'],image,cohort.epoch_id,cohort.public_id)
        backend=HostBackend(image=image,parent=data['worker_parent'],cgroup_parent=data['worker_slice'],
            epoch_id=cohort.epoch_id,gates=candidate_authority,private_rehearsal=True)
        with deadline(COMPLETE_EVALUATION_SECONDS) as check:
            prepared=prepare_references(backend=backend,cohort=cohort,source=reference,source_sha256=source_hash,
                supervisor_source_sha256=config['supervisor_source_sha256'],reference_source_commit=config['source_commit'],
                epoch_manifest_sha256=epoch_hash,cases=cases,checkpoint=check)
        owned_daemon.publish(root/'draft-references.json',prepared)
        audit_receipt=audit_reference(prepared,cases=cases,directory=backend.directory,cohort=cohort,
            source_sha256=source_hash,worker_image=image,supervisor_source_sha256=config['supervisor_source_sha256'],
            reference_source_commit=config['source_commit'],epoch_manifest_sha256=epoch_hash,seal_path=root/'epoch-seal.json')
        key=secrets.token_bytes(32)
        descriptor=os.open(root/'reference-authority.key',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'wb') as stream: stream.write(key);stream.flush();os.fsync(stream.fileno())
        authority=seal(prepared['table'],audit_receipt=audit_receipt,key=key)
        owned_daemon.publish(root/'reference-authority.json',authority)
        result.update(reference_passed=True,cohort_id=cohort.public_id,epoch_id=cohort.epoch_id,
            worker_image=image,reference_table_sha256=__import__('research.mlwe_v060_preparation.reference_authority',fromlist=['digest']).digest(prepared['table']))
        application_acceptance(journal,config,data,protocol,root,backend,cohort,candidate_authority,cases,
            prepared,authority,key,epoch_hash)
        result.update(passed=True,remaining_gates=['contract adoption','production/default activation'])
        return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
            evidence_refs=['v060/worker-artifact.json','v060/epoch-seal.json','v060/application.json','v060/acceptance.json'],
            source_sha256=config['acceptance_source_sha256'])
    except BaseException as error: original=error;result['error']=repr(error);raise
    finally:
        try: owned_daemon.publish(root/'acceptance.json',result)
        except BaseException as publication:
            if original is None: raise
            original.add_note('Acceptance evidence publication failed: '+repr(publication))


def cleanup_application_resources(engine,server,thread):
    """Attempt every acquired resource independently; never wait without limit."""
    import threading
    errors=[]
    shutdown_thread=None
    alive=False
    if thread is not None:
        try:alive=thread.is_alive()
        except BaseException as error:errors.append(repr(error));alive=True
    if server is not None and alive:
        shutdown_errors=[]
        def shutdown():
            try:server.shutdown()
            except BaseException as error:shutdown_errors.append(repr(error))
        try:
            shutdown_thread=threading.Thread(target=shutdown,daemon=True)
            shutdown_thread.start();shutdown_thread.join(timeout=10)
            if shutdown_thread.is_alive():errors.append('Private HTTP shutdown did not exit')
        except BaseException as error:errors.append(repr(error))
        errors.extend(shutdown_errors)
    if server is not None:
        try:server.server_close()
        except BaseException as error:errors.append(repr(error))
    if thread is not None:
        try:
            if thread.ident is not None:thread.join(timeout=10)
            if thread.is_alive():errors.append('Private HTTP server did not exit')
        except BaseException as error:errors.append(repr(error))
    if engine is not None:
        try:engine.dispose()
        except BaseException as error:errors.append(repr(error))
    return errors


def finalize_application(root,application,original,errors):
    application.update(schema='mldsafail.v060-native-application.v1',passed=original is None and not errors and application.get('behavior_passed') is True,
        cleanup_complete=not errors,cleanup_errors=list(errors))
    if original is not None:application['error']=repr(original)
    try:owned_daemon.publish(root/'application.json',application)
    except BaseException as publication:
        message='Application disposition publication failed: '+repr(publication)
        errors.append(message)
        if original is not None:original.add_note(message)
        application.update(passed=False,cleanup_complete=False,cleanup_errors=list(errors),evidence_publication_failed=True)
        try:owned_daemon.publish(root/'application.json',application)
        except BaseException as retry:
            errors.append('Negative application disposition publication failed: '+repr(retry))
            if original is not None:original.add_note(errors[-1])
    if errors:
        if original is None:raise RuntimeError('Application cleanup failed: '+repr(errors))
        original.add_note('Application cleanup failed: '+repr(errors))


def application_acceptance(journal,config,data,protocol,root,backend,cohort,candidate_authority,cases,prepared,authority,reference_key,epoch_hash):
    """Fresh second owned daemon isolates PostgreSQL from measured worker CPU."""
    import threading
    import time
    import requests
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from werkzeug.serving import make_server
    from mldsafail import cli
    from mldsafail.benchmark_versions import RegisteredBackend,VersionRegistry
    from mldsafail.benchmark_v060.coordinator import Coordinator
    from mldsafail.benchmark_v060.evaluation import evaluate
    from mldsafail.web.app import create_app
    from mldsafail.web.db import get_session
    from mldsafail.web.models import Base,User,Submission,EvaluationJob,ExperimentResult
    from mldsafail.web.services import create_api_token
    outer_manifest=owned_daemon.load_manifest(data['manifest_path'])
    pg=dict(protocol['postgres_artifact'])
    if set(pg)!={'image','image_archive','image_archive_sha256'}: raise ValueError('Pinned separate PostgreSQL artifact required')
    inner_config=dict(config,**pg,state_root=str(root/'postgres-context'),additional_images=[])
    inner_config['protected_roots']=config['protected_roots']+[value['path'] for value in outer_manifest['roots'].values()]
    inner_config['protected_cgroups']=config['protected_cgroups']+[outer_manifest['domain']['path'],outer_manifest['worker_domain']['path']]
    previous={name:os.environ.get(name) for name in ('DOCKER_HOST','DOCKER_CONTEXT','MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','MLDSAFAIL_CPU_DAEMON_MANIFEST','XDG_CONFIG_HOME')}
    application={}
    def pg_callback(inner_journal,inner_cfg,inner_data):
        name='v060-db-'+inner_data['id']
        inspected=json.loads(inner_journal.command(['docker','image','inspect',pg['image']]).stdout)[0]
        if set(inspected['Config'].get('Volumes') or {})-{'/var/lib/postgresql/data'}:
            raise RuntimeError('Unaccounted PostgreSQL volume forbidden')
        identifier=inner_journal.command(['docker','run','-d','--name',name,'--label','org.mldsafail.native='+name,
            '--memory','384m','--pids-limit','128','--tmpfs','/var/lib/postgresql/data:size=256m',
            '-e','POSTGRES_HOST_AUTH_METHOD=trust','-p','127.0.0.1::5432',pg['image']],kind='database_start',timeout=90).stdout.decode().strip()
        expires=time.monotonic()+60
        while True:
            ready=inner_journal.command(['docker','exec',identifier,'pg_isready','-U','postgres'],check=False,timeout=10)
            if ready.returncode==0:break
            if time.monotonic()>expires:raise TimeoutError('Disposable PostgreSQL startup deadline')
            time.sleep(.2)
        ports=json.loads(inner_journal.command(['docker','inspect',identifier]).stdout)[0]['NetworkSettings']['Ports']['5432/tcp']
        if len(ports)!=1 or ports[0]['HostIp']!='127.0.0.1': raise RuntimeError('Private loopback PostgreSQL only')
        database_url='postgresql+psycopg://postgres@127.0.0.1:'+ports[0]['HostPort']+'/postgres'
        registry=VersionRegistry([RegisteredBackend(cohort,lambda job:dict(benchmark_version='0.6.0',**{
            name:getattr(cohort,name) for name in ('epoch_id','evaluator_fingerprint','hidden_suite_version','worker_class')}),
            candidate_authority,private_rehearsal=True)])
        engine=server=thread=None
        original=None
        try:
            app=create_app(config_name='test',config=dict(DATABASE_URL=database_url,BENCHMARK_VERSION='0.5.0',
                MLWE_EPOCH_ID='disposable-compatibility-only',EVALUATOR_FINGERPRINT='0'*64,HIDDEN_SUITE_VERSION='disposable-v050',WORKER_CLASS='disposable-v050',
                BENCHMARK_VERSION_REGISTRY=registry,V060_PRIVATE_CANDIDATE_REHEARSAL=True))
            engine=app.extensions['mldsafail_engine'];Base.metadata.create_all(engine)
            with app.app_context():
                database=get_session();user=User(display_name='Isolated native candidate rehearsal');database.add(user);database.commit()
                _,token=create_api_token(database,user,'isolated-native');user_id=user.id
            server=make_server('127.0.0.1',0,app)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start();base=f'http://127.0.0.1:{server.server_port}'
            os.environ['XDG_CONFIG_HOME']=str(root/'cli-private')
            os.environ['DOCKER_HOST']='unix://'+data['socket']
            os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']=data['manifest_path']
            os.environ.pop('MLDSAFAIL_CPU_DAEMON_MANIFEST',None)
            artifact_directory=root/'participant-artifact'
            artifact_directory.mkdir(mode=0o700)
            inner_journal.command(['uv','build','--wheel','--out-dir',str(artifact_directory),str(Path(__file__).resolve().parents[2])],kind='artifact_build',timeout=120)
            wheels=list(artifact_directory.glob('*.whl'))
            if len(wheels)!=1: raise RuntimeError('Exactly one separately retained participant wheel required')
            environment=root/'participant-environment'
            inner_journal.command(['uv','venv','--system-site-packages','--python',sys.executable,str(environment)],kind='artifact_install',timeout=60)
            python=environment/'bin/python'
            inner_journal.command(['uv','pip','install','--python',str(python),'--no-deps',str(wheels[0])],kind='artifact_install',timeout=120)
            installed=inner_journal.command([str(python),'-I','-c','import mldsafail; print(mldsafail.__file__)']).stdout.decode().strip()
            if not Path(installed).is_relative_to(environment): raise RuntimeError('Installed participant package resolved outside retained isolated environment')
            owned_daemon.publish(root/'participant-artifact.json',dict(schema='mldsafail.v060-participant-artifact.v1',benchmark_version='0.6.0',source_commit=config['source_commit'],wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(),installed_package=str(Path(installed).relative_to(environment))))
            workspace=root/'participant'
            inner_journal.command([str(python),'-I','-m','mldsafail.cli','clone',str(workspace),'--benchmark-version','0.6.0'],kind='participant_scaffold',timeout=60)
            commit=inner_journal.command(['git','-C',str(workspace),'rev-parse','HEAD'],kind='read',timeout=15).stdout.decode().strip()
            cli._write_config(dict(server=base,token=token))
            # Native receipt proves actual HTTP preflight and queue admission;
            # participant token remains exclusively in private evidence.
            key='isolated-v060-'+uuid.uuid4().hex
            inner_journal.command([str(python),'-I','-m','mldsafail.cli','submit','--repo',workspace.as_uri(),'--commit',commit,
                '--hypothesis','source-bound isolated native rehearsal','--benchmark-version','0.6.0','--idempotency-key',key],kind='participant_submission',timeout=60)
            with Session(engine) as database:
                submission=database.scalar(select(Submission));job=database.scalar(select(EvaluationJob))
                if submission is None or submission.benchmark_version!='0.6.0' or submission.epoch_id!=cohort.epoch_id or job.status!='queued':
                    raise RuntimeError('Exact candidate cohort queue admission failed')
                submission_id=submission.id
                owned_daemon.publish(root/'application-progress.json',dict(schema='mldsafail.v060-native-application-progress.v1',submission_id=submission_id,phase='queued',job_state=job.status,cohort_id=cohort.public_id))
            signing_key=secrets.token_bytes(32)
            descriptor=os.open(root/'candidate-signing.key',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(descriptor,'wb') as stream:stream.write(signing_key);stream.flush();os.fsync(stream.fileno())
            owned_daemon.publish(root/'candidate-key-receipt.json',dict(schema='mldsafail.v060-key-receipt.v1',key_sha256=hashlib.sha256(signing_key).hexdigest()))
            def run_source(contestant,checkpoint):
                envelope=evaluate(backend=backend,source=contestant,source_sha256=python_identity(contestant),
                    supervisor_source_sha256=config['supervisor_source_sha256'],cohort=cohort,cases=cases,references=prepared['table'],
                    epoch_manifest_sha256=epoch_hash,reference_source_commit=config['source_commit'],reference_worker_image=backend.image,
                    reference_audit_sha256=prepared['table']['audit_receipt_sha256'],signing_key=signing_key,checkpoint=checkpoint,
                    reference_authority=authority,reference_authority_key=reference_key)
                owned_daemon.publish(root/'candidate-envelope.json',envelope)
                return envelope
            coordinator=Coordinator(engine=engine,cohort=cohort,gates=candidate_authority,private_rehearsal=True,
                work_root=root/'coordinator',evaluate_source=run_source,signing_key=signing_key)
            if coordinator.run_once() is not True or coordinator.run_once() is not False:raise RuntimeError('Serialized exact one candidate queue job required')
            with Session(engine) as database:
                submission=database.get(Submission,submission_id)
                result=database.scalar(select(ExperimentResult))
                owned_daemon.publish(root/'application-progress.json',dict(schema='mldsafail.v060-native-application-progress.v1',submission_id=submission_id,phase='coordinator_finished',submission_state=submission.state,result_available=result is not None,cohort_id=cohort.public_id))
                if submission.state!='accepted' or result is None or result.benchmark_version!='0.6.0' or result.epoch_id!=cohort.epoch_id:
                    raise RuntimeError('Native independently audited candidate did not accept')
                from mldsafail.benchmark_v060.envelope import verify
                payload=verify(owned_daemon.read_private_json(root/'candidate-envelope.json',cap=8*1024*1024),signing_key,cohort_id=cohort.public_id,source_sha256=result.source_digest)
                if payload['score']!=result.mlwe_score or payload['verified'] is not True:raise RuntimeError('Retained independent signed result differs from API result')
            headers={'Authorization':'Bearer '+token}
            response=requests.get(base+'/api/v1/leaderboard?benchmark_version=0.6.0',headers=headers,timeout=10)
            response.raise_for_status();candidate=response.json()
            response=requests.get(base+'/api/v1/leaderboard',headers=headers,timeout=10);response.raise_for_status();legacy=response.json()
            if candidate['benchmark_version']!='0.6.0' or len(candidate['leaderboard'])!=1 or legacy['benchmark_version']!='0.5.0' or legacy['leaderboard']!=[]:
                raise RuntimeError('Independent cohort separation/default compatibility failed')
            rendered=json.dumps(candidate)
            if any(value in rendered for value in (token,str(root),epoch_hash)):
                raise RuntimeError('Private native evidence leaked to participant response')
            application.update(schema='mldsafail.v060-native-application.v1',native_executed=True,behavior_passed=True,
                disposable_postgresql=True,actual_http_cli=True,coordinator_queue=True,independent_evidence=True,
                cohort_separation=True,legacy_default_preserved=True,contract_adopted=False,submission_id=submission_id,
                cohort_id=cohort.public_id,source_commit=config['source_commit'])
        except BaseException as error:original=error;raise
        finally:
            errors=cleanup_application_resources(engine,server,thread)
            errors.extend(restore_environment(previous))
            errors.extend(restore_environment(dict(DOCKER_HOST='unix://'+inner_data['socket'],DOCKER_CONTEXT=None,MLDSAFAIL_OPERATOR_DAEMON_MANIFEST=inner_data['manifest_path'],MLDSAFAIL_CPU_DAEMON_MANIFEST=None)))
            finalize_application(root,application,original,errors)
        return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
            evidence_refs=['application.json'],source_sha256=config['acceptance_source_sha256'])
    nested_error=None
    try:
        native_driver.execute(inner_config,Path(__file__).resolve().parents[2],acceptance=pg_callback,daemon_kind='owned')
    except BaseException as error:nested_error=error;raise
    finally:
        errors=restore_environment(previous)
        if errors:
            if nested_error is None:raise RuntimeError('Nested environment restoration failed: '+repr(errors))
            nested_error.add_note('Nested environment restoration failed: '+repr(errors))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    result=native_driver.execute(owned_daemon.read_private_json(args.config),Path(__file__).resolve().parents[2],
        acceptance=callback,daemon_kind='owned')
    print(json.dumps(dict(passed=result['native_acceptance_passed'],native_executed=True,
        contract_adopted=False,production_default_changed=False)))


if __name__=='__main__':main()
