"""Build a fixed, root-owned scheduling collector with an exact sudo command.

Building grants no host authority. An administrator copies the artifact into an
exclusive root directory, verifies its hash, then explicitly installs its rule.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = '/root/mldsafail-owner-facts-20261022'
RULE = '/etc/sudoers.d/mldsafail-owner-facts'
COMMAND = '/usr/bin/python3 -I -B '+ROOT+'/collector.pyz'
SUDOERS = 'mldsafail ALL=(root) NOPASSWD: '+COMMAND+'\n'
SOURCES = ('scripts/workload_owner_collection.py', 'deploy/privileged_scheduling.py')

BOOTSTRAP = r'''import hashlib,json,os,stat,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(ROOT_LITERAL)
RULE=Path(RULE_LITERAL)
SUDOERS=SUDOERS_LITERAL
MANIFEST=MANIFEST_LITERAL

def trusted(path):
    for parent in (path,*path.parents):
        info=parent.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
            raise ValueError('root_owned_nonwritable_path_required')
    return path

def exclusive(path,data,mode=0o600):
    with path.open('xb') as stream:
        os.chmod(path,mode);stream.write(data);stream.flush();os.fsync(stream.fileno())
    descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)

def install_rule():
    trusted(RULE.parent)
    if os.path.lexists(RULE):raise ValueError('existing_sudoers_resource_preserved')
    subprocess.run(['/usr/sbin/visudo','-c'],check=True,stdin=subprocess.DEVNULL)
    candidate=ROOT/'sudoers.candidate'
    exclusive(candidate,SUDOERS.encode(),0o440)
    subprocess.run(['/usr/sbin/visudo','-c','-f',str(candidate)],check=True,stdin=subprocess.DEVNULL)
    # Only validated bytes are written, exclusively; no existing file is edited.
    exclusive(RULE,SUDOERS.encode(),0o440)
    subprocess.run(['/usr/sbin/visudo','-c'],check=True,stdin=subprocess.DEVNULL)
    print(json.dumps(dict(rule=str(RULE),sha256=hashlib.sha256(RULE.read_bytes()).hexdigest(),command=COMMAND_LITERAL)))

class BoundedRaw:
    def __init__(self,stream):self.stream=stream;self.bytes=0
    def write(self,data):
        if self.bytes+len(data)>32*1024**2:raise ValueError('raw_output_bound')
        self.stream.write(data);self.bytes+=len(data)

def collect():
    with tempfile.TemporaryDirectory(prefix='mldsafail-owner-facts-') as directory:
        source=Path(directory)
        with zipfile.ZipFile(sys.argv[0]) as archive:
            for name,expected in MANIFEST.items():
                data=archive.read(name)
                if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('collector_source_changed')
                target=source/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                exclusive(target,data)
        sys.path.insert(0,str(source))
        from scripts.workload_owner_collection import collect as scheduling
        with tempfile.TemporaryFile() as stream:
            raw=BoundedRaw(stream);failure=None
            try:summary=scheduling(raw)
            except Exception as error:
                summary=dict(complete=False,readiness=False,execution_authority=False)
                failure=dict(type=type(error).__name__,message=str(error))
            stream.seek(0);data=stream.read(32*1024**2+1)
        print(json.dumps(dict(schema='mldsafail.owner-collection-export.v1',
            source_sha256=MANIFEST,collection=summary,error=failure,raw_jsonl=data.decode('ascii'),
            raw_sha256=hashlib.sha256(data).hexdigest(),execution_authority=False),sort_keys=True))

def main():
    if os.getuid()!=0 or os.geteuid()!=0:raise ValueError('root_required')
    if Path(sys.argv[0])!=ROOT/'collector.pyz':raise ValueError('fixed_installation_path_required')
    trusted(ROOT/'collector.pyz')
    os.umask(0o077);os.chdir('/')
    os.environ.clear();os.environ.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin',LC_ALL='C')
    if sys.argv[1:]==['--install-rule']:install_rule()
    elif len(sys.argv)==1:collect()
    else:raise ValueError('arguments_not_permitted')

if __name__=='__main__':main()
'''


def build(source, output):
    source=Path(source);output=Path(output)
    files={name:(source/name).read_bytes() for name in SOURCES}
    files.update({'scripts/__init__.py':b'', 'deploy/__init__.py':b''})
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    bootstrap=(BOOTSTRAP.replace('ROOT_LITERAL',repr(ROOT)).replace('RULE_LITERAL',repr(RULE))
        .replace('SUDOERS_LITERAL',repr(SUDOERS)).replace('MANIFEST_LITERAL',repr(manifest))
        .replace('COMMAND_LITERAL',repr(COMMAND)))
    files['__main__.py']=bootstrap.encode()
    with output.open('xb') as stream:
        output.chmod(0o600)
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in sorted(files.items()):
                info=zipfile.ZipInfo(name,date_time=(2026,10,22,0,0,0));info.external_attr=0o100600<<16
                archive.writestr(info,data)
    return dict(artifact=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                sources=manifest,root=ROOT,sudoers_path=RULE,command=COMMAND,sudoers=SUDOERS)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],args.output),sort_keys=True))


if __name__=='__main__':main()
