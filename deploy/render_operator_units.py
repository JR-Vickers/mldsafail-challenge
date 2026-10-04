"""Render inactive source-bound operator units; never installs or activates them."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SERVICES = {
    'mldsafail-offhost-backup.service': ('deploy.daily_recovery', 'daily-recovery', '4h'),
    'mldsafail-offhost-check.service': ('deploy.recovery', 'recovery', '4h'),
    'mldsafail-monitor.service': ('deploy.host_checks', 'monitor', '2min'),
}


def literal_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts or not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)):
        raise ValueError('Absolute literal operator paths required')
    return path


def render(source, interpreter, metadata, configuration, user, uid, output):
    source, interpreter, output = map(literal_path, (source, interpreter, output))
    if user == 'root' or not re.fullmatch(r'[a-z_][a-z0-9_-]*', user) or type(uid) is not int or uid < 1:
        raise ValueError('Non-root deployment user and UID required')
    if not re.fullmatch(r'[a-f0-9]{40}', metadata.get('source_commit', '')):
        raise ValueError('Full operator source identity required')
    if output.exists():
        raise ValueError('Rendered units destination must be new')
    if not source.is_dir() or source.resolve() != source:
        raise ValueError('Retained operator source must be a real directory')
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('Installed executable interpreter required')
    sources = metadata.get('source_files_sha256', {})
    # Bind every deploy module: imported helper changes must not escape identity.
    modules = sorted((source / 'deploy').glob('*.py'))
    if not modules or not all((source / (module.replace('.', '/') + '.py')).is_file() for module, _, _ in SERVICES.values()):
        raise ValueError('Operator modules absent from retained source')
    for path in modules:
        relative = str(path.relative_to(source))
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sources.get(relative):
            raise ValueError('Operator module does not match retained source metadata')
    if set(configuration) != {'daily-recovery', 'recovery', 'monitor'}:
        raise ValueError('Explicit private configuration paths required')
    configurations = {name: literal_path(path) for name, path in configuration.items()}
    config_status = {}
    for name, path in configurations.items():
        if path.exists():
            if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
                raise ValueError('Existing operator configurations must be private regular files')
            config_status[name] = 'private_file_present_contents_not_audited'
        else:
            config_status[name] = 'missing_activation_blocked'
    version = subprocess.check_output([str(interpreter), '-c', 'import platform; print(platform.python_version())'], timeout=30).decode().strip()
    if version != '3.12.10':
        raise ValueError('Frozen operator Python 3.12.10 required')
    # Verify module resolution in the supplied source directory, not whichever
    # checkout an editable interpreter installation happens to point to.
    code = ('import importlib,json,sys; print(json.dumps({name:importlib.import_module(name).__file__ '
            'for name in sys.argv[1:]}))')
    module_names = [value[0] for value in SERVICES.values()]
    resolved = json.loads(subprocess.check_output([str(interpreter), '-c', code, *module_names],
                         cwd=source, env={**os.environ, 'PYTHONPATH': str(source)}, timeout=30))
    for module in module_names:
        if Path(resolved[module]).resolve() != source / (module.replace('.', '/') + '.py'):
            raise ValueError('Interpreter imports an unexpected operator source')
    output.mkdir(mode=0o700, parents=True)
    checksums = {}
    for name, (module, config_name, timeout) in SERVICES.items():
        text = ('[Unit]\nDescription=Inactive reviewed MLDSAFAIL operator unit\n'
                '[Service]\nType=oneshot\nDelegate=yes\nUser=' + user + '\nUMask=0077\n'
                'WorkingDirectory=' + str(source) + '\n'
                'Environment=DOCKER_HOST=unix:///run/user/' + str(uid) + '/docker.sock\n'
                'Environment=XDG_RUNTIME_DIR=/run/user/' + str(uid) + '\n'
                'Environment=MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT=/sys/fs/cgroup/system.slice/%n\n'
                'ExecStart=' + str(interpreter) + ' -m ' + module +
                (' check' if config_name == 'recovery' else '') + ' --config ' + str(configurations[config_name]) + '\n')
        if config_name == 'daily-recovery':
            text += 'ExecStopPost=' + str(interpreter) + ' -m ' + module + ' --cleanup --config ' + str(configurations[config_name]) + '\nTimeoutStopSec=5min\n'
        text += 'TimeoutStartSec=' + timeout + '\nNoNewPrivileges=true\n'
        path = output / name
        path.write_text(text)
        path.chmod(0o600)
        checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(source_commit=metadata['source_commit'], source_directory=str(source),
                  interpreter=str(interpreter), interpreter_version=version, interpreter_sha256=hashlib.sha256(interpreter.read_bytes()).hexdigest(),
                  module_source_verified=True, configuration=config_status, unit_sha256=checksums,
                  installed=False, activated=False, native_systemd_verification_pending=True,
                  repeat_activation_parent_binding='blocked_requires_persistent_delegated_parent_or_reviewed_per_activation_registration',
                  operator_client_cgroup='per-unit delegated system.slice unit; separate from benchmark accounting parent')
    path = output / 'render-report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    path.chmod(0o600)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--interpreter', required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--configs', type=Path, required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--uid', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = render(args.source, args.interpreter, json.loads(args.metadata.read_text()),
                        json.loads(args.configs.read_text()), args.user, args.uid, args.output)
        print(json.dumps({'operator_units_rendered': True, 'activated': False}))
    except Exception:
        print(json.dumps({'operator_units_render_failed': True}))
        raise SystemExit(1)
