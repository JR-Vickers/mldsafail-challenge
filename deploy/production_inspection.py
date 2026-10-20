"""Bounded read-only host inspection. Raw stdout is private; redirect to a 0600 file.

Standalone stdlib helper may be streamed through the recorded pinned SSH command;
it never writes remote files, runs images or changes services.
"""
import argparse


def inspect_host():
    import json,os,pathlib,subprocess,time
    os.environ['DOCKER_HOST']='unix:///run/user/1000/docker.sock'
    os.environ.pop('DOCKER_CONTEXT',None)
    def run(args):
     return subprocess.check_output(args,text=True,timeout=12)
    def objects(kind,ids):
     return json.loads(run(['docker',kind,'inspect',*ids])) if ids else []
    images=['31383f86703dcc8b4ba4c36acd8933ed5bf306ee98fa129e50d4625dd4c12a4b','b3f27a3b1b3d25d808f21ac56f2653dc5bd29f77dd9903acfd84969080c0d0a4','6aaf71aa16e36631dec607f0726fb1e8d6f94954ce55a15a74ba4989777b5cfe','6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b','639ab7ceb90e13123085b741fb31ef493fba25463002f6da665352e7b534b652']
    paths=['/srv/mldsafail-production-evaluator','/srv/mldsafail-production-evaluator/jobs','/srv/mldsafail-production-evaluator/secrets/signing.key','/srv/mldsafail-production-tls','/srv/mldsafail-production-acme','/run/user/1000/docker.sock']
    def describe(s):
     p=pathlib.Path(s); parts=[p,*p.parents]; existing=next(x for x in parts if x.exists())
     return dict(path=s,resolved=str(p.resolve()),symlinks=[str(x) for x in parts if x.is_symlink()],ancestor=str(existing),device=existing.stat().st_dev,inode=existing.stat().st_ino,uid=existing.stat().st_uid,mode=existing.stat().st_mode)
    r=dict(time=time.time(),uid=os.getuid(),account=os.environ.get('USER'),hostname=run(['hostname']).strip(),info=json.loads(run(['docker','info','--format','{{json .}}'])),images=objects('image',['sha256:'+x for x in images]),containers=objects('container',run(['docker','ps','-aq']).split()),volumes=objects('volume',run(['docker','volume','ls','-q']).split()),paths=[describe(x) for x in paths],mountinfo=pathlib.Path('/proc/self/mountinfo').read_text(),processes=run(['ps','-eo','pid,uid,args']),jobs=run(['systemctl','--user','list-jobs','--no-pager']),meminfo=pathlib.Path('/proc/meminfo').read_text(),disk_available=os.statvfs('/srv').f_bavail*os.statvfs('/srv').f_frsize)
    print(json.dumps(r))


def inspect_retained():
    import pathlib,json,os,subprocess
    roots=['/tmp/pr-261016-a/state','/tmp/pr-261017-b/state','/tmp/pr-261017-c/state','/tmp/pr-261018-c/state']
    r=[]
    for root in roots:
     p=pathlib.Path(root)/'production/synthetic.env'
     item=dict(root=root,path=str(p),exists=p.is_file(),resolved=str(p.resolve()))
     if p.is_file():
      item['environment']=p.read_text()
      c=p.parent/'compose.json'
      item['compose']=json.loads(c.read_text()) if c.is_file() else None
      j=p.parent/'journal.json'
      item['journal']=json.loads(j.read_text()) if j.is_file() else None
     r.append(item)
    print(json.dumps(r))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('host', 'retained'))
    args = parser.parse_args()
    (inspect_host if args.kind == 'host' else inspect_retained)()


if __name__ == '__main__':
    main()
