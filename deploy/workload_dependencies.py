"""Lock-derived offline wheel closure and installed dependency byte inventory.

No network, lock mutation or source builds. Unsupported marker/specifier syntax
fails rather than guessing. The exact installer still performs an offline solve
when the dependency environment is built in a disposable target installation.
"""
import ast
from email.parser import BytesParser
import hashlib
import os
from pathlib import Path
import re
import stat
import tomllib
from urllib.parse import unquote, urlparse
import zipfile

from deploy.workload_release import canonical, digest, regular
from deploy.workload_wheels import compatible, inspect_wheel
from mldsafail.evaluator.native_workload import require

ENV = dict(python_version='3.12', python_full_version='3.12.0', sys_platform='linux',
           platform_system='Linux', platform_machine='x86_64', implementation_name='cpython',
           platform_python_implementation='CPython', os_name='posix', extra='')


def version(value):
    require(re.fullmatch(r'\d+(?:\.\d+)*',value) is not None,'dependency_version_syntax_unsupported')
    return tuple(int(v) for v in value.split('.'))+(0,)*max(0,4-len(value.split('.')))


def marker(expression,env):
    tree=ast.parse(expression,mode='eval')
    def evaluate(node):
        if isinstance(node,ast.Constant) and type(node.value) is str: return node.value
        if isinstance(node,ast.Name):
            require(node.id in env,'dependency_unknown_marker'); return env[node.id]
        if isinstance(node,ast.BoolOp):
            values=[evaluate(v) for v in node.values]
            require(all(type(v) is bool for v in values),'dependency_marker_not_boolean')
            return all(values) if isinstance(node.op,ast.And) else any(values)
        if isinstance(node,ast.Compare) and len(node.ops)==len(node.comparators)==1:
            left,right=evaluate(node.left),evaluate(node.comparators[0]); op=node.ops[0]
            if isinstance(op,ast.In): return left in right
            if isinstance(op,ast.NotIn): return left not in right
            if isinstance(op,ast.Eq): return left==right
            if isinstance(op,ast.NotEq): return left!=right
            require(re.fullmatch(r'\d+(?:\.\d+)*',left) and re.fullmatch(r'\d+(?:\.\d+)*',right),'dependency_marker_comparison_unsupported')
            a,b=version(left),version(right)
            if isinstance(op,ast.Lt): return a<b
            if isinstance(op,ast.LtE): return a<=b
            if isinstance(op,ast.Gt): return a>b
            if isinstance(op,ast.GtE): return a>=b
        require(False,'dependency_marker_syntax_unsupported')
    result=evaluate(tree.body); require(type(result) is bool,'dependency_marker_not_boolean'); return result


def normalized(name): return re.sub(r'[-_.]+','-',name).lower()


def satisfies(selected,specifier):
    if not specifier: return True
    target=version(selected)
    for clause in specifier.strip(' ()').split(','):
        match=re.fullmatch(r'\s*(~=|==|!=|>=|<=|>|<)\s*(\d+(?:\.\d+)*(?:\.\*)?)\s*',clause)
        require(match is not None,'dependency_specifier_unsupported')
        op,text=match.groups()
        if text.endswith('.*'):
            require(op in ('==','!='),'dependency_wildcard_unsupported')
            equal=selected.split('.')[:len(text.split('.'))-1]==text.split('.')[:-1]
            if equal != (op=='=='): return False
            continue
        other=version(text)
        if op=='~=':
            parts=[int(v) for v in text.split('.')]; require(len(parts)>=2,'dependency_compatible_specifier_invalid')
            upper=parts[:-1]; upper[-1]+=1
            if not other<=target<version('.'.join(map(str,upper))): return False
        elif not {'==':target==other,'!=':target!=other,'>=':target>=other,'<=':target<=other,'>':target>other,'<':target<other}[op]: return False
    return True


