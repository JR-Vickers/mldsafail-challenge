"""Build a new fixed-reader archive; preserve the installed first collector.

The plan freezes finite reviewed-script and output paths at build time. Running
this builder installs nothing and grants no host authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from scripts.prepare_owner_collection_access import BOOTSTRAP, SOURCES
from deploy.workload_owner_readers import validate_plan

ROOT = '/root/mldsafail-owner-facts-20261022-v2'
RULE = '/etc/sudoers.d/mldsafail-owner-facts-v2'
COMMAND = '/usr/bin/python3 -I -B ' + ROOT + '/collector.pyz'
SUDOERS = 'mldsafail ALL=(root) NOPASSWD: ' + COMMAND + '\n'


def build(source, output, plan):
    validate_plan(plan)
    source, output = Path(source), Path(output)
    files = {name: (source/name).read_bytes() for name in
             (*SOURCES, 'deploy/workload_owner_readers.py', 'deploy/workload_observation.py')}
    files.update({'scripts/__init__.py': b'', 'deploy/__init__.py': b''})
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    code = (BOOTSTRAP.replace('ROOT_LITERAL', repr(ROOT)).replace('RULE_LITERAL', repr(RULE))
        .replace('SUDOERS_LITERAL', repr(SUDOERS)).replace('MANIFEST_LITERAL', repr(manifest))
        .replace('COMMAND_LITERAL', repr(COMMAND)))
    # The reviewed path set is embedded, not accepted as runtime arguments.
    code = code.replace('summary=scheduling(raw)',
        'summary=scheduling(raw, reviewed_paths=' + repr(tuple(plan['reviewed_paths'])) + ',command_runner=scheduling_command)')
    code = code.replace('from scripts.workload_owner_collection import collect as scheduling',
        'from scripts.workload_owner_collection import collect as scheduling\n'
        '        from deploy.workload_owner_readers import collect as supplemental,scheduling_command\n'
        '        import signal,time\n'
        '        started=time.monotonic()')
    code = code.replace('            stream.seek(0);data=stream.read(32*1024**2+1)',
        "            class SupplementalDeadline(Exception):pass\n"
        "            def expired(signum,frame):raise SupplementalDeadline('supplemental_collection_deadline')\n"
        '            remaining=max(0,180-(time.monotonic()-started))\n'
        '            previous=signal.signal(signal.SIGALRM,expired)\n'
        '            try:\n'
        "                if remaining<=0:raise TimeoutError('supplemental_collection_deadline')\n"
        '                signal.setitimer(signal.ITIMER_REAL,remaining)\n'
        '                summary[\'supplemental\']=supplemental(' + repr(plan) + ',seconds=remaining)\n'
        '            except Exception as error:\n'
        '                summary[\'supplemental\']=dict(readiness=False,error=type(error).__name__,detail=str(error))\n'
        '            finally:\n'
        '                signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)\n'
        "            summary['complete']=summary.get('complete') is True and summary['supplemental'].get('complete') is True\n"
        '            stream.seek(0);data=stream.read(32*1024**2+1)')
    compile(code, '__main__.py', 'exec')
    files['__main__.py'] = code.encode()
    with output.open('xb') as stream:
        output.chmod(0o600)
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
                info.external_attr = 0o100600 << 16
                archive.writestr(info, data)
    return dict(artifact=str(output), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        sources=manifest, plan=plan, root=ROOT, sudoers_path=RULE,
        command=COMMAND, sudoers=SUDOERS, installed=False, execution_authority=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output,
                           json.loads(args.plan.read_bytes())), sort_keys=True))


if __name__ == '__main__':
    main()
