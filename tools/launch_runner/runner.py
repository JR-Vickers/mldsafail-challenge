#!/usr/bin/env python3
"""Sequential fresh-context Codex controller. Standard library, local preparation only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
REVIEW_DOC = 'docs/LAUNCH_ARCHITECTURE_REVIEW.md'
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'session': {'type': 'string'},
        'status': {'type': 'string', 'enum': ['complete', 'changes_requested', 'blocked']},
        'commit': {'type': 'string'}, 'summary': {'type': 'string'},
        'checks': {'type': 'array', 'items': {'type': 'string'}},
        'blockers': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['session', 'status', 'commit', 'summary', 'checks', 'blockers'],
}


class Stop(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    """Publish durable state before effects; retain previous run artifacts separately."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def head(repo):
    return git(repo, 'rev-parse', 'HEAD')


def tree_digest(repo):
    material = subprocess.check_output(['git', '-C', str(repo), 'diff', '--binary', 'HEAD'])
    material += git(repo, 'status', '--porcelain', '--untracked-files=all').encode()
    names = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '--others', '--exclude-standard', '-z'])
    for name in names.split(b'\0'):
        if not name:
            continue
        path = repo / os.fsdecode(name)
        material += name + str(path.lstat().st_mode).encode()
        material += os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
    return digest(material)


def clean(repo):
    if git(repo, 'status', '--porcelain', '--untracked-files=all'):
        raise Stop('Working tree is dirty; preserve and inspect it before continuing.')


@contextmanager
def locked(root):
    fd = os.open(root / 'lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop('Another runner or child still holds this run lock.') from None
        yield fd
    finally:
        os.close(fd)


def schedule(repo):
    rows = {}
    for line in (repo / REVIEW_DOC).read_text().splitlines():
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) == 4 and re.match(r'S\d\d / [1-6] — ', cells[0]):
            sid = cells[0][:3]
            if sid in rows:
                raise Stop('Duplicate session row: ' + sid)
            rows[sid] = dict(title=cells[0], read_first=cells[1], assignment=cells[2], exit=cells[3])
    if set(rows) != {f'S{i:02}' for i in range(1, 22)}:
        raise Stop('Expected exactly S01–S21 in the architecture schedule.')
    return rows