def closure(lock_bytes,*,python_full_version='3.12.0',extras=()):
    lock=tomllib.loads(lock_bytes.decode()); env={**ENV,'python_full_version':python_full_version}
    require(python_full_version.startswith('3.12.'),'dependency_wrong_python')
    packages={}
    for row in lock['package']:
        if row.get('resolution-markers') and not any(marker(m,env) for m in row['resolution-markers']): continue
        name=normalized(row['name']); require(name not in packages,'dependency_ambiguous_lock_package'); packages[name]=row
    project=packages.get('mldsafail-challenge'); require(project is not None,'dependency_project_missing')
    selected={}; pending=list(project.get('dependencies',[])); processed=set()
    for extra in extras:
        require(extra in project.get('optional-dependencies',{}),'dependency_project_extra_unresolved')
        pending.extend(project['optional-dependencies'][extra])
    while pending:
        edge=pending.pop()
        if edge.get('marker') and not marker(edge['marker'],env): continue
        name=normalized(edge['name']); require(name in packages,'dependency_unresolved:'+name)
        row=packages[name]
        require(row.get('source',{}).get('registry')=='https://pypi.org/simple','dependency_unbound_source')
        require(not edge.get('version') or edge['version']==row['version'],'dependency_lock_edge_changed')
        selected[name]=row
        extras=edge.get('extra',[])
        key=(name,tuple(sorted(extras)))
        if key in processed: continue
        processed.add(key); pending.extend(row.get('dependencies',[]))
        for extra in extras:
            require(extra in row.get('optional-dependencies',{}),'dependency_extra_unresolved')
            pending.extend(row['optional-dependencies'][extra])
    return selected,env


def wheel_candidates(lock_bytes,*,python_full_version='3.12.0',extras=()):
    packages,_=closure(lock_bytes,python_full_version=python_full_version,extras=extras)
    result={}
    for name,row in packages.items():
        candidates=[]
        for wheel in row.get('wheels',[]):
            filename=unquote(Path(urlparse(wheel['url']).path).name)
            parts=filename[:-4].split('-')
            if filename.endswith('.whl') and len(parts) in (5,6) and any(compatible(f'{p}-{a}-{s}',glibc_minor=28) for p in parts[-3].split('.') for a in parts[-2].split('.') for s in parts[-1].split('.')):
                candidates.append(dict(wheel,filename=filename))
        require(candidates,'dependency_compatible_wheel_missing:'+name)
        result[name]=candidates
    return result


def plan(lock_bytes,wheels,*,python_full_version='3.12.0'):
    packages,env=closure(lock_bytes,python_full_version=python_full_version)
    rows={}; paths={}
    for path in wheels:
        path=Path(path); data,_=regular(path.parent,path.name)
        metadata=inspect_wheel(path,digest(data),glibc_minor=28); name=normalized(metadata['name'])
        require(name in packages and name not in rows,'dependency_extra_or_duplicate_wheel')
        package=packages[name]
        require(metadata['version']==package['version'] and any(w['hash']=='sha256:'+metadata['sha256'] for w in package.get('wheels',[])),
                'dependency_artifact_not_locked')
        rows[name]=metadata; paths[name]=path
    require(set(rows)==set(packages),'dependency_closure_incomplete:'+','.join(sorted(set(packages)-set(rows))))
    # Independently validate wheel metadata requirements, including extras.
    active_extras={name:{''} for name in packages}
    for row in packages.values():
        for edge in row.get('dependencies',[]):
            if not edge.get('marker') or marker(edge['marker'],env):
                active_extras.setdefault(normalized(edge['name']),{''}).update(edge.get('extra',[]))
    project=next(r for r in tomllib.loads(lock_bytes.decode())['package'] if r['name']=='mldsafail-challenge')
    for edge in project['dependencies']: active_extras.setdefault(normalized(edge['name']),{''}).update(edge.get('extra',[]))
    changed=True
    while changed:
        changed=False
        for name,row in rows.items():
            for requirement in row['requires']:
                expression,sep,condition=requirement.partition(';')
                if sep and not any(marker(condition.strip(),{**env,'extra':extra}) for extra in active_extras[name]): continue
                match=re.fullmatch(r'\s*([A-Za-z0-9_.-]+)(?:\[([A-Za-z0-9_,.-]+)\])?\s*(.*?)\s*',expression)
                require(match is not None,'dependency_requirement_syntax')
                required,extras,specifier=match.groups(); required=normalized(required)
                require(required in rows,'dependency_metadata_unresolved:'+required)
                require(satisfies(rows[required]['version'],specifier),'dependency_metadata_version_conflict')
                prior=set(active_extras[required]); active_extras[required].update(extras.split(',') if extras else [])
                changed=changed or prior!=active_extras[required]
    requirements=''.join(name+'=='+rows[name]['version']+' --hash=sha256:'+rows[name]['sha256']+'\n' for name in sorted(rows))
    return dict(lock_sha256=digest(lock_bytes),wheels={'offline/'+paths[name].name:rows[name]['sha256'] for name in sorted(rows)},
                requirements_sha256=digest(requirements.encode()),target='cpython-3.12-linux-x86_64-glibc2.28'),requirements


