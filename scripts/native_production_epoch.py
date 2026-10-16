"""Create one fresh rehearsal-only 0.5.0 epoch in the owned native daemon.

Never retries or replaces failed viability evidence. No application activation,
production credentials, score conversion, changed worker or profile selection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from deploy import owned_daemon
from research.cpu_measurement import native_driver


def require_host_floor():
    from deploy.host_checks import evaluate
    if evaluate(True, {"host": True}, [], None, [], scope="service"):
        raise RuntimeError("Host disk/RAM floor or inspection failed before epoch creation")


def callback(journal, config, data):
    protocol_path = journal.path.parent.parent / 'production-epoch-protocol.json'
    protocol = owned_daemon.read_private_json(protocol_path)
    review = owned_daemon.read_private_json(config['review_packet'])
    if (set(protocol) != {'schema', 'benchmark_version', 'worker', 'coordinator', 'purpose'}
            or protocol['schema'] != 'mldsafail.production-epoch.v1'
            or protocol['benchmark_version'] != '0.5.0'
            or protocol['purpose'] != 'disposable_rehearsal_only'
            or review.get('production_epoch_protocol_sha256') != hashlib.sha256(protocol_path.read_bytes()).hexdigest()):
        raise ValueError('Exact independently reviewed rehearsal epoch protocol required')
    for role in ('worker', 'coordinator'):
        if not re.fullmatch('sha256:[a-f0-9]{64}', protocol[role]) or protocol[role] not in data['loaded_images']:
            raise ValueError('Exact imported epoch controller and unchanged worker required')
    require_host_floor()
    output = journal.path.parent / 'rehearsal-epoch'
    output.mkdir(mode=0o700)
    evidence = output / 'evaluator'
    evidence.mkdir(mode=0o700)
    tools = output / 'tools'
    tools.mkdir(mode=0o700)
    wrapper = tools / 'docker'
    wrapper.write_text('#!/app/.venv/bin/python\nimport os,sys\narguments=sys.argv[1:]\n'
        'if arguments and arguments[0]=="run": arguments[1:1]=' + repr([
            '--label', 'org.mldsafail.rehearsal-epoch=' + data['id'],
            '--cgroup-parent', data['worker_slice']]) + '\n'
        'os.execv("/usr/local/bin/docker",["docker",*arguments])\n')
    wrapper.chmod(0o700)
    report = dict(schema='mldsafail.production-epoch-result.v1', passed=False,
                  benchmark_version='0.5.0', purpose=protocol['purpose'],
                  production_activation=False, epoch_attempts=1,
                  worker=protocol['worker'], coordinator=protocol['coordinator'],
                  wrapper_sha256=hashlib.sha256(wrapper.read_bytes()).hexdigest())
    owned_daemon.publish(output / 'report.json', report)
    controller = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '0:0',
        '--cgroup-parent', data['worker_slice'], '--tmpfs', '/tmp:size=128m',
        '--mount', 'type=bind,src=' + str(evidence) + ',dst=' + str(evidence),
        '--mount', 'type=bind,src=' + str(tools) + ',dst=/rehearsal-tools,readonly',
        '--mount', 'type=bind,src=' + data['socket'] + ',dst=/var/run/docker.sock',
        '-e', 'DOCKER_HOST=unix:///var/run/docker.sock',
        '-e', 'PATH=/rehearsal-tools:/app/.venv/bin:/usr/local/bin:/usr/bin:/bin',
        '--entrypoint', '/app/.venv/bin/python', protocol['coordinator'], '-c']
    epoch = evidence / 'epoch'
    code = ('from pathlib import Path; from mldsafail.benchmark_v050 import cli,execution; '
            'cli.environment=lambda:execution.environment(' + repr(protocol['worker']) + '); '
            'cli.create_epoch(Path(' + repr(str(epoch)) + '))')
    try:
        result = journal.command(controller + [code], kind='fresh_epoch', timeout=5400)
        for name, raw in (('create.stdout', result.stdout), ('create.stderr', result.stderr)):
            path = output / name
            path.write_bytes(raw)
            path.chmod(0o600)
        if not (epoch / 'COMPLETE.json').is_file():
            raise RuntimeError('Fresh rehearsal epoch did not complete frozen viability gates')
        # A separate controller independently regenerates and audits the sealed evidence.
        code = ('import json; from pathlib import Path; '
                'from mldsafail.benchmark_v050.evidence import audit_epoch; '
                'manifest,reference=audit_epoch(Path(' + repr(str(epoch)) + ')); '
                'print(json.dumps(dict(epoch_id=manifest["id"],reference_cases=len(reference))))')
        audited = json.loads(journal.command(controller + [code], kind='epoch_audit', timeout=600).stdout)
        if audited['reference_cases'] != 100:
            raise RuntimeError('Frozen reference inventory differs')
        report.update(audited, passed=True, independently_audited=True,
                      completion_sha256=hashlib.sha256((epoch / 'COMPLETE.json').read_bytes()).hexdigest())
    except BaseException as error:
        report['failure_class'] = type(error).__name__
        raise
    finally:
        owned_daemon.publish(output / 'report.json', report)
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
                source_sha256=config['acceptance_source_sha256'], evidence_refs=['rehearsal-epoch/report.json'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    native_driver.execute(owned_daemon.read_private_json(args.config), Path(__file__).resolve().parents[1],
                          acceptance=callback, daemon_kind='owned')


if __name__ == '__main__':
    main()
