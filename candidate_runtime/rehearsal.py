"""Private image rehearsal; host authority never enters application containers.

Native execution is exclusively a same-process owned-driver callback. Source
checks do not establish any deployment or benchmark acceptance.
"""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import threading
import time
from types import MappingProxyType
from deploy import owned_daemon
from candidate_runtime.gateway import Gateway
from candidate_runtime.native import application_create
from candidate_runtime.image_artifact import require_image
from candidate_runtime.worker_artifact import accepted_worker
from research.cpu_measurement import native_driver
from research.mlwe_v060_preparation import native_acceptance


class OperationCleanupIncomplete(RuntimeError):
    """Operator must exit after outer cleanup; never reuse this runtime."""


def serve_operation(gateway, operation, *, seconds, journal=None, receipt=None):
    """Dispatch native evaluation here; independently stop owned I/O on failure."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Native measurement dispatcher must remain on main thread')
    from deploy import owned_client
    result=[];errors=[];cancel=threading.Event();original=None
    start=len(journal.data.get('clients',[])) if journal else 0
    record=dict(schema='mldsafail.candidate-io-lifecycle.v1',state='intent',cleanup_complete=False,
        owner=owned_client.identity(os.getpid()),operation_id=secrets.token_hex(16))
    def publish():
        if receipt is not None:owned_daemon.publish(receipt,record)
    publish()
    def run():
        try:result.append(operation(cancel))
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=run,daemon=True);thread.start()
    try:
        record.update(state='running',thread_ident=thread.ident);publish()
        expires=time.monotonic()+seconds;gateway.server.settimeout(.2)
        while thread.is_alive():
            if time.monotonic()>=expires:raise TimeoutError('Bounded private application operation')
            try:gateway.serve_once()
            except socket.timeout:continue
        if errors:raise errors[0]
        return result[0]
    except BaseException as error:original=error;raise
    finally:
        cancel.set();cleanup_errors=[]
        expires=time.monotonic()+35
        # These operations are HTTP readiness, CLI submission or Docker wait,
        # never daemon/container creators. Each client has its own birth fence.
        while thread.is_alive() and time.monotonic()<expires:
            if journal is not None:
                for entry in list(journal.data.get('clients',[])[start:]):
                    try:owned_client.stop(entry)
                    except BaseException as error:cleanup_errors.append(repr(error))
            thread.join(timeout=.1)
        record.update(state='cleanup_incomplete' if thread.is_alive() or cleanup_errors else 'closed',
            cleanup_complete=not thread.is_alive() and not cleanup_errors,cleanup_errors=cleanup_errors,
            thread_alive=thread.is_alive(),cancel_requested=True)
        try:publish()
        except BaseException as error:cleanup_errors.append('Lifecycle publication: '+repr(error))
        if thread.is_alive():
            failure=OperationCleanupIncomplete('Private application I/O thread remains active; runtime reuse prohibited')
            if original is not None:failure.add_note('Original operation failure: '+repr(original))
            raise failure
        if cleanup_errors:
            if original is not None:original.add_note('Independent operation cleanup: '+repr(cleanup_errors))
            else:raise RuntimeError('Private operation cleanup incomplete: '+repr(cleanup_errors))


def callback(journal,config,data):
    protocol=owned_daemon.read_private_json(journal.path.parent.parent/'candidate-image-protocol.json')
    if protocol.get('schema')!='mldsafail.private-candidate-image-protocol.v1':
        raise ValueError('Explicit source-bound private image protocol required')
    worker=accepted_worker(protocol['worker_artifact'],protocol['prerequisites'],
        expected_image=config['image'],expected_archive_sha256=config['image_archive_sha256'],
        supervisor_source_sha256=config['supervisor_source_sha256'],loaded_images=data['loaded_images'])
    application=require_image(journal,protocol['application_artifact'],expected_source=config['source_commit'],loaded_images=data['loaded_images'])
    def images(*args):return application_rehearsal(*args,application_image=application['image'])
    return native_acceptance.callback(journal,config,data,retained_worker=worker,application_rehearsal=images)


def application_rehearsal(journal,config,data,protocol,root,backend,cohort,candidate_authority,cases,
                          prepared,authority,reference_key,epoch_hash,*,application_image):
    """Separate daemon and CPU domains for database/apps versus measured worker."""
    from sqlalchemy import create_engine,select
    from sqlalchemy.orm import Session
    from mldsafail.web.models import Base,User,Submission,EvaluationJob,ExperimentResult
    from mldsafail.web.services import create_api_token
    from mldsafail.benchmark_v060.evaluation import evaluate
    from mldsafail.benchmark_v060.envelope import verify
    import requests
    source=Path(__file__).resolve().parents[1]
    outer=owned_daemon.load_manifest(data['manifest_path'])
    pg=dict(protocol['postgres_artifact'])
    if set(pg)!={'image','image_archive','image_archive_sha256'}:
        raise ValueError('Exact separate PostgreSQL artifact required')
    additional=[row for row in config.get('additional_images',[]) if row['image']==application_image]
    if len(additional)!=1:raise ValueError('Exactly one retained private application archive required')
    inner=dict(config,**pg,state_root=str(root/'application-context'),additional_images=additional)
    inner['protected_roots']=config['protected_roots']+[v['path'] for v in outer['roots'].values()]
    inner['protected_cgroups']=config['protected_cgroups']+[outer['domain']['path'],outer['worker_domain']['path']]
    names=('DOCKER_HOST','DOCKER_CONTEXT','MLDSAFAIL_OPERATOR_DAEMON_MANIFEST','MLDSAFAIL_CPU_DAEMON_MANIFEST','XDG_CONFIG_HOME')
    previous={name:os.environ.get(name) for name in names}
    application={};original=None
    def execute(inner_journal,inner_config,inner_data):
        engine=gateway=None;failure=None;errors=[]
        try:
            domain=owned_daemon.load_manifest(inner_data['manifest_path'])['worker_domain']
            network='candidate-'+inner_data['id'];db=network+'-db';web=network+'-web';coordinator=network+'-coordinator'
            inner_journal.command(['docker','network','create',network],kind='network_create',timeout=30)
            inner_journal.command(['docker','run','-d','--name',db,'--network',network,'--network-alias','database',
                '--cgroup-parent',inner_data['worker_slice'],'--pids-limit','128','--memory','384m',
                '--tmpfs','/var/lib/postgresql/data:size=256m','-e','POSTGRES_HOST_AUTH_METHOD=trust',
                '-p','127.0.0.1::5432',pg['image']],kind='database_start',timeout=90)
            expires=time.monotonic()+60
            while inner_journal.command(['docker','exec',db,'pg_isready','-U','postgres'],check=False,timeout=10).returncode:
                if time.monotonic()>expires:raise TimeoutError('Disposable PostgreSQL readiness')
                time.sleep(.2)
            ports=json.loads(inner_journal.command(['docker','inspect',db],timeout=30).stdout)[0]['NetworkSettings']['Ports']['5432/tcp']
            if len(ports)!=1 or ports[0]['HostIp']!='127.0.0.1':raise RuntimeError('Loopback-only disposable database')
            database_port=ports[0]['HostPort']
            engine=create_engine('postgresql+psycopg://postgres@127.0.0.1:'+database_port+'/postgres')
            Base.metadata.create_all(engine)
            with Session(engine) as database:
                user=User(display_name='Private native image rehearsal');database.add(user);database.commit()
                _,token=create_api_token(database,user,'private-image')
            signing_key=secrets.token_bytes(32)
            def run_source(contestant,checkpoint):
                saved={name:os.environ.get(name) for name in names}
                try:
                    os.environ['DOCKER_HOST']='unix://'+data['socket']
                    os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']=data['manifest_path']
                    os.environ.pop('DOCKER_CONTEXT',None);os.environ.pop('MLDSAFAIL_CPU_DAEMON_MANIFEST',None)
                    envelope=evaluate(backend=backend,source=contestant,source_sha256=native_acceptance.python_identity(contestant),
                        supervisor_source_sha256=config['supervisor_source_sha256'],cohort=cohort,cases=cases,references=prepared['table'],
                        epoch_manifest_sha256=epoch_hash,reference_source_commit=config['source_commit'],reference_worker_image=backend.image,
                        reference_audit_sha256=prepared['table']['audit_receipt_sha256'],signing_key=signing_key,checkpoint=checkpoint,
                        reference_authority=authority,reference_authority_key=reference_key)
                    owned_daemon.publish(root/'candidate-envelope.json',envelope)
                    return envelope
                finally:
                    failures=native_acceptance.restore_environment(saved)
                    if failures:raise RuntimeError('Host evaluation environment restoration failed: '+repr(failures))
            gateway=Gateway(root=root/'gateway-evidence',worker_domain=domain,authority=candidate_authority,evaluate_source=run_source)
            work=root/'application-work';work.mkdir(mode=0o700)
            mounted=root/'application-config.json'
            owned_daemon.publish(mounted,dict(schema='mldsafail.private-candidate-application.v1',candidate_only=True,
                database_url='postgresql+psycopg://postgres@database:5432/postgres',gateway_socket='/candidate/gateway/candidate.sock',
                cohort=dataclasses.asdict(cohort),session_secret=secrets.token_hex(32),signing_key_hex=signing_key.hex(),work_root='/candidate/work'))
            for role,name in [('web',web),('coordinator',coordinator)]:
                args=application_create(name=name,image=application_image,role=role,network=network,
                    application_parent=inner_data['worker_slice'],gateway_root=gateway.shared,config_path=mounted,work_root=work)
                if role=='web':args[2:2]=['-p','127.0.0.1::8000']
                inner_journal.command(args,kind='application_create',timeout=60)
            inner_journal.command(['docker','start',web],kind='application_start',timeout=60)
            ports=json.loads(inner_journal.command(['docker','inspect',web],timeout=30).stdout)[0]['NetworkSettings']['Ports']['8000/tcp']
            if len(ports)!=1 or ports[0]['HostIp']!='127.0.0.1':raise RuntimeError('Loopback-only candidate website')
            base='http://127.0.0.1:'+ports[0]['HostPort']
            def readiness(cancel):
                expires=time.monotonic()+60
                while time.monotonic()<expires and not cancel.is_set():
                    try:
                        if requests.get(base+'/health/ready',timeout=2).status_code==200:return True
                    except requests.RequestException:pass
                    time.sleep(.2)
                raise TimeoutError('Private candidate HTTP readiness')
            serve_operation(gateway,readiness,seconds=65,journal=inner_journal,receipt=root/(secrets.token_hex(16)+'-io.json'))
            environment=root/'participant-environment';artifacts=root/'participant-artifact';artifacts.mkdir(mode=0o700)
            inner_journal.command(['uv','build','--wheel','--out-dir',str(artifacts),str(source)],kind='artifact_build',timeout=120)
            wheels=list(artifacts.glob('*.whl'))
            if len(wheels)!=1:raise RuntimeError('Exactly one installed source-bound participant wheel')
            inner_journal.command(['uv','venv','--system-site-packages','--python',__import__('sys').executable,str(environment)],kind='artifact_install',timeout=60)
            python=environment/'bin/python'
            inner_journal.command(['uv','pip','install','--python',str(python),'--no-deps',str(wheels[0])],kind='artifact_install',timeout=120)
            installed=inner_journal.command([str(python),'-I','-c','import mldsafail;print(mldsafail.__file__)']).stdout.decode().strip()
            if not Path(installed).is_relative_to(environment):raise RuntimeError('Participant import escaped installed environment')
            os.environ['XDG_CONFIG_HOME']=str(root/'cli-private')
            from mldsafail import cli
            cli._write_config(dict(server=base,token=token))
            workspace=work/'participant'
            inner_journal.command([str(python),'-I','-m','mldsafail.cli','clone',str(workspace),'--benchmark-version','0.6.0'],kind='participant_scaffold',timeout=60)
            commit=inner_journal.command(['git','-C',str(workspace),'rev-parse','HEAD'],timeout=15).stdout.decode().strip()
            application_environment=dict(os.environ)
            application_environment.update(DOCKER_HOST='unix://'+inner_data['socket'],
                MLDSAFAIL_OPERATOR_DAEMON_MANIFEST=inner_data['manifest_path'])
            application_environment.pop('DOCKER_CONTEXT',None)
            application_environment.pop('MLDSAFAIL_CPU_DAEMON_MANIFEST',None)
            application_environment=MappingProxyType(application_environment)
            serve_operation(gateway,lambda cancel:inner_journal.command([str(python),'-I','-m','mldsafail.cli','submit',
                '--repo','file:///candidate/work/participant','--commit',commit,'--hypothesis','private source-bound native image rehearsal',
                '--benchmark-version','0.6.0','--idempotency-key','private-image-'+secrets.token_hex(16)],kind='participant_submission',timeout=60,env=application_environment),seconds=65,journal=inner_journal,receipt=root/(secrets.token_hex(16)+'-io.json'))
            with Session(engine) as database:
                submission=database.scalar(select(Submission));job=database.scalar(select(EvaluationJob))
                if submission is None or job is None or job.status!='queued' or submission.benchmark_version!='0.6.0':raise RuntimeError('Candidate queue admission failed')
                submission_id=submission.id
            inner_journal.command(['docker','start',coordinator],kind='application_start',timeout=60)
            serve_operation(gateway,lambda cancel:inner_journal.command(['docker','wait',coordinator],kind='application_wait',timeout=1200,env=application_environment),seconds=1200,journal=inner_journal,receipt=root/(secrets.token_hex(16)+'-io.json'))
            state=json.loads(inner_journal.command(['docker','inspect',coordinator],timeout=30).stdout)[0]['State']
            if state['Running'] or state['ExitCode']!=0:raise RuntimeError('Private coordinator did not exit successfully')
            with Session(engine) as database:
                submission=database.get(Submission,submission_id);result=database.scalar(select(ExperimentResult))
                if submission.state!='accepted' or result is None or result.epoch_id!=cohort.epoch_id or result.benchmark_version!='0.6.0':
                    raise RuntimeError('Native image result was not accepted in its exact cohort')
                payload=verify(owned_daemon.read_private_json(root/'candidate-envelope.json',cap=8*1024*1024),signing_key,
                    cohort_id=cohort.public_id,source_sha256=result.source_digest)
                if payload['score']!=result.mlwe_score or payload['verified'] is not True:raise RuntimeError('Signed result does not match database')
                expected_score=result.mlwe_score
            headers={'Authorization':'Bearer '+token}
            candidate=requests.get(base+'/api/v1/leaderboard?benchmark_version=0.6.0',headers=headers,timeout=10)
            legacy=requests.get(base+'/api/v1/leaderboard',headers=headers,timeout=10)
            candidate.raise_for_status();legacy.raise_for_status()
            if candidate.json()['benchmark_version']!='0.6.0' or len(candidate.json()['leaderboard'])!=1 or legacy.json()['benchmark_version']!='0.5.0' or legacy.json()['leaderboard']!=[]:
                raise RuntimeError('Private candidate leaderboard isolation failed')
            if requests.get(base+'/api/v1/me',timeout=10).status_code!=401:raise RuntimeError('Unauthenticated private identity access')
            rendered=json.dumps(candidate.json())
            if any(value in rendered for value in (token,str(root),epoch_hash,reference_key.hex(),signing_key.hex())):
                raise RuntimeError('Host-private authority leaked through participant API')
            inner_journal.command(['docker','exec',db,'pg_dump','-U','postgres','-Fc','-f','/tmp/rehearsal.dump','postgres'],kind='database_backup',timeout=60)
            dump=root/'rehearsal.dump'
            inner_journal.command(['docker','cp',db+':/tmp/rehearsal.dump',str(dump)],kind='database_backup',timeout=60)
            os.chmod(dump,0o400)
            inner_journal.command(['docker','exec',db,'createdb','-U','postgres','restored'],kind='database_restore',timeout=30)
            inner_journal.command(['docker','exec',db,'pg_restore','-U','postgres','--exit-on-error','-d','restored','/tmp/rehearsal.dump'],kind='database_restore',timeout=60)
            restored=create_engine('postgresql+psycopg://postgres@127.0.0.1:'+database_port+'/restored')
            try:
                with Session(restored) as database:
                    rows=list(database.scalars(select(ExperimentResult)))
                    if len(rows)!=1 or rows[0].mlwe_score!=expected_score or rows[0].epoch_id!=cohort.epoch_id:
                        raise RuntimeError('Fresh isolated database restoration changed accepted result')
            finally:restored.dispose()
            # Restart is explicitly recorded as restart, never mislabeled rollback.
            inner_journal.command(['docker','stop','--time','10',web],kind='application_stop',timeout=30)
            inner_journal.command(['docker','start',web],kind='application_start',timeout=30)
            serve_operation(gateway,readiness,seconds=65,journal=inner_journal,receipt=root/(secrets.token_hex(16)+'-io.json'))
            repeated=requests.get(base+'/api/v1/leaderboard?benchmark_version=0.6.0',headers=headers,timeout=10)
            repeated.raise_for_status()
            if repeated.json()!=candidate.json():raise RuntimeError('Application restart changed accepted leaderboard')
            application.update(native_executed=True,behavior_passed=True,application_image=application_image,
                application_source_commit=config['source_commit'],actual_installed_cli=True,container_coordinator=True,
                main_thread_host_evaluation=True,signed_result_verified=True,cohort_isolation=True,
                disposable_database_restoration=True,application_restart=True,application_rollback_passed=False,
                independent_recovery_acceptance_passed=False,contract_adopted=False,default_changed=False,
                participant_wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest(),
                dump_sha256=hashlib.sha256(dump.read_bytes()).hexdigest(),submission_id=submission_id)
            return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
                source_sha256=config['acceptance_source_sha256'],evidence_refs=['application.json'])

        except BaseException as error:failure=error;raise
        finally:
            if isinstance(failure,OperationCleanupIncomplete):
                errors.append('Application I/O thread survives; runtime reuse prohibited')
            if gateway is not None:
                try:gateway.close()
                except BaseException as error:errors.append(repr(error))
            if engine is not None:
                try:engine.dispose()
                except BaseException as error:errors.append(repr(error))
            native_acceptance.finalize_application(root,application,failure,errors)
    try:native_driver.execute(inner,source,acceptance=execute,daemon_kind='owned')
    except BaseException as error:original=error;raise
    finally:
        errors=['Runtime reuse prohibited after surviving application I/O'] if isinstance(original,OperationCleanupIncomplete) else native_acceptance.restore_environment(previous)
        if errors:
            if original is None:raise RuntimeError('Nested application environment restoration failed: '+repr(errors))
            original.add_note('Nested application environment restoration failed: '+repr(errors))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    config=owned_daemon.read_private_json(args.config)
    result=native_driver.execute(config,Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')
    print(json.dumps(dict(native_executed=True,passed=result['native_acceptance_passed'],
        candidate_only=True,production_adopted=False,default_changed=False)))


if __name__=='__main__':main()
