"""Build and retain new native application pairs inside the owned daemon.

No production activation, worker rebuild, registry publication or staging access.
Input contexts are exact archived clean checkpoints, separately identified from
historical releases. Invoke only through the reviewed owned native driver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from deploy import owned_daemon
from research.cpu_measurement import native_driver

ROLLBACK = '4602f455c7cc365b41d05bb0ef49f738dd6d9d2b'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_context(context, manifest):
    root = owned_daemon._canonical(context)
    if not re.fullmatch('[0-9a-f]{40}', manifest.get('source_commit', '')):
        raise ValueError('Full clean context source identity required')
    files = manifest.get('source_files_sha256', {})
    if not files or not {'Dockerfile', 'Dockerfile.coordinator', 'uv.lock', 'pyproject.toml', '.dockerignore'} <= files.keys():
        raise ValueError('Complete source/build context inventory required')
    actual = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Build context links forbidden')
        if path.is_file():
            actual[path.relative_to(root).as_posix()] = digest(path)
    if actual != files:
        raise ValueError('Actual build context differs from frozen inventory')
    return root


def validate_protocol(protocol):
    if (protocol.get('schema') != 'mldsafail.production-release-build.v1'
            or protocol.get('benchmark_version') != '0.5.0'
            or set(protocol.get('pairs', {})) != {'candidate', 'rollback'}):
        raise ValueError('Explicit new frozen-0.5.0 release build protocol required')
    pairs = protocol['pairs']
    for pair in pairs.values():
        inspect_context(pair['context'], pair['manifest'])
    if pairs['rollback']['manifest']['source_commit'] != ROLLBACK:
        raise ValueError('Rollback must be newly built from source 4602f45')
    candidate = pairs['candidate']['manifest']
    rollback = pairs['rollback']['manifest']
    # Compare the actual frozen benchmark, lock and schema bytes before builds.
    for prefix in ('src/mldsafail/benchmark_v050/', 'migrations/'):
        subset = lambda value: {k: v for k, v in value['source_files_sha256'].items() if k.startswith(prefix)}
        if not subset(candidate) or subset(candidate) != subset(rollback):
            raise ValueError('Candidate/rollback frozen benchmark or schema incompatibility')
    for name in ('uv.lock', 'deploy/worker-linux-amd64.requirements.txt'):
        if candidate['source_files_sha256'][name] != rollback['source_files_sha256'][name]:
            raise ValueError('Candidate/rollback dependency lock incompatibility')
    return pairs


def callback(journal, config, data):
    protocol_path = journal.path.parent.parent / 'production-release-protocol.json'
    protocol = owned_daemon.read_private_json(protocol_path, cap=4 * 1024 * 1024)
    review = owned_daemon.read_private_json(config['review_packet'])
    if review.get('production_release_protocol_sha256') != digest(protocol_path):
        raise ValueError('Exact build protocol absent from independent review')
    pairs = validate_protocol(protocol)
    output = journal.path.parent / 'release-artifacts'
    output.mkdir(mode=0o700)
    report = dict(schema='mldsafail.production-release-build-result.v1', passed=False,
                  benchmark_version='0.5.0', production_activation=False,
                  protocol_sha256=digest(protocol_path), pairs={})
    owned_daemon.publish(output / 'report.json', report)
    try:
        info = json.loads(journal.command(['docker', 'info', '--format', '{{json .}}']).stdout)
        if info.get('Architecture') not in {'x86_64', 'amd64'}:
            raise RuntimeError('Native amd64 daemon required')
        inventory_code = ('import json,platform,importlib.metadata as m; '
                          'print(json.dumps(dict(python=platform.python_version(),'
                          'packages=sorted((d.metadata["Name"],d.version) for d in m.distributions()))))')
        for name, pair in pairs.items():
            context = inspect_context(pair['context'], pair['manifest'])
            result = dict(source_commit=pair['manifest']['source_commit'],
                          source_files_sha256=pair['manifest']['source_files_sha256'], images={})
            report['pairs'][name] = result
            for role, dockerfile in (('web', 'Dockerfile'), ('coordinator', 'Dockerfile.coordinator')):
                iid = output / (name + '-' + role + '.iid')
                journal.command(['docker', 'build', '--platform', 'linux/amd64', '--label',
                    'org.mldsafail.source=' + result['source_commit'], '--iidfile', str(iid),
                    '-f', str(context / dockerfile), str(context)], kind='application_build', timeout=1800)
                image = iid.read_text().strip()
                if not re.fullmatch('sha256:[a-f0-9]{64}', image):
                    raise RuntimeError('Immutable built application image ID required')
                inspected = json.loads(journal.command(['docker', 'image', 'inspect', image]).stdout)[0]
                if (inspected['Id'] != image or inspected['Architecture'] != 'amd64'
                        or inspected['Os'] != 'linux'
                        or inspected['Config']['Labels'].get('org.mldsafail.source') != result['source_commit']):
                    raise RuntimeError('Built image identity differs')
                inventory = json.loads(journal.command(['docker', 'run', '--rm', '--network', 'none',
                    '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                    '--cgroup-parent', data['worker_slice'], '--entrypoint', '/app/.venv/bin/python',
                    image, '-c', inventory_code], kind='inventory_controller', timeout=60).stdout)
                if inventory['python'] != '3.12.10':
                    raise RuntimeError('Frozen Python 3.12.10 required')
                archive = output / (name + '-' + role + '.tar')
                journal.command(['docker', 'image', 'save', '--output', str(archive), image],
                                kind='image_archive', timeout=180)
                archive.chmod(0o600)
                result['images'][role] = dict(id=image, architecture='amd64', inspection=inspected,
                    interpreter_dependencies=inventory, archive=archive.name, archive_sha256=digest(archive))
                owned_daemon.publish(output / 'report.json', report)
            inspect_context(context, pair['manifest'])
        report['passed'] = True
    finally:
        owned_daemon.publish(output / 'report.json', report)
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
                source_sha256=config['acceptance_source_sha256'], evidence_refs=['release-artifacts/report.json'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config), Path(__file__).resolve().parents[1],
                          acceptance=callback, daemon_kind='owned')


if __name__ == '__main__':
    main()
