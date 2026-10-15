"""Actual Docker lost-ACK probes for operational Journal repair, never measurement."""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import uuid
from deploy import owned_daemon
from deploy.recovery_journal import Journal, atomic_json
from deploy.native_recovery_powerloss import receipt
from research.cpu_measurement.native_transport import drop_acknowledgement


class LostAcknowledgement:
    """One declared mutation; all proxy connections gone before daemon repair."""
    def __init__(self, root, upstream, operation):
        self.path = root / 'proxy.sock'
        self.receipt = root / 'transport.json'
        self.upstream = upstream
        self.operation = operation
        self.errors = []
        self.stop = threading.Event()
        self.connections = []
        self.server = socket.socket(socket.AF_UNIX)
        try:
            self.server.bind(str(self.path))
            os.chmod(self.path, 0o600)
            self.server.listen(1)
            self.server.settimeout(.2)
            self.thread = threading.Thread(target=self.serve, daemon=True)
            self.thread.start()
        except BaseException:
            self.server.close()
            raise

    def serve(self):
        deadline = time.monotonic() + 60
        preludes = []
        try:
            while not self.stop.is_set() and time.monotonic() < deadline:
                try: client, _ = self.server.accept()
                except socket.timeout: continue
                upstream = socket.socket(socket.AF_UNIX)
                self.connections.extend([client, upstream])
                upstream.settimeout(15)
                upstream.connect(self.upstream)
                if drop_acknowledgement(client, upstream, self.receipt,
                        self.operation, preludes=preludes):
                    return
            if not self.stop.is_set(): raise TimeoutError('Diagnostic mutation deadline')
        except BaseException as error:
            if not self.stop.is_set(): self.errors.append(error)

    def quiescent(self):
        return not self.thread.is_alive() and all(connection.fileno() == -1
            for connection in [self.server, *self.connections])

    def close(self):
        self.stop.set()
        errors = []
        for connection in [self.server, *self.connections]:
            try: connection.close()
            except BaseException as error: errors.append(error)
        try: self.thread.join(50)
        except BaseException as error: errors.append(error)
        # A connection accepted during the first close snapshot still belongs
        # to this proxy; independently close the final inventory as well.
        for connection in self.connections:
            try: connection.close()
            except BaseException as error: errors.append(error)
        if self.thread.is_alive(): errors.append(RuntimeError('Proxy executor remains live; no daemon restart permitted'))
        errors.extend(self.errors)
        if not self.thread.is_alive():
            try: self.path.unlink(missing_ok=True)
            except BaseException as error: errors.append(error)
        if not self.quiescent(): errors.append(RuntimeError('Diagnostic socket authority remains live'))
        if errors: raise RuntimeError('Diagnostic proxy cleanup failed') from errors[0]


def validate_repair(operation, before, manifest_path):
    mutations = operation.data.get('daemon_mutations', [])
    lost = [item for item in mutations if item.get('acknowledged') is False]
    if len(lost) != 1: raise ValueError('Exactly one unacknowledged native mutation required')
    resolution = lost[0].get('resolved_by_barrier')
    if not isinstance(resolution, dict) or resolution.get('old_epoch') != before['epoch']:
        raise ValueError('Lost mutation lacks exact old-epoch repair proof')
    after = owned_daemon.load_manifest(manifest_path)
    if after['epoch'] == before['epoch'] or resolution.get('new_epoch') != after['epoch']:
        raise ValueError('Repair did not durably register a fresh daemon epoch')
    from deploy.recovery_daemon import _positive
    context = owned_daemon.fingerprint(before)
    attempt = 'recovery-' + context[:32]
    if resolution.get('proof_file') != attempt + '-rpc-repair.json':
        raise ValueError('Exact owned repair proof filename required')
    proof = owned_daemon.read_private_json(operation.path.parent / resolution['proof_file'])
    if (proof.get('schema') != 'mldsafail.recovery-rpc-repair.v1' or
            proof.get('context') != context or proof.get('attempt_id') != attempt):
        raise ValueError('Exact versioned RPC repair identity required')
    _positive(proof.get('barrier'), before, attempt)
    if operation.data.get('cleanup_complete') is not True:
        raise ValueError('Operational cleanup remains fenced')
    owned_daemon.verify_environment(after)
    return {'old_epoch': before['epoch'], 'new_epoch': after['epoch'], 'whole_barrier_verified': True}


