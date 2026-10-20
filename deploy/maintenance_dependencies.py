"""Static import closure and explicit external runtime requirements; no imports."""
import ast
import hashlib
from pathlib import Path
import sys
import tomllib


def source_closure(root, entries):
    root=Path(root).resolve(strict=True)
    pending=list(entries)
    files, external, dynamic, commands = {}, set(), [], set()
    def module_paths(module):
        stem=module.replace('.', '/')
        for prefix in ('', 'src/'):
            path=root/(prefix+stem+'.py')
            if path.is_file():
                return [path]
            package=root/(prefix+stem)/'__init__.py'
            if package.is_file():
                return [package]
        return []
    while pending:
        relative=pending.pop()
        if relative in files:
            continue
        path=root/relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('operator_source_dependency_missing')
        data=path.read_bytes()
        files[relative]=hashlib.sha256(data).hexdigest()
        tree=ast.parse(data,filename=relative)
        parts=Path(relative).with_suffix('').parts
        if parts[0]=='src': parts=parts[1:]
        package=list(parts[:-1])
        for index in range(1,len(package)+1):
            for parent in module_paths('.'.join(package[:index])):
                pending.append(str(parent.relative_to(root)))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):
                names=[a.name for a in node.names]
            elif isinstance(node,ast.ImportFrom):
                base=package[:len(package)-node.level+1] if node.level else []
                if node.module: base+=node.module.split('.')
                stem='.'.join(base)
                if stem: names.append(stem)
                names += ['.'.join([*base,a.name]) for a in node.names if a.name!='*' and module_paths('.'.join([*base,a.name]))]
                if any(a.name=='*' for a in node.names):
                    dynamic.append(dict(file=relative,line=node.lineno,reason='wildcard import requires review'))
            for name in names:
                found=module_paths(name)
                if found:
                    pending += [str(p.relative_to(root)) for p in found]
                elif ((root/name.replace('.','/')).is_dir() or (root/'src'/name.replace('.','/')).is_dir()):
                    pass  # Local namespace package; child imports are traversed.
                elif name.split('.')[0] not in sys.stdlib_module_names:
                    external.add(name.split('.')[0])
            if isinstance(node,ast.Call):
                function=node.func
                if isinstance(function,ast.Name) and function.id in ('__import__','eval','exec'):
                    dynamic.append(dict(file=relative,line=node.lineno,reason=function.id))
                if isinstance(function,ast.Attribute) and function.attr in ('import_module','spec_from_file_location'):
                    dynamic.append(dict(file=relative,line=node.lineno,reason=function.attr))
                if isinstance(function,ast.Attribute) and function.attr in ('run','Popen','check_output','check_call') and node.args:
                    argv=node.args[0]
                    if isinstance(argv,(ast.List,ast.Tuple)) and argv.elts and isinstance(argv.elts[0],ast.Constant) and isinstance(argv.elts[0].value,str):
                        commands.add(argv.elts[0].value)
    lock=tomllib.loads((root/'uv.lock').read_text())
    locked={p['name']:p['version'] for p in lock['package'] if 'version' in p}
    aliases={'psycopg':'psycopg','yaml':'pyyaml','PIL':'pillow','dotenv':'python-dotenv'}
    requirements={name:dict(distribution=aliases.get(name,name.replace('_','-')),
                            version=locked.get(aliases.get(name,name.replace('_','-')))) for name in sorted(external)}
    return dict(source_files=files,external_imports=requirements,runtime_commands=sorted(commands),
                dynamic_review=dynamic,lock_sha256=hashlib.sha256((root/'uv.lock').read_bytes()).hexdigest(),
                runtime_complete=False,complete=False,
                limitation='Static transitive source closure; native/runtime/configuration and dynamic entries require inspected review')
