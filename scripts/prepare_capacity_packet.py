"""Offline exclusive approval packet builder. Never executes proposed commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from deploy.production_preparation import read_manifest, IMAGES
from deploy.recovery_journal import atomic_json, safe_path

BLOCKERS = [
    'Owner must bind disposable host boot/daemon/provider identity, size and execution window',
    'Native Linux amd64 end-to-end acceptance requires an approved compatible host; local smoke is emulated',
    'Frozen coordinator image is absent from the local Docker daemon; compatible transport container acceptance remains unverified',
    'Owner-only scheduling paths, dynamic configuration/import semantics and all restart owners require remaining evidence',
    'Approved exclusive operation/control-leaf delegation is not installed or certified',
    'Production retained-service/timer/ancestor measurements and source compatibility remain unresolved',
    'Source and relative-receipt relocation is testable, but runtime/configuration evidence closure remains incomplete',
    'Production restoration and investigation adapters need end-to-end acceptance on the bound native host',
    'Capacity investigation execution and generation require separate approval',
]



def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(previous, destination):
    previous, destination = safe_path(Path(previous).absolute()), safe_path(Path(destination).absolute())
    # Retain predecessor references without claiming semantic graph closure.
    protocol = read_manifest(previous / 'capacity-protocol.json')
    if protocol['controller']['index'] != 'sha256:' + IMAGES['COORDINATOR_IMAGE'] or protocol['worker']['index'] != 'sha256:' + IMAGES['WORKER_IMAGE']:
        raise ValueError('frozen_image_mismatch')
    destination.mkdir(mode=0o700)
    if destination.stat().st_mode & 0o077:
        raise ValueError('private_output_required')
    operation = uuid.uuid4().hex
    generation = 'capacity-investigation-' + operation
    commands = json.loads(json.dumps(protocol['commands']))
    replacements = {
        protocol['operation_id']: operation,
        protocol['operation']: '/opt/mldsafail/' + generation,
        str(Path(protocol['epoch']).parent): '/srv/' + generation,
        'production-epoch.slice': 'mldsafail-investigation.slice',
    }
    for command in commands:
        for i, word in enumerate(command['argv']):
            for old, new in replacements.items():
                word = word.replace(old, new)
            command['argv'][i] = word
    for command in commands:
        argv=command['argv']
        position=argv.index('--memory')
        argv[position:position]=['--memory-swap','512m','--log-driver','none']
    retained = {p.name: sha(p) for p in previous.iterdir() if p.is_file()}
    atomic_json(destination / 'predecessor.json', dict(path=str(previous), files=retained))
    packet = dict(schema='mldsafail.capacity-approval-packet.v1', state='maintenance_proposal',
                  purpose='capacity_investigation_preparation', execution_authority=False,
                  scheduling_exclusion_verified=False, transferable=False,
                  prepared_at=time.time(),source=protocol['source'], operator_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  operation_id=operation, operation='/opt/mldsafail/'+generation, epoch='/srv/'+generation+'/epoch',
                  benchmark_version='0.5.0',helper_hashes=protocol.get('helper_hashes',{}),
                  commands=commands, command_state='blocked_review_material',
                  host=None, provider_size=None, execution_window=None,configuration_sha256=None,
                  controller=protocol['controller'], worker=protocol['worker'],
                  ceilings=protocol['ceilings'], lifetime=8000, capacity='unresolved',
                  preparation_freshness_seconds=86400, execution_freshness_seconds=300,
                  blockers=BLOCKERS, prior_evidence='predecessor.json',
                  implementation_complete=False,
                  operation_limits={'memory.max':'3221225472','memory.swap.max':'0','cpu.max':'125000 100000','pids.max':'448'},
                  interfaces={'capture_validation':'python -m scripts.capacity_investigation validate-capture ROOT',
                              'execute':'python -m scripts.capacity_investigation execute ROOT PACKET CONFIGURATION AUTHORIZATION',
                              'cleanup_only':'python -m scripts.capacity_investigation cleanup ROOT PACKET CONFIGURATION'})
    atomic_json(destination / 'packet.json', packet)
    host = dict(schema='mldsafail.isolated-measurement-host.v1', platform='linux/amd64',
                disposable=True, host_identity=None, provider_size=None, execution_window=None,
                current_2gib_vps='rejected: 2.5 GiB operation ceiling alone exceeds physical RAM',
                operation_common_parent=dict(memory_bytes=3221225472, cpus=1.25, pids=448),
                control_overhead='128 MiB for two helpers, 128 MiB monitor and 64 MiB clients; 192 MiB aggregate margin inside 3 GiB; planning reserves only, must measure',
                planning_headroom='max(256 MiB,20% simultaneous operation plus retained peak), with written variability/kernel/sampler/timer rationale',
                certified_host_size=None, runtime_versions='retained v8 host evidence; isolated host must record exact Docker, kernel, systemd and cgroup-v2 versions',
                images={k: 'sha256:' + IMAGES[k] for k in ('COORDINATOR_IMAGE', 'WORKER_IMAGE')},
                admission=['verify index, linux/amd64 platform manifest and configuration digests against packet',
                           'reject build or image substitution; read-only image inspect before launch',
                           'dedicated daemon, exclusive private 0700 storage, no production secrets/network/mounts',
                           'private input only; no public ports; independent audit without socket'],
                provisioning='blocked until host/size/window bound; owner-selected Linux amd64 provisioning commands remain unresolved',
                termination=['persist intent; stop exact controller first', 'stop positively owned workers/helpers/clients',
                             'verify process births, container IDs, cgroup emptiness and daemon identity',
                             'retain hash-bound partial evidence; ambiguous termination requires reconciliation'],
                teardown='Only exact owned disposable resources after verified quiescence and retained-record checks; no shared prune',
                production_compatibility=['frozen source/images/profiles/100 cases/concurrency/mounts/limits',
                                          'separate fresh production retained-service and every-ancestor evidence',
                                          'timer overlap or complete fresh exclusion for entire window',
                                          'independent review before capacity validator'])
    atomic_json(destination / 'isolated-host.json', host)
    dependencies = dict(complete=False, transferable=False, mappings=[], unresolved=BLOCKERS[1:8],
                        source_files={str(p): sha(p) for pattern in ('deploy/*maintenance*.py', 'deploy/capacity*.py', 'deploy/investigation*.py', 'scripts/*capacity*.py', 'scripts/maintenance_service_context.py', 'tests/test*capacity*.py', 'tests/test_investigation*.py', 'tests/test_maintenance_closure.py', 'tests/test_maintenance_pipe_postgres.py') for p in sorted(Path('.').glob(pattern))},
                        retained_graph=dict(path=str(previous / 'transfer-dependencies.json'), sha256=sha(previous / 'transfer-dependencies.json')),
                        scheduling_graph=dict(path=str(previous / 'scheduling-semantic-review.json'), sha256=sha(previous / 'scheduling-semantic-review.json')),
                        collector_allowlist=None, owner_console_collection_ready=False,
                        delegation='existing v8 app/session evidence retained; no cgroups created')
    atomic_json(destination / 'dependencies.json', dependencies)
    atomic_json(destination / 'measurement-status.json', dict(capacity='unresolved', measured=False,
                source_compatible=False, raw_evidence=[], compatibility='unreviewed', validator_invoked=False))
    finalize(destination)
    return destination


def finalize(destination):
    destination = Path(destination)
    atomic_json(destination / 'file-manifest.json', {
        p.name: sha(p) for p in sorted(destination.iterdir()) if p.is_file() and p.name != 'file-manifest.json'})


def validate(destination):
    """Read only, including relocated bundle; never interprets argv as commands."""
    destination = Path(destination)
    manifest = read_manifest(destination / 'file-manifest.json')
    if set(manifest) != {p.name for p in destination.iterdir() if p.name != 'file-manifest.json'}:
        raise ValueError('packet_file_set_changed')
    for name, digest in manifest.items():
        if Path(name).name != name or sha(safe_path(destination.absolute() / name)) != digest:
            raise ValueError('packet_hash_mismatch')
        private = safe_path(destination.absolute() / name).stat()
        if private.st_uid != os.getuid() or private.st_mode & 0o077 or private.st_nlink != 1:
            raise ValueError('private_packet_file_required')
        if name.endswith('.json'):
            read_manifest(destination / name)
    packet = read_manifest(destination / 'packet.json')
    if (packet['state'] != 'maintenance_proposal' or packet['execution_authority'] is not False
            or packet['scheduling_exclusion_verified'] is not False or packet['transferable'] is not False):
        raise ValueError('proposal_state_invalid')
    return dict(valid_preparation=True, transferable=False, executable=False, blockers=packet['blockers'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('previous')
    prepare.add_argument('destination')
    verify = sub.add_parser('validate')
    verify.add_argument('destination')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(build(args.previous, args.destination))
    else:
        print(json.dumps(validate(args.destination), sort_keys=True))
