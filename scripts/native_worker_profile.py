"""Two bounded explanatory probes of the retained worker; never score evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from deploy import owned_daemon
from research.cpu_measurement import native_driver
from research.cpu_measurement.harness import fields
from mldsafail.benchmark_v050.generator import generate_mlwe


PROFILE = '''import time
started = time.process_time()
import cProfile, pstats, runpy, sys
profiler = cProfile.Profile()
profiler.enable()
runpy.run_module("mldsafail.benchmark_v060.worker", run_name="__main__")
profiler.disable()
print("\\nPROFILE_CPU_SECONDS=" + str(time.process_time()-started), file=sys.stderr)
pstats.Stats(profiler, stream=sys.stderr).strip_dirs().sort_stats("cumulative").print_stats(40)
'''


def callback(driver, config, data):
    root = driver.path.parent / 'worker-profile'
    root.mkdir(mode=0o700)
    fixture = root / 'solver'
    fixture.mkdir(mode=0o755)
    fixture.chmod(0o755)
    source = Path(__file__).resolve().parents[1] / 'research/cpu_measurement/fixtures/empty/solver.py'
    (fixture / 'solver.py').write_bytes(source.read_bytes())
    (fixture / 'solver.py').chmod(0o644)
    report = dict(schema='mldsafail.worker-profile.v1', passed=False,
                  adoption_gates_passed=False, score_evidence=False, rows=[],
                  source_commit=config['source_commit'], image=config['image'],
                  fixture_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    owned_daemon.publish(root / 'report.json', report)
    payload = json.dumps(dict(instance=generate_mlwe('small', 0, 1).public.to_dict(),
                              solver='contestant')).encode()
    parent = Path(data['worker_parent'])
    for mode in ('control', 'profile'):
        owned_daemon.verify_environment(owned_daemon.load_manifest(), measurement_parent=parent)
        if fields(parent / 'cgroup.events')['populated']:
            raise RuntimeError('Explanatory worker domain is not empty')
        before = fields(parent / 'cpu.stat')['usage_usec']
        started = time.monotonic()
        name = 'worker-profile-' + mode + '-' + data['id']
        argv = ['docker', 'create', '--name', name, '--cgroup-parent', data['worker_slice'],
                '--cgroupns', 'private', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', '65534:65534',
                '--cpus', '1', '--memory', '2g', '--memory-swap', '2g', '--pids-limit', '64',
                '--log-driver', 'none', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=64m',
                '--mount', 'type=bind,src=' + str(fixture) + ',dst=/solver,readonly',
                '--restart', 'no', '-i']
        if mode == 'profile':
            argv += ['--entrypoint', 'python']
        argv += [config['image']]
        if mode == 'profile':
            argv += ['-X', 'importtime', '-c', PROFILE]
        identifier = driver.command(argv, kind='container_create', timeout=30).stdout.decode().strip()
        if not re.fullmatch('[0-9a-f]{64}', identifier):
            raise RuntimeError('Exact probe container identity required')
        result = driver.command(['docker', 'start', '--attach', '--interactive', identifier],
                                kind='container_start', timeout=60, input=payload)
        # Fixed trusted empty fixture and profiler produce bounded output. Retain
        # any unexpected output privately and fail rather than retry a sample.
        for label, raw in [('stdout', result.stdout), ('stderr', result.stderr)]:
            (root / (mode + '.' + label)).write_bytes(raw)
            if len(raw) > 1024 * 1024:
                raise RuntimeError('Fixed probe output exceeded diagnostic cap')
        inspected = json.loads(driver.command(['docker', 'inspect', identifier], timeout=30).stdout)[0]
        if (inspected['Id'] != identifier or inspected['Image'] != config['image']
                or inspected['Name'] != '/' + name or inspected['State']['Running']
                or inspected['State']['ExitCode'] != 0
                or json.loads(result.stdout) != {'candidate': None}):
            raise RuntimeError('Fixed empty worker did not complete as declared')
        driver.command(['docker', 'rm', identifier], kind='container_remove', timeout=30)
        if fields(parent / 'cgroup.events')['populated']:
            raise RuntimeError('Probe descendants survived')
        after = fields(parent / 'cpu.stat')['usage_usec']
        if after < before:
            raise RuntimeError('Diagnostic counter regressed')
        report['rows'].append(dict(mode=mode, cpu_usec=after-before,
                                   wall_seconds=time.monotonic()-started,
                                   stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                                   stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
        owned_daemon.publish(root / 'report.json', report)
    report['passed'] = True
    report['outer_cleanup_required'] = True
    owned_daemon.publish(root / 'report.json', report)
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True,
                native_executed=True, evidence_refs=[str(root / 'report.json')],
                source_sha256=config['acceptance_source_sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),
                          Path(__file__).resolve().parents[1],
                          acceptance=callback, daemon_kind='owned')
