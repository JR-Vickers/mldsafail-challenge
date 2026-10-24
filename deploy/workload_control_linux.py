"""Bounded inert Linux process controls; no Docker or installed-native claims.

This adapter makes creator acknowledgements and cleanup operate on real owned
processes. Capacity/preflight denial remains an explicit fixture hook. It cannot
prove Docker routing, cgroup enforcement, filesystem quotas or host scheduling.
"""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

from deploy.workload_control_fixture import FixtureRuntime, execute as fixture_execute
from mldsafail.evaluator.native_workload import process_birth, require

from deploy.workload_control_registry import LOCAL_CASES as CASES


class ProcessRuntime(FixtureRuntime):
    def __init__(self,root):
        super().__init__()
        self.root=Path(root);self.children=[];self.births=[]
        self.host=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            daemon_id='generation-owned-inert-process-fixture')

    def launch(self,state,specification):
        marker=self.root/('start-'+str(len(self.children)))
        code='''import pathlib,sys,time
marker=pathlib.Path(sys.argv[1])
while not marker.exists():time.sleep(.01)
time.sleep(20)
'''
        def limits():
            resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2))
            resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
        self.calls.append('create')
        child=subprocess.Popen([sys.executable,'-B','-c',code,str(marker)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            close_fds=True,preexec_fn=limits)
        self.children.append(child)
        identity=process_birth(child.pid);self.births.append(identity);self.live=True
        if self.ack_lost=='create':raise OSError('fixture_create_ack_lost')
        self.calls.append('start');marker.write_text(state['workload_id'])
        if self.ack_lost=='start':raise OSError('fixture_start_ack_lost')
        return identity

    def inspect(self,state,birth):
        try:return process_birth(birth['pid'])==birth
        except FileNotFoundError:return False

    def sample(self,state):
        sample=super().sample(state)
        meminfo={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        sample['available']=meminfo['MemAvailable'];sample['disk_free']=shutil.disk_usage(self.root).free
        memory=0
        for child,identity in zip(self.children,self.births):
            if child.poll() is not None:continue
            require(process_birth(child.pid)==identity,'fixture_descendant_replaced')
            status=(Path('/proc')/str(child.pid)/'status').read_text().splitlines()
            memory+=sum(int(line.split()[1])*1024 for line in status if line.startswith('VmRSS:'))
        sample['memory']=memory
        return sample

    def terminate(self,state):
        self.calls.append('terminate')
        if not self.cleanup:return False
        self.final_cleanup()
        return self.stopped(state)

    def stopped(self,state):
        stopped=all(child.poll() is not None for child in self.children)
        self.live=not stopped
        return stopped

    def final_cleanup(self):
        for child,identity in zip(self.children,self.births):
            if child.poll() is None:
                require(process_birth(child.pid)==identity,'fixture_descendant_replaced')
                child.kill()
            child.wait(timeout=.65)
        self.live=False

    def snapshot(self):
        row=super().snapshot()
        row['processes']=[dict(identity=birth,returncode=child.poll()) for child,birth in zip(self.children,self.births)]
        row['limits']=dict(address_space_bytes=64*1024**2,pids=32)
        return row


def execute(control,scenario,root):
    require(sys.platform=='linux','linux_control_fixture_requires_linux')
    require((control,scenario) in CASES,'linux_control_fixture_case_not_implemented')
    result=fixture_execute(control,scenario,root,runtime_factory=ProcessRuntime)
    observations=result['observations']
    if 'containers' in observations:observations['owned_processes']=observations.pop('containers')
    observations.pop('populated',None)  # cgroup population is not measured by this process-only adapter.
    result['origin']='local_linux'
    result['scope']='generation_owned_inert_processes_only'
    result['installed_native_eligible']=False
    return result
