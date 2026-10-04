"""Retain unpublished proposed0.6 participant wheel and deterministic public archive."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import zipfile

from mldsafail.benchmark_v050.generator import generate_mlwe


def sha(data):return hashlib.sha256(data).hexdigest()


def git(source,*args):return subprocess.check_output(['git','-C',str(source),*args],timeout=15)


def public_files(source,wheel,identity):
    info=wheel.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>128*1024*1024:
        raise ValueError('Bounded regular candidate wheel required')
    data=wheel.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or any(name.startswith('/') or '..' in Path(name).parts or '\\' in name for name in names):
            raise ValueError('Unsafe candidate wheel inventory')
        if 'mldsafail/benchmark_v060/backend.py' not in names:raise ValueError('Inactive proposed0.6 package code required')
        if any(not (name.startswith('mldsafail/') or name.startswith('mldsafail_challenge-0.5.1.dist-info/')) or stat.S_ISLNK(entry.external_attr>>16) for entry in archive.infolist() for name in [entry.filename]):
            raise ValueError('Wheel contains non-package or linked member')
        if sum(entry.file_size for entry in archive.infolist())>128*1024*1024:raise ValueError('Expanded wheel exceeds cap')
        metadata=archive.read('mldsafail_challenge-0.5.1.dist-info/METADATA').decode()
        if '\nVersion: 0.5.1\n' not in metadata:raise ValueError('Package version must remain0.5.1')
        if any(any(part in name.lower() for part in ('.env','.git/','private','epoch','nonce','witness')) for name in names if not name.startswith('mldsafail/benchmark_v060/')):
            # Trusted package modules named epoch/evidence are public source; raw
            # operational artifacts and hidden state never belong in a wheel.
            bad=[name for name in names if any(part in name.lower() for part in ('.env','.git/','private/', 'nonce/', 'witness/'))]
            if bad:raise ValueError('Private artifact in candidate wheel')
    files={wheel.name:data,'README.md':(Path(__file__).resolve().parents[1]/'docs/PARTICIPANT_V060_CANDIDATE.md').read_bytes()}
    for relative in ('examples/mlwe/primal-lll/solver.py','scripts/install.sh'):
        files[relative]=git(source,'show','HEAD:'+relative)
    original=git(source,'show','HEAD:docs/MLWE_V060_CONTRACT.md')
    presentation=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:m.group(0) if m[2].startswith(('http://','https://','#')) else m[1],original.decode()).encode()
    files['docs/MLWE_V060_CONTRACT.md']=presentation
    files['public-fixtures.json']=(json.dumps([generate_mlwe(p,0,e).public.to_dict() for p in ('small','medium','large') for e in (1,2)],sort_keys=True,indent=2)+'\n').encode()
    identity.update(wheel_sha256=sha(data),starter_sha256=sha(files['examples/mlwe/primal-lll/solver.py']),
        original_proposed_contract_sha256=sha(original),included_contract_sha256=sha(presentation))
    files['SOURCE.json']=(json.dumps(identity,sort_keys=True,indent=2)+'\n').encode()
    checks={name:sha(value) for name,value in sorted(files.items())}
    files['SHA256SUMS']=''.join(value+'  '+name+'\n' for name,value in checks.items()).encode()
    return files,checks


def build(source,destination):
    source=Path(source).resolve();destination=Path(destination).absolute()
    if git(source,'status','--porcelain').strip():raise ValueError('Clean retained candidate source required')
    commit=git(source,'rev-parse','HEAD').decode().strip()
    if destination.exists():raise ValueError('Fresh private candidate destination required')
    if '0.6.0' not in git(source,'show','HEAD:src/mldsafail/benchmark_versions.py').decode():raise ValueError('Proposed version source required')
    destination.mkdir(mode=0o700,parents=True)
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')}
    env['SOURCE_DATE_EPOCH']=git(source,'show','-s','--format=%ct','HEAD').decode().strip()
    wheel_directory=destination/'wheel';wheel_directory.mkdir(mode=0o700)
    subprocess.run(['uv','build','--wheel','--out-dir',str(wheel_directory)],cwd=source,env=env,check=True,timeout=120)
    if git(source,'status','--porcelain').strip():raise ValueError('Build changed retained source')
    wheel=wheel_directory/'mldsafail_challenge-0.5.1-py3-none-any.whl'
    identity=dict(schema='mldsafail.participant-candidate.v1',source_commit=commit,source_tree=git(source,'rev-parse','HEAD^{tree}').decode().strip(),
        package_version='0.5.1',benchmark_protocol='0.6.0',candidate_only=True,contract_adopted=False,
        production_default_approved=False,publication_approved=False,native_install_passed=False,native_reproduction_passed=False,
        documentation_source_sha256=sha((Path(__file__).resolve().parents[1]/'docs/PARTICIPANT_V060_CANDIDATE.md').read_bytes()))
    files,checks=public_files(source,wheel,identity)
    archive=destination/'participant-v060-unapproved-candidate.tar.gz'
    with archive.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as output:
        for name,data in sorted(files.items()):
            entry=tarfile.TarInfo('mldsafail-v060-candidate/'+name);entry.size=len(data);entry.mode=0o644;entry.mtime=0
            output.addfile(entry,io.BytesIO(data))
    manifest={**identity,'archive_sha256':sha(archive.read_bytes()),'files_sha256':checks,'independent_archive_review_pending':True}
    for path in (wheel,archive):
        with path.open('rb') as stream:os.fchmod(stream.fileno(),0o400);os.fsync(stream.fileno())
    (destination/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');(destination/'manifest.json').chmod(0o400)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.source,args.destination),indent=2))
