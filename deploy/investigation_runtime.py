"""Native host investigation adapter. Import/construction never launches workload."""
import json
import copy
import hashlib
import re
import os
from pathlib import Path
import platform
import selectors
import subprocess
import time
import threading

from deploy.capacity_investigation import Runner, admission
from deploy.capacity_monitor import Monitor
from deploy.capacity_sampler import Sampler
from deploy.maintenance_transport import OwnedHelper
from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json, safe_path

LABEL='org.mldsafail.capacity-investigation'


def admit_resources(row, *, image, parent, memory, cpus, pids, resolved=None):
    host=row['HostConfig']
    if (row['Config']['Image']!=image or row['Image']!=(resolved or image) or host['CgroupParent']!=parent
            or host['Memory']!=memory or host['NanoCpus']!=int(cpus*1_000_000_000)
            or host['PidsLimit']!=pids or host['NetworkMode']!='none'
            or host.get('PortBindings') or host.get('Privileged') or not host['ReadonlyRootfs']
            or 'ALL' not in host['CapDrop'] or not any(x.startswith('no-new-privileges') for x in host['SecurityOpt'])):
        raise RuntimeError('investigation_container_configuration_changed')


def admit_controller(row, packet, command, *, resolved=None):
    args=command['argv']
    def value(flag): return args[args.index(flag)+1]
    admit_resources(row,image=packet['controller']['index'],parent=value('--cgroup-parent'),
                    memory=512*1024**2,cpus=1,pids=256,resolved=resolved)
    entry=args.index('--entrypoint')
    if (row['Config']['Entrypoint']!=[args[entry+1]] or row['Config']['Cmd']!=args[entry+3:]
            or row['Config']['User']!='0:0'):
        raise RuntimeError('investigation_controller_command_changed')
    expected=[]
    for index,word in enumerate(args):
        if word=='--mount':
            parts=args[index+1].split(',')
            fields=dict(part.split('=',1) for part in parts if '=' in part)
            expected.append((fields['src'],fields['dst'],'readonly' not in parts))
    actual=[(m['Source'],m['Destination'],m['RW']) for m in row['Mounts'] if m['Type']=='bind']
    if sorted(actual)!=sorted(expected) or any(m['Type']!='bind' and m['Destination']!='/tmp' for m in row['Mounts']):
        raise RuntimeError('investigation_controller_mounts_changed')
    env=row['Config']['Env']
    if any(args[index+1] not in env for index,word in enumerate(args) if word=='-e'):
        raise RuntimeError('investigation_controller_environment_changed')
    if command['phase']=='audit' and any(m['Destination']=='/var/run/docker.sock' for m in row['Mounts']):
        raise RuntimeError('investigation_audit_socket_forbidden')


class LoggedClient:
    """Incremental combined operation-log ceiling, including active client output."""
    def __init__(self, process, stdout, stderr, budget):
        self.process,self.stdout,self.stderr,self.budget=process,stdout,stderr,budget
        self.output_thread=None
        self.selector=selectors.DefaultSelector()
        for source,target in ((process.stdout,stdout),(process.stderr,stderr)):
            os.set_blocking(source.fileno(),False)
            self.selector.register(source,selectors.EVENT_READ,target)

    def io(self, callback):
        if self.output_thread is not None and self.output_thread.is_alive():
            raise RuntimeError('investigation_log_writer_remains')
        done,errors=threading.Event(),[]
        def write():
            try: callback()
            except BaseException as error: errors.append(error)
            finally: done.set()
        self.output_thread=threading.Thread(target=write,name='investigation-log-writer',daemon=True)
        self.output_thread.start()
        if not done.wait(.8):
            raise RuntimeError('investigation_log_write_deadline')
        if errors: raise errors[0]

    def poll(self):
        pending=[]
        for key,_ in self.selector.select(0):
            data=os.read(key.fileobj.fileno(),65536)
            if not data:
                self.selector.unregister(key.fileobj)
                continue
            if self.budget['bytes']+len(data)>128*1024**2:
                raise RuntimeError('investigation_log_output_limit')
            self.budget['bytes']+=len(data)
            pending.append((key.data,data))
        if pending:
            def write():
                for stream,data in pending:
                    stream.write(data)
                    stream.flush()
            self.io(write)
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
        self.io(lambda:(self.stdout.close(),self.stderr.close()))
        self.process.stdout.close()
        self.process.stderr.close()
        return self.process.poll() is not None