def anchors(path):
    import unicodedata
    seen = {}; result = set()
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', path.read_text(), re.M):
        title = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', title).replace('`', '').lower()
        slug = ''.join(c for c in title if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ', '-')
        count = seen.get(slug, 0); seen[slug] = count + 1
        result.add(slug + (f'-{count}' if count else ''))
    return result


def document_checks(repo, base):
    """Check changed Markdown's local destinations and heading anchors."""
    files = git(repo, 'diff', '--name-only', base, 'HEAD').splitlines()
    for name in files:
        path = repo / name
        if path.suffix != '.md' or not path.is_file():
            continue
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', link):
                continue
            target, _, fragment = link.partition('#')
            dest = path.parent / target if target else path
            if not dest.exists() or fragment and fragment not in anchors(dest):
                raise Stop(f'Broken local document link: {name}: {link}')


def routing(repo, sid):
    plan = (repo / 'docs/PLAN.md').read_text()
    review = (repo / REVIEW_DOC).read_text()
    if not re.search(rf'^\| {sid} \| Complete\b', review, re.M | re.I):
        raise Stop(f'{sid} has no complete ledger row.')
    if not re.search(rf'^## {sid} handoff\b', review, re.M):
        raise Stop(f'{sid} has no durable handoff.')
    nxt = f'S{int(sid[1:])+1:02}'
    if int(sid[1:]) < 21 and f'**Current session: {nxt},' not in plan:
        raise Stop('PLAN routing must select ' + nxt)


def report(path, sid, commit):
    value = read(path)
    if (type(value) is not dict or set(value) != set(SCHEMA['required']) or
            value['session'] != sid or value['commit'] != commit or
            value['status'] not in SCHEMA['properties']['status']['enum'] or
            not isinstance(value['summary'], str) or not value['summary'] or
            any(type(value[key]) is not list or any(type(x) is not str for x in value[key])
                for key in ('checks', 'blockers'))):
        raise Stop('Missing, malformed, or wrong-commit agent report.')
    if value['status'] == 'complete' and (value['blockers'] or not value['checks']):
        raise Stop('Complete report must include checks and no blockers.')
    return value


def group_alive(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def execute(argv, repo, directory, timeout, lock_fd, *, stdin=None):
    """Own one process group, inherit the run lock, terminate it on ordinary interruption."""
    with (directory / 'events.jsonl').open('xb') as out, (directory / 'stderr.log').open('xb') as err:
        bootstrap = [sys.executable, str(Path(__file__).resolve()), '_exec-child',
                     str(directory / 'process.json'), *argv]
        process = subprocess.Popen(bootstrap, cwd=repo, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=out, stderr=err, start_new_session=True, pass_fds=(lock_fd,))
        try:
            process.communicate(stdin.encode() if stdin is not None else None, timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                pass
            # A reaped parent does not prove its descendants terminated.
            if group_alive(process.pid):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        if group_alive(process.pid):
            raise Stop(f'Child process group {process.pid} still exists; inspect before recovery.')
        if process.returncode:
            raise Stop(f'Child exited {process.returncode}; inspect {directory}.')


class Runner:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.s = read(self.root / 'state.json')
        self.repo = Path(self.s['workspace'])
        self.manifest = read(self.root / 'manifest.json')
        if self.s['version'] != 1 or self.s['manifest_sha256'] != digest((self.root / 'manifest.json').read_bytes()):
            raise Stop('Unknown or changed run manifest.')
        if self.s['runner_sha256'] != digest(Path(__file__).read_bytes()):
            raise Stop('Controller changed; use the pinned controller copy for this run.')
        if git(self.repo, 'branch', '--show-current') != self.s['branch']:
            raise Stop('Workspace branch changed.')
        if schedule(self.repo) != self.s['schedule']:
            raise Stop('Session assignments changed; inspect and start a newly reviewed run.')

    def guard(self):
        if schedule(self.repo) != self.s['schedule']:
            raise Stop('Session assignments changed during agent work.')
        if git(self.repo, 'branch', '--show-current') != self.s['branch']:
            raise Stop('Workspace branch changed during agent work.')
        subprocess.run(['git', '-C', str(self.repo), 'merge-base', '--is-ancestor',
                        self.s['baseline'], 'HEAD'], check=True)
        changed = git(self.repo, 'diff', '--name-only', self.s['baseline']).splitlines()
        changed += git(self.repo, 'ls-files', '--others', '--exclude-standard').splitlines()
        forbidden = ('AGENTS.md', 'tools/launch_runner/', 'docs/PRIMITIVE_SELECTION_SPEC.md',
                     'src/mldsafail/benchmark_v050/', 'src/mldsafail/benchmark/',
                     'src/mldsafail/trusted/', 'config/', 'uv.lock', 'Dockerfile.worker',
                     'deploy/worker-linux-amd64.requirements.txt', 'pyproject.toml')
        if any(name == item or item.endswith('/') and name.startswith(item)
               for name in changed for item in forbidden):
            raise Stop('Agent changed protected contract/controller/frozen benchmark files.')

    def no_live_children(self):
        for attempt in self.s['attempts']:
            process_file = Path(attempt['path']) / 'process.json'
            if not attempt['finished'] and process_file.exists():
                if group_alive(read(process_file)['pid']):
                    raise Stop('An interrupted child process group still exists; inspect it first.')

    def write(self):
        save(self.root / 'state.json', self.s)

    def stop(self, reason, *, kind='blocked'):
        self.s.update(status=kind, reason=reason)
        self.write()
        raise Stop(reason)

    def start_attempt(self, kind, fd):
        number = len(self.s['attempts']) + 1
        directory = self.root / f'attempt-{number:04}'
        directory.mkdir(mode=0o700)
        attempt = dict(kind=kind, session=self.s['session'], start=head(self.repo), path=str(directory),
                       finished=False)
        self.s['attempts'].append(attempt)
        self.s['inflight'] = attempt
        attempt['tree'] = tree_digest(self.repo)
        self.write()  # Never replay an ambiguous child invocation.
        return directory, attempt

    def agent(self, kind, fd):
        directory, attempt = self.start_attempt(kind, fd)
        sid = self.s['session']
        role = ('Review independently; do not edit files or commits. Inspect actual code, diff, tests and handoff. '
                'Reject omissions and unsupported pass claims.' if kind == 'review' else
                'Implement only this session, or repair the findings below. Run focused tests plus make check. '
                'Update PLAN routing and the architecture ledger/handoff together. Do not stage or commit: '
                'the external controller creates the local checkpoint after your report. '
                'If blocked, preserve the evidence and record the blocker; never mark the session complete.')
        prompt = f'''You are a new fresh-context agent for {sid}, role {kind}.
Read AGENTS.md, docs/PLAN.md, {REVIEW_DOC}, its S02 contract and latest handoffs.
The controller assignment below selects your ONE session even if draft routing advanced.
{role}
Assignment: {json.dumps(self.s['schedule'][sid])}
Baseline commit: {self.s['baseline']}; current commit: {head(self.repo)}.
Prior findings: {json.dumps(self.s.get('feedback', {}))}
Authority: local engineering/tests/documentation/commits and disposable fixtures only.
No SSH mutations, deployment, native VPS tests, private/production evaluations, epochs,
notifications, invitations, publication, cleanup of retained artifacts, or pushes.
Do not change frozen science, scoring, worker locks, AGENTS.md, session assignments,
tools/launch_runner, the controller state, or unrelated files. Do not spawn agents.
Work alone; do not launch the next session. Do not detach or daemonize background processes. Preserve failed evidence. Use the local
uv environment (uv sync --extra dev if needed, then source .venv/bin/activate).
Review must inspect the whole baseline-to-current change, including repair commits.
For external completion, inspect the supplied exact authority and retained receipts;
never run the live operation or infer a pass from a summary. Missing evidence is blocked.
Return the required JSON, binding session and full current HEAD, with actual checks.
The controller owns staging/committing; leave implementation edits for its checkpoint.
Use plain Sxx identifiers in ledger rows (three columns) and preserve schedule rows exactly.
External completion: {json.dumps(self.s.get('external', None))}
'''
        (directory / 'prompt.txt').write_text(prompt)
        argv = [self.s['codex'], 'exec', '-c', 'approval_policy="never"', '--sandbox', 'read-only' if kind == 'review' else 'workspace-write',
                '--json', '--output-schema', str(self.root / 'report-schema.json'),
                '-o', str(directory / 'report.json'), '-C', str(self.repo), '-']
        execute(argv, self.repo, directory, self.s['timeout'], fd, stdin=prompt)
        result = report(directory / 'report.json', sid, head(self.repo))
        self.guard()
        if kind == 'review' and head(self.repo) != attempt['start']:
            raise Stop('Reviewer changed the commit.')
        if kind == 'review':
            if tree_digest(self.repo) != attempt['tree']:
                raise Stop('Reviewer changed the working tree.')
        attempt.update(finished=True, commit=head(self.repo), report=result)
        self.s['inflight'] = None
        self.write()
        return result

    def checks(self, fd):
        directory, attempt = self.start_attempt('checks', fd)
        execute(['make', 'check'], self.repo, directory, self.s['check_timeout'], fd)
        subprocess.run(['git', '-C', str(self.repo), 'diff', '--check', self.s['baseline'], 'HEAD'], check=True)
        document_checks(self.repo, self.s['baseline'])
        routing(self.repo, self.s['session'])
        clean(self.repo)
        self.guard()
        if head(self.repo) != attempt['start']:
            raise Stop('HEAD changed during checks.')
        attempt.update(finished=True, commit=head(self.repo))
        self.s['inflight'] = None
        self.write()

    def run(self, fd):
        self.no_live_children()
        if self.s['inflight']:
            self.stop('Interrupted child intent retained; use recover for fresh inspection. No automatic replay.', kind='interrupted')
        if self.s['status'] not in ('ready', 'running'):
            raise Stop('Run is stopped: ' + self.s.get('reason', '') + ' (use recover after resolving it)')
        if not (self.s['phase'] == 'repair' and self.s.get('recovery_tree') == tree_digest(self.repo)):
            clean(self.repo)
        if head(self.repo) != self.s['expected_head']:
            self.stop('HEAD moved outside the controller; inspect before recover.')
        while self.s['session']:
            self.no_live_children()
            sid = self.s['session']; spec = self.manifest[sid]
            if spec['mode'] == 'external' and not self.s.get('external'):
                self.stop(f'{sid} requires its separately authorized external procedure. Supply retained completion evidence with record-external.', kind='awaiting_external')
            if self.s['launches'] >= self.s['max_launches']:
                self.stop('Run launch budget exhausted.')
            self.s['status'] = 'running'; self.write()
            try:
                phase = self.s['phase']
                if phase in ('implement', 'repair'):
                    self.s['launches'] += 1; self.write()
                    result = self.agent(phase, fd)
                    self.s['expected_head'] = head(self.repo)
                    if result['status'] == 'blocked':
                        self.s['feedback'] = result
                        self.stop(result['summary'])
                    if result['status'] != 'complete':
                        self.fail(result); continue
                    self.guard()
                    if git(self.repo, 'status', '--porcelain', '--untracked-files=all'):
                        subprocess.run(['git', '-C', str(self.repo), 'add', '--all'], check=True)
                        subprocess.run(['git', '-C', str(self.repo), 'commit', '-m',
                                        f'{sid}: {result["summary"][:160]}'], check=True)
                    if head(self.repo) == self.s['baseline']:
                        self.stop('Session reported complete without checkpoint changes.')
                    clean(self.repo)
                    self.s['expected_head'] = head(self.repo)
                    self.s['phase'] = 'checks'; self.write()
                elif phase == 'checks':
                    try:
                        self.checks(fd)
                    except (Stop, subprocess.CalledProcessError) as exc:
                        # A completed check failure is safe to repair; never replay an agent.
                        self.s['inflight'] = None
                        if self.s.get('external'):
                            self.stop('External completion checks failed; no writable repair: ' + str(exc))
                        self.fail(dict(summary=str(exc), checks=['Controller checks failed']))
                        continue
                    self.s['phase'] = 'review'; self.write()
                elif phase == 'review':
                    self.s['launches'] += 1; self.write()
                    result = self.agent('review', fd)
                    if result['status'] == 'complete':
                        self.advance(result)
                    elif result['status'] == 'blocked':
                        self.s['feedback'] = result; self.stop(result['summary'])
                    else:
                        if self.s.get('external'):
                            self.s['feedback'] = result; self.stop('External receipt review rejected: ' + result['summary'])
                        self.fail(result)
                else:
                    self.stop('Unknown phase; inspect state.')
            except (OSError, ValueError, subprocess.SubprocessError, Stop) as exc:
                if self.s['status'] == 'running':
                    self.s.update(status='interrupted' if self.s['inflight'] else 'blocked', reason=str(exc))
                    self.write()
                raise Stop(str(exc)) from exc
        self.s.update(status='complete', reason='All selected sessions independently accepted.'); self.write()

    def fail(self, findings):
        self.s['feedback'] = findings
        self.s['expected_head'] = head(self.repo)
        if self.s['repairs'] >= self.s['max_repairs']:
            self.stop('Repair budget exhausted: ' + findings['summary'])
        self.s['repairs'] += 1
        self.s['phase'] = 'repair'; self.write()

    def advance(self, result):
        self.guard()
        sid = self.s['session']
        self.s['completed'].append(dict(session=sid, baseline=self.s['baseline'], commit=head(self.repo),
                                        review=result, external=self.s.get('external')))
        next_number = int(sid[1:]) + 1
        self.s.update(session=f'S{next_number:02}' if next_number <= self.s['through'] else None,
                      baseline=head(self.repo), expected_head=head(self.repo), phase='implement', repairs=0,
                      feedback={}, external=None)
        self.write()

    def recover(self, fd):
        """Read-only fresh inspection after interruption; never repeats computation."""
        if self.s['status'] == 'complete':
            raise Stop('Run already complete.')
        self.no_live_children()
        previous = self.s.get('inflight')
        if previous:
            self.s['feedback'] = dict(summary='Inspect interrupted invocation; do not replay it.', attempt=previous)
        if previous:
            save(self.root / f'recovery-{len(self.s["attempts"]):04}.json',
                 dict(interrupted=previous, head=head(self.repo), tree=tree_digest(self.repo),
                      status=git(self.repo, 'status', '--porcelain', '--untracked-files=all')))
        self.s['inflight'] = None
        if self.s['launches'] >= self.s['max_launches']:
            raise Stop('Run launch budget exhausted; start a newly scoped run.')
        if self.manifest[self.s['session']]['mode'] == 'external' and not self.s.get('external'):
            raise Stop('External gate needs an evidence record, never a writable repair.')
        self.s['launches'] += 1; self.write()
        result = self.agent('review', fd)
        self.s['expected_head'] = head(self.repo)
        self.s['feedback'] = result
        self.s['recovery_tree'] = tree_digest(self.repo)
        if result['status'] == 'complete' and git(self.repo, 'status', '--porcelain', '--untracked-files=all'):
            result = {**result, 'status': 'changes_requested',
                      'summary': 'Preserved interrupted edits need a controller checkpoint after local repair.'}
            self.s['feedback'] = result
        if result['status'] == 'blocked':
            self.stop(result['summary'])
        if result['status'] == 'complete':
            self.s['phase'] = 'checks'  # Recheck actual checkpoint, then another independent review.
        elif self.s.get('external'):
            self.stop('External completion needs corrected authority/evidence; do not repair by executing it.')
        else:
            self.fail(result)
        self.s.update(status='ready', reason='Recovery inspection recorded; run to continue.'); self.write()


def initialize(args):
    repo = Path(args.repo).resolve(); clean(repo)
    root = Path(args.state_dir).expanduser().resolve()
    if root.is_relative_to(repo) or repo.is_relative_to(root):
        raise Stop('State directory must be outside the source checkout.')
    if root.exists():
        raise Stop('State directory already exists; use status/run/recover.')
    if not args.branch.startswith('engineering/'):
        raise Stop('Use a dedicated engineering/ branch.')
    if not (3 <= args.start <= args.through <= 21):
        raise Stop('Select an ordered range within S03–S21.')
    if f'**Current session: S{args.start:02},' not in (repo / 'docs/PLAN.md').read_text():
        raise Stop('Start session must match the current PLAN routing; no skipped rows.')
    rows = schedule(repo)
    manifest = read(HERE / 'sessions.json')
    root.mkdir(mode=0o700, parents=True)
    # Freeze the controller/manifest outside the editable worker checkout.
    (root / 'controller.py').write_bytes(Path(__file__).read_bytes())
    save(root / 'manifest.json', manifest); save(root / 'report-schema.json', SCHEMA)
    workspace = root / 'workspace'
    subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-b', args.branch, str(workspace), 'HEAD'], check=True)
    state = dict(version=1, workspace=str(workspace), branch=args.branch, source=str(repo),
                 runner_sha256=digest((root / 'controller.py').read_bytes()),
                 manifest_sha256=digest((root / 'manifest.json').read_bytes()), schedule=rows,
                 baseline=head(workspace), expected_head=head(workspace), session=f'S{args.start:02}',
                 through=args.through, status='ready', reason='', phase='implement', repairs=0,
                 launches=0, max_launches=args.max_launches, max_repairs=args.max_repairs,
                 timeout=args.timeout, check_timeout=args.check_timeout, codex=args.codex,
                 completed=[], attempts=[], inflight=None, external=None, feedback={})
    save(root / 'state.json', state)
    print(f'Initialized {workspace}; use {sys.executable} {root / "controller.py"} run --state-dir {root}')


def dispatch(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--repo', default='.')
    init.add_argument('--state-dir', required=True)
    init.add_argument('--branch', default='engineering/launch-sessions')
    init.add_argument('--start', type=int, default=3)
    init.add_argument('--through', type=int, default=19)
    init.add_argument('--max-repairs', type=int, default=2)
    init.add_argument('--max-launches', type=int, default=80)
    init.add_argument('--timeout', type=int, default=3600)
    init.add_argument('--check-timeout', type=int, default=1800)
    init.add_argument('--codex', default='codex')
    for command in ('run', 'status', 'recover', 'record-external'):
        item = sub.add_parser(command); item.add_argument('--state-dir', required=True)
        if command == 'record-external':
            item.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            if min(args.timeout, args.check_timeout, args.max_launches) < 1 or args.max_repairs < 0:
                raise Stop('Budgets must be positive (repairs may be zero).')
            initialize(args); return 0
        root = Path(args.state_dir).expanduser().resolve()
        with locked(root) as fd:
            runner = Runner(root)
            if args.command == 'status':
                print(json.dumps(runner.s, indent=2))
            elif args.command == 'record-external':
                sid = runner.s['session']
                if runner.manifest[sid]['mode'] != 'external' or runner.s['inflight']:
                    raise Stop('Not at a reconciled external gate.')
                clean(runner.repo)
                receipt = read(args.receipt)
                if (receipt.get('session') != sid or receipt.get('commit') != head(runner.repo) or
                        not receipt.get('authority') or not receipt.get('evidence')):
                    raise Stop('Receipt needs session, full commit, exact authority and evidence references.')
                # Importing a record grants no execution. A fresh agent reviews evidence before advance.
                runner.s.update(external=receipt, expected_head=head(runner.repo), phase='checks', status='ready', reason='')
                runner.write()
            elif args.command == 'recover':
                runner.recover(fd)
            else:
                runner.run(fd)
        return 0
    except (Stop, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr); return 2
    except KeyboardInterrupt:
        print('Interrupted; retained intent requires recover.', file=sys.stderr); return 130


def main(argv=None):
    return dispatch(argv)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '_exec-child':
        # Record our own process birth before any agent/check can spawn descendants.
        # The inherited lock bridges Popen -> registration, even if the parent dies.
        previous_umask = os.umask(0o077)
        try:
            save(Path(sys.argv[2]), dict(pid=os.getpid(), argv=sys.argv[3:], started_at=time.time()))
        finally:
            os.umask(previous_umask)
        os.execvp(sys.argv[3], sys.argv[3:])
    raise SystemExit(main())
