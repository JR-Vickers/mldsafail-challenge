import json, sys, time
from research.primitive_selection.constants import PROFILES
from research.primitive_selection.generator import generate_mlwe
import subprocess
def _invoke(instance,solver):
 started=time.perf_counter()
 try:
  completed=subprocess.run([sys.executable,'-m','research.primitive_selection.worker'],input=json.dumps({'instance':instance.to_dict(),'solver':solver}).encode(),capture_output=True,timeout=60)
  result=json.loads(completed.stdout)
 except subprocess.TimeoutExpired:
  result={'timeout':True}
 except Exception as exc:
  result={'error':str(exc),'stderr':completed.stderr.decode()}
 result['process_wall_seconds']=time.perf_counter()-started
 return result
PROFILES.update({'small': {'n':4,'q':97,'k':2,'l':1,'msis_rows':2,'msis_cols':3}, 'medium':{'n':8,'q':97,'k':2,'l':2,'msis_rows':2,'msis_cols':3}, 'large':{'n':16,'q':193,'k':3,'l':2,'msis_rows':3,'msis_cols':4}})
for profile in PROFILES:
 for eta in (1,2):
  for seed in range(3):
   instance=generate_mlwe(profile,seed,eta).public
   for solver in ('exhaustive','primal-lll','primal-bkz','hybrid-bdd'):
    result=_invoke(instance,solver)
    print(json.dumps({'profile':profile,'configuration':PROFILES[profile],'eta':eta,'seed':seed,'solver':solver,'instance_id':instance.instance_id,'result':result}),flush=True)
