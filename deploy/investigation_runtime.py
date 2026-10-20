"""Native host investigation adapter. Import/construction never launches workload."""
import json
import os
from pathlib import Path
import platform
import selectors
import subprocess
import time

from deploy.capacity_investigation import Runner, admission
from deploy.capacity_monitor import Monitor
from deploy.capacity_sampler import Sampler
from deploy.maintenance_transport import OwnedHelper
from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json, safe_path

LABEL='org.mldsafail.capacity-investigation'


class LoggedClient:
    """Incremental combined operation-log ceiling, including active client output."""
    def __init__(self, process, stdout, stderr, budget):
        self.process,self.stdout,self.stderr,self.budget=process,stdout,stderr,budget
        self.selector=selectors.DefaultSelector()
        for source,target in ((process.stdout,stdout),(process.stderr,stderr)):
            os.set_blocking(source.fileno(),False)
            self.selector.register(source,selectors.EVENT_READ,target)

    def poll(self):
        for key,_ in self.selector.select(0):
            data=os.read(key.fileobj.fileno(),65536)
            if not data:
                self.selector.unregister(key.fileobj)
                continue
            if self.budget['bytes']+len(data)>128*1024**2:
                raise RuntimeError('investigation_log_output_limit')
            key.data.write(data)
            key.data.flush()
            self.budget['bytes']+=len(data)
        status=self.process.poll()
        if status is not None and not self.selector.get_map():
            return status
        return None

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.selector.close()
        self.stdout.close()
        self.stderr.close()
        return self.process.poll() is not None


