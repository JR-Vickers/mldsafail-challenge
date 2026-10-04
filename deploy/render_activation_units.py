"""Render inactive user units using fresh per-activation daemon authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

JOBS = {'fixture': 'mldsafail-activation-fixture.service',
        'daily-recovery': 'mldsafail-offhost-backup.service',
        'recovery-check': 'mldsafail-offhost-check.service'}


def literal_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)):
        raise ValueError('Absolute literal retained paths required')
    return path


def render(source, interpreter, metadata, configurations, output):
    source, interpreter, output = map(literal_path, (source, interpreter, output))
    if not re.fullmatch('[a-f0-9]{40}', metadata.get('source_commit', '')):
        raise ValueError('Full retained source identity required')
    if source.resolve() != source or not source.is_dir() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('Real retained source and installed executable required')
    files = [*sorted((source/'deploy').glob('*.py')), *sorted((source/'research/cpu_measurement').glob('*.py')),
             source/'research/cpu_measurement/templates/owned-daemon.service.in']
    expected = metadata.get('source_files_sha256', {})
    for path in files:
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected.get(str(path.relative_to(source))):
            raise ValueError('Complete operator and provisioning source hashes required')
    if not configurations or set(configurations)-set(JOBS):
        raise ValueError('Fixed operator jobs and explicit activation configurations required')
    paths = {job: literal_path(path) for job, path in configurations.items()}
    for path in paths.values():
        if path.exists() and (path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077):
            raise ValueError('Private regular activation configuration required')
    environment = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'}}
    environment.update(PYTHONPATH=str(source), PYTHONNOUSERSITE='1')
    command = 'import platform,deploy.operator_activation as m; print(platform.python_version()); print(m.__file__)'
    identity = subprocess.check_output([str(interpreter), '-c', command], cwd=source, env=environment, timeout=30).decode().splitlines()
    if identity != ['3.12.10', str(source/'deploy/operator_activation.py')]:
        raise ValueError('Source-bound Python3.12.10 activation module required')
    output.mkdir(mode=0o700, parents=True)
    hashes = {}
    for job, config in paths.items():
        name = JOBS[job]
        argv = str(interpreter)+' -m deploy.operator_activation --unit %n --config '+str(config)
        text = ('[Unit]\nDescription=Inactive source-bound fresh operator activation\n'
                '[Service]\nType=oneshot\nDelegate=yes\nUMask=0077\nRestart=no\nKillMode=control-group\n'
                'WorkingDirectory='+str(source)+'\nEnvironment=PYTHONPATH='+str(source)+'\n'
                'Environment=XDG_RUNTIME_DIR=%t\nExecStart='+argv+'\nExecStopPost='+argv+' --cleanup\n'
                'TimeoutStartSec='+('5min' if job == 'fixture' else '5h')+'\nTimeoutStopSec=5min\n')
        path = output/name
        path.write_text(text)
        path.chmod(0o600)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(source_commit=metadata['source_commit'], unit_sha256=hashes,
                  installed=False, activated=False, manager='systemd-user',
                  repeat_activation_design='fresh_source_bound_daemon_worker_and_controller_per_activation',
                  native_two_activation_gate='pending',
                  configuration={job: 'private_file_present_contents_not_audited' if path.exists() else 'missing_activation_blocked'
                                 for job, path in paths.items()})
    (output/'render-report.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/'render-report.json').chmod(0o600)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--interpreter', required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--configurations', type=Path, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    render(args.source, args.interpreter, json.loads(args.metadata.read_text()),
           json.loads(args.configurations.read_text()), args.output)
