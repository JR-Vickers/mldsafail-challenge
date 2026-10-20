"""Concrete native production actions; preparation only constructs this adapter.

Every mutation uses the existing birth-gated owned-client cgroup API. Reviewed
scheduling, current inspected identities and distinct maintenance approval are
required before Supervisor invokes any action.
"""
import json
from pathlib import Path
import re
import time

from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json


class ProductionActions:
    def __init__(self, root, packet_path, fence, docker, client_parent, restart_units, *, runner=None):
        self.root, self.packet_path, self.fence = Path(root), Path(packet_path), fence
        from scripts.production_epoch_operation import read_packet
        self.packet=read_packet(packet_path)
        self.docker=list(docker)
        self.parent=client_parent
        self.restart_units=tuple(restart_units)
        if not all(re.fullmatch(r'[A-Za-z0-9_.@-]+\.service',u) and u not in ('docker.service',) for u in restart_units):
            raise ValueError('maintenance_restart_owner_not_isolatable')
        import threading
        self.command_lock=threading.RLock()
        self.runner=runner
        self.clients=[]
        self.states={}
        self.coordinator=self.packet['maintenance_coordinator_container']
        self.original=self.packet['maintenance_coordinator_identity']
        self.restore_commands=[]

    def save(self):
        atomic_json(self.root/'action-state.json',dict(operation_id=self.packet['operation_id'],
                    clients=self.clients,original=self.original,units=self.states,restore_commands=self.restore_commands))

    def command(self, argv, timeout=2, *, mutation=False, cleanup=False):
        if not mutation and self.runner is None:
            from deploy.maintenance_transport import OwnedHelper
            helper=object.__new__(OwnedHelper)
            helper.docker,helper.runner=[],None
            if not cleanup:
                self.fence.verify()
            return helper.command(argv)
        from deploy.owned_client import run
        runner=self.runner or run
        self.save()  # Intent and birth-gated client registration precede execution.
        def observe():
            if not cleanup:
                self.fence.verify()
        observe()
        result=runner(argv,self.clients,self.save,self.root,timeout=timeout,
                      client_cgroup_root=self.parent,capture_output=True,
                      cancel=None if cleanup else self.fence.failed)
        observe()
        return result.stdout

    def inspect_coordinator(self):
        rows=json.loads(self.command(self.docker+['inspect',self.coordinator]))
        if len(rows)!=1:
            raise RuntimeError('maintenance_coordinator_identity_changed')
        row=rows[0]
        if (row['Id']!=self.original['Id'] or row['Image']!=self.original['Image']
                or row['Config']['Labels']!=self.original['Labels']):
            raise RuntimeError('maintenance_coordinator_identity_changed')
        return row

    def verify_stopped(self):
        row=self.inspect_coordinator()
        if row['State']['Running'] or row['State']['Restarting']:
            raise RuntimeError('maintenance_coordinator_restart_interference')
        if row['HostConfig']['RestartPolicy'] != {'Name':'no','MaximumRetryCount':0}:
            raise RuntimeError('maintenance_coordinator_restart_owner_remains')
        for unit in self.restart_units:
            props=dict(line.split('=',1) for line in self.command(['systemctl','--user','show',unit,
                '--property=ActiveState,UnitFileState']).decode().splitlines() if '=' in line)
            if props.get('ActiveState') not in ('inactive','failed') or props.get('UnitFileState')!='masked-runtime':
                raise RuntimeError('maintenance_restart_owner_changed')
        return True

    def exclude_scheduling(self):
        from deploy.production_maintenance import bound_privileged
        bound_privileged(self.packet,execution=True)
        row=self.inspect_coordinator()
        if row['State']['StartedAt']!=self.original['StartedAt'] or row['HostConfig']['RestartPolicy']!=self.original['RestartPolicy']:
            raise RuntimeError('maintenance_coordinator_birth_changed')
        for unit in self.restart_units:
            props=dict(line.split('=',1) for line in self.command(['systemctl','--user','show',unit,
                '--property=ActiveState,UnitFileState']).decode().splitlines() if '=' in line)
            if props.get('UnitFileState') not in ('enabled','disabled','static'):
                raise RuntimeError('maintenance_original_unit_state_unsupported')
            self.states[unit]=props
            self.save()
            self.command(['systemctl','--user','mask','--runtime',unit],mutation=True)
            self.command(['systemctl','--user','stop',unit],timeout=30,mutation=True)
        self.restore_commands.append(self.docker+['update','--restart='+self.restart_policy(),self.coordinator])
        self.save()
        self.command(self.docker+['update','--restart=no',self.coordinator],mutation=True)
        return True

    def restart_policy(self):
        policy=self.original['RestartPolicy']
        name=policy['Name']
        if name not in ('no','always','unless-stopped','on-failure'):
            raise ValueError('maintenance_restart_policy_unsupported')
        count=policy['MaximumRetryCount']
        return name+(':'+str(count) if name=='on-failure' and count else '')

    def stop_coordinator(self):
        row=self.inspect_coordinator()
        if row['State']['StartedAt']!=self.original['StartedAt']:
            raise RuntimeError('maintenance_coordinator_restarted_before_stop')
        self.command(self.docker+['stop','--time','10',self.coordinator],timeout=20,mutation=True)
        return self.verify_stopped()

    def create(self):
        from scripts.production_epoch_operation import execute
        self.verify_stopped()
        execute(self.packet_path,self.packet['production_epoch_authorization'])
        return self.verify_stopped()

    def audit(self):
        from scripts.production_epoch_operation import audit
        self.verify_stopped()
        audit(self.packet_path)
        return self.verify_stopped()

    def inspection(self):
        from scripts.production_epoch_operation import finalize
        self.verify_stopped()
        finalize(self.packet_path,self.packet['final_destination'])
        return self.verify_stopped()

    def terminate(self):
        from scripts.production_epoch_operation import terminate_owned
        from deploy.owned_client import stop
        failures=[]
        for client in self.clients:
            try:
                stop(client)
            except BaseException as error:
                failures.append(type(error).__name__)
        if Path(self.packet['operation']).exists():
            receipt=terminate_owned(self.packet)
            if receipt['verified_stopped'] is not True:
                failures.append('operation_remains')
        if failures:
            raise RuntimeError('maintenance_owned_resources_remain')
        return True

    def resources_stopped(self):
        from deploy.owned_client import verify_domain, populated
        for client in self.clients:
            path=verify_domain(client)
            if path is not None and populated(path):
                return False
        # terminate_owned is independently birth-bound and verifies exact resources.
        from scripts.production_epoch_operation import terminate_owned
        return not Path(self.packet['operation']).exists() or terminate_owned(self.packet)['verified_stopped'] is True

    def postflight(self):
        self.verify_stopped()
        # Existing host/identity/capacity/scheduler checks remain mandatory.
        from scripts.production_epoch_operation import validate, delegation_gate, scheduling_gate
        validate(self.packet,local_outputs=True)
        delegation_gate(self.packet)
        scheduling_gate(self.packet)
        info=json.loads(self.command(self.docker+['info','--format','{{json .}}']))
        if info['ID']!=self.packet['daemon_id']:
            raise RuntimeError('maintenance_postflight_daemon_changed')
        for identifier in self.packet['allowed_running_services']:
            service=json.loads(self.command(self.docker+['inspect',identifier]))[0]
            if service['Id']!=identifier or not service['State']['Running'] or service['State'].get('Health',{}).get('Status','healthy')!='healthy':
                raise RuntimeError('maintenance_postflight_retained_service_degraded')
        atomic_json(self.root/'postflight.json',dict(time=time.time(),daemon_id=info['ID'],operation_id=self.packet['operation_id']))
        return self.fence.verify()

    def restore(self):
        if not self.resources_stopped() or not self.postflight():
            raise RuntimeError('maintenance_restoration_postflight_required')
        self.command(self.restore_commands[0],mutation=True)
        for unit,original in self.states.items():
            self.command(['systemctl','--user','unmask','--runtime',unit],mutation=True)
            if original['ActiveState']=='active':
                self.command(['systemctl','--user','start',unit],timeout=30,mutation=True)
        if self.original['Running']:
            self.command(self.docker+['start',self.coordinator],timeout=30,mutation=True)
        row=self.inspect_coordinator()
        if row['State']['Running']!=self.original['Running'] or row['HostConfig']['RestartPolicy']!=self.original['RestartPolicy']:
            raise RuntimeError('maintenance_restoration_ambiguous')
        return True

    def mapping(self):
        return {name:getattr(self,name) for name in ('exclude_scheduling','stop_coordinator','create','audit',
                'inspection','terminate','resources_stopped','postflight','restore')} | {'watch_state':self.verify_stopped}
