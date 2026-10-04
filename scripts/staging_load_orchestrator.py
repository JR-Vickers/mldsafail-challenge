"""Durable private-staging read-load acceptance; sole native operator only.

Never retries an uncertain submission POST. Resume reconciles the existing
idempotency record and verifies evidence; it never repeats a measurement.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import queue
import threading
import datetime as dt
import subprocess
import time
import urllib.request
import uuid
import math
import stat
import re
from contextlib import ExitStack

from deploy import owned_client, owned_daemon
from deploy.recovery_journal import atomic_json
from scripts import staging_read_load

SOURCE = '6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf'
FIXTURE = 'e547caffb06ced2e82f28cf1c130c8131613384d'
PROTOCOL_SHA = 'c39bdb683d6b08ef5b76851c2944a3fa82f8b7041ccdc433e03cfc8eca029004'
READ_LOAD_SHA = 'b1708d02a46e9e3d3b98ca1ef09ffa8a1894b442d769211b4836a337dd4a9efe'


def require(value, message):
    if not value: raise RuntimeError(message)


class Progress:
    """Private bounded asynchronous partial evidence; never captures headers."""
    def __init__(self,path):
        self.path=path;self.queue=queue.Queue(maxsize=1560);self.stopping=threading.Event();self.errors=[]
        self.descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        self.thread=threading.Thread(target=self.write,name='staging-load-private-evidence',daemon=True)
        try:self.thread.start()
        except BaseException:os.close(self.descriptor);raise
    def record(self,item):
        if self.errors:raise RuntimeError('Partial load evidence publication failed')
        self.queue.put_nowait(item)
    def write(self):
        last=time.monotonic()
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                try:item=self.queue.get(timeout=.2)
                except queue.Empty:item=None
                if item is not None:
                    block=(json.dumps(item,separators=(',',':'))+'\n').encode()
                    require(len(block)<4096,'Partial request record exceeds cap')
                    view=memoryview(block)
                    while view:
                        size=os.write(self.descriptor,view);require(size>0,'Partial evidence short write');view=view[size:]
                if time.monotonic()-last>=5:os.fsync(self.descriptor);last=time.monotonic()
            os.fsync(self.descriptor)
        except BaseException as error:self.errors.append(type(error).__name__)
        finally:
            try:os.close(self.descriptor)
            except BaseException as error:self.errors.append(type(error).__name__)
    def close(self):
        self.stopping.set();self.thread.join(timeout=10)
        require(not self.thread.is_alive() and not self.errors,'Partial evidence cleanup/publication incomplete')


class Operator:
    def __init__(self, config, root):
        self.c=config;self.root=root;self.path=root/'journal.json'
        binding=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.token=owned_daemon.read_private_json(config['credentials'])['token']
        self.j=owned_daemon.read_private_json(self.path) if self.path.exists() else dict(
            schema='mldsafail.staging-load-journal.v1',run_id=uuid.uuid4().hex,gate=config['gate'],
            configuration_sha256=binding,clients=[],passed=False,cleanup_complete=False,protocol_sha256=PROTOCOL_SHA,
            source_commit=subprocess.check_output(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],timeout=15).decode().strip(),
            orchestrator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            probe_sha256=config['probe_sha256'],started_at=time.time(),state='prepared')
        require(self.j['configuration_sha256']==binding,'Run configuration changed; cleanup requires original authority')
        require(self.j['gate']==config['gate'] and self.j['protocol_sha256']==PROTOCOL_SHA,'Journal protocol mismatch')
        require(self.j['probe_sha256']==config['probe_sha256'],'Journal probe source mismatch')
        if not self.path.exists():self.save()

    def save(self):atomic_json(self.path,self.j)

    def command(self,argv,**kwargs):
        return owned_client.run(argv,self.j['clients'],self.save,self.root,timeout=kwargs.pop('timeout',30),capture_output=True,**kwargs).stdout

    def probe(self,action,**fields):
        code=Path(self.c['probe_source']).read_text()
        require(hashlib.sha256(code.encode()).hexdigest()==self.c['probe_sha256'],'Probe source changed')
        request=json.dumps(dict(action=action,**fields))
        wrapper='import io,sys;sys.stdin=io.StringIO('+repr(request)+');exec('+repr(code)+')'
        response=json.loads(self.command(['docker','exec','-i',self.c['coordinator_container'],'/app/.venv/bin/python','-'],input=wrapper.encode()))
        require(not response.get('probe_failed'),'Read-only native probe failed')
        return response

    def api(self,route,payload=None,key=None,json_response=True):
        headers={'Authorization':'Bearer '+self.token}
        if key:headers['Idempotency-Key']=key
        if payload is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request('http://127.0.0.1:8080'+route,headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None)
        with urllib.request.urlopen(request,timeout=10) as response:
            raw=response.read(4*1024*1024+1)
            require(len(raw)<=4*1024*1024,'API response exceeds cap')
            require(response.status in (200,201),'API response failed')
        text=raw.decode();self.probe('privacy',text=text)
        return (json.loads(text) if text else {}) if json_response else text

    def containers(self):
        ids=self.command(['docker','ps','-aq']).decode().split()
        return json.loads(self.command(['docker','inspect',*ids])) if ids else []

    def identity(self):
        release=owned_daemon.read_private_json(self.c['release_manifest'])
        require(release['source_commit']==SOURCE,'Compatible retained application source required')
        images=self.containers()
        for role in ('web','coordinator'):
            found=[row for row in images if row['Name'].lstrip('/')==self.c[role+'_container']]
            require(len(found)==1 and found[0]['Image']==release['images'][role]['id'],'Deployed application image identity mismatch')
            require(found[0]['State']['Running'] and found[0]['State'].get('Health',{}).get('Status')=='healthy','Application not healthy')
        require(len(self.c['service_images'])==4,'Exact four-service health inventory required')
        for name,image in self.c['service_images'].items():
            found=[row for row in images if row['Name'].lstrip('/')==name]
            require(len(found)==1 and found[0]['Image']==image and found[0]['State']['Running']
                and found[0]['State'].get('Health',{}).get('Status')=='healthy','Service health/image changed')
        value=self.probe('identity')
        require(value['worker']==release['images']['worker']['id'],'Frozen worker identity mismatch')
        return value

    def guard(self, allowed=None):
        active=self.probe('active')['active']
        require(set(active)<=({allowed} if allowed else set()),'Unrelated queued or active work')
        workers=[row for row in self.containers() if row['Name'].startswith('/mlwe-') and row['State']['Running']]
        require(len(workers)<=1,'Concurrent worker execution')
        for worker in workers:
            mounts=worker.get('Mounts',[])
            require(allowed and len(mounts)==1 and mounts[0]['Destination']=='/solver' and mounts[0]['RW'] is False
                and mounts[0]['Source']==self.c['evaluator_work_root']+'/runs/'+allowed+'/1/solver','Unrelated worker')
            require(worker['Image']==self.j['identity']['worker'],'Worker image changed')
        available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
        return available>=134217728 and shutil.disk_usage('/srv').free>=5368709120

    def reconcile(self):
        if self.j.get('submission_intent') and not self.j.get('submission'):
            existing=self.probe('lookup',key=self.j['submission_intent']['key'],user=self.c['user_id'])['submission']
            if existing:self.j['submission']=existing;self.save()
        return self.j.get('submission')

    def submit_once(self):
        if self.j.get('submission_intent'):
            require(self.reconcile(),'Uncertain prior POST remains fenced; never resubmit')
            return self.j['submission']
        intent=dict(key=self.j['run_id']+'-reference-load',request=dict(repository_url=self.c['fixture_repository'],
            commit_sha=FIXTURE,solver_path='reference',benchmark_version='0.5.0',
            hypothesis='Predeclared private staging reference-read-load acceptance',tags=['private-load-acceptance']),post_intent_at=time.time(),post_intent_monotonic=time.monotonic(),boot_id=owned_client.boot_id())
        self.j['submission_intent']=intent;self.save()  # Durable BEFORE first network operation.
        try:
            response=self.api('/api/v1/submissions',intent['request'],key=intent['key'])
            identifier=response['submission']['id'];require(isinstance(identifier,str) and identifier,'Malformed submission acknowledgement')
            self.j['submission']=identifier;self.save()
        except BaseException as error:
            try:
                existing=self.reconcile()
                if existing:return existing
            except BaseException as lookup:error.add_note('Idempotency lookup failed: '+type(lookup).__name__)
            raise
        return identifier

    def wait_state(self, predicate, identifier, deadline):
        while True:
            require(self.guard(identifier),'Host resource floor violation')
            state=self.probe('state',submission=identifier)
            if predicate(state):return state
            require(time.monotonic()<deadline,'Complete evaluation 1200-second ceiling exceeded')
            time.sleep(min(2,max(0,deadline-time.monotonic())))

    def verify_terminal(self, identifier, deadline):
        state=self.wait_state(lambda row:row['job_status'] in {'complete','failed'},identifier,deadline)
        require(state['state']=='accepted' and state['job_status']=='complete','Reference evaluation not accepted')
        require(state['attempt_count']==1 and len(state['attempts'])==1 and state['attempts'][0]['status']=='accepted','Reference retry or attempt disposition differs')
        require(state['transitions']==['queued','validating','running','accepted'] and len(state['results'])==1,'Reference transitions/result count differ')
        finished=dt.datetime.fromisoformat(state['attempts'][0]['finished'])
        require(finished.tzinfo is not None and finished.timestamp()<=self.j['submission_intent']['post_intent_at']+1200,'Actual reference completion exceeded ceiling')
        audit=self.probe('audit',submission=identifier,kind='reference');require(audit['evidence_verified'] is True,'Reference evidence audit failed')
        require(self.api('/api/v1/submissions/'+identifier)['submission']['state']=='accepted','API terminal state differs')
        self.api('/api/v1/submissions/'+identifier+'/logs')
        ranks={row['submission'] for row in self.api('/api/v1/leaderboard')['leaderboard']}
        require(all(result in ranks for result in state['results']),'Audited result absent from leaderboard')
        for result in state['results']:self.api('/experiment/'+result,json_response=False)
        self.j['terminal']=state;self.j['audit']=audit;self.save()

    def execute(self):
        resume=self.j['state']!='prepared'
        if not resume:
            require(self.guard(),'Initial queue/resource floor not idle')
            self.j['identity']=self.identity()
            require(self.api('/api/v1/me')['id']==self.c['user_id'],'Credential owner differs from lookup authority')
            self.j['state']='preflight_passed';self.save()
        identifier=self.reconcile()
        if self.c['gate']=='reference-read-load':
            if resume:
                require(identifier,'Interrupted request remains fenced; no resubmission')
            else:identifier=self.submit_once()
            require(self.j['submission_intent']['boot_id']==owned_client.boot_id(),'Interrupted evaluation crossed a host boot; remains fenced')
            deadline=self.j['submission_intent']['post_intent_monotonic']+1200
            if not resume:
                self.wait_state(lambda row:row['state']=='running',identifier,deadline)
        else:deadline=time.monotonic()+1200
        if not resume:
            require(time.monotonic()<deadline,'Evaluation ceiling expired before measurement')
            self.j['measurement_started_at']=time.time();self.j['state']='measuring';self.save()
            progress=Progress(self.root/'partial-requests.jsonl')
            measurement_error=None
            try:result=staging_read_load.run('http://127.0.0.1:8080',self.token,lambda:self.guard(identifier),duration=300,progress=progress.record)
            except BaseException as error:measurement_error=error;raise
            finally:
                try:progress.close()
                except BaseException as publication:
                    if measurement_error is None:raise
                    measurement_error.add_note('Partial evidence close failed: '+type(publication).__name__)
            self.j['measurement']=result;self.j['state']='measurement_complete';self.save()
            require(time.monotonic()<=deadline,'Evaluation ceiling exceeded during read load')
        require(self.j.get('measurement'),'Interrupted measurement retained; do not repeat unchanged experiment')
        if identifier:self.verify_terminal(identifier,deadline)
        require(self.guard(),'Final queue/resources not idle')
        require(not [row for row in self.containers() if row['Name'].startswith('/mlwe-')],'Worker cleanup incomplete')
        require(self.identity()==self.j['identity'],'Private epoch/worker identity changed')
        self.api('/',json_response=False)
        for route in ('/health/ready','/api/v1/me'):
            self.api(route)
        measurement=self.j['measurement']
        require(measurement.get('duration_seconds')==300 and measurement.get('requests')==1560
            and measurement.get('read_failures')==0 and measurement.get('host_floor_violations')==0
            and measurement.get('solver_jobs_submitted')==0
            and all(type(measurement.get(key)) in (int,float) and math.isfinite(measurement[key])
                and 0<=measurement[key]<limit for key,limit in [('p95_seconds',1),('p99_seconds',2)]),'Frozen measurement criteria differ')
        self.j['passed']=measurement['passed'] is True;self.j['state']='verified';self.save()
        require(self.j['passed'],'Frozen load thresholds failed')

    def cleanup(self):
        errors=[]
        clients=self.j.get('clients')
        if not isinstance(clients,list) or any(not isinstance(entry,dict) for entry in clients):
            self.j.setdefault('corrupt_clients_receipt',clients)
            self.j['clients']=[entry for entry in clients if isinstance(entry,dict)] if isinstance(clients,list) else []
        if 'corrupt_clients_receipt' in self.j:errors.append('CorruptClientAuthority')
        try:
            identifier=self.reconcile()
            if self.j.get('submission_intent') and not identifier:raise RuntimeError('Unresolved request intent remains fenced')
            if identifier:
                state=self.probe('state',submission=identifier)
                if state['job_status'] not in {'complete','failed'}:
                    self.api('/api/v1/submissions/'+identifier+'/cancel',{})
                    self.wait_state(lambda row:row['job_status'] in {'complete','failed'},identifier,time.monotonic()+90)
            require(self.guard(),'Cleanup queue/resources not idle')
            require(not [row for row in self.containers() if row['Name'].startswith('/mlwe-')],'Worker remains after cleanup')
            require(self.identity()==self.j['identity'],'Cleanup identity changed')
        except BaseException as error:errors.append(type(error).__name__)
        for entry in list(self.j['clients']):
            try:owned_client.stop(entry)
            except BaseException as error:errors.append(type(error).__name__)
        self.j['cleanup_complete']=not errors;self.j['cleanup_errors']=errors
        if errors:self.j['passed']=False
        try:self.save()
        except BaseException as original:
            self.j['passed']=False;self.j['cleanup_complete']=False
            self.j['evidence_publication_failed']=True
            self.j['cleanup_errors'].append(type(original).__name__)
            try:self.save()
            except BaseException as publication:original.add_note('Negative cleanup publication failed: '+type(publication).__name__)
            raise
        return not errors


def run(config, cleanup_only=False, cleanup_source_commit=None):
    source=Path(__file__).resolve().parents[1]
    require(not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],timeout=15),'Clean retained operator source required')
    require(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],timeout=15).decode().strip()==(cleanup_source_commit or config['operator_source_commit']),'Operator source commit mismatch')
    require(hashlib.sha256((source/'docs/acceptance/public-launch/staging-load-protocol.json').read_bytes()).hexdigest()==PROTOCOL_SHA,'Frozen protocol file changed')
    require(hashlib.sha256(Path(staging_read_load.__file__).read_bytes()).hexdigest()==READ_LOAD_SHA,'Frozen read-load implementation changed')
    require(config['gate'] in {'idle-read-load','reference-read-load'},'Unknown gate')
    require(re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',config['fixture_repository']),'Reviewed GitHub fixture repository required')
    require(config['protocol_sha256']==PROTOCOL_SHA,'Predeclared protocol changed')
    root=owned_daemon._canonical(config['run_directory']);root.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with ExitStack() as leases:
        hostlock_path=Path('/run/user')/str(os.getuid())/'mldsafail-staging-read-load.lock'
        hostlock=os.open(hostlock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        leases.callback(os.close,hostlock)
        info=os.fstat(hostlock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and not info.st_mode&0o077,'Private host load lock required')
        fcntl.flock(hostlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        lock=os.open(root.with_name('.'+root.name+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        leases.callback(os.close,lock)
        info=os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and not info.st_mode&0o077,'Private run lock required')
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not root.exists():root.mkdir(mode=0o700)
        require(root.stat().st_uid==os.getuid() and not root.stat().st_mode&0o077,'Private run directory required')
        operator=Operator(config,root);original=None
        try:
            if cleanup_only:
                operator.j.setdefault('cleanup_generations',[]).append(dict(source_commit=cleanup_source_commit or config['operator_source_commit'],
                    orchestrator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
                operator.save()
            if not cleanup_only:operator.execute()
        except BaseException as error:
            original=error;operator.j['failure_class']=type(error).__name__;operator.j['passed']=False
            try:operator.save()
            except BaseException as publication:error.add_note('Failure publication failed: '+type(publication).__name__)
            raise
        finally:
            try:
                clean=operator.cleanup()
                if not clean and original is None:raise RuntimeError('Owned cleanup remains incomplete')
            except BaseException as cleanup:
                if original is None:raise
                original.add_note('Cleanup failed: '+type(cleanup).__name__)
        return dict(passed=operator.j['passed'],cleanup_complete=operator.j['cleanup_complete'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--cleanup',action='store_true');parser.add_argument('--cleanup-source-commit');args=parser.parse_args()
    print(json.dumps(run(owned_daemon.read_private_json(args.config),args.cleanup,args.cleanup_source_commit)))


if __name__=='__main__':main()