class NativeInvestigation:
    def __init__(self,root,packet,configuration,*,configuration_sha256=None):
        self.root=safe_path(Path(root).absolute())
        self.packet,self.configuration=copy.deepcopy(packet),copy.deepcopy(configuration)
        self.configuration_digest=configuration_sha256 or hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()
        self.controllers,self.clients=[],[]
        self.cleanup_mode=False
        self.births={}
        self.images={}
        self.log_budget={'bytes':0}
        self.command_helper=object.__new__(OwnedHelper)
        self.command_helper.docker=list(configuration['docker'])
        self.command_helper.runner=None

    def validate_configuration(self):
        expected=self.packet.get('configuration_sha256')
        if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or self.configuration_digest!=expected:
            raise ValueError('investigation_configuration_not_bound')
        return True

    def command(self,args):
        return self.command_helper.command(args)

    def host_gate(self):
        if self.root!=safe_path(Path(self.packet['operation']).absolute()):
            raise RuntimeError('investigation_operation_destination_changed')
        if platform.system()!='Linux' or platform.machine()!='x86_64':
            raise RuntimeError('investigation_native_amd64_host_required')
        if os.getuid()!=self.packet['host']['uid'] or platform.node()!=self.packet['host']['hostname']:
            raise RuntimeError('investigation_host_identity_changed')
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=self.packet['host']['boot_id']:
            raise RuntimeError('investigation_host_boot_changed')
        from deploy.owned_client import domain_identity
        if domain_identity(self.configuration['operation_parent']['path'])!=self.configuration['operation_parent']:
            raise RuntimeError('investigation_operation_parent_changed')
        leaf=self.configuration['control_leaf']
        if self.packet['operation_id'] not in Path(leaf['path']).name:
            raise RuntimeError('investigation_control_leaf_not_generation_owned')
        if (domain_identity(leaf['path'])!=leaf or not Path(leaf['path']).is_relative_to(self.configuration['operation_parent']['path'])
                or leaf['path']==self.configuration['operation_parent']['path']):
            raise RuntimeError('investigation_control_leaf_changed')
        current=Path('/proc/self/cgroup').read_text().strip()
        relative='/'+str(Path(leaf['path']).relative_to('/sys/fs/cgroup'))
        if not self.cleanup_mode and current!='0::'+relative:
            raise RuntimeError('investigation_control_not_in_operation_parent')
        for output in (self.root,Path(self.packet['epoch']).parent):
            path=output if output.exists() else output.parent
            fs=os.statvfs(path)
            if fs.f_bavail*fs.f_frsize < 2*1024**3:
                raise RuntimeError('investigation_output_filesystem_floor')
        parent_path=Path(self.configuration['operation_parent']['path'])
        actual_limits={name:(parent_path/name).read_text().strip() for name in ('memory.max','memory.swap.max','cpu.max','pids.max')}
        if actual_limits!=self.packet['operation_limits'] or self.configuration['operation_limits']!=self.packet['operation_limits']:
            raise RuntimeError('investigation_operation_limits_changed')
        info=json.loads(self.command(['info','--format','{{json .}}']))
        if (info['ID']!=self.packet['host']['daemon_id'] or info['Architecture'] not in ('x86_64','amd64')
                or str(info['CgroupVersion'])!='2' or info['CgroupDriver']!='systemd'
                or not any('rootless' in value for value in info['SecurityOptions'])):
            raise RuntimeError('investigation_daemon_changed')
        if any(info.get(key)!=value for key,value in self.configuration['runtime'].items()):
            raise RuntimeError('investigation_runtime_version_changed')
        for role in ('controller','worker'):
            image=json.loads(self.command(['image','inspect',self.packet[role]['index']]))[0]
            if image['Id'] not in (self.packet[role]['index'],self.packet[role]['configuration']) or image['Os']!='linux' or image['Architecture']!='amd64':
                raise RuntimeError('investigation_frozen_image_changed')
            if role in self.images and self.images[role]!=image['Id']:
                raise RuntimeError('investigation_resolved_image_changed')
            self.images[role]=image['Id']
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
                admit_resources(row,image=self.images['worker'],parent=self.configuration['docker_parent'],
                                memory=2*1024**3,cpus=1,pids=64)
                if row['State']['Running']: workers+=1
            elif name=='capacity-artifacts-'+self.packet['operation_id']:
                admit_resources(row,image=self.images['worker'],parent=self.configuration['docker_parent'],
                                memory=64*1024**2,cpus=.1,pids=16)
            else:
                records=[c for c in self.controllers if c['name']==name]
                if len(records)!=1:
                    raise RuntimeError('investigation_unexpected_container')
                admit_controller(row,self.packet,records[0]['command'],resolved=self.images['controller'])
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
        atomic_json(self.root/'container-births.json',self.births)
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
        record=dict(name=name,phase=command['phase'],command=command,state='create_intent')
        self.controllers.append(record)
        atomic_json(self.root/'controllers.json',self.controllers)
        cid=self.command(['create',*args[2:]]).decode().strip()
        row=json.loads(self.command(['inspect',cid]))[0]
        if row['Id']!=cid or row['Name']!='/'+name or row['Config']['Labels'].get(LABEL)!=self.packet['operation_id']:
            raise RuntimeError('investigation_controller_launch_ambiguous')
        admit_controller(row,self.packet,command,resolved=self.images['controller'])
        record.update(container_id=cid,state='start_intent')
        atomic_json(self.root/'controllers.json',self.controllers)
        out=(self.root/(command['phase']+'.stdout')).open('xb')
        err=(self.root/(command['phase']+'.stderr')).open('xb')
        os.chmod(out.name,0o600);os.chmod(err.name,0o600)
        process=subprocess.Popen(self.command_helper.docker+['start','--attach',cid],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        client=LoggedClient(process,out,err,self.log_budget)
        self.clients.append(client)
        from deploy.owned_client import identity as process_identity
        record.update(state='client_started',client_pid=process.pid,client_birth=process_identity(process.pid))
        deadline=time.monotonic()+2
        while True:
            state=json.loads(self.command(['inspect',cid]))[0]['State']
            if state['StartedAt'] and not state['StartedAt'].startswith('0001-'):
                break
            if time.monotonic()>deadline:
                raise RuntimeError('investigation_controller_start_ambiguous')
            time.sleep(.02)
        self.births[cid]=(cid,state['StartedAt'],state['Pid'])
        record['container_birth']=self.births[cid]
        atomic_json(self.root/'container-births.json',self.births)
        atomic_json(self.root/'controllers.json',self.controllers)
        return client

    def cleanup_authority(self):
        # Emergency cleanup must still run after capacity or free-space aborts.
        # Only immutable ownership gates apply; never repeat workload admission.
        if (platform.system()!='Linux' or os.getuid()!=self.packet['host']['uid']
                or platform.node()!=self.packet['host']['hostname']
                or Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=self.packet['host']['boot_id']):
            raise RuntimeError('investigation_cleanup_host_changed')
        from deploy.owned_client import domain_identity
        for key in ('operation_parent','control_leaf'):
            expected=self.configuration[key]
            if domain_identity(expected['path'])!=expected:
                raise RuntimeError('investigation_cleanup_scope_changed')
        if self.packet['operation_id'] not in Path(self.configuration['control_leaf']['path']).name:
            raise RuntimeError('investigation_cleanup_scope_not_generation_owned')
        info=json.loads(self.command(['info','--format','{{json .}}']))
        if info['ID']!=self.packet['host']['daemon_id']:
            raise RuntimeError('investigation_cleanup_daemon_changed')
        return True

    def stop(self):
        self.cleanup_authority()
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
        client_errors=[]
        for client in self.clients:
            try:
                if not client.stop(): client_errors.append('client_remains')
            except BaseException as error:
                client_errors.append(type(error).__name__)
        if client_errors:
            raise RuntimeError('investigation_client_remains')
        if self.cleanup_mode:
            self.cleanup_control_leaf()
        if any(not row.get('container_id') for row in self.controllers):
            raise RuntimeError('investigation_launch_acknowledgement_missing')
        return True

    def cleanup_control_leaf(self):
        from deploy.owned_client import verify_domain, populated
        leaf=self.configuration['control_leaf']
        path=verify_domain({'cgroup':leaf})
        if path is None:
            return True
        current=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().removeprefix('0::/').lstrip('/')
        if current.is_relative_to(path):
            raise RuntimeError('investigation_cleanup_must_run_outside_owned_control_leaf')
        atomic_json(self.root/'control-cleanup.json',dict(state='kill_intent',identity=leaf))
        (path/'cgroup.kill').write_text('1')
        deadline=time.monotonic()+15
        while populated(path):
            if time.monotonic()>deadline:
                raise RuntimeError('investigation_control_clients_remain')
            time.sleep(.05)
        atomic_json(self.root/'control-cleanup.json',dict(state='terminated',identity=leaf))
        return True

    def cleanup(self):
        self.validate_configuration()
        self.cleanup_mode=True
        self.controllers=read_manifest(self.root/'controllers.json')
        self.births=read_manifest(self.root/'container-births.json')
        for record in self.controllers:
            if record.get('container_id') is None:
                raise RuntimeError('investigation_launch_acknowledgement_missing')
        self.stop()
        return self.stopped()

    def stopped(self):
        self.cleanup_authority()
        running=self.command(['ps','--quiet','--filter','label='+LABEL+'='+self.packet['operation_id']]).decode().split()
        return not running and all(c.process.poll() is not None for c in self.clients)

    def run(self,authorization):
        self.validate_configuration()
        admission(self.packet,authorization)
        self.host_gate()
        scopes=self.configuration['scopes']
        sampler=Sampler(scopes,self.configuration['scope_births'],self.root)
        # Only existing logs enter the budget scan; the whole generation is always scanned.
        monitor=Monitor(self.root,sampler,self.identity,self.health,operation_id=self.packet['operation_id'],
                        additional_roots=[Path(self.packet['epoch']).parent])
        runner=Runner(self.root,self.packet,self.launch,self.stop,self.stopped,self.identity,monitor=monitor)
        runner.run(authorization)
        # Sampler readers have stopped; no operation CLI may remain in its leaf.
        leaf=Path(self.configuration['control_leaf']['path'])
        if set((leaf/'cgroup.procs').read_text().split()) != {str(os.getpid())}:
            atomic_json(self.root/'attempt.json',dict(state='reconciliation_required',operation_id=self.packet['operation_id']))
            raise RuntimeError('investigation_control_client_remains')
