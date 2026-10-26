"""Disposable Git/process rehearsals; never launch project work or live operations."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

MODULE = Path(__file__).resolve().parents[1] / 'tools/launch_runner/runner.py'
spec = importlib.util.spec_from_file_location('launch_runner', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

FAKE = '''#!/usr/bin/env python3
import json, pathlib, subprocess, sys, uuid, time
args=sys.argv[1:]
assert args[0]=='exec' and 'resume' not in args and 'fork' not in args
root=pathlib.Path(args[args.index('-o')+1]).parent.parent
cfgpath=root/'scenario.json'
cfg=json.loads(cfgpath.read_text()) if cfgpath.exists() else {}
prompt=sys.stdin.read()
sid=prompt.split('agent for ')[1][:3]
role=prompt.split('role ')[1].split('.')[0]
report=pathlib.Path(args[args.index('-o')+1])
repo=pathlib.Path.cwd()
def git(*a): return subprocess.check_output(['git',*a],text=True).strip()
(root/'child-started').write_text(str(__import__('os').getpid()))
while cfg.get('wait') and not (root/'release-child').exists(): time.sleep(.02)
status='complete'
if role!='review':
    if cfg.get('dirty_interrupt'):
        (repo/'unfinished.txt').write_text('retained edit')
        raise SystemExit(9)
    (repo/'work.txt').write_text(sid+' '+role)
    review=repo/'docs/LAUNCH_ARCHITECTURE_REVIEW.md'
    review.write_text(review.read_text()+f'\\n| {sid} | Complete | fixture |\\n## {sid} handoff — fixture\\nChecked.\\n')
    (repo/'docs/PLAN.md').write_text(f'**Current session: S{int(sid[1:])+1:02}, pending**\\n')
    # Controller creates implementation checkpoint outside the Codex sandbox.
if cfg.get('blocked'): status='blocked'
if role=='review' and cfg.get('reject',0):
    status='changes_requested';cfg['reject']-=1;cfgpath.write_text(json.dumps(cfg))
if role=='review' and git('status','--porcelain'): status='changes_requested'
if role=='review' and cfg.get('review_edit'): (repo/'bad.txt').write_text('reviewer mutation')
value=dict(session=sid,status=status,commit=git('rev-parse','HEAD'),summary='fixture '+status,
           checks=['fixture check'],blockers=['missing owner facts'] if status=='blocked' else [])
if cfg.get('wrong_commit'): value['commit']='0'*40
report.write_text('invalid' if cfg.get('malformed') else json.dumps(value))
print(json.dumps(dict(type='thread.started',thread_id=str(uuid.uuid4()))))
'''


def write_json(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def runroot(tmp_path, monkeypatch):
    monkeypatch.setenv('GIT_AUTHOR_NAME', 'Runner Test')
    monkeypatch.setenv('GIT_AUTHOR_EMAIL', 'runner@example.invalid')
    monkeypatch.setenv('GIT_COMMITTER_NAME', 'Runner Test')
    monkeypatch.setenv('GIT_COMMITTER_EMAIL', 'runner@example.invalid')
    repo = tmp_path / 'repo'; repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'docs').mkdir()
    rows = '\n'.join(f'| S{i:02} / 1 — fixture | inputs | work | checks |' for i in range(1,22))
    (repo / r.REVIEW_DOC).write_text(rows+'\n')
    (repo / 'docs/PLAN.md').write_text('**Current session: S03, pending**\n')
    (repo / 'AGENTS.md').write_text('Local disposable fixture only.\n')
    (repo / 'Makefile').write_text('check:\n\t@test ! -f fail-check\n')
    r.git(repo, 'add', '.'); r.git(repo, 'commit', '-qm', 'baseline')
    fake = tmp_path / 'codex'; fake.write_text(FAKE); fake.chmod(0o700)
    root = tmp_path / 'state'
    def init(start=3, through=4, repairs=2, launches=20):
        if start != 3:
            (repo/'docs/PLAN.md').write_text(f'**Current session: S{start:02}, pending**\n')
            r.git(repo,'add','.');r.git(repo,'commit','-qm','fixture routing')
        assert r.main(['init','--repo',str(repo),'--state-dir',str(root),'--codex',str(fake),
                       '--start',str(start),'--through',str(through),'--max-repairs',str(repairs),
                       '--max-launches',str(launches)]) == 0
        return root
    return root, repo, init


def command(root, name='run', *args):
    return r.main([name, '--state-dir',str(root), *args])


def state(root):
    return r.read(root/'state.json')


def test_two_sessions_fresh_review_failure_repair_and_recheck(runroot):
    root, repo, init = runroot; init()
    write_json(root/'scenario.json', dict(reject=1))
    assert command(root) == 0
    value = state(root)
    assert value['status'] == 'complete'
    assert [x['session'] for x in value['completed']] == ['S03','S04']
    assert [x['kind'] for x in value['attempts']] == ['implement','checks','review','repair','checks','review',
                                                   'implement','checks','review']
    events = [json.loads((Path(a['path'])/'events.jsonl').read_text())['thread_id']
              for a in value['attempts'] if a['kind'] != 'checks']
    assert len(set(events)) == 6
    assert r.head(repo) != r.head(Path(value['workspace']))
    assert not r.git(repo, 'status', '--porcelain')
    assert (root/'state.json').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('problem',['malformed','wrong_commit','review_edit'])
def test_untrusted_report_or_reviewer_edit_never_advances(runroot, problem):
    root, _, init = runroot; init(through=3)
    write_json(root/'scenario.json', {problem:True})
    assert command(root) == 2
    assert state(root)['completed'] == []
    assert state(root)['status'] == 'interrupted'


def test_review_rejection_budget_stops_before_next_session(runroot):
    root, _, init = runroot; init(repairs=0)
    write_json(root/'scenario.json', dict(reject=10))
    assert command(root) == 2
    assert state(root)['session'] == 'S03'
    assert 'Repair budget exhausted' in state(root)['reason']
    assert not state(root)['completed']


def test_external_blocker_not_automatically_repaired(runroot):
    root, _, init = runroot; init()
    write_json(root/'scenario.json', dict(blocked=True))
    assert command(root) == 2
    assert state(root)['repairs'] == 0
    assert len(state(root)['attempts']) == 1
    assert command(root) == 2  # no blind retry


def test_checks_failure_has_bounded_repairs_and_retains_logs(runroot):
    root, _, init = runroot; init(through=3, repairs=1)
    repo = Path(state(root)['workspace'])
    (repo/'fail-check').write_text('failure')
    r.git(repo,'add','.');r.git(repo,'commit','-qm','failing fixture')
    value=state(root);value['expected_head']=r.head(repo);r.save(root/'state.json',value)
    assert command(root) == 2
    assert 'Repair budget exhausted' in state(root)['reason']
    failed = [a for a in state(root)['attempts'] if a['kind']=='checks']
    assert len(failed)==2
    assert all((Path(a['path'])/'stderr.log').exists() for a in failed)


def test_dirty_interruption_inspected_fresh_then_repaired_without_reset(runroot):
    root, _, init = runroot; init(through=3)
    write_json(root/'scenario.json', dict(dirty_interrupt=True))
    assert command(root) == 2
    assert state(root)['inflight']['finished'] is False
    assert command(root) == 2
    write_json(root/'scenario.json', {})
    assert command(root,'recover') == 0
    assert state(root)['phase'] == 'repair'
    assert (Path(state(root)['workspace'])/'unfinished.txt').read_text() == 'retained edit'
    # The repair preserves and commits the unfinished evidence.
    assert command(root) == 0
    assert state(root)['status']=='complete'
    assert [a['kind'] for a in state(root)['attempts']] == ['implement','review','repair','checks','review']


def test_external_gate_never_launches_a_child_and_receipt_requires_review(runroot):
    root, _, init = runroot; init(start=12,through=12)
    assert command(root) == 2
    assert state(root)['status']=='awaiting_external'
    assert state(root)['attempts']==[]
    repo=Path(state(root)['workspace'])
    review=repo/r.REVIEW_DOC
    review.write_text(review.read_text()+'\n| S12 | Complete | fixture |\n## S12 handoff — fixture\n')
    (repo/'docs/PLAN.md').write_text('**Current session: S13, pending**\n')
    r.git(repo,'add','.');r.git(repo,'commit','-qm','external fixture receipt')
    receipt=root/'external.json'
    write_json(receipt,dict(session='S12',commit=r.head(repo),authority='fixture approved exact bytes',evidence='fixture receipts'))
    assert command(root,'record-external','--receipt',str(receipt))==0
    assert command(root)==0
    assert [a['kind'] for a in state(root)['attempts']]==['checks','review']
    assert state(root)['completed'][0]['external']['authority']=='fixture approved exact bytes'


def test_wrong_receipt_cannot_skip_gate(runroot):
    root, _, init=runroot;init(start=12,through=12)
    receipt=root/'bad.json';write_json(receipt,dict(session='S13',commit='wrong'))
    assert command(root,'record-external','--receipt',str(receipt))==2
    assert state(root)['session']=='S12'


def test_schedule_and_manifest_tampering_rejected(runroot):
    root, _, init=runroot;init()
    manifest=r.read(root/'manifest.json');manifest['S12']['mode']='local'
    write_json(root/'manifest.json',manifest)
    assert command(root)==2
    assert state(root)['attempts']==[]


def test_moved_head_requires_recovery(runroot):
    root, _, init=runroot;init()
    repo=Path(state(root)['workspace'])
    (repo/'unrelated').write_text('inspect this')
    r.git(repo,'add','.');r.git(repo,'commit','-qm','unexpected')
    assert command(root)==2
    assert state(root)['attempts']==[]


def test_launch_budget_survives_restarts(runroot):
    root, _, init=runroot;init(launches=1)
    assert command(root)==2
    assert state(root)['launches']==1
    assert command(root,'recover')==2
    assert state(root)['completed']==[]


def test_killed_controller_cannot_overlap_live_child_then_recovers(runroot):
    root, _, init=runroot;init(through=3)
    write_json(root/'scenario.json',dict(wait=True))
    process=subprocess.Popen([sys.executable,str(root/'controller.py'),'run','--state-dir',str(root)],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+10
        while not (root/'child-started').exists():
            assert process.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.02)
        process.kill();process.wait(timeout=5)
        assert command(root)==2  # inherited flock held by still-live child
        assert state(root)['inflight']
    finally:
        (root/'release-child').touch()
        if process.poll() is None: process.kill();process.wait(timeout=5)
    deadline=time.monotonic()+10
    while True:
        try:
            with r.locked(root): pass
            break
        except r.Stop:
            assert time.monotonic()<deadline
            time.sleep(.02)
    assert command(root)==2  # durable unfinished intent prevents replay
    assert command(root,'recover')==0
    assert command(root)==0
    assert [a['kind'] for a in state(root)['attempts']].count('implement')==1


def test_actual_schedule_has_all_sessions_and_gate_modes():
    repo=MODULE.parents[2]
    assert len(r.schedule(repo))==21
    manifest=r.read(MODULE.parent/'sessions.json')
    assert {s for s,v in manifest.items() if v['mode']=='external'} == {'S12','S13','S15','S16','S17','S19','S21'}


def test_external_failed_checks_never_start_writable_repair(runroot):
    root, _, init=runroot;init(start=12,through=12)
    repo=Path(state(root)['workspace'])
    (repo/'fail-check').write_text('external failure')
    r.git(repo,'add','.');r.git(repo,'commit','-qm','external failure receipt')
    receipt=root/'receipt.json'
    write_json(receipt,dict(session='S12',commit=r.head(repo),authority='fixture',evidence='fixture'))
    assert command(root,'record-external','--receipt',str(receipt))==0
    assert command(root)==2
    assert [a['kind'] for a in state(root)['attempts']]==['checks']
    assert state(root)['repairs']==0
    write_json(root/'scenario.json', dict(reject=1))
    assert command(root,'recover')==2  # rejected external evidence never authorizes repair
    assert all(a['kind']!='repair' for a in state(root)['attempts'])


def test_escaping_common_group_descendant_blocks_progress(tmp_path):
    directory=tmp_path/'attempt';directory.mkdir()
    pidfile=tmp_path/'grandchild'
    script=('import subprocess,sys; '
            'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"], '
            'stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True); '
            f'open({str(pidfile)!r},"w").write(str(p.pid))')
    try:
        with r.locked(tmp_path) as fd:
            with pytest.raises(r.Stop,match='process group'):
                r.execute([sys.executable,'-c',script],tmp_path,directory,5,fd)
        assert pidfile.exists()
        process=r.read(directory/'process.json')
        assert r.group_alive(process['pid'])
    finally:
        if pidfile.exists():
            try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError: pass


def test_runtime_schedule_or_protected_file_mutation_rejected(runroot):
    root, _, init=runroot;init()
    repo=Path(state(root)['workspace'])
    (repo/'AGENTS.md').write_text('weakened')
    r.git(repo,'add','.');r.git(repo,'commit','-qm','forbidden contract edit')
    with pytest.raises(r.Stop,match='protected'):
        r.Runner(root).guard()


def test_embedded_entrypoint_restores_callers_umask(runroot):
    root, _, init=runroot
    previous=os.umask(0o022)
    try:
        init()
        current=os.umask(0o022)
        assert current==0o022
    finally:
        os.umask(previous)


def test_child_bootstrap_preserves_test_process_umask(tmp_path):
    directory=tmp_path/'attempt';directory.mkdir()
    previous=os.umask(0o022)
    try:
        with r.locked(tmp_path) as fd:
            r.execute([sys.executable,'-c','import os; print(oct(os.umask(0o022)))'],
                      tmp_path,directory,5,fd)
        assert (directory/'events.jsonl').read_text().strip()=='0o22'
    finally:
        os.umask(previous)
