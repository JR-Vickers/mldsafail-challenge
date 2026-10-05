"""Assemble new inert candidate app image contexts from reviewed retained inputs."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import zipfile
from deploy import owned_daemon

SOURCE='6b332cdb051a9da5651a2fc1e1e1bac0f7df0acf'


def context(output,*,source,wheel,wheel_manifest,base_manifest):
    output,source,wheel=map(Path,(output,source,wheel))
    if output.exists():raise ValueError('Fresh protected image context required')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],timeout=15).strip():raise ValueError('Clean reviewed package source required')
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],timeout=15).decode().strip()
    if wheel_manifest.get('source_commit')!=commit or wheel_manifest.get('benchmark_protocol')!='0.6.0' or wheel_manifest.get('package_version')!='0.5.1' or wheel_manifest.get('publication_approved') is not False:
        raise ValueError('Exact separately identified unapproved wheel source required')
    descriptor=os.open(wheel,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.getuid() or before.st_mode&0o022 or not 0<before.st_size<=128*1024*1024:raise ValueError('Bounded private regular wheel required')
        with os.fdopen(os.dup(descriptor),'rb') as stream:block=stream.read(128*1024*1024+1)
        after=os.fstat(descriptor)
        if len(block)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Retained wheel changed during read')
    finally:os.close(descriptor)
    if hashlib.sha256(block).hexdigest()!=wheel_manifest.get('wheel_sha256'):raise ValueError('Retained wheel checksum changed')
    with zipfile.ZipFile(io.BytesIO(block)) as archive:
        entries=archive.infolist()
        if len({entry.filename for entry in entries})!=len(entries) or sum(entry.file_size for entry in entries)>128*1024*1024:raise ValueError('Bounded unique wheel inventory required')
        for entry in entries:
            if stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Wheel links forbidden')
            if not (entry.filename.startswith('mldsafail/') or entry.filename.startswith('mldsafail_challenge-0.5.1.dist-info/')) or '..' in Path(entry.filename).parts or '\\' in entry.filename:
                raise ValueError('Only approved package wheel paths allowed')
    if base_manifest.get('source_commit')!=SOURCE:raise ValueError('Exact compatible frozen baseline release required')
    base=base_manifest['images']['web']['id']
    if not re.fullmatch('sha256:[0-9a-f]{64}',base):raise ValueError('Immutable retained baseline web required')
    operator=Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git','-C',str(operator),'status','--porcelain'],timeout=15).strip():raise ValueError('Clean candidate runtime source required')
    output.mkdir(mode=0o700,parents=True);(output/'candidate.whl').write_bytes(block)
    runtime=output/'candidate_runtime';runtime.mkdir()
    for name in ('__init__.py','__main__.py','config.py','client.py','protocol.py'):
        path=operator/'candidate_runtime'/name
        if path.is_symlink():raise ValueError('Runtime links forbidden')
        shutil.copyfile(path,runtime/path.name)
    helpers=output/'deploy';helpers.mkdir();(helpers/'__init__.py').write_text('')
    for name in ('owned_daemon.py','owned_client.py'):
        value=subprocess.check_output(['git','-C',str(source),'show','HEAD:deploy/'+name],timeout=15)
        (helpers/name).write_bytes(value)
    install="""import sysconfig,pathlib,zipfile,shutil
root=pathlib.Path(sysconfig.get_paths()['purelib'])
for name in ('mldsafail','mldsafail_challenge-0.5.1.dist-info'):
    path=root/name
    if path.exists():shutil.rmtree(path)
with zipfile.ZipFile('/candidate.whl') as archive:archive.extractall(root)
"""
    (output/'install_candidate.py').write_text(install)
    (output/'Dockerfile').write_text('FROM '+base+'\nLABEL org.mldsafail.candidate=private-unapproved org.mldsafail.protocol=0.6.0 org.mldsafail.default=0.5.0\nUSER 0:0\nCOPY candidate.whl /candidate.whl\nCOPY install_candidate.py /install_candidate.py\nRUN /app/.venv/bin/python /install_candidate.py && rm /candidate.whl /install_candidate.py\nCOPY candidate_runtime /app/candidate_runtime\nCOPY deploy /app/deploy\nENV PYTHONPATH=/app\nWORKDIR /app\nUSER 0:0\nENTRYPOINT ["/app/.venv/bin/python","-m","candidate_runtime"]\n')
    files={path.relative_to(output).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.rglob('*')) if path.is_file()}
    record=dict(schema='mldsafail.private-candidate-image-context.v1',candidate_only=True,production_adopted=False,default_changed=False,
        native_image_build_passed=False,native_rehearsal_passed=False,base_image=base,base_source_commit=SOURCE,
        wheel_source_commit=commit,wheel_sha256=wheel_manifest['wheel_sha256'],runtime_source_commit=subprocess.check_output(['git','-C',str(operator),'rev-parse','HEAD'],timeout=15).decode().strip(),
        files_sha256=files,context_sha256=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    owned_daemon.publish(output.parent/(output.name+'-manifest.json'),record)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','source','wheel','wheel-manifest','base-manifest'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(context(a.output,source=a.source,wheel=a.wheel,wheel_manifest=owned_daemon.read_private_json(a.wheel_manifest),base_manifest=owned_daemon.read_private_json(a.base_manifest))))
