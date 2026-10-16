"""Private offline participant install: reviewed owned-native-driver callback only."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import tarfile

from deploy import owned_daemon
from research.cpu_measurement import native_driver


def retained_bytes(path, expected, cap=128*1024*1024):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1
                or info.st_mode & 0o222 or not 0<info.st_size<=cap):
            raise ValueError('Sealed owned bounded regular artifact required')
        result=b''
        while chunk:=os.read(descriptor,min(1024*1024,cap+1-len(result))):
            result+=chunk
            if len(result)>cap:raise ValueError('Artifact grew beyond cap')
        current=os.fstat(descriptor);named=os.stat(path,follow_symlinks=False)
        if ((current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
                or (named.st_dev,named.st_ino)!=(info.st_dev,info.st_ino)
                or hashlib.sha256(result).hexdigest()!=expected):
            raise ValueError('Retained artifact identity changed')
        return result
    finally:os.close(descriptor)


def admission(protocol):
    if protocol.get('schema')!='mldsafail.participant-native-install-protocol.v1':
        raise ValueError('Explicit participant installation protocol required')
    manifest=owned_daemon.read_private_json(Path(protocol['manifest']))
    review=owned_daemon.read_private_json(Path(protocol['review']))
    source=protocol['participant_source_commit']
    if (not re.fullmatch('[0-9a-f]{40}',source) or manifest.get('source_commit')!=source
            or manifest.get('schema')!='mldsafail.participant-candidate.v1'
            or manifest.get('package_version')!='0.5.1' or manifest.get('benchmark_protocol')!='0.6.0'
            or manifest.get('candidate_only') is not True
            or any(manifest.get(key) is not False for key in ('contract_adopted','production_default_approved','publication_approved'))
            or review.get('source_review_passed') is not True or review.get('archive_review_passed') is not True
            or review.get('author_source_commit')!=source
            or review.get('archive_sha256')!=manifest.get('archive_sha256')
            or review.get('wheel_sha256')!=manifest.get('wheel_sha256')):
        raise ValueError('Separately bound unapproved participant source and archive review required')
    source_path=Path(protocol['participant_source'])
    archive=retained_bytes(protocol['archive'],manifest['archive_sha256'])
    wheel=retained_bytes(protocol['wheel'],manifest['wheel_sha256'])
    files={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as stream:
        members=stream.getmembers()
        if len(members)>32 or sum(item.size for item in members)>128*1024*1024:
            raise ValueError('Bounded participant archive required')
        for item in members:
            parts=Path(item.name).parts
            if (not item.isfile() or len(parts)<2 or parts[0]!='mldsafail-v060-candidate'
                    or '..' in parts or '\\' in item.name):raise ValueError('Unsafe participant member')
            name='/'.join(parts[1:])
            if name in files:raise ValueError('Duplicate participant member')
            files[name]=stream.extractfile(item).read()
    expected=manifest['files_sha256']
    if set(files)!=set(expected)|{'SHA256SUMS'} or any(hashlib.sha256(files[name]).hexdigest()!=value for name,value in expected.items()):
        raise ValueError('Exact reviewed archive inventory required')
    sums=''.join(value+'  '+name+'\n' for name,value in sorted(expected.items())).encode()
    if files['SHA256SUMS']!=sums:raise ValueError('Archive checksum presentation differs from manifest')
    if files.get(Path(protocol['wheel']).name)!=wheel or json.loads(files['SOURCE.json']).get('source_commit')!=source:
        raise ValueError('Archive wheel/source mismatch')
    dependencies=protocol['dependency_wheels']
    if not isinstance(dependencies,list) or not dependencies:raise ValueError('Explicit offline dependency wheels required')
    names=set()
    for item in dependencies:
        name=Path(item['path']).name
        if not name.endswith('.whl') or name in names or name==Path(protocol['wheel']).name:raise ValueError('Unique dependency wheels required')
        names.add(name);retained_bytes(item['path'],item['sha256'])
    return manifest,files,source_path


# Executed with the freshly installed interpreter, without the operator source
# on sys.path. No private epochs, accounting, reference costs or Docker access.
PROBE=r'''
import importlib.metadata,json,pathlib,platform,runpy,sys,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
import mldsafail
from mldsafail import cli
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.verify import verify_candidate
root=pathlib.Path(sys.argv[1]);prefix=pathlib.Path(sys.prefix).resolve()
assert prefix==root/'installed' and prefix in pathlib.Path(mldsafail.__file__).resolve().parents
assert importlib.metadata.version('mldsafail-challenge')=='0.5.1'
solver=runpy.run_path(str(root/'candidate/solver/solver.py'))['solve']
fixtures=json.loads((root/'public-fixtures.json').read_text())
fixtures=[public for public in fixtures if public['profile']=='small']
assert len(fixtures)==2
for public in fixtures:
    assert verify_candidate(instance_from_dict(public),solver(public))['verified']
requests=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        requests.append(('GET',self.path))
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps({'schema':'mldsafail.api-capabilities.v1','explicit_version_selection':True,'submission_versions':['0.5.0']}).encode())
    def do_POST(self):
        requests.append(('POST',self.path));self.send_response(500);self.end_headers()
server=HTTPServer(('127.0.0.1',0),Handler)
server.timeout=1
thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.05},daemon=True);thread.start()
try:
    cli._write_config({'token':'private-disposable-preflight-token'})
    status=cli.main(['submit','--benchmark-version','0.6.0','--server','http://127.0.0.1:'+str(server.server_port),'--repo','https://invalid.example/unused','--commit','0'*40,'--hypothesis','private fail-closed probe'])
    assert status==2 and requests==[('GET','/api/v1/capabilities')]
finally:
    server.shutdown();server.server_close();thread.join(2)
    assert not thread.is_alive()
assert not list((root/'home').rglob('submission-intent*'))
print(json.dumps({'passed':True,'installed_package':'0.5.1','python':platform.python_version(),'platform':platform.platform(),'public_fixtures_verified':len(fixtures),'unsupported_server_preflight':True,'submission_post_count':0}))
'''


def callback(journal,config,data):
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):
        raise RuntimeError('Native Linux amd64 participant install required')
    protocol=owned_daemon.read_private_json(journal.path.parent/'participant-install-protocol.json')
    manifest,files,source=admission(protocol)
    def command(argv,timeout=180):
        return journal.command(argv,kind='read',timeout=timeout,env=env).stdout
    env={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','PYTHONSTARTUP')}
    env.update(PYTHONNOUSERSITE='1',PYTHON_KEYRING_BACKEND='keyring.backends.null.Keyring',UV_OFFLINE='1',PIP_NO_INDEX='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
    if command(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()!=protocol['participant_source_commit'] or command(['git','-C',str(source),'status','--porcelain']).strip():
        raise RuntimeError('Exact clean separately retained participant source required')
    root=journal.path.parent/'participant-install';root.mkdir(mode=0o700)
    home=root/'home';home.mkdir(mode=0o700)
    env.update(HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_CACHE_HOME=str(home/'cache'),XDG_DATA_HOME=str(home/'data'),UV_CACHE_DIR=str(home/'uv-cache'))
    wheelhouse=root/'wheelhouse';wheelhouse.mkdir(mode=0o700)
    for item in protocol['dependency_wheels']:
        (wheelhouse/Path(item['path']).name).write_bytes(retained_bytes(item['path'],item['sha256']))
    wheel=wheelhouse/Path(protocol['wheel']).name;wheel.write_bytes(retained_bytes(protocol['wheel'],manifest['wheel_sha256']))
    install=root/'installed'
    command(['uv','venv','--offline','--python',protocol['python'],str(install)])
    command(['uv','pip','install','--offline','--no-index','--find-links',str(wheelhouse),'--python',str(install/'bin/python'),str(wheel)])
    executable=str(install/'bin/mldsafail')
    command([executable,'--help'])
    command([executable,'clone','--benchmark-version','0.6.0',str(root/'candidate')])
    starter=root/'candidate/solver/solver.py'
    if starter.read_bytes()!=files['examples/mlwe/primal-lll/solver.py']:raise RuntimeError('Installed clone starter differs from reviewed archive')
    command([executable,'clone','--benchmark-version','0.4.0',str(root/'historical')])
    historical=json.loads(command([executable,'run','--profile','small','--no-record']))
    if historical.get('score')!=3901:raise RuntimeError('Historical baseline compatibility changed')
    (root/'public-fixtures.json').write_bytes(files['public-fixtures.json'])
    (root/'probe.py').write_text(PROBE)
    probe=json.loads(command([str(install/'bin/python'),'-I',str(root/'probe.py'),str(root)],timeout=180).splitlines()[-1])
    if (probe.get('passed') is not True or probe.get('installed_package')!='0.5.1'
            or probe.get('public_fixtures_verified')!=2 or probe.get('unsupported_server_preflight') is not True
            or probe.get('submission_post_count')!=0):raise RuntimeError('Exact installed participant probe required')
    artifact=root/'artifact.json'
    result=dict(schema='mldsafail.participant-native-install.v1',passed=True,native_executed=True,
        source_commit=protocol['participant_source_commit'],wheel_sha256=manifest['wheel_sha256'],archive_sha256=manifest['archive_sha256'],
        operator_source_commit=config['source_commit'],source_sha256=config['acceptance_source_sha256'],owned_driver_journal=str(journal.path),
        outer_cleanup_required=True,package_version='0.5.1',benchmark_protocol='0.6.0',probe=probe,historical_score=3901,
        dependency_wheels=[dict(name=Path(item['path']).name,sha256=item['sha256']) for item in protocol['dependency_wheels']],
        native_accounting_passed=False,native_reproduction_passed=False,reference_created=False,contract_adopted=False,publication_approved=False)
    try:owned_daemon.publish(artifact,result)
    except BaseException as error:
        result.update(passed=False,publication_incomplete=True)
        try:owned_daemon.publish(artifact,result)
        except BaseException as cleanup:error.add_note('Negative installation proof publication also failed: '+type(cleanup).__name__)
        raise
    return dict(schema='mldsafail.owned-native-acceptance.v1',passed=True,native_executed=True,
        evidence_refs=[str(artifact)],source_sha256=config['acceptance_source_sha256'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args();config=owned_daemon.read_private_json(args.config)
    native_driver.execute(config,repository=Path(__file__).resolve().parents[1],acceptance=callback,daemon_kind='owned')

if __name__=='__main__':main()