def installed_inventory(venv, *, interpreter=None):
    """Read actual installed bytes and modes, including generated bin entrypoints.

    Interpreter symlinks are separately bound tools. Bytecode is never expected;
    installing and importing uses PYTHONDONTWRITEBYTECODE=1.
    """
    root=Path(venv); result={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            path=Path(parent)/name
            if path.is_symlink():
                require(path==root/'lib64' and os.readlink(path)=='lib','dependency_installed_directory_symlink')
        for name in files:
            path=Path(parent)/name
            if path.is_symlink():
                require(path.parent==root/'bin' and name in ('python','python3','python3.12') and
                        interpreter is not None and path.resolve()==Path(interpreter).resolve(),
                        'dependency_installed_interpreter_changed')
                continue
            info=path.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'dependency_installed_unknown_file')
            data,_=regular(path.parent,path.name)
            result[str(path.relative_to(root))]=dict(sha256=digest(data),bytes=len(data),mode=stat.S_IMODE(info.st_mode))
    require(result,'dependency_installed_empty')
    return result


def entrypoint_code(bundle,python,module,function):
    require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',module) and
            re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',function),'dependency_entrypoint_invalid')
    return ('#!'+str(python)+'\nimport sys\nsys.dont_write_bytecode = True\nsys.path[:0] = '+
            repr([str(Path(bundle)/'src'),str(bundle)])+'\nfrom '+module+' import '+function+
            '\nif __name__ == "__main__":\n    sys.exit('+function+'())\n').encode()


def project_entrypoints(bundle,venv):
    """Deterministic source-package entrypoints built at their final paths."""
    from deploy.workload_installation import exclusive
    bundle=Path(bundle);venv=Path(venv)
    project=tomllib.loads(regular(bundle,'pyproject.toml')[0].decode())['project']
    for name,target in project['scripts'].items():
        require(re.fullmatch(r'[A-Za-z0-9_-]+',name) and
                re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*',target),
                'dependency_entrypoint_invalid')
        module,function=target.split(':')
        exclusive(venv/'bin'/name,entrypoint_code(bundle,venv/'bin/python',module,function),0o700)


def entrypoint_import_command(bundle,venv,*,release_files=None):
    """Import runtime entrypoints in isolated Python with network namespace disabled."""
    bundle=Path(bundle);venv=Path(venv)
    project=tomllib.loads(regular(bundle,'pyproject.toml')[0].decode())['project']
    declared={target.split(':')[0] for target in project['scripts'].values()}
    helpers={
        'mldsafail.evaluator.workload_service','mldsafail.evaluator.native_workload',
        'mldsafail.evaluator.coordinator','mldsafail.evaluator.worker','mldsafail.evaluator.workload_controller','mldsafail.evaluator.workload_router',
        'deploy.workload_images','deploy.workload_prerequisites','scripts.prepare_workload_packet',
        'deploy.workload_installation','deploy.workload_installed','deploy.workload_native_acceptance',
        'deploy.workload_artifacts','deploy.workload_socket_probe','deploy.workload_watchdog',
        'scripts.inspect_workload_rollback','scripts.workload_cgroup_collection',
        'deploy.workload_acceptance_packet','deploy.workload_observation','scripts.workload_control_packet'}
    if release_files is not None:
        # A preserved release imports its own frozen helper set, rather than
        # depending on deployment modules introduced by a newer checkout.
        essentials={'mldsafail.evaluator.workload_service','mldsafail.evaluator.native_workload',
                    'mldsafail.evaluator.workload_controller','mldsafail.evaluator.workload_router'}
        def source_name(name):return ('src/' if name.startswith('mldsafail.') else '')+name.replace('.','/')+'.py'
        require(all(source_name(name) in release_files for name in essentials),'dependency_rollback_runtime_incomplete')
        helpers={name for name in helpers if source_name(name) in release_files}
    modules=sorted(declared|helpers)
    require(all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*',name) for name in modules),'dependency_import_module_invalid')
    code=('import sys,importlib,json;sys.dont_write_bytecode=True;sys.path[:0]='+repr([str(bundle/'src'),str(bundle)])+
          ';modules='+repr(modules)+';[importlib.import_module(name) for name in modules];print(json.dumps(modules))')
    return ['/usr/bin/sudo','-n','/usr/bin/unshare','--net','--setgid='+str(os.getgid()),'--setuid='+str(os.getuid()),
            str(venv/'bin/python'),'-I','-B','-c',code],modules
