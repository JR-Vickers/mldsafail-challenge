import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

import pytest

from scripts import production_diagnostic_deadline as deadline
from scripts import production_diagnostic_runtime as runtime
from scripts import native_production_diagnostic as native
from scripts import production_diagnostic_phases as phases


def test_nested_absolute_deadlines_never_reset():
    assert deadline.remaining(200, 100, clock=lambda:150) == 50
    with pytest.raises(TimeoutError): deadline.remaining(200, 1, clock=lambda:200)
    with deadline.bounded(time.monotonic()+1):
        with deadline.bounded(time.monotonic()+100):
            assert deadline.timeout(100) <= 1
    for value in (float('nan'), float('inf'), True):
        with pytest.raises(ValueError): deadline.remaining(value, 1)


def test_direct_helpers_are_interrupted_at_absolute_deadline():
    with pytest.raises(TimeoutError, match='deadline'):
        with deadline.interrupt_at(time.monotonic()+.02):
            time.sleep(.1)


def test_client_registries_are_separate_and_deadlines_propagate(tmp_path, monkeypatch):
    calls = []
    def run(argv, clients, save, root, **kwargs):
        clients.append(dict(id=str(root)))
        save()
        calls.append((str(root), kwargs['timeout'], kwargs['cancel']))
        return SimpleNamespace(stdout=b'{}', returncode=0)
    monkeypatch.setattr(runtime.owned_client, 'run', run)
    clients = [runtime.Client(tmp_path/name, time.monotonic()+10) for name in ('lifecycle','worker','observer')]
    for client in clients:
        client.run(['docker','info'], ceiling=30)
    assert len({path for path,_,_ in calls}) == 3
    assert all(0 < seconds <= 10 for _,seconds,_ in calls)
    assert len({id(cancel) for _,_,cancel in calls}) == 3
    for client in clients:
        assert len(json.loads((client.root/'clients.json').read_text())['clients']) == 1
        client.deadline = time.monotonic()-1
        with pytest.raises(TimeoutError): client.run(['docker','info'])
    assert len(calls) == 3


def test_disposable_compose_has_no_epoch_socket_or_dispatch_access(tmp_path):
    generated = dict(services={name:dict(environment={'MLDSAFAIL_DATABASE_URL':'synthetic'},
        volumes=['forbidden:/epoch','forbidden:/var/run/docker.sock'], depends_on={},
        mem_limit=256000000) for name in ('web','coordinator','proxy','db','migrate')})
    result = native.compose_configuration(generated, tmp_path, tmp_path, 'a'*32, 'fresh.slice')
    coordinator = result['services']['coordinator']
    assert coordinator['volumes'] == []
    assert coordinator['entrypoint'][-1] == 'import time; time.sleep(7200)'
    assert set(coordinator['environment']) == {'MLDSAFAIL_DATABASE_URL'}
    assert all(port['host_ip'] == '127.0.0.1' for name in ('web','proxy')
        for port in result['services'][name]['ports'])
    assert result['services']['web']['mem_limit'] == 256000000
    assert result['services']['web']['environment']['GUNICORN_CMD_ARGS'] == '--config python:scripts.production_diagnostic_service'
    assert all(service['restart']=='no' for service in result['services'].values())
    assert generated['services']['coordinator']['volumes']  # no shared mutation


