"""Fault-only native accounting gate: never launch the default 30-pair suite."""
import argparse
from pathlib import Path
import sys

from deploy import owned_daemon
from research.cpu_measurement import native_driver


def callback(driver, config, data):
    target = driver.path.parent / 'accounting-faults'
    args = ['--image', config['image'], '--parent', data['worker_parent'],
            '--cgroup-parent', data['worker_slice'], '--output', str(target),
            '--api-version', config['api_version']]
    driver.command([sys.executable, '-m', 'research.cpu_measurement.native_fault_suite', *args],
                   kind='native_faults', timeout=3600)
    report = owned_daemon.read_private_json(target / 'report.json', cap=4 * 1024 * 1024)
    if report.get('contract_fault_gate_passed') is not True:
        raise RuntimeError('Complete accounting fault suite did not pass')
    # Fault recovery may refresh the owned daemon epoch. Verify the exact new
    # environment before returning; the outer driver still owns final cleanup.
    owned_daemon.verify_environment(owned_daemon.load_manifest(),
                                    measurement_parent=Path(data['worker_parent']))
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True,
                native_executed=True, source_sha256=config['acceptance_source_sha256'],
                evidence_refs=[str(target / 'report.json')])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),
                          Path(__file__).resolve().parents[1], acceptance=callback,
                          daemon_kind='owned')
