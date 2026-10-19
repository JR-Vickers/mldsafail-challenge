"""Separate source-bound no-epoch diagnostic callback and cleanup-only operation."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import sys
import time
import uuid

from deploy import owned_client, owned_daemon
from deploy.render_operator_units import render
from research.cpu_measurement import native_driver
from scripts import production_diagnostic as diagnostic
from scripts.production_diagnostic_runtime import Client
from scripts.production_diagnostic_deadline import remaining, interrupt_at


def preflight(packet, config, repository):
    if diagnostic.file_digest(packet['driver_config']) != packet['driver_configuration_sha256']:
        raise ValueError('Actual driver configuration changed')
    config_root = Path(packet['bindings']['configuration']['root'])
    environment = Path(packet['synthetic_environment'])
    if not environment.is_relative_to(config_root) or environment.relative_to(config_root).as_posix() not in packet['bindings']['configuration']['files']:
        raise ValueError('Synthetic configuration must belong to frozen inventory')
    if packet['legacy_source'] != packet['bindings']['legacy_source']:
        raise ValueError('Actual legacy execution path differs from frozen source')
    artifacts = [dict(image=config['image'], archive=config['image_archive'], archive_sha256=config['image_archive_sha256']), *config.get('additional_images',[])]
    expected = {(identity,packet['bindings']['archive_'+role],packet['protocol']['archives'][role])
        for role,identity in packet['protocol']['images'].items()}
    if len(artifacts) != 5 or {(row['image'],row['archive'],row['archive_sha256']) for row in artifacts} != expected:
        raise ValueError('Driver image imports differ from reviewed artifact bindings')
    diagnostic.validate_artifacts(packet['protocol'], packet['bindings'])
    from scripts.native_production_rehearsal import verify_sources
    manifest = owned_daemon.read_private_json(packet['source_manifest'], cap=4*1024*1024)
    verify_sources(repository, manifest)
    if manifest['source_commit'] != config['source_commit']:
        raise ValueError('Diagnostic source commit differs')
    reference = Path(packet['reference_solver_directory'])
    if (diagnostic.verify_inventory(reference, {'solver.py': diagnostic.file_digest(repository/'examples/mlwe/primal-lll/solver.py')})
            != packet['reference_solver_inventory_sha256']):
        raise ValueError('Exact unchanged reference solver inventory required')
    review = owned_daemon.read_private_json(config['review_packet'])
    if (review.get('diagnostic_packet_sha256') != diagnostic.file_digest(packet['packet_path'])
            or review.get('diagnostic_review_passed') is not True
            or review.get('acceptance_source_sha256') != diagnostic.file_digest(__file__)
            or review.get('cleanup_source_sha256') != diagnostic.file_digest(__file__)):
        raise ValueError('Exact independent diagnostic source and cleanup review required')
    from scripts.production_diagnostic_fixture import _validate_rows
    fixture = owned_daemon.read_private_json(packet['bindings']['fixture'], cap=1024*1024)
    diagnostic.validate_fixture(fixture['metadata'], required_until=datetime.now(timezone.utc)+timedelta(seconds=7200))
    if hashlib.sha256(fixture['encoded'].encode()).hexdigest() != fixture['metadata']['dump_sha256']:
        raise ValueError('Canonical fixture bytes differ')
    data = json.loads(fixture['encoded'])
    if diagnostic.digest(data['rows']) != fixture['metadata']['identity_sha256']:
        raise ValueError('Canonical fixture identity differs')
    _validate_rows(data, fixture['metadata'])
    return manifest


def compose_configuration(generated, root, source, run_id, worker_slice):
    """Remove epoch/socket mounts and dispatch; retain deployed limits and Python."""
    from scripts.production_diagnostic_runtime import LABEL
    generated = json.loads(json.dumps(generated))
    generated['name'] = 'mldsafail-diagnostic-' + run_id
    generated['volumes'] = {'postgres_data': {'labels': {LABEL: run_id}}}
    generated['networks'] = {'default': {'labels': {LABEL: run_id}}}
    for role, service in generated['services'].items():
        service.update(labels={LABEL: run_id, 'org.mldsafail.diagnostic-role': role},
                       restart='no', cgroup_parent=worker_slice)
        service.pop('depends_on', None)
    web = generated['services']['web']
    web['ports'] = [dict(target=8000, published='0', host_ip='127.0.0.1', protocol='tcp')]
    # Trusted diagnostic helper source only, no evidence/epochs/host socket mounts.
    helper_mount = dict(type='bind', source=str(root/'helpers'), target='/diagnostic', read_only=True)
    web['volumes'] = [helper_mount]
    web['environment'].update(PYTHONPATH='/diagnostic',
        GUNICORN_CMD_ARGS='--config python:scripts.production_diagnostic_service')
    coordinator = generated['services']['coordinator']
    coordinator.update(entrypoint=['/app/.venv/bin/python', '-c', 'import time; time.sleep(7200)'], volumes=[])
    coordinator['environment'] = {'MLDSAFAIL_DATABASE_URL': coordinator['environment']['MLDSAFAIL_DATABASE_URL']}
    proxy = generated['services']['proxy']
    proxy.update(ports=[dict(target=8080, published='0', host_ip='127.0.0.1', protocol='tcp')],
        volumes=[dict(type='bind', source=str(source/'deploy/Caddyfile.private'), target='/etc/caddy/Caddyfile', read_only=True)],
        tmpfs=['/tmp:size=16m', '/data:size=16m', '/config:size=16m'])
    return generated


def wait_ready(packet, client):
    import urllib.request
    while True:
        try:
            with urllib.request.urlopen(packet['base']+'/health/ready', timeout=remaining(client.deadline, 2)) as response:
                if response.status == 200:
                    return
        except Exception:
            remaining(client.deadline, 1)
        time.sleep(.1)


def compose_environment(values):
    """Override every interpolation, retaining owned-client authority variables."""
    import re
    template = Path(__file__).resolve().parents[1]/'compose.production.yaml'
    variables = set(re.findall(r'\$\{([A-Z_][A-Z_0-9]*)', template.read_text()))
    frozen = dict(values, MLDSAFAIL_OUTSTANDING_PER_ACCOUNT='1',
                  MLDSAFAIL_SUBMISSIONS_PER_DAY='2', MLDSAFAIL_QUEUED_GLOBALLY='10')
    if variables != set(frozen):
        raise ValueError('Compose substitution inventory changed')
    return dict(os.environ, **frozen)


def verify_rendered_configuration(generated, values, images):
    services = generated['services']
    roles = dict(migrate='web', web='web', coordinator='coordinator', db='postgres', proxy='caddy')
    if set(services) != set(roles) or any(services[role]['image'] != images[image] for role,image in roles.items()):
        raise ValueError('Rendered image identities differ')
    database = 'postgresql+psycopg://mldsafail:'+values['POSTGRES_PASSWORD']+'@db/mldsafail'
    expected = {key:value for key,value in values.items() if key.startswith('GITHUB_') or
                key in ('MLDSAFAIL_SECRET_KEY','MLDSAFAIL_BENCHMARK_VERSION',
                        'MLDSAFAIL_EVALUATOR_FINGERPRINT','MLDSAFAIL_HIDDEN_SUITE_VERSION',
                        'MLDSAFAIL_WORKER_CLASS','MLDSAFAIL_MLWE_EPOCH_ID')}
    expected.update(MLDSAFAIL_DATABASE_URL=database, MLDSAFAIL_ENV='production',
        MLDSAFAIL_ADMISSION_LIMITS_ENABLED='1', MLDSAFAIL_OUTSTANDING_PER_ACCOUNT='1',
        MLDSAFAIL_SUBMISSIONS_PER_DAY='2', MLDSAFAIL_QUEUED_GLOBALLY='10', MLDSAFAIL_SKIP_MIGRATIONS='1')
    if any(services[role]['environment'] != expected for role in ('web','migrate')):
        raise ValueError('Rendered application environment differs')
    if (services['coordinator']['environment']['MLDSAFAIL_DATABASE_URL'] != database or
            services['db']['environment'] != dict(POSTGRES_DB='mldsafail', POSTGRES_USER='mldsafail',
                                                POSTGRES_PASSWORD=values['POSTGRES_PASSWORD']) or
            services['proxy']['environment'] != dict(MLDSAFAIL_DOMAIN=values['MLDSAFAIL_DOMAIN'])):
        raise ValueError('Rendered service environment differs')


def bootstrap(packet, root, data, client):
    images = packet['protocol']['images']
    cohort = 'synthetic-diagnostic-' + packet['run_id']
    expected = dict(POSTGRES_PASSWORD=None, MLDSAFAIL_SECRET_KEY=None,
        GITHUB_CLIENT_ID='synthetic-diagnostic', GITHUB_CLIENT_SECRET='synthetic-diagnostic',
        MLDSAFAIL_DOMAIN='diagnostic.invalid', MLDSAFAIL_BENCHMARK_VERSION='0.5.0',
        PRODUCTION_TLS_ROOT=str(root/'no-tls'), PRODUCTION_ACME_WEBROOT=str(root/'no-acme'),
        PRODUCTION_EVALUATOR_ROOT=str(root/'no-epoch'), ROOTLESS_DOCKER_SOCKET=data['socket'],
        WEB_IMAGE=images['web'], COORDINATOR_IMAGE=images['coordinator'], WORKER_IMAGE=images['worker'],
        POSTGRES_IMAGE=images['postgres'], CADDY_IMAGE=images['caddy'], MLDSAFAIL_EVALUATOR_FINGERPRINT=cohort,
        MLDSAFAIL_HIDDEN_SUITE_VERSION=cohort, MLDSAFAIL_WORKER_CLASS=cohort, MLDSAFAIL_MLWE_EPOCH_ID=cohort)
    values = owned_daemon.read_private_json(packet['synthetic_environment'])
    import re
    if (set(values) != set(expected)
            or any(values[key] != value for key,value in expected.items() if value is not None)
            or any(not isinstance(values[key],str) or not re.fullmatch('[0-9a-f]{64}',values[key])
                   for key in ('POSTGRES_PASSWORD','MLDSAFAIL_SECRET_KEY'))):
        raise ValueError('Actual synthetic configuration differs from reviewed inventory')
    env_file = root/'synthetic.env'
    from research.cpu_measurement.native_driver import install
    install(env_file, ''.join(key+'='+value+'\n' for key,value in values.items()))
    source = Path(__file__).resolve().parents[1]
    helpers = root/'helpers/scripts'
    helpers.mkdir(parents=True, mode=0o755)
    helpers.parent.chmod(0o755)
    for name in ('__init__.py', 'production_diagnostic.py', 'production_diagnostic_fixture.py',
                 'production_diagnostic_instrumentation.py', 'production_diagnostic_service.py'):
        target = helpers/name
        target.write_bytes((source/'scripts'/name).read_bytes())
        target.chmod(0o444)
    generated = json.loads(client.docker(['compose', '--env-file', str(env_file), '-f',
        str(source/'compose.production.yaml'), 'config', '--format', 'json'], env=compose_environment(values)))
    verify_rendered_configuration(generated, values, images)
    generated = compose_configuration(generated, root, source, packet['run_id'], data['worker_slice'])
    owned_daemon.publish(root/'compose.json', generated)
    compose = ['docker', 'compose', '-p', generated['name'], '-f', str(root/'compose.json')]
    client.run(compose+['up', '-d', '--no-deps', 'db'], ceiling=60, mutation=True)
    ready_deadline = min(client.deadline, time.monotonic()+60)
    while True:
        ready = client.run(compose+['exec', '-T', 'db', 'pg_isready', '-U', 'mldsafail'], check=False)
        if ready.returncode == 0:
            break
        remaining(ready_deadline, 1)
        time.sleep(.2)
    client.run(compose+['run', '--rm', '--no-deps', 'migrate'], ceiling=60, mutation=True)
    client.run(compose+['up', '-d', '--no-deps', 'web', 'coordinator', 'proxy'], ceiling=60, mutation=True)
    endpoint = client.run(compose+['port', 'web', '8000']).stdout.decode().strip()
    if not endpoint.startswith('127.0.0.1:'):
        raise RuntimeError('Loopback-only endpoint required')
    packet.update(compose=compose, base='http://'+endpoint, root=str(root),
        worker_slice=data['worker_slice'], manifest_path=data['manifest_path'],
        coordinator_id=client.run(compose+['ps', '-q', 'coordinator']).stdout.decode().strip(),
        public_cases=packet['protocol']['public_cases'])
    wait_ready(packet, client)
    return generated


def restore_fixture(packet, client):
    fixture = owned_daemon.read_private_json(packet['bindings']['fixture'], cap=1024*1024)
    fixture['required_until'] = (datetime.now(timezone.utc)+timedelta(seconds=7200)).isoformat()
    result = client.run(packet['compose'] + ['exec', '-T', 'web', '/app/.venv/bin/python', '-m',
        'scripts.production_diagnostic_service', 'restore'], ceiling=20, input=json.dumps(fixture).encode())
    value = json.loads(result.stdout)
    if value['identity_sha256'] != fixture['metadata']['identity_sha256']:
        raise ValueError('Restored PostgreSQL fixture differs')
    packet['token'] = value['token']


def install_monitor(packet, config, data, client, metadata):
    root, source = Path(packet['root']), Path(__file__).resolve().parents[1]
    endpoint = client.run(packet['compose']+['port', 'proxy', '8080']).stdout.decode().strip()
    if not endpoint.startswith('127.0.0.1:'):
        raise RuntimeError('Loopback monitor endpoint required')
    monitor = dict(scope='service', env_file=str(root/'synthetic.env'), compose=str(root/'compose.json'),
        readiness_url='http://'+endpoint+'/health/ready', daemon_manifest=data['manifest_path'],
        service_scheduled_units=[], alert_enabled=False, healthchecks=dict(enabled=False))
    owned_daemon.publish(root/'monitor.json', monitor)
    name = 'mldsafail-diagnostic-' + packet['run_id'] + '-monitor'
    report = render(str(source), sys.executable, metadata, dict(monitor=str(root/'monitor.json')),
        pwd.getpwuid(os.getuid()).pw_name, os.getuid(), str(root/'monitor-units'), monitor_only=True,
        docker_socket=data['socket'], cgroup_root=str(Path(config['operator_parent']).parent),
        monitor_name=name, owner_unit=config['operator_unit'], user_manager=True)
    journal = dict(monitor_units=[], monitor_start_intent=False)
    for unit in report['unit_sha256']:
        path = root/'monitor-units'/unit
        text = path.read_text()
        if unit.endswith('.service'):
            text = text.replace(' -m deploy.host_checks ', ' -m scripts.production_diagnostic_service monitor ')
            text += 'Environment=MLDSAFAIL_DIAGNOSTIC_MONITOR_EVIDENCE='+str(root/'monitor-commands.jsonl')+'\n'
        destination = Path.home()/'.config/systemd/user'/unit
        checksum = hashlib.sha256(text.encode()).hexdigest()
        journal['monitor_units'].append(dict(path=str(destination), sha256=checksum))
        owned_daemon.publish(root/'journal.json', journal)
        native_driver.install(destination, text)
    client.run(['systemctl', '--user', 'daemon-reload'])
    journal['monitor_start_intent'] = True
    owned_daemon.publish(root/'journal.json', journal)
    packet['monitor'] = name


def stopped_monitor(packet, client):
    from scripts.production_rehearsal_monitor_load import stop_monitors
    # Existing source-bound monitor cleanup, using its own client registry.
    root = Path(packet['root'])
    env = dict(os.environ, MLDSAFAIL_OWNED_CLIENT_ROOT=str(root))
    stop_monitors(root, env)
    for suffix in ('.service', '.timer'):
        result = client.run(['systemctl', '--user', 'show', packet['monitor']+suffix,
            '--property=ActiveState,MainPID,ControlGroup']).stdout.decode()
        values = dict(line.split('=',1) for line in result.splitlines() if '=' in line)
        if values.get('ActiveState') not in ('inactive', 'failed') or values.get('MainPID', '0') != '0':
            raise RuntimeError('Monitor remains active')


def configuration_inventory(root, phase):
    root = Path(root)
    paths = [root/'synthetic.env',root/'compose.json',root/'monitor.json']
    paths += [path for path in (root/'helpers').rglob('*') if path.is_file()]
    journal = owned_daemon.read_private_json(root/'journal.json')
    paths += [Path(item['path']) for item in journal['monitor_units']]
    owned_daemon.publish(root/('configuration-'+phase+'.json'), dict(
        files_sha256={str(path):diagnostic.file_digest(path) for path in paths}))


def run_phase(packet, config, client, name, phase_deadline, terminal_deadline):
    from scripts.production_diagnostic_controller import quiesce_engine
    phase_client = Client(Path(packet['root'])/(name+'-controller'), phase_deadline)
    phase_client.run([sys.executable, '-B', '-m', 'scripts.production_diagnostic_phases',
        str(Path(packet['root'])/'phase-packet.json'), name, str(phase_deadline)],
        ceiling=remaining(phase_deadline,2100),
        before_cancel=lambda entry: quiesce_engine(config,Path(packet['root']),entry,terminal_deadline))


def callback(driver, config, data):
    packet_path = Path(config['state_root']).parent/'packet.json'
    packet = owned_daemon.read_private_json(packet_path, cap=4*1024*1024)
    packet['packet_path'] = str(packet_path)
    metadata = preflight(packet, config, Path(__file__).resolve().parents[1])
    if set(packet['protocol']['images'].values()) - set(data['loaded_images']):
        raise ValueError('Exact imported diagnostic images required')
    start = owned_daemon.read_private_json(Path(packet['budget_root'])/(packet['protocol']['generation']+'-start.json'))
    if start['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise ValueError('Generation boot identity changed')
    started = start['monotonic_started']
    work_deadline = started + 2100
    root = Path(config['state_root'])/'diagnostic'
    root.mkdir(mode=0o700)
    setup = packet['protocol']['phases'][0]
    client = Client(root/'lifecycle-client', min(work_deadline, started+setup['outer_seconds']))
    original = None
    report = dict(complete=False, diagnostic_only=True, private_acceptance=False, ranking=False, phases=[])
    try:
        with interrupt_at(client.deadline):
            from mldsafail.benchmark_v050.execution import fingerprint
            for name, image in packet['protocol']['images'].items():
                inspected = json.loads(client.docker(['image','inspect',image]))[0]
                if inspected['Id'] != image or inspected['Architecture'] != 'amd64':
                    raise ValueError('Immutable native amd64 image identity differs')
                labels = inspected['Config'].get('Labels',{})
                if name == 'worker' and labels.get('org.mldsafail.trusted') != fingerprint():
                    raise ValueError('Frozen worker trusted fingerprint differs')
                if name in ('web','coordinator') and labels.get('org.mldsafail.source') != packet['application_source_commit']:
                    raise ValueError('Application image provenance differs')
            bootstrap(packet, root, data, client)
            for role in ('web','coordinator'):
                version = client.run(packet['compose']+['exec','-T',role,'/app/.venv/bin/python','-c','import platform; print(platform.python_version())']).stdout.decode().strip()
                if version != '3.12.10':
                    raise ValueError('Frozen Python 3.12.10 required')
            restore_fixture(packet, client)
            install_monitor(packet, config, data, client, metadata)
        # The engine's outer setup timer covered provisioning/imports as well
        # as this callback. Only completed setup releases it for measured phases.
        from scripts.production_diagnostic_deadline import release_setup
        release_setup()
        configuration_inventory(root, 'setup')
        packet['sample_domains'] = dict(worker=data['worker_parent'], daemon=data['registered_manifest']['domain']['path'])
        client.deadline = work_deadline
        for phase in packet['protocol']['phases'][1:]:
            ceiling = phase['outer_seconds']
            if time.monotonic()+ceiling > work_deadline:
                raise TimeoutError('Next complete phase cannot fit work allowance')
            phase_deadline = time.monotonic()+ceiling
            client.deadline = phase_deadline
            with interrupt_at(phase_deadline):
                restore_fixture(packet, client)
                if not phase['name'].startswith('monitor-'):
                    stopped_monitor(packet, client)
            if phase['name'] == 'final-idle':
                # Recreate the same application image/settings without the hook.
                (root/'compose-before-final.json').write_bytes((root/'compose.json').read_bytes())
                (root/'compose-before-final.json').chmod(0o600)
                generated = owned_daemon.read_private_json(root/'compose.json')
                generated['services']['web']['environment'].pop('GUNICORN_CMD_ARGS')
                # Preserve the actual allocated loopback endpoint on recreation.
                generated['services']['web']['ports'][0]['published'] = packet['base'].rsplit(':',1)[1]
                owned_daemon.publish(root/'compose.json', generated)
                client.run(packet['compose']+['up','-d','--no-deps','--force-recreate','web'], mutation=True, ceiling=60)
                wait_ready(packet, client)
                proof = client.run(packet['compose']+['exec','-T','web','/app/.venv/bin/python','-c',
                    "from pathlib import Path; assert not Path('/tmp/diagnostic-timings').exists(); print('instrumentation_disabled')"]).stdout.decode().strip()
                if proof != 'instrumentation_disabled':
                    raise RuntimeError('Heavy instrumentation remains active')
            configuration_inventory(root, phase['name'])
            owned_daemon.publish(root/'phase-packet.json', packet)
            run_phase(packet, config, client, phase['name'], phase_deadline, started+3000)
            if phase['name'].startswith('http-'):
                timings = client.run(packet['compose']+['exec','-T','web','/app/.venv/bin/python','-m',
                    'scripts.production_diagnostic_service','timings'], ceiling=10).stdout
                snapshot = json.loads(timings)
                from scripts.production_diagnostic_instrumentation import validate_snapshot
                requests = owned_daemon.read_private_json(root/phase['name']/'requests.json')['rows']
                validate_snapshot(snapshot, requests)
                owned_daemon.publish(root/(phase['name']+'-server-timings.json'), snapshot)
            report['phases'].append(phase['name'])
            owned_daemon.publish(root/'report.json', report)
        report['complete'] = True
    except BaseException as error:
        original = error
        report['error_type'] = type(error).__name__
        raise
    finally:
        client.deadline = started+3000
        try:
            if packet.get('monitor'):
                with interrupt_at(started+3000):
                    stopped_monitor(packet, client)
        except BaseException as error:
            report['monitor_cleanup_error'] = type(error).__name__
            if original is None:
                raise
        finally:
            owned_daemon.publish(root/'report.json', report)
    return dict(schema='mldsafail.owned-native-acceptance.v1', passed=True, native_executed=True,
        evidence_refs=[str(root/'report.json')], source_sha256=config['acceptance_source_sha256'])


def terminal_cleanup(path, controller_config, repository):
    """Retained ownership only: never provision, import, restore or resume."""
    native_driver.validate(controller_config, repository)
    review = owned_daemon.read_private_json(controller_config['review_packet'])
    if (review.get('diagnostic_review_passed') is not True
            or review.get('cleanup_source_sha256') != diagnostic.file_digest(__file__)):
        raise ValueError('Exact independently reviewed diagnostic cleanup required')
    path = owned_daemon._canonical(path)
    root = path.parent/'diagnostic'
    errors = []
    if (root/'journal.json').exists():
        from scripts.production_rehearsal_monitor_load import stop_monitors
        data = owned_daemon.read_private_json(path, cap=4*1024*1024)
        env = dict(os.environ, DOCKER_HOST='unix://'+data['socket'], MLDSAFAIL_OWNED_CLIENT_ROOT=str(root))
        try:
            stop_monitors(root, env)
        except BaseException as error:
            errors.append(dict(step='monitor', error_type=type(error).__name__))
    receipt = native_driver.cleanup_state(path, controller_config=controller_config, repository=repository)
    if receipt.get('cleanup_complete') is True:
        # Only after the daemon barrier may interrupted phase/observer clients
        # be cancelled and their independent registries inspected.
        registries = list(root.rglob('clients.json')) if root.exists() else []
        if (path.parent.parent/'supervisor-clients.json').exists():
            registries.append(path.parent.parent/'supervisor-clients.json')
        for registry in registries:
            value = json.loads(registry.read_text())
            clients = value['clients'] if isinstance(value, dict) else value
            for entry in clients:
                try:
                    owned_client.stop(entry)
                except BaseException as error:
                    errors.append(dict(step='client', error_type=type(error).__name__))
    return dict(cleanup_complete=receipt.get('cleanup_complete') is True and not errors,
                daemon_cleanup=receipt, errors=errors)
