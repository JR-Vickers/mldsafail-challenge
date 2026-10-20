"""Explicit hash-preserving dependency relocation, without command execution."""
import hashlib
import json
import os
from pathlib import Path
import shutil

from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json, safe_path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference_file(root, relative):
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('bundle_reference_must_be_relative')
    return safe_path(root/path)


def materialize(destination, files, references, *, unresolved):
    """Each edge names a JSON-pointer field and its exact relative target.

    Private receipt bytes are never rewritten. Caller supplies all edges explicitly;
    unknown runtime/import/configuration dependencies remain blockers.
    """
    destination=safe_path(Path(destination).absolute())
    destination.mkdir(mode=0o700)
    digests={}
    for relative, row in files.items():
        source=safe_path(Path(row['source']).absolute())
        if sha(source)!=row['sha256']:
            raise ValueError('bundle_source_hash_mismatch')
        st=source.stat()
        if not source.is_file() or st.st_nlink!=1:
            raise ValueError('bundle_source_ownership_ambiguous')
        target=reference_file(destination,relative)
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(source.read_bytes())
        target.chmod(0o600)
        digests[relative]=row['sha256']
    manifest=dict(schema='mldsafail.maintenance-bundle.v1',files=digests,references=references,
                  unresolved=unresolved,static_mapping_complete=not unresolved,complete=False,transferable=False)
    atomic_json(destination/'bundle.json',manifest)
    validate(destination)
    return manifest


def validate(root):
    root=safe_path(Path(root).absolute())
    manifest=read_manifest(root/'bundle.json')
    expected=set(manifest['files'])|{'bundle.json'}
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    if actual!=expected:
        raise ValueError('bundle_file_set_mismatch')
    for relative,digest in manifest['files'].items():
        path=reference_file(root,relative)
        st=path.stat()
        if not path.is_file() or st.st_nlink!=1 or st.st_uid!=os.getuid() or st.st_mode&0o077 or sha(path)!=digest:
            raise ValueError('bundle_identity_mismatch')
    for edge in manifest['references']:
        source=reference_file(root,edge['source'])
        value=json.loads(source.read_text())
        # JSON pointer, including escaped '/' in dictionary keys.
        pointer=edge['pointer']
        if not pointer.startswith('/'):
            raise ValueError('bundle_pointer_invalid')
        for part in pointer[1:].split('/'):
            part=part.replace('~1','/').replace('~0','~')
            value=value[int(part)] if isinstance(value,list) else value[part]
        if value!=edge['relative_target']:
            raise ValueError('bundle_reference_changed')
        relative=Path(value)
        if relative.is_absolute() or '..' in relative.parts:
            # Parent references may be retained only by placing their source at
            # a depth where canonical target remains inside the bundle.
            if relative.is_absolute():
                raise ValueError('bundle_reference_not_relocatable')
        target=source.parent/relative
        resolved=target.resolve(strict=True)
        if not resolved.is_relative_to(root) or any(p.is_symlink() for p in (target,*target.parents)):
            raise ValueError('bundle_reference_escape')
        if str(resolved.relative_to(root)) not in manifest['files']:
            raise ValueError('bundle_dependency_missing')
        if edge.get('sha256') and sha(resolved)!=edge['sha256']:
            raise ValueError('bundle_reference_hash_mismatch')
    return dict(valid=True,dependencies_complete=manifest['complete'],transferable=False,
                unresolved=manifest['unresolved'])
