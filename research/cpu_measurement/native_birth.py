"""Real owner SIGKILL between durable bootstrap acknowledgement and exec release."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from research.cpu_measurement.ownership import canonical_directory, publish, Ownership
from research.cpu_measurement.native_lifecycle import wait_for
from research.cpu_measurement.reconcile import reconcile

CODE = '''
import os,signal,sys
from pathlib import Path
from research.cpu_measurement.ownership import Ownership
from research.cpu_measurement.harness import run
from mldsafail.benchmark_v050.generator import generate_mlwe
original=Ownership.mutation
def save(self,operation,**fields):
    original(self,operation,**fields)
    if operation=='host_client_domain' and fields.get('pid') is not None:
        os.kill(os.getpid(),signal.SIGSTOP)
Ownership.mutation=save
run(sys.argv[1],Path(sys.argv[2]),sys.argv[3],Path(sys.argv[4]),generate_mlwe('small',0,1).public.to_dict(),lambda *args:False,ownership_directory=Path(sys.argv[5]),epoch='isolated-native-birth-gap')
'''


def probe(args, output):
    state=canonical_directory(args.parent)
    previous=json.loads((state/'journal.json').read_text())['generation']
    source=Path(__file__).parent/'fixtures'/'child'
    owner=subprocess.Popen([sys.executable,'-c',CODE,args.image,str(args.parent),args.cgroup_parent,str(source),str(state)],
                           stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    result=dict(fault='SIGKILL_before_client_exec',passed=False,injection_reached=False)
    cleanup_errors=[]
    try:
        def acknowledged():
            record=json.loads((state/'journal.json').read_text())
            suspended = (Path('/proc')/str(owner.pid)/'stat').read_text().split(') ',1)[1].split()[0]=='T'
            return record if suspended and record['generation']!=previous and any(row['operation']=='host_client_domain' and row.get('pid') is not None for row in record['mutations']) else None
        record=wait_for(acknowledged)
        result.update(generation=record['generation'],injection_reached=True)
        os.kill(owner.pid,signal.SIGKILL)
        owner.wait(timeout=10)
        fenced=False
        try:
            with Ownership(state,args.parent): pass
        except RuntimeError as error:
            fenced='reconciliation' in str(error)
        result['fenced']=fenced
    finally:
        try:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=10)
        except Exception as error:
            cleanup_errors.append(dict(step='birth_owner_cleanup',error=repr(error)))
        try:
            cleanup=reconcile(state,args.parent)
        except Exception as error:
            cleanup={'cleanup_complete':False,'error':repr(error)}
        result.update(cleanup=cleanup,cleanup_errors=cleanup_errors)
        result['passed']=result['injection_reached'] and result.get('fenced',False) and cleanup['cleanup_complete'] and not cleanup_errors
        publish(Path(output),result)
    if not result['passed']:
        raise RuntimeError('Native client birth-gap fault or cleanup failed')
    return result
