"""Same-process disposable PostgreSQL and frozen application acceptance.

Called only by the reviewed isolated native driver; no staging endpoint is used.
"""
import hashlib
import json
from pathlib import Path

from deploy import owned_daemon
from research.cpu_measurement import native_driver
from scripts import native_postgres_acceptance

DATABASE_IMAGE = 'sha256:639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652'
WEB_IMAGE = 'sha256:336462b8995c03dec545601634a9d430e6b3edea7663437f8edcbfe7016177d5'


def acceptance(journal, config, data):
    if not {DATABASE_IMAGE, WEB_IMAGE}.issubset(data['loaded_images']):
        raise RuntimeError('Exact retained database and frozen web images required')
    output = journal.path.parent / 'postgres'
    native_postgres_acceptance.run(DATABASE_IMAGE, output)
    postgres = owned_daemon.read_private_json(output / 'report.json', cap=4 * 1024 * 1024)
    if postgres.get('passed') is not True or postgres.get('cleanup_complete') is not True:
        raise RuntimeError('Complete native PostgreSQL acceptance required')
    probe = Path(__file__).with_name('native_expired_token_probe.py').resolve()
    name = 'mldsafail-token-probe-' + data['id']
    identifier = journal.command([
        'docker', 'create', '--name', name, '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--pids-limit', '64', '--memory', '256m',
        '--cgroup-parent', data['worker_slice'], '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
        '--mount', 'type=bind,source=' + str(probe) + ',target=/probe.py,readonly',
        '--entrypoint', 'python', WEB_IMAGE, '/probe.py'], kind='container_create').stdout.decode().strip()
    import re
    if not re.fullmatch('[a-f0-9]{64}', identifier):
        raise RuntimeError('Exact disposable application container identity required')
    result = journal.command(['docker', 'start', '--attach', identifier], kind='container_start', timeout=90)
    token = json.loads(result.stdout)
    inspected = json.loads(journal.command(['docker', 'inspect', identifier]).stdout)[0]
    if (inspected['Id'] != identifier or inspected['Image'] != WEB_IMAGE or
            inspected['Name'] != '/' + name or inspected['State']['Running'] is not False or
            inspected['State']['ExitCode'] != 0 or token.get('passed') is not True):
        raise RuntimeError('Frozen image expired-token acceptance failed')
    receipt = journal.path.parent / 'application-acceptance.json'
    owned_daemon.publish(receipt, dict(passed=True, native_executed=True,
        postgres=postgres, expired_token=token, web_image=WEB_IMAGE,
        database_image=DATABASE_IMAGE, probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest()))
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True,
                native_executed=True, evidence_refs=[str(receipt)],
                source_sha256=config['acceptance_source_sha256'])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config),
        Path(__file__).resolve().parents[1], acceptance=acceptance, daemon_kind='owned')


if __name__ == '__main__':
    main()
