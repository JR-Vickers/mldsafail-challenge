"""Retain immutable image archives using only read-only Docker daemon requests.

No container, image, service, network or volume mutation is permitted. All
command clients are durably gated in the explicitly delegated operator domain.
Failed and partial artifacts remain private and are never promoted by cleanup.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import shutil
import subprocess
import uuid
from deploy import owned_client, owned_daemon
from deploy.recovery_daemon import shared_scope
from deploy.recovery_journal import atomic_json, safe_path, sync_directory

SCHEMA='mldsafail.native-image-export.v1'
SHA=re.compile(r'sha256:[0-9a-f]{64}')


def validate(config, repository):
    expected={'schema','source_commit','script_sha256','docker_host','expected_architecture','images','minimum_free_bytes'}
    if not isinstance(config,dict) or set(config)!=expected or config['schema']!=SCHEMA:
        raise ValueError('Exact private image export configuration required')
    if config['expected_architecture'] not in {'amd64','arm64'}:
        raise ValueError('Explicit native image architecture required')
    if type(config['minimum_free_bytes']) is not int or config['minimum_free_bytes']<=0:
        raise ValueError('Predeclared existing host disk floor required')
    images=config['images']
    if not isinstance(images,list) or not images or len(images)>32 or any(not isinstance(x,str) or not SHA.fullmatch(x) for x in images) or len(set(images))!=len(images):
        raise ValueError('Unique immutable image SHA256 IDs only')
    if not isinstance(config['docker_host'],str) or not config['docker_host'].startswith('unix:///'):
        raise ValueError('Explicit local user Docker socket required')
    socket=safe_path(config['docker_host'][7:])
    if not stat.S_ISSOCK(socket.stat().st_mode) or socket.stat().st_uid!=os.getuid():
        raise ValueError('Owned local Docker socket required')
    commit=subprocess.check_output(['git','-C',str(repository),'rev-parse','HEAD'],text=True,timeout=15).strip()
    if subprocess.check_output(['git','-C',str(repository),'status','--porcelain'],timeout=15):
        raise ValueError('Clean retained source required')
    actual=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if config['source_commit']!=commit or config['script_sha256']!=actual:
        raise ValueError('Exact retained exporter source identity required')


def file_identity(path):
    info=path.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_mode & 0o077:
        raise ValueError('Private single-link regular artifact required')
    return dict(device=info.st_dev,inode=info.st_ino,uid=info.st_uid)


def seal(path, expected, destination):
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or
            dict(device=info.st_dev,inode=info.st_ino,uid=info.st_uid)!=expected or
            file_identity(path)!=expected or info.st_size<=0):
            raise ValueError('Exported artifact identity changed or empty')
        os.fsync(descriptor)
        with os.fdopen(os.dup(descriptor),'rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        os.fchmod(descriptor,0o400)
        os.fsync(descriptor)
        if file_identity(path)!=expected or destination.exists():
            raise ValueError('Immutable artifact destination or identity changed')
        os.rename(path,destination)
        sync_directory(destination.parent)
        return dict(image_archive=str(destination),image_archive_sha256=digest,image_archive_bytes=info.st_size)
    finally:os.close(descriptor)


class Export:
    def __init__(self,root,data):self.root,self.data=root,data
    def save(self):atomic_json(self.root/'journal.json',self.data)
    def command(self,argv,timeout=60):
        # Guard the exact read-only subset even if an internal caller changes.
        if not (len(argv)>=4 and argv[:3]==['docker','image','inspect'] and len(argv)==4 and SHA.fullmatch(argv[3]) or
                len(argv)==6 and argv[:3]==['docker','image','save'] and argv[3]=='--output' and SHA.fullmatch(argv[5]) and Path(argv[4]).parent==self.root):
            raise ValueError('Read-only exact image inspect/save command required')
        return owned_client.run(argv,self.data['clients'],self.save,self.root,capture_output=True,check=True,timeout=timeout)
    def verify_retained(self):
        images=self.data.get('images')
        expected=self.data.get('config',{}).get('images')
        if not isinstance(images,list) or not isinstance(expected,list) or len(images)!=len(expected):
            raise ValueError('Complete retained image inventory required')
        for row,image in zip(images,expected,strict=True):
            path=self.root/(image[7:]+'.tar')
            if row.get('state')!='retained' or row.get('image')!=image or row.get('image_archive')!=str(path):
                raise ValueError('Exact retained archive identity required')
            file_identity(path)
            descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                info=os.fstat(descriptor)
                if stat.S_IMODE(info.st_mode)!=0o400 or info.st_size!=row.get('image_archive_bytes'):
                    raise ValueError('Immutable retained archive size/mode mismatch')
                with os.fdopen(os.dup(descriptor),'rb') as stream:
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if digest!=row.get('image_archive_sha256') or file_identity(path)!=dict(device=info.st_dev,inode=info.st_ino,uid=info.st_uid):
                    raise ValueError('Retained archive digest/identity mismatch')
            finally:os.close(descriptor)

    def cleanup(self):
        errors=[]
        clients=self.data.get('clients',[])
        if not isinstance(clients,list):
            errors.append('corrupt_client_authority');clients=[]
        for item in clients:
            try:
                if not isinstance(item,dict):raise ValueError('Invalid client ownership receipt')
                if item.get('finished') is not True:
                    owned_client.stop(item)
                    item['finished']=True
            except BaseException as error:errors.append('client_cleanup:'+type(error).__name__)
        self.data['cleanup_complete']=not errors
        self.data['cleanup_errors']=errors
        try:self.save()
        except BaseException as error:errors.append('cleanup_publication:'+type(error).__name__)
        if errors:
            self.data['cleanup_complete']=False
            try:self.save()
            except BaseException:pass
            raise RuntimeError('Image export cleanup incomplete: '+repr(errors))


def execute(root,config,repository):
    validate(config,repository)
    root.mkdir(mode=0o700,exist_ok=False)
    data=dict(schema=SCHEMA,id=uuid.uuid4().hex,config=config,clients=[],images=[],
        native_executed=False,passed=False,cleanup_complete=False)
    operation=Export(root,data)
    original=None
    try:
        operation.save()
        environment=dict(DOCKER_HOST=config['docker_host'],DOCKER_CONTEXT=None,
            MLDSAFAIL_OPERATOR_DAEMON_MANIFEST=None,MLDSAFAIL_CPU_DAEMON_MANIFEST=None)
        with shared_scope(environment):
            for image in config['images']:
                inspected=json.loads(operation.command(['docker','image','inspect',image]).stdout)
                if not isinstance(inspected,list) or len(inspected)!=1:
                    raise ValueError('Exact single native image inspection required')
                info=inspected[0]
                if info.get('Id')!=image or info.get('Architecture')!=config['expected_architecture'] or not isinstance(info.get('RepoDigests',[]),list):
                    raise ValueError('Native image identity/architecture mismatch')
                if type(info.get('Size')) is not int or info['Size']<0 or shutil.disk_usage(root).free<config['minimum_free_bytes']+2*info['Size']+1024*1024:
                    raise RuntimeError('Existing disk floor plus bounded image export headroom required')
                partial=root/(image[7:]+'.partial.tar');final=root/(image[7:]+'.tar')
                descriptor=os.open(partial,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600);os.close(descriptor)
                artifact=dict(image=image,architecture=info['Architecture'],original_image_inspection=info,
                    image_archive=str(partial),file_identity=file_identity(partial),state='save_intent')
                data['images'].append(artifact);operation.save()
                operation.command(['docker','image','save','--output',str(partial),image],timeout=600)
                data['native_executed']=True
                artifact['state']='seal_intent';operation.save()
                artifact.update(seal(partial,artifact['file_identity'],final),state='retained')
                operation.save()
    except BaseException as error:
        original=error;data['error_type']=type(error).__name__
        try:operation.save()
        except BaseException as publication:error.add_note('Failure publication: '+type(publication).__name__)
    finally:
        try:operation.cleanup()
        except BaseException as error:
            if original is None:original=error
            else:original.add_note('Independent cleanup: '+type(error).__name__)
        data['passed']=original is None and data['cleanup_complete'] is True and len(data['images'])==len(config['images']) and all(row['state']=='retained' for row in data['images'])
        try:operation.save()
        except BaseException as error:
            data['passed']=False
            if original is None:original=error
            else:original.add_note('Final publication: '+type(error).__name__)
            try:operation.save()
            except BaseException as retry:original.add_note('Negative publication: '+type(retry).__name__)
        if original is not None:raise original
    return data


def run(output,config_path=None,cleanup_only=False):
    root=safe_path(output)
    descriptor=os.open(root.parent/('.'+root.name+'.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1 or info.st_mode & 0o077:
            raise ValueError('Private exclusive export lock required')
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if cleanup_only:
            info=root.stat()
            if info.st_uid!=os.getuid() or info.st_mode & 0o077:raise ValueError('Private owned export root required')
            data=owned_daemon.read_private_json(root/'journal.json',cap=4*1024*1024)
            if data.get('schema')!=SCHEMA:raise ValueError('Exact export journal required')
            operation=Export(root,data);operation.cleanup()
            if data.get('passed') is True:
                try:operation.verify_retained()
                except BaseException as error:
                    data['passed']=False
                    data['artifact_error']=type(error).__name__
                    operation.save()
                    raise
            return dict(cleanup_complete=True,passed=data.get('passed') is True)
        return execute(root,owned_daemon.read_private_json(config_path),Path(__file__).resolve().parents[1])
    finally:os.close(descriptor)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--cleanup',action='store_true')
    args=parser.parse_args()
    result=run(args.output,args.config,args.cleanup)
    print(json.dumps(dict(passed=result['passed'],cleanup_complete=result['cleanup_complete'],native_executed=result.get('native_executed',False))))


if __name__=='__main__':os.umask(0o077);main()
