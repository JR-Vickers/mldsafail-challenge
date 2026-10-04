"""VPS-only compatible application deployment using a retained reviewed driver.

Input is private JSON on stdin. Raw journals and backup material remain on host.
The operator driver must exactly match the retained release manifest.
"""
import importlib.util
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import threading
import time


def load_driver(config):
    path = pathlib.Path(config['operator_source']) / 'scripts/hosted_vps_failure_driver.py'
    expected = config['release_manifest']['source_files_sha256']['scripts/hosted_vps_failure_driver.py']
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Operator driver differs from retained release')
    spec = importlib.util.spec_from_file_location('retained_driver', path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver


def finish_cleanup(driver, subject, stop, thread, watcher):
    errors = []
    stop.set()
    thread.join(timeout=15)
    if thread.is_alive():
        errors.append('heartbeat_shutdown')
    try:
        driver.cleanup(subject.path)
    except BaseException:
        errors.append('maintenance_cleanup')
    # Independent watchdog shutdown must run even if maintenance cleanup fails.
    try:
        watcher.terminate()
        watcher.wait(timeout=10)
    except BaseException:
        errors.append('watchdog_shutdown')
    if errors:
        driver.save(subject.directory / 'preparation-cleanup-errors.json', {'errors': errors})
        raise RuntimeError('Preparation cleanup incomplete; protected journal requires reconciliation')


def run(c):
    os.umask(63)
    d = load_driver(c)
    p = pathlib.Path.home() / ('.mldsafail-acceptance-' + c['run_id'])
    p.mkdir(mode=448)
    c['directory'] = str(p)
    (p / 'probe.py').write_text(c.pop('probe'))
    subject = d.Driver(c)
    coordinator = d.command(subject.compose + ['ps', '-aq', 'coordinator'])
    web = d.command(subject.compose + ['ps', '-aq', 'web'])
    template = json.loads(d.command(['docker', 'inspect', coordinator]))[0]
    web_info = json.loads(d.command(['docker', 'inspect', web]))[0]
    release = c['release_manifest']
    rollback = c['rollback_manifest']
    for k in ('configuration_sha256', 'dependency_lock_sha256', 'worker_lock_sha256', 'historical_trusted_fingerprint', 'mlwe_trusted_fingerprint'):
        d.require(release[k] == rollback[k], k)
    d.require(template['Image'] == rollback['images']['coordinator']['id'])
    d.require(web_info['Image'] == rollback['images']['web']['id'])
    for manifest in (release, rollback):
        for role in ('web', 'coordinator', 'worker'):
            info = json.loads(d.command(['docker', 'image', 'inspect', manifest['images'][role]['id']]))[0]
            d.require(info['Architecture'] == 'amd64')
            if role != 'worker':
                d.require(info['Config']['Labels']['org.mldsafail.source'] == manifest['source_commit'])
    d.require(release['images']['worker']['id'] == rollback['images']['worker']['id'])
    d.require(hashlib.sha256(pathlib.Path(c['deployment'], 'compose.private.yaml').read_bytes()).hexdigest() == release['configuration_sha256'], 'Deployed configuration differs from release')
    subject.probe_id = coordinator
    identity = subject.probe('identity')
    before = subject.probe('snapshot')
    check = 'import os,json;from sqlalchemy import create_engine,text\nwith create_engine(os.environ[\'MLDSAFAIL_DATABASE_URL\']).connect() as db:\n rows=list(db.execute(text("select j.status,s.state,j.attempts from evaluation_jobs j join submissions s on s.id=j.submission_id where j.status in (\'queued\',\'claimed\',\'running\')")))\n assert all(tuple(r)==(\'queued\',\'cancelled\',0) for r in rows)\n print(json.dumps({\'cancelled_queue_rows\':len(rows)}))\n'
    queue = json.loads(d.command(['docker', 'exec', coordinator, '/app/.venv/bin/python', '-c', check]))
    d.require(not any((w['Name'].startswith('/mlwe-') and w['State']['Running'] for w in d.containers())))
    subject.api('/api/v1/me')
    subject.api('/api/v1/me', token=c['revoked_token'], expected=401)
    d.require(subject.health())
    env = dict((e.split('=', 1) for e in template['Config']['Env']))
    work = env['MLDSAFAIL_EVALUATOR_WORK_ROOT']
    rollback_override = p / 'rollback.yaml'
    forward_override = p / 'forward.yaml'
    for target, manifest in [(rollback_override, rollback), (forward_override, release)]:
        d.application_override(target, manifest)
    subject.j.update(worker_image=release['images']['worker']['id'], work_root=work, original_mode=os.stat(work).st_mode & 4095, compose=subject.compose, service_states={'web': web_info['State']['Running'], 'coordinator': template['State']['Running']}, maintenance=True, cleanup_complete=False, generation=1, watch_host=True, restore_command=subject.compose + ['-f', str(rollback_override), 'up', '-d', '--no-deps', 'web', 'coordinator'])
    d.save(subject.path, subject.j)
    subject.touch()
    watcher = subprocess.Popen(['python3', str(pathlib.Path(c['operator_source']) / 'scripts/hosted_vps_failure_driver.py'), '--watchdog', str(subject.path), '1'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    stop = threading.Event()

    def pulse():
        while not stop.wait(5):
            subject.heartbeat()
    thread = threading.Thread(target=pulse, daemon=True)
    thread.start()
    success = False
    try:
        inspector = subject.clone(template, image=release['images']['coordinator']['id'])
        subject.probe_id = inspector
        d.require(subject.probe('identity') == identity)
        print('Maintenance started: stop claims and writes, backup, narrow queue repair, application-only deployment.', flush=True)
        d.set_service_state(subject.compose, 'coordinator', False)
        d.set_service_state(subject.compose, 'web', False)
        d.require(not any((w['Name'].startswith('/mlwe-') and w['State']['Running'] for w in d.containers())))
        backup = json.loads(d.command(['python3', c['deployment'] + '/deploy/backup_postgres.py', '--env-file', c['env_file'], '--compose', c['deployment'] + '/compose.private.yaml', '--output', str(p / 'pre-maintenance-backup'), '--verify-restore'], timeout=360))
        d.require(backup['restore_verified'])
        repair_root = pathlib.Path(work).parent / ('acceptance-' + c['run_id'])
        repair_root.mkdir(mode=448)
        reports = []
        for index, apply in enumerate((False, True, True)):
            report = str(repair_root / ('repair-' + str(index) + '.jsonl'))
            code = "import os,sys,runpy;os.environ['DATABASE_URL']=os.environ['MLDSAFAIL_DATABASE_URL'];sys.argv=" + repr(['repair', '--report', report] + (['--apply'] if apply else [])) + ";runpy.run_path('/opt/mldsafail/deploy/reconcile_cancelled_jobs.py',run_name='__main__')"
            result = json.loads(subject.mutate(['docker', 'exec', inspector, '/app/.venv/bin/python', '-c', code]))
            d.require(result['affected_count'] == (0 if index == 2 else queue['cancelled_queue_rows']))
            reports.append(result)
        d.require(not subject.probe('active')['active'])
        d.require(subject.probe('snapshot') == before)
        subject.mutate(subject.compose + ['-f', str(forward_override), 'up', '--no-start', '--no-deps', 'coordinator'], timeout=60)
        subject.mutate(subject.compose + ['-f', str(forward_override), 'up', '-d', '--no-deps', 'web'], timeout=60)
        subject.wait(lambda: subject.health(), 90)
        subject.api('/api/v1/me')
        subject.api('/api/v1/me', token=c['revoked_token'], expected=401)
        d.require(subject.probe('snapshot') == before)
        d.require(subject.probe('identity') == identity)
        subject.j['restore_command'] = subject.compose + ['-f', str(forward_override), 'up', '-d', '--no-deps', 'web', 'coordinator']
        subject.touch()
        success = True
        outcome = dict(passed=False, deployment_verified=True, queue_repair=reports, backup_restore_verified=True, immutable_state_preserved=True, epoch_compatibility=True, source_commit=release['source_commit'])
        d.save(p / 'deployment-report.json', outcome)
    finally:
        finish_cleanup(d, subject, stop, thread, watcher)
    outcome.update(passed=True, cleanup_verified=True)
    d.save(p / 'deployment-report.json', outcome)
    print(json.dumps({'compatible_deployment': success, 'queue_repaired': True, 'backup_restore_verified': True, 'immutable_state_preserved': True, 'cleanup_verified': True}), flush=True)


if __name__ == "__main__":
    run(json.load(sys.stdin))
