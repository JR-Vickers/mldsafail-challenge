"""Bound standalone interpreter/installer archives, without build or network steps."""
import io
import os
from pathlib import Path,PurePosixPath
import posixpath
import stat
import tarfile

from deploy.workload_release import canonical,digest,regular,relative
from mldsafail.evaluator.native_workload import require


def archive_inventory(data):
    require(len(data)<=256*1024**2,'tool_archive_too_large')
    rows={};total=0
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as archive:
        members=archive.getmembers()
        require(len(members)<=10000,'tool_archive_member_limit')
        for member in members:
            name=relative(member.name.rstrip('/'))
            require(name!='.','tool_archive_root_member')
            require(name not in rows,'tool_archive_duplicate')
            if member.isdir():rows[name]=dict(kind='directory',mode=0o700)
            elif member.issym():
                target=member.linkname
                require(target and not target.startswith('/') and '\\' not in target,'tool_archive_symlink_target')
                resolved=posixpath.normpath(str(PurePosixPath(name).parent/target))
                relative(resolved)
                rows[name]=dict(kind='symlink',target=target,resolved=resolved)
            elif member.isfile() or member.islnk():
                if member.islnk():relative(member.linkname)
                require(0<=member.size<=512*1024**2-total,'tool_archive_expansion_limit')
                stream=archive.extractfile(member);require(stream is not None,'tool_archive_file_missing')
                contents=stream.read();total+=len(contents)
                require(total<=512*1024**2,'tool_archive_expansion_limit')
                rows[name]=dict(kind='file',sha256=digest(contents),bytes=len(contents),mode=0o700 if member.mode&0o111 else 0o600)
            else:require(False,'tool_archive_special_member')
        for name,row in rows.items():
            for parent in PurePosixPath(name).parents:
                if str(parent)=='.':continue
                require(rows.get(str(parent),{}).get('kind','directory')=='directory','tool_archive_symlink_parent')
            if row['kind']=='symlink':
                target=row['resolved'];seen={name}
                while rows.get(target,{}).get('kind')=='symlink':
                    require(target not in seen,'tool_archive_symlink_cycle');seen.add(target);target=rows[target]['resolved']
                require(target in rows,'tool_archive_unresolved_symlink')
    return rows


def verify_tree(root,expected):
    root=Path(root);require(not any(parent.is_symlink() for parent in root.parents),'tool_parent_symlink')
    require(root.is_dir() and not root.is_symlink() and root.stat().st_uid==os.getuid() and
            stat.S_IMODE(root.stat().st_mode)==0o700,'tool_root_invalid')
    actual={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in [*dirs,*files]:
            path=Path(parent)/name;key=str(path.relative_to(root));info=path.lstat()
            require(info.st_uid==os.getuid(),'tool_installed_owner_changed')
            if stat.S_ISLNK(info.st_mode):actual[key]=dict(kind='symlink',target=os.readlink(path),resolved=posixpath.normpath(str(PurePosixPath(key).parent/os.readlink(path))))
            elif stat.S_ISDIR(info.st_mode):actual[key]=dict(kind='directory',mode=stat.S_IMODE(info.st_mode))
            else:
                contents,mode=regular(path.parent,path.name)
                actual[key]=dict(kind='file',sha256=digest(contents),bytes=len(contents),mode=mode)
    # Parent directory entries can be implicit in a tar stream.
    expanded=dict(expected)
    for name in expected:
        for parent in PurePosixPath(name).parents:
            if str(parent)!='.':expanded.setdefault(str(parent),dict(kind='directory',mode=0o700))
    require(actual==expanded,'tool_installed_tree_changed')
    return actual


def extract(data,root,expected):
    """Exclusive regular copies, including tar hardlinks, then internal symlinks."""
    from deploy.workload_installation import exclusive,sync_directory
    require(archive_inventory(data)==expected,'tool_archive_inventory_changed')
    root=Path(root);require(not any(parent.is_symlink() for parent in root.parents),'tool_parent_symlink')
    root.mkdir(mode=0o700,exist_ok=False)
    directories=set()
    for name,row in expected.items():
        directories.update(str(parent) for parent in PurePosixPath(name).parents if str(parent)!='.')
        if row['kind']=='directory':directories.add(name)
    for name in sorted(directories,key=lambda value:(len(PurePosixPath(value).parts),value)):
        (root/name).mkdir(mode=0o700,exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as archive:
        by_name={member.name.rstrip('/'):member for member in archive.getmembers()}
        for name,row in expected.items():
            if row['kind']=='directory':(root/name).mkdir(mode=0o700,parents=True,exist_ok=True)
            elif row['kind']=='file':
                path=root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                exclusive(path,archive.extractfile(by_name[name]).read(),row['mode'])
        for name,row in expected.items():
            if row['kind']=='symlink':
                path=root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.symlink(row['target'],path);sync_directory(path.parent)
    verify_tree(root,expected);sync_directory(root.parent)


def describe(path, *, role,version,entrypoint):
    path=Path(path);data,_=regular(path.parent,path.name)
    members=archive_inventory(data);relative(entrypoint)
    require(members.get(entrypoint,{}).get('kind')=='file' and members[entrypoint]['mode']==0o700,
            'tool_archive_entrypoint_missing')
    return dict(archive='offline/tools/'+role+'.tar.gz',sha256=digest(data),bytes=len(data),
                version=version,entrypoint=entrypoint,members=members)


def validate_tools(manifest):
    tools=manifest['tools']
    require(set(tools)=={'interpreter','installer'},'release_tool_roles')
    for role,row in tools.items():
        require(set(row)=={'archive','sha256','bytes','version','entrypoint','members'},'release_tool_fields')
        require(row['archive']=='offline/tools/'+role+'.tar.gz','release_tool_archive_role')
        record=manifest['files'].get(row['archive'])
        require(record==dict(sha256=row['sha256'],bytes=row['bytes'],mode=0o600),'release_tool_archive_binding')
        require(row['members'].get(row['entrypoint'],{}).get('kind')=='file','release_tool_entrypoint')
    require(tools['interpreter']['version']=='3.12.10' and tools['installer']['version']=='0.13.1','release_tool_version')
    require(manifest.get('inclusion_policy',{}).get('name')=='tracked-complete-runtime-v1' and
            set(manifest['inclusion_policy']['sources'])<=set(manifest['files']),'release_inclusion_policy')
    require(manifest.get('dependency_plan',{}).get('lock_sha256')==manifest['files'].get('uv.lock',{}).get('sha256'),
            'release_tool_lock_binding')


def verify_installed_tools(release,manifest):
    """Verify every tool file, including interpreter stdlib and shared libraries."""
    require('tools' in manifest,'installed_offline_tool_bindings_missing')
    root=Path(release)/'tools'
    require(root.is_dir() and not root.is_symlink() and root.stat().st_uid==os.getuid() and
            stat.S_IMODE(root.stat().st_mode)==0o700 and
            {path.name for path in root.iterdir()}==set(manifest['tools']), 'installed_tool_roles_changed')
    return {role:digest(canonical(verify_tree(root/role,row['members']))) for role,row in manifest['tools'].items()}
