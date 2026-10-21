"""Control-only local Linux fixture: sockets, peer UIDs, process death and locks.

Uses synthetic adapter observations and bounded inert processes. It does not
certify systemd, Docker cgroup placement, quotas or production resource demand.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

from mldsafail.evaluator.native_workload import private_json, process_birth, publish
from mldsafail.evaluator.workload import HostGate, WorkloadBlocked
from mldsafail.evaluator.workload_client import WorkloadClient
from mldsafail.evaluator.workload_service import cleanup, remove_stale_socket, serve


class Runtime:
    def __init__(self, root): self.root = Path(root)
    def identity(self): return dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), daemon_id='synthetic')
    def preflight(self, policy): return 2*1024**3
    def sample(self, state):
        return dict(available=2*1024**3,memory=0,oom_events=0,swap=0,disk_free=6*1024**3,logs=0,generation=0,identity_valid=True)
    def launch(self, state, specification):
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], start_new_session=True)
        identity = process_birth(process.pid)
        publish(self.root/'worker.json', identity)
        return identity
    def inspect(self, state, identity): return process_birth(identity['pid']) == identity
    def terminate(self, state):
        path = self.root/'worker.json'
        if path.exists():
            identity = private_json(path)
            try:
                assert process_birth(identity['pid']) == identity
                os.kill(identity['pid'], signal.SIGKILL)
            except FileNotFoundError: pass
        return True
    def stopped(self, state):
        path = self.root/'worker.json'
        if not path.exists(): return True
        try: process_birth(private_json(path)['pid'])
        except FileNotFoundError: return True
        return False


def service(root):
    import threading
    runtime = Runtime(root)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    with HostGate(root, runtime).locked() as gate:
        serve(gate, Path(root)/'supervisor.sock', {'controller':{'inert':True}}, stop)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', type=Path)
    parser.add_argument('--cleanup', type=Path)
    args = parser.parse_args()
    if args.service: service(args.service); return
    if args.cleanup:
        with HostGate(args.cleanup, Runtime(args.cleanup)).locked() as gate:
            cleanup(gate); remove_stale_socket(gate, args.cleanup/'supervisor.sock')
        return
    if sys.platform != 'linux': raise RuntimeError('Linux fixture only')
    with tempfile.TemporaryDirectory(prefix='workload-linux-') as temporary:
        root = Path(temporary)/'gate'; root.mkdir(mode=0o700)
        command = [sys.executable, str(Path(__file__).absolute())]
        process = subprocess.Popen([*command, '--service', str(root)])
        client = WorkloadClient(root/'supervisor.sock', Path(temporary)/'client')
        try:
            deadline = time.monotonic()+5
            while not (root/'supervisor.sock').exists():
                assert process.poll() is None and time.monotonic()<deadline
                time.sleep(.02)
            state = client.status(); assert state['paused']
            client.attach(state); client.mutation('reconcile'); client.mutation('resume')
            client.acquire('evaluation', {'database':'one'}); client.launch('controller')
            try:
                with HostGate(root, Runtime(root)).locked(): raise AssertionError('overlapping supervisor')
            except WorkloadBlocked: pass
            other = WorkloadClient(root/'supervisor.sock', Path(temporary)/'other')
            try: other.acquire('administration', {'database':'two'})
            except WorkloadBlocked: pass
            else: raise AssertionError('overlapping administrative work')
            slow = socket.socket(socket.AF_UNIX); slow.connect(str(root/'supervisor.sock')); slow.sendall(b'{')
            assert client.status()['workload_id'] == client.token
            time.sleep(.9); slow.close()
            # Relax only disposable fixture permissions to exercise SO_PEERCRED
            # rather than stopping the unauthorized peer at the filesystem ACL.
            os.chmod(temporary, 0o711); root.chmod(0o711); os.chmod(root/'supervisor.sock', 0o666)
            outsider = subprocess.run([sys.executable, '-c',
                'import os,socket,sys;os.setgid(65534);os.setuid(65534);s=socket.socket(socket.AF_UNIX);'
                's.connect(sys.argv[1]);s.sendall(b"{\\"id\\":\\"status\\",\\"method\\":\\"status\\",\\"argument\\":{}}\\n");'
                '\ntry: data=s.recv(4096)\nexcept ConnectionResetError: data=b""\nassert not data',
                str(root/'supervisor.sock')], capture_output=True, timeout=2)
            assert outsider.returncode == 0, outsider.stderr.decode()
            root.chmod(0o700); os.chmod(root/'supervisor.sock', 0o600); os.chmod(temporary, 0o700)
            worker = private_json(root/'worker.json')
            os.kill(process.pid, signal.SIGKILL); process.wait(timeout=2)
            assert process_birth(worker['pid']) == worker  # Daemon death is not worker termination.
            subprocess.run([*command, '--cleanup', str(root)], check=True, timeout=5)
            state = private_json(root/'workload.json')
            assert state['paused'] and state['phase'] == 'cleaned'
            assert not (root/'supervisor.sock').exists()
            try: process_birth(worker['pid'])
            except FileNotFoundError: pass
            else: raise AssertionError('owned worker survived cleanup')
            limited=Path(temporary)/'limited.log'
            subprocess.run([sys.executable,'-c',
                'import errno,resource,sys;resource.setrlimit(resource.RLIMIT_FSIZE,(2048,2048));'
                '\ntry:\n with open(sys.argv[1],"xb") as f:f.write(b"x"*4096);f.flush()'
                '\nexcept OSError as e:assert e.errno==errno.EFBIG\nelse:raise AssertionError("unbounded log")',str(limited)],check=True,timeout=2)
            assert limited.stat().st_size<=2048;limited.unlink()
            quota=Path(temporary)/'quota.bin'
            subprocess.run([sys.executable,'-c',
                'import errno,sys;f=open(sys.argv[1],"xb");data=b"x"*(1024*1024);'
                '\ntry:\n for _ in range(64):f.write(data);f.flush()'
                '\nexcept OSError as e:assert e.errno==errno.ENOSPC\nelse:raise AssertionError("unbounded volume")',str(quota)],check=True,timeout=5)
            assert quota.stat().st_size<=32*1024**2;quota.unlink()
            print(json.dumps(dict(schema='mldsafail.local-linux-workload.v1', passed=True,
                cases=['uid_peer_rejection','slow_client','cross_database_admin_contention','supervisor_sigkill',
                       'independent_cleanup','durable_pause','kernel_log_writer_bound','kernel_volume_exhaustion'], native_resource_acceptance=False)))
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=2)
            subprocess.run([*command, '--cleanup', str(root)], timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__': main()
