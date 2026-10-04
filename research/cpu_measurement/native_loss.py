"""Real dedicated-daemon response-loss/owner-loss diagnostic probes.

Require a healthy reviewed native baseline first. Faults retain a real daemon
response before owner SIGKILL; cleanup must prove the entire old daemon and
worker parent empty before restart. This diagnostic never measures performance.
"""
import json
import os
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
from deploy import owned_client,owned_daemon
from research.cpu_measurement.ownership import canonical_directory,publish,Ownership
from research.cpu_measurement.reconcile import reconcile
from research.cpu_measurement import client as owned_streaming_client
from research.cpu_measurement.native_transport import drop_acknowledgement

CODE='''
import sys
from pathlib import Path
from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
run(sys.argv[1],Path(sys.argv[2]),sys.argv[3],Path(sys.argv[4]),generate_mlwe('small',0,1).public.to_dict(),lambda *args:False,ownership_directory=Path(sys.argv[5]),epoch='isolated-native-rpc-loss')
'''


def probe(args,output,*,operation,api_version):
    if not isinstance(api_version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+',api_version): raise ValueError('Explicit native Docker API version required')
    if operation not in {'create','start'}: raise ValueError('Exact native mutation required')
    manifest=owned_daemon.verify_environment(owned_daemon.load_manifest(),measurement_parent=args.parent)
    state=canonical_directory(args.parent)
    previous=json.loads((state/'journal.json').read_text())
    if previous['state']!='complete': raise RuntimeError('Healthy completed native baseline required')
    directory=Path(output).parent/('rpc-loss-'+os.urandom(12).hex())
    directory.mkdir(mode=0o700)
    real_docker=shutil.which('docker')
    if real_docker is None: raise RuntimeError('Native Docker unavailable')
    proxy=directory/'proxy.sock';listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    listener.bind(str(proxy));os.chmod(proxy,0o600);listener.listen(1);listener.settimeout(60)
    shim=directory/'docker'
    shim.write_text('#!'+sys.executable+'\nimport os,sys\nenv=dict(os.environ)\nif len(sys.argv)>1 and sys.argv[1]=='+repr(operation)+':\n env["DOCKER_HOST"]='+repr('unix://'+str(proxy))+'\n env["DOCKER_API_VERSION"]='+repr(api_version)+'\nos.execve('+repr(real_docker)+',['+repr(real_docker)+',*sys.argv[1:]],env)\n')
    shim.chmod(0o700)
    observed=threading.Event();release=threading.Event();transport_errors=[]
    receipt_path=directory/'transport.json'
    def transport():
        try:
            connection,_=listener.accept()
            upstream=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);upstream.connect(manifest['socket'])
            def retained():
                observed.set()
                if not release.wait(60): raise RuntimeError('Native owner-loss orchestration timed out')
            drop_acknowledgement(connection,upstream,receipt_path,operation,retained)
        except BaseException as error: transport_errors.append(repr(error))
    thread=threading.Thread(target=transport,daemon=True);thread.start()
    environment=dict(os.environ,PATH=str(directory)+os.pathsep+os.environ.get('PATH',''))
    class ToolOwner:
        def __init__(self):
            self.directory=directory
            self.record=dict(generation=os.urandom(16).hex(),mutations=[])
        def mutation(self,operation,**fields):
            self.record['mutations'].append(dict(operation=operation,**fields))
            publish(directory/'native-owner.json',self.record)
    tool_owner=ToolOwner()
    owner=owner_entry=None;cleanup_errors=[]
    result=dict(fault='SIGKILL_lost_'+operation+'_ack',passed=False,injection_reached=False)
    try:
        # Gated bootstrap and operator cgroup identities are durable before
        # this test owner can issue its first Docker mutation.
        old_environment=dict(os.environ)
        try:
            os.environ.update(environment)
            owner,owner_entry=owned_streaming_client.spawn([sys.executable,'-c',CODE,args.image,str(args.parent),args.cgroup_parent,
                 str(Path(__file__).parent/'fixtures'/'child'),str(state)],tool_owner,args.parent)
        finally:
            os.environ.clear();os.environ.update(old_environment)
        result['owner_identity']=owned_client.identity(owner.pid)
        if not observed.wait(60): raise RuntimeError('Actual daemon mutation response was not observed')
        transport_receipt=owned_daemon.read_private_json(receipt_path)
        if transport_receipt['actual_mutation_response_observed'] is not True: raise RuntimeError('Daemon mutation did not succeed')
        record=json.loads((state/'journal.json').read_text())
        if record['generation']==previous['generation'] or not any(entry['operation']=='host_client_release_intent' and entry.get('phase')==operation for entry in record['mutations']):
            raise RuntimeError('Durable released guardian phase was not observed')
        if operation=='start':
            created=[row['container_id'] for row in record['mutations'] if row['operation']=='daemon_mutation_acknowledged' and row.get('operation_name')=='create']
            if len(created)!=1: raise RuntimeError('Started worker has no exact retained create ID')
            inspected=json.loads(subprocess.check_output([real_docker,'inspect',created[0]],timeout=15))[0]
            if inspected['State']['Running'] is not True or inspected['Config']['OpenStdin'] is not True or any(row['operation']=='input_delivery_intent' for row in record['mutations']):
                raise RuntimeError('Open stdin did not keep started worker alive before attach/input')
            result['open_stdin_start_before_attach']=True
        result.update(injection_reached=True,transport=transport_receipt,generation=record['generation'])
        os.kill(owner.pid,signal.SIGKILL);owner.wait(timeout=10)
        release.set();thread.join(timeout=10)
        if thread.is_alive(): raise RuntimeError('Native transport did not terminate')
        try:
            with Ownership(state,args.parent): pass
        except RuntimeError as error: result['fenced']='reconciliation' in str(error)
    finally:
        release.set()
        try:
            if owner is not None and owner.poll() is None: owner.kill();owner.wait(timeout=10)
        except BaseException as error: cleanup_errors.append(dict(step='native_owner',error=repr(error)))
        if owner_entry is not None:
            try: owned_client.stop(owner_entry)
            except BaseException as error: cleanup_errors.append(dict(step='native_owner_domain',error=repr(error)))
        if owner is not None:
            for stream in (owner.stdin,owner.stdout,owner.stderr):
                try: stream.close()
                except BaseException as error: cleanup_errors.append(dict(step='native_owner_pipe',error=repr(error)))
        try: listener.close()
        except BaseException as error: cleanup_errors.append(dict(step='native_listener',error=repr(error)))
        thread.join(timeout=10)
        if thread.is_alive(): cleanup_errors.append(dict(step='native_transport',error='Thread remains alive'))
        try: cleanup=reconcile(state,args.parent)
        except BaseException as error: cleanup=dict(cleanup_complete=False,error=repr(error))
        try:
            if proxy.exists(): proxy.unlink()
        except BaseException as error: cleanup_errors.append(dict(step='native_socket',error=repr(error)))
        result.update(cleanup=cleanup,cleanup_errors=cleanup_errors,transport_errors=transport_errors)
        result['daemon_epoch_repaired']=False
        try:
            repaired=json.loads((state/'journal.json').read_text())
            result['daemon_epoch_repaired']=any(entry['operation']=='daemon_epoch_repaired' for entry in repaired['mutations'])
        except BaseException as error: cleanup_errors.append(dict(step='repair_journal',error=repr(error)))
        result['passed']=result['injection_reached'] and result.get('fenced',False) and cleanup['cleanup_complete'] and result['daemon_epoch_repaired'] and not cleanup_errors and not transport_errors
        publish(Path(output),result)
    if not result['passed']: raise RuntimeError('Native real lost-mutation acknowledgement gate failed')
    return result
