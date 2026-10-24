"""Provision an exclusively owned QEMU guest; installations remain offline.

Package downloads are allowed only here. Package versions, rootless launcher,
image archives and runtime kit files are supplied with exact hashes. No VPS,
shared daemon, scientific epoch or coordinator is a target of this command.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat
import time

from deploy.workload_installation import Journal, LinuxBackend, exclusive, identity, private
from deploy.workload_release import canonical, copy_regular, digest, file_record, regular
from deploy.workload_prerequisites import root_exclusive_write
from mldsafail.evaluator.native_workload import require
from scripts.workload_installation_fixture import absolute, environment, lifecycle_lock

PACKAGES={'docker.io','uidmap','dbus-user-session','rootlesskit','slirp4netns','containerd','runc','libslirp0'}
REQUIRED={'docker.io','uidmap','dbus-user-session','rootlesskit','slirp4netns'}


@contextmanager
def environment_lock():
    parent=Path(f'/run/user/{os.getuid()}')
    require(not any(p.is_symlink() for p in (parent,*parent.parents)) and parent.stat().st_uid==os.getuid() and
            stat.S_IMODE(parent.stat().st_mode)==0o700,'fixture_guest_runtime_directory_invalid')
    fd=os.open(parent/'mldsafail-fixture-provision.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid() and
                stat.S_IMODE(info.st_mode)==0o600,'fixture_guest_environment_lock_invalid')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


@contextmanager
def provision_locks(root):
    try:
        with lifecycle_lock(root),environment_lock():yield
    except BaseException as error:
        path=root/'lock-or-phase-failed.json'
        if not path.exists():exclusive(path,canonical(dict(error=type(error).__name__,message=str(error),automatic_retry=False)))
        raise


def owned_guest():
    require(not environment()['blockers'] and os.getuid()>0 and socket.gethostname().startswith('workload-rehearsal') and
            Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU' and
            Path('/var/lib/cloud/data/instance-id').read_text().strip().startswith('workload-v3-'),
            'fixture_owned_qemu_guest_required')


def review_source(review):
    from scripts.rehearse_workload_installation_fixture import REVIEW_FILES
    source=Path(__file__).resolve().parents[1]
    require(review.get('decision')=='approved' and review.get('scope')=='disposable_fixture_components_only' and
            review.get('implemented_by') and review.get('reviewed_by') and review['implemented_by']!=review['reviewed_by'] and
            all(review.get('source_sha256',{}).get(name)==digest(regular(source,name)[0]) for name in REVIEW_FILES),
            'fixture_independent_component_review_required')


def package_arguments(packages):
    require(type(packages) is dict and REQUIRED<=set(packages)<=PACKAGES,'fixture_package_lock_incomplete')
    require(all(type(version) is str and re.fullmatch(r'[A-Za-z0-9:.+~_-]+',version) for version in packages.values()),
            'fixture_package_version_invalid')
    return [name+'='+packages[name] for name in sorted(packages)]


def provision(root, specification, component_review, *, budget=1200):
    root=absolute(root);specification=absolute(specification);component_review=absolute(component_review)
    from deploy.workload_units import absolute as unit_path
    unit_path(str(root/'tools/dockerd-rootless.sh'))
    owned_guest()
    raw,spec=private(specification);review_raw,review=private(component_review)
    review_source(review)
    require(set(spec)=={'packages','rootless_launcher','files','wheels','postgres_image'},'fixture_guest_kit_fields')
    packages=package_arguments(spec['packages'])
    require(30<budget<=1500,'fixture_guest_provision_budget')
    root.mkdir(mode=0o700)
    exclusive(root/'intent.json',canonical(dict(fixture_only=True,specification_sha256=digest(raw),
            component_review_sha256=digest(review_raw),budget_seconds=budget,target=dict(hostname=socket.gethostname(),uid=os.getuid()),
            resources=['journal','tools','offline','docker-store',str(Path.home()/'.config/systemd/user/docker.service')],
            package_versions=spec['packages'])))
    finish_deadline=time.monotonic()+budget
    with provision_locks(root):
        journal_root=root/'journal';journal_root.mkdir(mode=0o700)
        journal=Journal(journal_root,digest(raw))
        backend=LinuxBackend.__new__(LinuxBackend)
        backend.journal=journal;backend.recipe=dict(journal_root=str(journal_root))
        backend.bundle=Path(__file__).resolve().parents[1]
        backend.deadline=finish_deadline-30
        endpoint=['/usr/bin/docker','--host',f'unix:///run/user/{os.getuid()}/docker.sock']
        daemon_binding=None
        def daemon_birth():
            from mldsafail.evaluator.native_workload import process_birth
            pid=int(regular(Path(f'/run/user/{os.getuid()}'),'docker.pid')[0])
            return dict(process=process_birth(pid),socket=identity(f'/run/user/{os.getuid()}/docker.sock',content=False),
                        executable=identity(root/'tools/dockerd',content=False))
        def run(argv):
            review_source(review)
            checked=daemon_binding is not None and argv[:3]==endpoint
            if checked:require(daemon_birth()==daemon_binding,'fixture_guest_daemon_replaced')
            data=backend.command(argv)
            if checked:require(daemon_birth()==daemon_binding,'fixture_guest_daemon_replaced')
            return data
        unit=Path.home()/'.config/systemd/user/docker.service'
        written=None
        try:
            for path in (unit,Path(f'/run/user/{os.getuid()}/docker.sock'),Path(f'/run/user/{os.getuid()}/docker.pid')):
                require(identity(path,content=False)['state']=='absent','fixture_guest_inherited_docker_preserve')
            require(run(['/usr/bin/sudo','-n','/usr/bin/systemctl','show','docker.service','--property=ActiveState','--value']).strip()
                    in (b'inactive',b'failed'),'fixture_guest_rootful_docker_active_preserve')
            # Freeze and hash all supplied offline inputs before any package or
            # system configuration mutation. Copies never share hardlinks.
            offline=root/'offline';offline.mkdir(mode=0o700)
            required={'manifest','interpreter_archive','installer_archive','image_archive','postgres_archive'}
            require(set(spec['files'])==required,'fixture_guest_offline_kit_incomplete')
            staged={}
            for name,row in spec['files'].items():
                require(time.monotonic()<backend.deadline,'fixture_guest_provision_budget_expired')
                source=absolute(row['path']);record=file_record(source.parent,source.name)
                require(record['sha256']==row['sha256'],'fixture_guest_input_changed:'+name)
                destination=offline/name
                journal.append('fixture_guest_copy_intent',path=str(destination),source=record)
                copy_regular(source.parent,source.name,destination,dict(record,mode=0o600),source_record=record)
                journal.append('fixture_guest_copy_complete',observed=identity(destination,content=False),sha256=record['sha256'])
                staged[name]=str(destination)
            wheels=offline/'wheels';wheels.mkdir(mode=0o700)
            for row in spec['wheels']:
                require(time.monotonic()<backend.deadline,'fixture_guest_provision_budget_expired')
                source=absolute(row['path']);record=file_record(source.parent,source.name)
                require(source.name.endswith('.whl') and record['sha256']==row['sha256'],'fixture_guest_wheel_changed')
                copy_regular(source.parent,source.name,wheels/source.name,dict(record,mode=0o600),source_record=record)
            launcher=spec['rootless_launcher']
            source=absolute(launcher['path']);record=file_record(source.parent,source.name)
            require(record['sha256']==launcher['sha256'],'fixture_rootless_launcher_changed')
            tools=root/'tools';tools.mkdir(mode=0o700)
            copy_regular(source.parent,source.name,tools/'dockerd-rootless.sh',dict(record,mode=0o700),source_record=record)
            # Exact package pins are inputs. No lock or package pin is inferred
            # from current registry popularity, and no PostgreSQL package runs.
            run(['/usr/bin/sudo','-n','/usr/bin/env','DEBIAN_FRONTEND=noninteractive','/usr/bin/apt-get','update'])
            run(['/usr/bin/sudo','-n','/usr/bin/env','DEBIAN_FRONTEND=noninteractive','/usr/bin/apt-get','install','-y','--no-install-recommends',*packages])
            run(['/usr/bin/sudo','-n','/usr/bin/systemctl','disable','--now','docker.service','docker.socket'])
            for name in ('dockerd','docker','containerd','runc'):
                executable=shutil.which(name,path='/usr/sbin:/usr/bin:/sbin:/bin')
                require(executable is not None,'fixture_guest_runtime_binary_missing:'+name)
                source=Path(executable).resolve()
                record=file_record(source.parent,source.name)
                copy_regular(source.parent,source.name,tools/name,dict(record,mode=0o700),source_record=record)
            account=pwd.getpwuid(os.getuid()).pw_name
            for name in ('subuid','subgid'):
                rows=[line.split(':') for line in Path('/etc/'+name).read_text().splitlines() if line.strip()]
                require(any(row[0]==account and int(row[2])>=65536 for row in rows),'fixture_subid_mapping_missing:'+name)
            # Ubuntu 24.04's restriction is changed only in this disposable VM,
            # never persisted to sysctl.d and never applied to the production host.
            before=run(['/usr/bin/sudo','-n','/usr/sbin/sysctl','-n','kernel.apparmor_restrict_unprivileged_userns']).decode().strip()
            journal.append('fixture_guest_sysctl_before',value=before)
            run(['/usr/bin/sudo','-n','/usr/sbin/sysctl','-w','kernel.apparmor_restrict_unprivileged_userns=0'])
            manager=f'user@{os.getuid()}.service'
            dropin=Path('/etc/systemd/system')/(manager+'.d')/'50-workload-fixture-delegate.conf'
            require(identity(dropin,content=False)['state']=='absent','fixture_guest_delegation_dropin_exists')
            run(['/usr/bin/sudo','-n','/usr/bin/install','-d','-m','0755',str(dropin.parent)])
            run(root_exclusive_write(dropin,b'[Service]\nDelegate=cpu cpuset io memory pids\n'))
            run(['/usr/bin/sudo','-n','/usr/bin/systemctl','daemon-reload'])
            # Never restart a user manager to obtain delegation. Fresh allocated
            # guests receive the template before first user-manager startup.
            controllers=Path(f'/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/{manager}/cgroup.controllers')
            require({'cpu','memory','pids'}<=set(controllers.read_text().split()),
                    'fixture_guest_delegation_requires_fresh_boot')
            (root/'docker-store').mkdir(mode=0o700)
            unit.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            contents=('[Unit]\nDescription=Disposable fixture rootless Docker\nRequires=dbus.socket\n[Service]\n'
                      'Environment=PATH='+str(tools)+':/usr/sbin:/usr/bin:/sbin:/bin\n'
                      'ExecStart='+str(tools/'dockerd-rootless.sh')+' --iptables=false --exec-opt native.cgroupdriver=systemd '+
                      '--data-root='+str(root/'docker-store')+' --pidfile=/run/user/'+str(os.getuid())+'/docker.pid\n'
                      'Delegate=yes\nType=notify\nNotifyAccess=all\nKillMode=control-group\nTimeoutStopSec=30\n'
                      'Restart=no\n[Install]\nWantedBy=default.target\n')
            journal.append('fixture_guest_unit_intent',path=str(unit),sha256=digest(contents.encode()))
            exclusive(unit,contents.encode());written=identity(unit)
            journal.append('fixture_guest_unit_created',observed=written)
            run(['/usr/bin/systemctl','--user','daemon-reload'])
            run(['/usr/bin/systemctl','--user','start','docker.service'])
            info=json.loads(run([*endpoint,'info','--format','{{json .}}']))
            require(info['CgroupDriver']=='systemd' and info['CgroupVersion']=='2' and
                    any('rootless' in v for v in info['SecurityOptions']),'fixture_guest_rootless_controls_unavailable')
            daemon_binding=daemon_birth()
            journal.append('fixture_guest_daemon_bound',observed=daemon_binding,daemon_id=info['ID'])
            bindings=json.loads(regular(offline,'manifest')[0])
            from deploy.workload_images import without_tags
            selected=dict(coordinator=bindings['coordinator_image'],worker=bindings['worker_environment']['image_id'])
            images=without_tags(offline/'image_archive',offline/'runtime-images.tar',selected)
            require(not images['tags'],'fixture_guest_mutable_image_tags')
            run([*endpoint,'load','--input',str(offline/'runtime-images.tar')])
            run([*endpoint,'load','--input',str(offline/'postgres_archive')])
            for image in [*selected.values(),spec['postgres_image']]:
                actual=json.loads(run([*endpoint,'image','inspect',image]))[0]
                require(actual['Id']==image and actual['Os']=='linux' and actual['Architecture']=='amd64','fixture_guest_image_binding')
            loaded=set(run([*endpoint,'image','ls','-aq','--no-trunc']).decode().split())
            require(loaded==set(selected.values())|{spec['postgres_image']},'fixture_guest_unplanned_image_loaded')
            exclusive(root/'complete.json',canonical(dict(fixture_only=True,daemon_id=info['ID'],unit=written,
                files=staged,wheels=str(wheels),postgres_image=spec['postgres_image'],package_versions=spec['packages'],
                rootless_launcher_sha256=launcher['sha256'],computational_services_started=0,network_download_phase_closed=True)))
            return root/'complete.json'
        except BaseException as error:
            cleanup='no_owned_daemon_started'
            backend.deadline=finish_deadline
            if written is not None:
                try:
                    require(identity(unit)==written,'fixture_guest_unit_replaced')
                    run(['/usr/bin/systemctl','--user','stop','docker.service'])
                    cleanup='owned_unit_stopped;resources_preserved'
                except Exception as stopped:cleanup='unresolved:'+str(stopped)
            exclusive(root/'failed.json',canonical(dict(error=type(error).__name__,message=str(error),cleanup=cleanup,automatic_retry=False)))
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path);parser.add_argument('--specification',type=Path,required=True)
    parser.add_argument('--component-review',type=Path,required=True);parser.add_argument('--budget',type=int,default=1200)
    args=parser.parse_args()
    print(provision(args.root,args.specification,args.component_review,budget=args.budget))


if __name__=='__main__':main()