def test_workload_short_outer_window_stops_without_invocation(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('worker created')
    monkeypatch.setattr(runtime.Client, 'run', forbidden)
    workload = runtime.Workload({}, tmp_path, time.monotonic()+1, 'a'*32, 'fresh.slice')
    with pytest.raises(RuntimeError, match='first invocation'):
        workload.start()
    workload.finish()
    assert workload.error is None and workload.rows == []


def test_workload_uses_repository_order_and_attaches_stdin_during_start(tmp_path, monkeypatch):
    from scripts.production_diagnostic import public_workload, WORKER
    calls = []
    workload = runtime.Workload(dict(public_cases=public_workload(), reference_solver_directory='/public/solver'),
        tmp_path, time.monotonic()+120, 'a'*32, 'fresh.slice')
    def run(argv, **kwargs):
        calls.append((argv,kwargs))
        if argv[1] == 'create':
            return SimpleNamespace(stdout=b'known-id', returncode=0)
        if argv[1] == 'inspect':
            return SimpleNamespace(stdout=json.dumps([dict(Image=WORKER,
                Config=dict(Labels={runtime.LABEL:'a'*32}))]).encode(), returncode=0)
        if argv[1] == 'start':
            payload = json.loads(kwargs['input'].read())
            assert payload['instance']['instance_id'] == public_workload()[0]['instance_id']
            workload.stop.set()
            return SimpleNamespace(stdout=b'{"candidate":null}',stderr=b'',returncode=0)
        return SimpleNamespace(stdout=b'',returncode=0)
    monkeypatch.setattr(workload.client,'run',run)
    workload.start().finish()
    assert workload.error is None
    assert workload.rows[0]['index'] == 0 and workload.rows[0]['complete']
    start = next(argv for argv,_ in calls if argv[1]=='start')
    assert start == ['docker','start','--attach','--interactive','known-id']
    create = next(argv for argv,_ in calls if argv[1]=='create')
    assert '--network=none' in create and '--memory=2g' in create and '--cpus=1' in create


def test_sampler_shutdown_does_not_cancel_in_progress_observation(tmp_path, monkeypatch):
    sampler = phases.Sampler(dict(sample_domains={}), tmp_path, time.monotonic()+10, False)
    observed = []
    class Thread:
        def join(self, timeout): observed.append(sampler.client.cancel.is_set())
        def is_alive(self): return False
    sampler.thread = Thread()
    sampler.finish()
    assert observed == [False]


def test_cleanup_validates_source_before_controlling_monitors(tmp_path, monkeypatch):
    calls = []
    def fail(*args):
        calls.append('validate')
        raise ValueError('Source not admitted')
    monkeypatch.setattr(native.native_driver,'validate',fail)
    with pytest.raises(ValueError): native.terminal_cleanup(tmp_path/'driver.json',{},tmp_path)
    assert calls == ['validate']


@pytest.mark.parametrize('lease_error,classification',[(None,'ok'),('timeout','timeout'),('command','command'),('query','query'),('parse','parsing')])
def test_monitor_timing_publication_keeps_ten_second_command_timeout(monkeypatch, tmp_path, capsys,lease_error,classification):
    from deploy import host_checks
    from scripts import production_diagnostic_service as service
    from deploy import healthchecks
    config = tmp_path/'monitor.json'
    config.write_text(json.dumps(dict(scope='service',env_file='/private/env',compose='/private/compose',
        readiness_url='http://127.0.0.1',healthchecks=dict(enabled=False))))
    config.chmod(0o600)
    monkeypatch.setattr('sys.argv',['monitor','--config',str(config)])
    calls = []
    def output(argv, **kwargs):
        calls.append(kwargs['timeout'])
        if 'ps' in argv:return 'id'
        if 'inspect' in argv:return '{"Running":true}'
        if '-c' in argv:
            if lease_error=='timeout':raise subprocess.TimeoutExpired(argv,10)
            if lease_error in ('command','query'):
                raise subprocess.CalledProcessError(1,argv,output='mldsafail_diagnostic_query_failed\n' if lease_error=='query' else 'unclassified')
            if lease_error=='parse':return 'invalid-json'
        return '[]'
    monkeypatch.setattr(subprocess,'check_output',output)
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr('urllib.request.urlopen',lambda *args,**kwargs:Response())
    monkeypatch.setattr(healthchecks,'notify',lambda *args:None)
    monkeypatch.setattr(host_checks,'evaluate',lambda readiness,services,leases,backup,jobs,**kwargs:set(jobs))
    rows=[]
    with pytest.raises(SystemExit) as end: host_checks.main(diagnostic=rows.append)
    assert end.value.code == (0 if lease_error is None else 1)
    assert calls and set(calls)=={10}
    assert len(rows)>=len(calls) and any(row['classification']==classification for row in rows)
    assert set(rows[0]) == {'kind','classification','seconds'}


def test_supervisor_requires_positive_barrier_before_cancellation(tmp_path, monkeypatch):
    from scripts import production_diagnostic_controller as controller
    from deploy import owned_daemon
    root = tmp_path/'state'
    root.mkdir()
    manifest = tmp_path/'manifest.json'
    manifest.write_text('{}')
    owned_daemon.publish(root/'driver.json', dict(start_intent=True,manifest_path=str(manifest),clients=[]))
    calls=[]
    monkeypatch.setattr(controller,'current_domain',lambda:Path('/own/supervisor'))
    monkeypatch.setattr(controller.owned_client,'verify_domain',lambda entry:None)
    monkeypatch.setattr(owned_daemon,'load_manifest',lambda path:{})
    def barrier(*args,**kwargs):
        calls.append('barrier')
        return dict(shutdown_proven=True)
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',barrier)
    controller.quiesce_engine(dict(state_root=str(root)),tmp_path,{'cgroup':{}},time.monotonic()+10)
    assert calls==['barrier']
    monkeypatch.setattr(owned_daemon,'shutdown_barrier',lambda *args,**kwargs:dict(shutdown_proven=False))
    with pytest.raises(RuntimeError):
        controller.quiesce_engine(dict(state_root=str(root)),tmp_path,{'cgroup':{}},time.monotonic()+10)


def test_final_harness_retains_intent_and_refuses_dispatch_after_slow_publication():
    from scripts import staging_read_load
    calls, intents = [], []
    def slow(row):
        intents.append(row)
        time.sleep(.11)
    result = staging_read_load.run('http://127.0.0.1', 'unused', lambda: True,
        duration=.2, request_open=lambda *args,**kwargs:calls.append(True),
        read_only_health=True, intent=slow)
    assert not calls and len(intents)==1 and intents[0]['incomplete']
    assert 'dispatched_after_seconds' not in intents[0]
    assert not result['passed'] and not result['pacing_valid']
    assert result['dispatched_requests']==0


def test_expired_terminal_deadline_admits_no_daemon_or_client_mutation(monkeypatch):
    from deploy import owned_daemon, owned_client
    def forbidden(*args,**kwargs): raise AssertionError('Mutation after terminal deadline')
    monkeypatch.setattr(owned_daemon,'_unit',forbidden)
    with deadline.bounded(time.monotonic()+.01):
        time.sleep(.02)
        with pytest.raises(TimeoutError):
            owned_daemon.shutdown_barrier({},evidence_directory='/unused',attempt_id='expired')
        with pytest.raises(TimeoutError): owned_client.stop({})


def test_unacknowledged_gated_client_is_reconciled_without_assuming_inode(tmp_path,monkeypatch):
    from scripts import production_diagnostic_controller as controller
    calls=[]
    monkeypatch.setattr(controller,'current_domain',lambda:Path('/own/supervisor'))
    monkeypatch.setattr(controller.owned_client,'stop',lambda item:calls.append(item))
    entry=dict(pid=None,cgroup_intent={'parent':{},'name':'gated'})
    controller.quiesce_engine(dict(state_root=str(tmp_path/'absent')),tmp_path,entry,time.monotonic()+1)
    assert calls==[entry]


def test_instrumentation_sink_and_marker_failure_cannot_be_hidden():
    from scripts.production_diagnostic_instrumentation import validate_snapshot,TIMINGS
    rows=[dict(dict.fromkeys(TIMINGS|{'seconds'},0.),request_id=str(index)*32,route=route,status=200)
          for index,route in enumerate(('/health/ready','/api/v1/me'))]
    requests=[dict(status=200,route=row['route'],correlation_id=row['request_id']) for row in rows]
    validate_snapshot(dict(failed=False,rows=rows),requests)
    with pytest.raises(ValueError,match='lacks durable'):
        validate_snapshot(dict(failed=False,rows=rows),requests+[dict(status=200,correlation_id='f'*32)])
    rows[0]['Authorization']='forbidden'
    with pytest.raises(ValueError,match='nonsanitized'):
        validate_snapshot(dict(failed=False,rows=rows),requests)


def test_http_error_response_requires_matching_server_evidence():
    import urllib.error
    from scripts.production_diagnostic_probes import request_comparison
    from scripts.production_diagnostic_instrumentation import validate_snapshot,TIMINGS
    def error(request,timeout):
        identifier = '1'*32 if request.full_url.endswith('/me') else '0'*32
        raise urllib.error.HTTPError(request.full_url,503,'unavailable',{'X-Diagnostic-ID':identifier},None)
    result=request_comparison('http://127.0.0.1','unused',lambda:True,lambda rows:None,
        request_open=error,duration=.1,count=2,read_only_health=True)
    assert all(row.get('correlation_id') for row in result['requests'])
    rows=[dict(dict.fromkeys(TIMINGS|{'seconds'},0.),request_id=str(index)*32,route=route,status=503)
          for index,route in enumerate(('/health/ready','/api/v1/me'))]
    validate_snapshot(dict(failed=False,rows=rows),result['requests'])
    rows[1]['status']=200
    with pytest.raises(ValueError,match='matching'):
        validate_snapshot(dict(failed=False,rows=rows),result['requests'])


def test_status_socket_exposes_memory_flag_even_when_failure_marker_is_absent():
    import socket,tempfile
    from scripts.production_diagnostic_service import StatusSocket
    with tempfile.TemporaryDirectory(prefix='dg-status-',dir='/tmp') as directory:
        app=SimpleNamespace(extensions={})
        listener=StatusSocket(app,Path(directory))
        try:
            def status():
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
                    channel.settimeout(1)
                    channel.connect(str(next(Path(directory).glob('*.sock'))))
                    return json.loads(channel.recv(1024))
            assert status()=={'failed':False}
            app.extensions['diagnostic_evidence_failed']=True
            assert status()=={'failed':True}
            assert not (Path(directory)/'FAILED').exists()
        finally:
            listener.close()


def test_preflight_rejects_foreign_build_and_accepts_protected_process(tmp_path):
    from scripts.production_diagnostic_bootstrap import assert_no_foreign_jobs
    process=tmp_path/'123'
    process.mkdir()
    (process/'cmdline').write_bytes(b'/usr/bin/python3\0-m\0research.unknown\0')
    (process/'cgroup').write_text('0::/user.slice/unknown.service\n')
    with pytest.raises(RuntimeError,match='Unreconciled'):
        assert_no_foreign_jobs([],proc_root=tmp_path)
    assert_no_foreign_jobs([dict(path='/sys/fs/cgroup/user.slice/unknown.service')],proc_root=tmp_path)


def test_compose_parent_cannot_override_frozen_substitutions(monkeypatch):
    import re
    template = Path(native.__file__).resolve().parents[1]/'compose.production.yaml'
    keys = set(re.findall(r'\$\{([A-Z_][A-Z_0-9]*)', template.read_text()))
    limits = {'MLDSAFAIL_OUTSTANDING_PER_ACCOUNT', 'MLDSAFAIL_SUBMISSIONS_PER_DAY', 'MLDSAFAIL_QUEUED_GLOBALLY'}
    values = {key:'frozen' for key in keys-limits}
    for key in keys:
        monkeypatch.setenv(key,'hostile')
    monkeypatch.setenv('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT','/owned/domain')
    actual = native.compose_environment(values)
    assert all(actual[key] == 'frozen' for key in values)
    assert actual['MLDSAFAIL_OUTSTANDING_PER_ACCOUNT'] == '1'
    assert actual['MLDSAFAIL_SUBMISSIONS_PER_DAY'] == '2'
    assert actual['MLDSAFAIL_QUEUED_GLOBALLY'] == '10'
    assert actual['MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT'] == '/owned/domain'
    with pytest.raises(ValueError, match='inventory'):
        native.compose_environment(dict(values, UNREVIEWED='extra'))
