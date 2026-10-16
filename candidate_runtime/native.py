"""Fixed private rootless application admission; never host-root or evaluator access."""
from pathlib import Path
import re


def application_create(*,name,image,role,network,application_parent,gateway_root,config_path,work_root):
    if role not in {'web','coordinator'} or not re.fullmatch('candidate-[a-z0-9-]{1,64}',name):
        raise ValueError('Fixed private candidate role/name required')
    if not re.fullmatch('sha256:[0-9a-f]{64}',image):raise ValueError('Immutable application image required')
    if not re.fullmatch('candidate-[a-z0-9-]{1,64}',network):raise ValueError('Dedicated private application network required')
    if not re.fullmatch('mldsafail-(owned|cpu)-workers-[a-f0-9]+\\.slice',application_parent):
        raise ValueError('Owned application slice required')
    paths={key:Path(value) for key,value in dict(gateway=gateway_root,config=config_path,work=work_root).items()}
    for path in paths.values():
        if not path.is_absolute() or any(part.is_symlink() for part in (path,*path.parents)) or ',' in str(path):
            raise ValueError('Canonical fixed private application mounts required')
    if len(set(paths.values()))!=3:raise ValueError('Separate gateway/config/work mounts required')
    args=['docker','create','--name',name,'--label','org.mldsafail.candidate=private-unapproved',
        '--user','0:0','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','64','--memory','512m','--network',network,'--cgroup-parent',application_parent,
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=32m',
        '--mount','type=bind,src='+str(paths['gateway'])+',dst=/candidate/gateway,readonly',
        '--mount','type=bind,src='+str(paths['config'])+',dst=/candidate/config.json,readonly',
        '--mount','type=bind,src='+str(paths['work'])+',dst=/candidate/work']
    return [*args,image,role,'--config','/candidate/config.json']