def probe(root, config, kind):
    root.mkdir(mode=0o700)
    manifest_path = os.environ['MLDSAFAIL_OPERATOR_DAEMON_MANIFEST']
    before = owned_daemon.load_manifest(manifest_path)
    operation = Journal(root / 'operation.json', {})
    name = 'recovery-rpc-' + uuid.uuid4().hex
    proxy = None
    quiescent = False
    original = None
    result = {'operation': kind, 'passed': False, 'native_executed': False}
    try:
        operation.container(name, config['image'], daemon_manifest_path=manifest_path)
        create = ['docker', 'create', '--name', name, '--label', 'org.mldsafail.recovery=' + name,
            '--network', 'none', '--memory', '32m', '--pids-limit', '16', '--entrypoint', '/bin/sh',
            config['image'], '-c', 'sleep 120']
        if kind == 'start':
            operation.command(create, daemon_manifest_path=manifest_path, capture_output=True, check=True, timeout=60)
        proxy = LostAcknowledgement(root, before['socket'], kind)
        argv = create if kind == 'create' else ['docker', 'start', name]
        argv = ['docker', '--host', 'unix://' + str(proxy.path), *argv[1:]]
        environment = dict(os.environ, DOCKER_API_VERSION=config['api_version'])
        try:
            operation.command(argv, daemon_manifest_path=manifest_path, env=environment,
                capture_output=True, check=True, timeout=65)
        except (subprocess.CalledProcessError, RuntimeError) as error:
            # The owned command boundary retains bounded logs and raises
            # RuntimeError for a failed client. Neither exception proves loss:
            # require the independently observed successful daemon ACK below.
            result['lost_ack_client_failure_class'] = type(error).__name__
        else: raise RuntimeError('Diagnostic client unexpectedly received mutation acknowledgement')
        proxy.close(); quiescent = True
        transport = owned_daemon.read_private_json(proxy.receipt)
        if (transport.get('operation') != kind or transport.get('actual_mutation_response_observed') is not True or
                transport.get('response_delivered') is not False or transport.get('daemon_response_code') != (201 if kind == 'create' else 204)):
            raise ValueError('Actual declared successful daemon response loss required')
        atomic_json(root / 'proxy-quiescence.json', {'proxy_executor_quiescent': True,
            'receipt_sha256': __import__('hashlib').sha256(proxy.receipt.read_bytes()).hexdigest()})
        operation.cleanup()
        result.update(validate_repair(operation, before, manifest_path), native_executed=True)
        operation.cleanup()  # Repeated cleanup must retain the same repaired epoch.
        validate_repair(operation, before, manifest_path)
    except BaseException as error:
        original = error
    finally:
        if proxy is not None and not quiescent:
            try: proxy.close(); quiescent = True
            except BaseException as error:
                quiescent = proxy.quiescent()
                if original is None: original = error
                else: original.add_note('Proxy cleanup: ' + type(error).__name__)
        if proxy is None or quiescent:
            try: operation.cleanup()
            except BaseException as error:
                if original is None: original = error
                else: original.add_note('Independent Journal cleanup: ' + type(error).__name__)
        result['cleanup_complete'] = operation.data.get('cleanup_complete') is True
        result['proxy_executor_quiescent'] = proxy is None or quiescent
        result['passed'] = original is None and result['native_executed'] and result['cleanup_complete'] and result['proxy_executor_quiescent']
        try: atomic_json(root / 'result.json', result)
        except BaseException as error:
            result['passed'] = False
            if original is None: original = error
            else: original.add_note('Publication: ' + type(error).__name__)
            try: atomic_json(root / 'result.json', result)
            except BaseException as retry: original.add_note('Negative publication: ' + type(retry).__name__)
        if original is not None: raise original
    return result


def callback(driver, config, data):
    if config['image'] not in data.get('loaded_images', []):
        raise ValueError('Driver-bound immutable preloaded fixture image required')
    inspected = json.loads(driver.command(['docker', 'image', 'inspect', config['image']], kind='read', timeout=30).stdout)
    if len(inspected) != 1 or inspected[0]['Id'] != config['image'] or inspected[0].get('Config', {}).get('Volumes'):
        raise ValueError('Exact immutable fixture without anonymous image volumes required')
    root = driver.path.parent / 'recovery-rpc-loss'
    root.mkdir(mode=0o700)
    for kind in ('create', 'start'):
        probe(root / kind, config, kind)
    return receipt(config, [str(root / kind / 'result.json') for kind in ('create', 'start')])