class NativeInvestigation:
    def __init__(self,root,packet,configuration):
        self.root=safe_path(Path(root).absolute())
        self.packet,self.configuration=packet,configuration
        self.controllers,self.clients=[],[]
        self.births={}
        self.log_budget={'bytes':0}
        self.command_helper=object.__new__(OwnedHelper)
        self.command_helper.docker=list(configuration['docker'])
        self.command_helper.runner=None

    def command(self,args):
        return self.command_helper.command(args)

    def host_gate(self):
        if platform.system()!='Linux' or platform.machine()!='x86_64':
            raise RuntimeError('investigation_native_amd64_host_required')
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=self.packet['host']['boot_id']:
            raise RuntimeError('investigation_host_boot_changed')
        from deploy.owned_client import domain_identity
        if domain_identity(self.configuration['operation_parent']['path'])!=self.configuration['operation_parent']:
            raise RuntimeError('investigation_operation_parent_changed')
        leaf=self.configuration['control_leaf']
        if (domain_identity(leaf['path'])!=leaf or not Path(leaf['path']).is_relative_to(self.configuration['operation_parent']['path'])
                or leaf['path']==self.configuration['operation_parent']['path']):
            raise RuntimeError('investigation_control_leaf_changed')
        current=Path('/proc/self/cgroup').read_text().strip()
        relative='/'+str(Path(leaf['path']).relative_to('/sys/fs/cgroup'))
        if current!='0::'+relative:
            raise RuntimeError('investigation_control_not_in_operation_parent')
        info=json.loads(self.command(['info','--format','{{json .}}']))
        if (info['ID']!=self.packet['host']['daemon_id'] or info['Architecture'] not in ('x86_64','amd64')
                or str(info['CgroupVersion'])!='2'):
            raise RuntimeError('investigation_daemon_changed')
        return True

    def identity(self):
        self.host_gate()
        identifiers=self.command(['ps','--all','--quiet','--no-trunc','--filter','label='+LABEL+'='+self.packet['operation_id']]).decode().split()
        workers=0
        for identifier in identifiers:
            row=json.loads(self.command(['inspect',identifier]))[0]
            name=row['Name'].lstrip('/')
            if row['Config']['Labels'].get(LABEL)!=self.packet['operation_id']:
                raise RuntimeError('investigation_operation_label_changed')
            if name.startswith('mlwe-'):
                if row['Config']['Image']!=self.packet['worker']['index']:
                    raise RuntimeError('investigation_worker_image_changed')
                if row['State']['Running']: workers+=1
            elif not (name=='capacity-artifacts-'+self.packet['operation_id'] or any(c['name']==name for c in self.controllers)):
                raise RuntimeError('investigation_unexpected_container')
            if row['State']['Running']:
                birth=(row['Id'],row['State']['StartedAt'],row['State']['Pid'])
                if identifier in self.births and self.births[identifier]!=birth:
                    raise RuntimeError('investigation_container_restarted')
                self.births[identifier]=birth
                membership=Path('/proc')/str(row['State']['Pid'])/'cgroup'
                cg=membership.read_text().strip().removeprefix('0::')
                parent=Path(self.configuration['operation_parent']['path']).relative_to('/sys/fs/cgroup')
                if not Path(cg).is_relative_to('/'+str(parent)):
                    raise RuntimeError('investigation_container_escaped_scope')
        if workers>1:
            raise RuntimeError('investigation_worker_concurrency_exceeded')
        return True

    def health(self):
        # The reviewed host proposal binds all retained service identities.
        for expected in self.configuration['retained_services']:
            row=json.loads(self.command(['inspect',expected['Id']]))[0]
            if (row['Id']!=expected['Id'] or row['State']['StartedAt']!=expected['StartedAt']
                    or not row['State']['Running'] or row['State'].get('Health',{}).get('Status','healthy')!='healthy'):
                raise RuntimeError('investigation_retained_service_degraded')
        return True

    def launch(self,command):
        self.identity()
        args=command['argv']
        if args[:2]!=['docker','run'] or '--rm' in args or '--name' not in args:
            raise ValueError('investigation_controller_shape_invalid')
        name=args[args.index('--name')+1]
        record=dict(name=name,phase=command['phase'],state='create_intent')
        self.controllers.append(record)
        atomic_json(self.root/'controllers.json',self.controllers)
        cid=self.command(['create',*args[2:]]).decode().strip()
        row=json.loads(self.command(['inspect',cid]))[0]
        if row['Id']!=cid or row['Name']!='/'+name or row['Config']['Labels'].get(LABEL)!=self.packet['operation_id']:
            raise RuntimeError('investigation_controller_launch_ambiguous')
        record.update(container_id=cid,state='start_intent')
        atomic_json(self.root/'controllers.json',self.controllers)
        out=(self.root/(command['phase']+'.stdout')).open('xb')
        err=(self.root/(command['phase']+'.stderr')).open('xb')
        os.chmod(out.name,0o600);os.chmod(err.name,0o600)
        process=subprocess.Popen(self.command_helper.docker+['start','--attach',cid],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        client=LoggedClient(process,out,err,self.log_budget)
        self.clients.append(client)
        record.update(state='client_started',client_pid=process.pid)
        atomic_json(self.root/'controllers.json',self.controllers)
        return client

    def stop(self):
        self.host_gate()
        # Stop controllers before exact label-owned workers. Never remove evidence.
        identifiers=[r['container_id'] for r in self.controllers if r.get('container_id')]
        identifiers+=self.command(['ps','--all','--quiet','--no-trunc','--filter','label='+LABEL+'='+self.packet['operation_id']]).decode().split()
        for identifier in dict.fromkeys(identifiers):
            row=json.loads(self.command(['inspect',identifier]))[0]
            if row['Id']!=identifier or row['Config']['Labels'].get(LABEL)!=self.packet['operation_id']:
                raise RuntimeError('investigation_cleanup_ownership_lost')
            if identifier in self.births and row['State']['StartedAt']!=self.births[identifier][1]:
                raise RuntimeError('investigation_cleanup_birth_changed')
            if row['State']['Running']:
                self.command(['kill',identifier])
            if json.loads(self.command(['inspect',identifier]))[0]['State']['Running']:
                raise RuntimeError('investigation_container_remains')
        if not all(client.stop() for client in self.clients):
            raise RuntimeError('investigation_client_remains')
        if any(not row.get('container_id') for row in self.controllers):
            raise RuntimeError('investigation_launch_acknowledgement_missing')
        return True

    def stopped(self):
        self.host_gate()
        running=self.command(['ps','--quiet','--filter','label='+LABEL+'='+self.packet['operation_id']]).decode().split()
        return not running and all(c.process.poll() is not None for c in self.clients)

    def run(self,authorization):
        admission(self.packet,authorization)
        self.host_gate()
        scopes=self.configuration['scopes']
        sampler=Sampler(scopes,self.configuration['scope_births'],self.root)
        logs=[self.root/(c['phase']+suffix) for c in self.packet['commands'] for suffix in ('.stdout','.stderr')]
        # Only existing logs enter the budget scan; the whole generation is always scanned.
        monitor=Monitor(self.root,sampler,self.identity,self.health,operation_id=self.packet['operation_id'],
                        additional_roots=[Path(self.packet['epoch']).parent])
        runner=Runner(self.root,self.packet,self.launch,self.stop,self.stopped,self.identity,monitor=monitor)
        runner.run(authorization)
