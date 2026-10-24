"""Freeze local disposable-guest kit settings; never install or activate."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from deploy.workload_installation import exclusive, identity, private
from deploy.workload_release import canonical, regular
from mldsafail.evaluator.native_workload import require
from scripts.workload_installation_fixture import SCHEMA, absolute, environment


def prepare(root, output, *, manifest, interpreter_archive, installer_archive, image_archive,
            wheels, postgres_image, component_review, mark_guest=False):
    root=absolute(root);output=absolute(output)
    output.mkdir(mode=0o700)
    exclusive(output/'intent.json',canonical(dict(fixture_only=True,fixture_root=str(root),
                                                marker_creation_requested=mark_guest)))
    try:
        return _prepare(root,output,manifest=manifest,interpreter_archive=interpreter_archive,
                        installer_archive=installer_archive,image_archive=image_archive,wheels=wheels,
                        postgres_image=postgres_image,component_review=component_review,mark_guest=mark_guest)
    except BaseException as error:
        exclusive(output/'failed.json',canonical(dict(error=type(error).__name__,message=str(error),
                                                      ownership='preserve',automatic_retry=False)))
        raise


def _prepare(root,output,*,manifest,interpreter_archive,installer_archive,image_archive,wheels,postgres_image,component_review,mark_guest):
    require(not environment()['blockers'] and os.getuid()>0 and socket.gethostname().startswith('workload-rehearsal'),
            'fixture_owned_disposable_linux_guest_required')
    _,review=private(absolute(component_review))
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    from deploy.workload_release import digest
    source=Path(__file__).resolve().parents[1]
    require(review.get('decision')=='approved' and review.get('scope')=='disposable_fixture_components_only' and
            review.get('implemented_by') and review.get('reviewed_by') and review['implemented_by']!=review['reviewed_by'] and
            all(review.get('source_sha256',{}).get(name)==digest(regular(source,name)[0]) for name in REVIEW_FILES),
            'fixture_independent_component_review_required')
    target=dict(hostname=socket.gethostname(),machine_id=Path('/etc/machine-id').read_text().strip(),uid=os.getuid())
    marker=Path('/run/mldsafail-disposable-fixture.json')
    expected=dict(schema=SCHEMA,fixture_only=True,**target)
    if mark_guest and not marker.exists():
        require(Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU','fixture_marker_requires_owned_qemu_guest')
        code=('import os,sys,pathlib; p=pathlib.Path(sys.argv[1]); '
              'assert p.parent==pathlib.Path("/run") and not any(q.is_symlink() for q in (p,*p.parents)); '
              'fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644); '
              'f=os.fdopen(fd,"wb");f.write(bytes.fromhex(sys.argv[2]));f.flush();os.fsync(f.fileno());'
              'os.fchmod(f.fileno(),0o644);f.close()')
        subprocess.run(['/usr/bin/sudo','-n','/usr/bin/python3','-c',code,str(marker),canonical(expected).hex()],
                       check=True,capture_output=True,timeout=5)
    require(marker.lstat().st_uid==0 and not marker.lstat().st_mode&0o022 and
            json.loads(marker.read_bytes())==expected,'fixture_vm_marker_required')
    _,bindings=private(absolute(manifest))
    endpoint=['/usr/bin/docker','--host',f'unix:///run/user/{os.getuid()}/docker.sock']
    info=json.loads(subprocess.check_output([*endpoint,'info','--format','{{json .}}'],timeout=5))
    require(info['CgroupDriver']=='systemd' and info['CgroupVersion']=='2' and
            any('rootless' in value for value in info['SecurityOptions']),'fixture_rootless_systemd_daemon_required')
    pid_path=Path(f'/run/user/{os.getuid()}/docker.pid')
    pid=int(regular(pid_path.parent,pid_path.name)[0])
    executable=Path(f'/proc/{pid}/exe').resolve()
    settings={name:bindings[name] for name in ('coordinator_image','worker_environment','evaluator_fingerprint')}
    settings.update(postgres_image=postgres_image,unit_directory=str(Path.home()/'.config/systemd/user'),
                    daemon_pid_file=str(pid_path),daemon_executable=str(executable))
    exclusive(output/'settings.json',canonical(settings))
    inputs=dict(settings=str(output/'settings.json'),interpreter_archive=str(absolute(interpreter_archive)),
                installer_archive=str(absolute(installer_archive)),image_archive=str(absolute(image_archive)),
                component_review=str(absolute(component_review)))
    for index,path in enumerate(sorted(absolute(wheels).iterdir())):
        require(path.name.endswith('.whl'),'fixture_wheel_directory_contains_nonwheel')
        inputs['wheel_'+str(index)]=str(absolute(path))
    recipe=dict(schema=SCHEMA,fixture_only=True,target=target,inputs=inputs,
                adapters={name:'builtin' for name in ('provision','inspect','postflight','cleanup')},resources=[])
    exclusive(output/'recipe.json',canonical(recipe))
    exclusive(output/'preparation.json',canonical(dict(fixture_only=True,fixture_root=str(root),marker=identity(marker),
                                                     daemon_id=info['ID'],execution_authority=False)))
    return output/'recipe.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('--output',type=Path,required=True)
    for name in ('manifest','interpreter-archive','installer-archive','image-archive','wheels','component-review'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--postgres-image',required=True);parser.add_argument('--mark-guest',action='store_true')
    args=parser.parse_args()
    print(prepare(args.root,args.output,manifest=args.manifest,interpreter_archive=args.interpreter_archive,
                  installer_archive=args.installer_archive,image_archive=args.image_archive,wheels=args.wheels,
                  postgres_image=args.postgres_image,component_review=args.component_review,mark_guest=args.mark_guest))


if __name__=='__main__':main()
