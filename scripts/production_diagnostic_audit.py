"""Independent read-only postflight and start-bound budget termination.

Execute in a distinct reviewed process after the engine/supervisor have settled.
Never starts a service, worker, daemon or measurement. A failed audit leaves the
slot fully reserved and prevents generation two.
"""
import argparse
import json
from pathlib import Path
import sys
import time

from deploy import owned_client, owned_daemon
from scripts import production_diagnostic as diagnostic
from scripts import production_diagnostic_state as state
from scripts.production_diagnostic_deadline import interrupt_at
from scripts.production_diagnostic_preflight import inspect
from scripts.production_diagnostic_runtime import Client


def audit(packet, slot, root):
    root = Path(root)
    start = owned_daemon.read_private_json(Path(packet['budget_root'])/(slot+'-start.json'))
    if start['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Ambiguous boot; slot remains fully reserved')
    deadline = start['monotonic_started']+start['limit_seconds']
    with interrupt_at(deadline):
        # Separate current read-only ownership/jobs/resource inspection, never a
        # recycled receipt from the engine or an earlier generation.
        inspect(packet, root/('independent-'+slot), deadline)
        complete = True
        if slot != 'preflight':
            config = owned_daemon.read_private_json(packet['driver_config'])
            driver = owned_daemon.read_private_json(Path(config['state_root'])/'driver.json', cap=4*1024*1024)
            if not driver.get('cleanup',{}).get('cleanup_complete'):
                raise RuntimeError('Driver cleanup incomplete')
            if not driver.get('cleanup',{}).get('daemon_barrier',{}).get('shutdown_proven'):
                raise RuntimeError('Positive terminal daemon barrier missing')
            if Path(driver['socket']).exists() or Path(driver['socket']).is_symlink():
                raise RuntimeError('Owned socket remains')
            registries = list(Path(config['state_root']).rglob('clients.json'))
            registries.append(root/'supervisor-clients.json')
            entries = list(driver['clients'])
            for path in registries:
                value = json.loads(path.read_text())
                entries.extend(value.get('clients',[]) if isinstance(value,dict) else value)
            for entry in entries:
                if owned_client.verify_domain(entry) is not None:
                    raise RuntimeError('Recorded client domain remains')
                if entry.get('pid'):
                    try:
                        actual = owned_client.identity(entry['pid'])
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    if actual['start_ticks'] == entry.get('start_ticks'):
                        raise RuntimeError('Recorded process birth remains')
            client = Client(root/('independent-'+slot)/'unit-client', deadline)
            units = [driver['daemon_unit'], driver['worker_slice']]
            monitor_journal = Path(config['state_root'])/'diagnostic/journal.json'
            if monitor_journal.exists():
                units += [Path(item['path']).name for item in owned_daemon.read_private_json(monitor_journal)['monitor_units']]
            for unit in units:
                raw = client.run(['systemctl','--user','show',unit,'--property=ActiveState,MainPID,ControlGroup']).stdout.decode()
                values = dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
                if (values.get('ActiveState') not in ('inactive','failed')
                        or values.get('MainPID','0') != '0' or values.get('ControlGroup')):
                    raise RuntimeError('Owned unit/domain remains active')
            for key in ('domain','worker_domain'):
                if Path(driver['registered_manifest'][key]['path']).exists():
                    raise RuntimeError('Recorded daemon/worker domain remains')
            report = owned_daemon.read_private_json(Path(config['state_root'])/'diagnostic/report.json')
            complete = report.get('complete') is True
        receipt = dict(independent=True, passed=True, budget_start_sha256=diagnostic.digest(start),
            slot=slot, verified_at_monotonic=time.monotonic(), measurements_complete=complete,
            source_sha256=diagnostic.file_digest(__file__))
        path = root/('independent-'+slot+'-receipt.json')
        owned_daemon.publish(path, receipt)
        with state.locked(packet['budget_root']) as budget:
            return budget.finish(slot, boot_id=start['boot_id'], complete=complete, cleanup_receipt=path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--slot', choices=state.SLOTS, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    packet = owned_daemon.read_private_json(args.packet, cap=4*1024*1024)
    print(json.dumps(audit(packet,args.slot,args.output_root)))
