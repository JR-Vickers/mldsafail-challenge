#!/usr/bin/env python3
"""Opt-in real Codex smoke; creates only a new disposable toy Git repository."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    base = args.directory.expanduser().resolve()
    base.mkdir(mode=0o700, parents=True, exist_ok=False)
    repo = base / 'source'; repo.mkdir(); (repo / 'docs').mkdir()
    (repo / 'AGENTS.md').write_text(
        'Isolated toy fixture: local edits/tests only. Never access other projects, SSH, '
        'services or credentials. Do not spawn agents, push or detach processes. '
        'Leave edits for the controller checkpoint.\n')
    (repo / 'docs/PLAN.md').write_text('**Current session: S03, pending**\n')
    assignment = ('Create smoke.txt containing runner-smoke. Add a three-column ledger row '
                  'with plain S03 and Complete status, plus an S03 handoff below; '
                  'route PLAN to S04. Leave edits for controller checkpoint.')
    rows = [f'| S{i:02} / 1 — toy | AGENTS.md | '
            f'{assignment if i == 3 else "No work in smoke test."} | make check and git diff --check |'
            for i in range(1, 22)]
    (repo / 'docs/LAUNCH_ARCHITECTURE_REVIEW.md').write_text(
        '# Disposable schedule\nS02 contract: toy local implementation and review only.\n'
        + '\n'.join(rows) + '\n')
    (repo / 'Makefile').write_text('check:\n\t@test "$$(cat smoke.txt)" = runner-smoke\n')
    def git(*argv):
        subprocess.run(['git', '-C', str(repo), *argv], check=True)
    git('init', '-q')
    git('config', 'user.name', 'Runner Smoke')
    git('config', 'user.email', 'runner@example.invalid')
    git('add', '.'); git('commit', '-qm', 'toy smoke baseline')
    state = base / 'state'
    subprocess.run([sys.executable, str(Path(__file__).with_name('runner.py')), 'init',
                    '--repo', str(repo), '--state-dir', str(state), '--through', '3',
                    '--timeout', '300', '--max-repairs', '1', '--max-launches', '5'], check=True)
    result = subprocess.run([sys.executable, str(state / 'controller.py'), 'run', '--state-dir', str(state)])
    value = json.loads((state / 'state.json').read_text())
    print(json.dumps(dict(status=value['status'], launches=value['launches'],
                          completed=value['completed'], state_directory=str(state)), indent=2))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
