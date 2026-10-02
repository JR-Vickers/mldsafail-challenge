"""Quiesce staging and assemble a new private DB/evidence recovery set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from deploy.recovery import private_file, validate_set


def assemble(config, destination):
    if destination.exists():
        raise ValueError('Recovery set must be new')
    destination.mkdir(mode=0o700, parents=True)
    compose = ['docker', 'compose', '--env-file', config['env_file'], '-f', config['compose']]
    def command(argv, timeout=30):
        return subprocess.check_output(argv, stderr=subprocess.DEVNULL, text=True, timeout=timeout)
    states = {}
    for role in ['web', 'coordinator']:
        identifier = command(compose + ['ps', '-aq', role]).strip()
        states[role] = json.loads(command(['docker', 'inspect', '--format', '{{json .State}}', identifier]))['Running']
    journal = destination / 'maintenance.json'
    journal.write_text(json.dumps({'compose': compose, 'service_states': states, 'cleanup_complete': False}))
    journal.chmod(0o600)
    categories = {key: [] for key in ['database', 'epoch', 'evidence', 'configuration', 'secrets', 'release', 'images']}
    try:
        command(compose + ['stop', 'coordinator'], 60)
        command(compose + ['stop', 'web'], 60)
        code = '''import json,os
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from mldsafail.web.models import EvaluationJob,ExperimentResult
from mldsafail.benchmark_v050 import evidence as ev
engine=create_engine(os.environ['MLDSAFAIL_DATABASE_URL'])
epoch=Path(os.environ['MLDSAFAIL_MLWE_EPOCH_PATH'])
manifest,reference=ev.audit_epoch(epoch)
paths=[]
with Session(engine) as session:
 if engine.dialect.name=='postgresql': session.execute(text('SET TRANSACTION READ ONLY'))
 if session.scalar(select(EvaluationJob).where(EvaluationJob.status.in_(['queued','claimed','running']))): raise RuntimeError('Active evaluation work prevents backup')
 for result in session.scalars(select(ExperimentResult)):
  job=session.scalar(select(EvaluationJob).where(EvaluationJob.submission_id==result.submission_id))
  if result.benchmark_version!='0.5.0' or result.epoch_id!=manifest['id'] or not job: raise RuntimeError('Recovery cohort mismatch')
  run=Path(os.environ['MLDSAFAIL_EVALUATOR_WORK_ROOT'])/'runs'/result.submission_id/str(job.attempts)
  m,rows=ev.audit_run(run,epoch)
  summary=ev.summary(m,rows,reference)
  if not result.verified or result.diagnostics!=summary or result.mlwe_score!=summary['score']: raise RuntimeError('Evidence mismatch')
  paths.append(str(run))
print(json.dumps({'epoch':str(epoch),'runs':paths,'epoch_id':manifest['id']}))
'''
        inventory = json.loads(command(compose + ['run', '--rm', '--no-deps', '--entrypoint',
                                       '/app/.venv/bin/python', 'coordinator', '-c', code], 600))
        output = destination / 'database'
        command([config['python'], str(Path(__file__).with_name('backup_postgres.py')),
                 '--env-file', config['env_file'], '--compose', config['compose'],
                 '--output', str(output), '--verify-restore'], 360)
        def copy(source, category, relative):
            source = Path(source)
            if source.is_symlink():
                raise ValueError('Symlink recovery source')
            target = destination / category / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if source.is_dir():
                if any(p.is_symlink() for p in source.rglob('*')):
                    raise ValueError('Symlink recovery tree')
                shutil.copytree(source, target)
            else:
                shutil.copyfile(source, target)
        copy(inventory['epoch'], 'epoch', 'sealed')
        for path in inventory['runs']:
            source = Path(path)
            copy(source, 'evidence', Path(source.parent.name) / source.name)
        # Retained images and required secrets/configuration are explicit owner inputs.
        for category in ['configuration', 'secrets', 'release', 'images']:
            for name, source in config['material'][category].items():
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unsafe recovery target')
                copy(source, category, name)
        files = {}
        for path in destination.rglob('*'):
            if path.is_file() and path != journal:
                relative = str(path.relative_to(destination))
                files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                categories[Path(relative).parts[0]].append(relative)
                path.chmod(0o600)
            elif path.is_dir():
                path.chmod(0o700)
        manifest = {'files': files, 'categories': categories,
                    'database_evidence_verified': True, 'epoch_id': inventory['epoch_id']}
        # Remove maintenance journal only after all original services are restored.
    finally:
        errors = []
        for role, running in states.items():
            try:
                command(compose + ['start' if running else 'stop', role], 60)
            except Exception:
                errors.append(role)
        journal.write_text(json.dumps({'compose': compose, 'service_states': states,
                                      'cleanup_complete': not errors, 'cleanup_errors': errors}))
        if errors:
            raise RuntimeError('Recovery assembly cleanup incomplete; restore states from private journal')
    journal.unlink()
    (destination / 'recovery.json').write_text(json.dumps(manifest, sort_keys=True))
    (destination / 'recovery.json').chmod(0o600)
    validate_set(destination)
    return {'sealed': True, 'epoch_id': inventory['epoch_id'], 'result_count': len(inventory['runs'])}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    import signal
    for sig in [signal.SIGTERM, signal.SIGHUP]:
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(InterruptedError()))
    try:
        print(json.dumps(assemble(json.loads(private_file(args.config).read_text()), args.output)))
    except Exception:
        print(json.dumps({'assembly_failed': True, 'private_evidence_retained': True}))
        raise SystemExit(1)
