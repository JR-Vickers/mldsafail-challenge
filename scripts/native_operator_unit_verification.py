"""Verify inactive source-bound system units on Linux without installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from deploy import owned_client
from deploy.recovery_journal import atomic_json, safe_path
from deploy.render_operator_units import SERVICES


def verify(units, metadata, output):
    if sys.platform != 'linux':
        raise RuntimeError('Native Linux systemd verification required')
    units, output = safe_path(units), safe_path(output)
    if output.exists():
        raise ValueError('New private verification directory required')
    output.mkdir(mode=0o700, parents=True)
    state = {'complete': False, 'installed': False, 'activated': False, 'clients': [], 'checks': [],
             'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    journal = output/'verification.json'
    save = lambda: atomic_json(journal, state)
    save()
    original = None
    try:
        report = json.loads(safe_path(units/'render-report.json').read_text())
        if report.get('installed') is not False or report.get('activated') is not False:
            raise ValueError('Only inactive rendered units are eligible')
        if report['source_commit'] != metadata['source_commit']:
            raise ValueError('Retained operator source identity mismatch')
        source = safe_path(report['source_directory'])
        interpreter = Path(report['interpreter'])
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK) or hashlib.sha256(interpreter.read_bytes()).hexdigest() != report['interpreter_sha256']:
            raise ValueError('Installed interpreter identity mismatch')
        modules = list((source/'deploy').glob('*.py'))
        expected_modules = {name for name in metadata['source_files_sha256'] if Path(name).parent == Path('deploy') and name.endswith('.py')}
        if not modules or {str(module.relative_to(source)) for module in modules} != expected_modules:
            raise ValueError('Exact retained operator module inventory required')
        for module in modules:
            if module.is_symlink() or hashlib.sha256(module.read_bytes()).hexdigest() != metadata['source_files_sha256'].get(str(module.relative_to(source))):
                raise ValueError('Operator module identity mismatch')
        if set(report['unit_sha256']) != set(SERVICES):
            raise ValueError('Exact inactive operator unit inventory required')
        paths = []
        for name in SERVICES:
            path = safe_path(units/name)
            if path.stat().st_mode & 0o077 or hashlib.sha256(path.read_bytes()).hexdigest() != report['unit_sha256'][name]:
                raise ValueError('Private unit identity mismatch')
            paths.append(str(path))
        environment = dict(os.environ)
        for name in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
            environment.pop(name, None)
        environment.update(PYTHONPATH=str(source), PYTHONNOUSERSITE='1')
        def command(name, argv):
            with (output/(name+'.stdout')).open('xb') as out, (output/(name+'.stderr')).open('xb') as err:
                os.fchmod(out.fileno(), 0o600); os.fchmod(err.fileno(), 0o600)
                result = owned_client.run(argv, state['clients'], save, output, env=environment,
                                          cwd=source, timeout=60, stdout=out, stderr=err)
            state['checks'].append({'check': name, 'returncode': result.returncode})
            save()
        names = [entry[0] for entry in SERVICES.values()]
        code = 'import importlib,json,platform,sys;print(json.dumps({"python":platform.python_version(),"modules":{name:importlib.import_module(name).__file__ for name in sys.argv[1:]}}))'
        command('installed-modules', [str(interpreter), '-c', code, *names])
        resolved = json.loads((output/'installed-modules.stdout').read_text())
        if resolved['python'] != '3.12.10' or any(Path(resolved['modules'][name]).resolve() != source/(name.replace('.', '/')+'.py') for name in names):
            raise ValueError('Native interpreter/module resolution mismatch')
        command('systemd-verify', ['systemd-analyze', 'verify', *paths])
        state.update(source_commit=metadata['source_commit'], unit_sha256=report['unit_sha256'],
                     interpreter_sha256=report['interpreter_sha256'], module_source_verified=True)
    except BaseException as error:
        original = error
        state['failure_class'] = type(error).__name__
    finally:
        errors = []
        for entry in state['clients']:
            try:
                owned_client.stop(entry)
            except BaseException as error:
                errors.append(type(error).__name__)
        state['cleanup_errors'] = errors
        state['cleanup_complete'] = not errors
        state['complete'] = original is None and not errors
        try:
            save()
        except BaseException as error:
            if original is None:
                original = error
            else:
                original.add_note('Final verification publication failed: '+type(error).__name__)
    if original is not None:
        raise original
    if not state['complete']:
        raise RuntimeError('Native verification cleanup incomplete')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.units, json.loads(safe_path(args.metadata).read_text()), args.output)
        print(json.dumps({'native_inactive_units_verified': result['complete'], 'activated': False}))
    except Exception:
        print(json.dumps({'native_inactive_units_verified': False, 'activated': False}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
