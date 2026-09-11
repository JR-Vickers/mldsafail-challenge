"""Explicit 0.5.0 local workflow, independent of historical commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys

from . import evidence as ev
from .execution import environment, invoke, solver_snapshot
from .generator import generate_mlwe
from .scoring import case_cost, eligibility, ranked_groups


def evaluate(output, grid, env, solver, epoch_manifest=None, solver_dir=None):
    output = ev.directory(output)
    files = solver_snapshot(solver_dir, output / 'solver') if solver_dir else None
    m = ev.manifest('run', env, grid, solver=solver, solver_files=files,
                    epoch_manifest_sha256=ev.sha(epoch_manifest) if epoch_manifest else None)
    ev.write(output / 'manifest.json', m)
    ev.directory(output / 'records')
    rows = []
    for index, case in enumerate(grid):
        instance = generate_mlwe(case['profile'], case['seed'], case['eta']).public
        outputs = []
        for repetition in range(4):
            result = invoke(instance, solver, env['image_id'], output / 'solver' if solver_dir else None)
            ev.write(output / 'records' / f'{index:03d}-{repetition}.json',
                     {'run_id': m['id'], 'case_index': index, 'repetition': repetition, 'result': result})
            outputs.append(result)
        rows.append(ev.aggregate(case, solver, outputs))
        print(f"{solver}: {index + 1}/{len(grid)} {case['profile']}/eta{case['eta']} {rows[-1]['status']}", file=sys.stderr, flush=True)
    ev.write(output / 'aggregates.json', rows)
    ev.write(output / 'summary.json', ev.summary(m, rows))
    ev.audit_run(output, check_complete=False)
    ev.seal(output)
    return m, rows


def create_epoch(output):
    output = ev.directory(output)
    nonce = secrets.token_hex(32)
    ev.write(output / 'secret.json', {'nonce': nonce, 'benchmark_version': '0.5.0'})
    env = environment()
    m = ev.manifest('epoch', env, ev.cases(nonce))
    ev.write(output / 'manifest.json', m)
    rows = []
    for solver in ('primal-lll', 'exhaustive', 'direct-linear'):
        _, values = evaluate(output / solver, m['cases'], env, solver, m)
        rows.extend(values)
    gates = eligibility(rows)
    ev.write(output / 'gates.json', gates)
    reference = [r for r in rows if r['solver'] == 'primal-lll']
    ev.write(output / 'reference-costs.json', {r['instance_id']: case_cost(r) for r in reference})
    if not gates['numeric_eligibility']:
        ev.write(output / 'FAILED.json', {'reason': 'frozen reference viability gate failed', 'gates': gates})
        raise ValueError('epoch viability failed; evidence retained; seeds must not be replaced automatically')
    ev.seal(output)
    ev.audit_epoch(output)
    return {'benchmark_version': '0.5.0', 'epoch_id': m['id'], 'ready': True, 'ranked_cases': 100,
            'reference_self_score': 1.0}


def main():
    parser = argparse.ArgumentParser(prog='mldsafail-mlwe')
    sub = parser.add_subparsers(dest='command', required=True)
    smoke = sub.add_parser('smoke'); smoke.add_argument('--output', type=Path, required=True)
    epoch = sub.add_parser('epoch').add_subparsers(dest='epoch_command', required=True)
    create = epoch.add_parser('create'); create.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--epoch', type=Path, required=True)
    run.add_argument('--solver-dir', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    for name in ('audit', 'rank'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--epoch', type=Path, required=True)
        cmd.add_argument('--run', type=Path, action='append', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'smoke':
            m, rows = evaluate(args.output, ev.cases(smoke=True), environment(), 'primal-lll')
            result = ev.summary(m, rows)
        elif args.command == 'epoch':
            result = create_epoch(args.output)
        elif args.command == 'run':
            if args.output.exists():
                raise ValueError('output directory already exists')
            epoch_manifest, reference = ev.audit_epoch(args.epoch)
            if environment() != epoch_manifest['environment']:
                raise ValueError('execution environment changed; create a new epoch')
            m, rows = evaluate(args.output, epoch_manifest['cases'], epoch_manifest['environment'], 'contestant', epoch_manifest, args.solver_dir)
            result = ev.summary(m, rows, reference)
        else:
            epoch_manifest, reference = ev.audit_epoch(args.epoch)
            summaries = []
            for path in args.run:
                if not (path / 'COMPLETE.json').exists():
                    diagnostic = ev.partial_diagnostics(path, epoch_manifest)
                    print(json.dumps(diagnostic, sort_keys=True, indent=2))
                    return 1
                m, rows = ev.audit_run(path, args.epoch)
                summaries.append(ev.summary(m, rows, reference))
            if len({s['run_id'] for s in summaries}) != len(summaries):
                raise ValueError('duplicate submission')
            if any(not s['eligible'] for s in summaries):
                raise ValueError('invalid candidate makes submission ineligible')
            result = summaries if args.command == 'audit' else [
                {**r, 'interval_95': next(s['interval_95'] for s in summaries if s['run_id'] == r['submission'])}
                for r in ranked_groups({s['run_id']: s['score'] for s in summaries})]
        print(json.dumps(result, sort_keys=True, indent=2))
        return 1 if isinstance(result, dict) and result.get('eligible') is False else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'mldsafail-mlwe: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
