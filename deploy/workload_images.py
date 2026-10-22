"""Bound OCI image archive closure, without extraction, networking or execution.

Accept only OCI image manifests with Linux amd64 configurations. Docker's legacy
manifest must agree with the OCI graph; tags are recorded for overwrite guards.
"""
import hashlib
import gzip
import json
from pathlib import Path
import re
import tarfile

from deploy.workload_release import canonical,digest,file_record,relative,regular_path,stable_stat
from mldsafail.evaluator.native_workload import require

MANIFEST='application/vnd.oci.image.manifest.v1+json'
CONFIG='application/vnd.oci.image.config.v1+json'
LAYERS={'application/vnd.oci.image.layer.v1.tar','application/vnd.oci.image.layer.v1.tar+gzip','application/vnd.docker.image.rootfs.diff.tar.gzip'}


def normalized_tag(tag):
    first=tag.split('/')[0]
    if '/' not in tag:return 'docker.io/library/'+tag
    if '.' not in first and ':' not in first and first!='localhost':return 'docker.io/'+tag
    return tag


def inspect_archive(path,selected):
    path=Path(path);path,before=regular_path(path.parent,path.name)
    require(set(selected)=={'coordinator','worker'} and len(set(selected.values()))==2 and
            all(re.fullmatch('sha256:[a-f0-9]{64}',value) for value in selected.values()),'image_archive_selection')
    require(before.st_size<=2*1024**3,'image_archive_size_limit')
    with tarfile.open(path,mode='r:') as archive:
        members=archive.getmembers();require(len(members)<=10000,'image_archive_member_limit')
        rows={}
        for member in members:
            name=relative(member.name.rstrip('/'))
            require(name not in rows and (member.isdir() or member.isfile()),'image_archive_unsafe_member')
            rows[name]=member
            if member.isfile():
                require(name in ('manifest.json','index.json','oci-layout') or
                        re.fullmatch('blobs/sha256/[a-f0-9]{64}',name),'image_archive_unknown_member')
                stream=archive.extractfile(member);sha=hashlib.sha256()
                while chunk:=stream.read(1024**2):sha.update(chunk)
                if name.startswith('blobs/'):require(sha.hexdigest()==name.rsplit('/',1)[1],'image_archive_blob_changed')
        def load(name):
            row=rows.get(name)
            require(row is not None and row.isfile() and row.size<=4*1024**2,'image_archive_metadata_missing')
            def unique(pairs):
                result={}
                for key,value in pairs:
                    require(key not in result,'image_archive_duplicate_json_key');result[key]=value
                return result
            return json.loads(archive.extractfile(row).read(),object_pairs_hook=unique)
        require(load('oci-layout')==dict(imageLayoutVersion='1.0.0'),'image_archive_layout')
        index=load('index.json');require(index.get('schemaVersion')==2 and type(index.get('manifests')) is list,'image_archive_index')
        manifests=index['manifests']
        require(len(manifests)==2 and {row.get('digest') for row in manifests}==set(selected.values()),'image_archive_unapproved_image')
        referenced=set();configurations={};tags={};layers={};config_blobs={};uncompressed={};expanded=0
        def descriptor(row,types):
            require(type(row) is dict and set(row)<={'mediaType','digest','size','annotations','platform'} and row.get('mediaType') in types and
                    re.fullmatch('sha256:[a-f0-9]{64}',row.get('digest','')) and
                    type(row.get('size')) is int and row['size']>=0,'image_archive_descriptor')
            name='blobs/sha256/'+row['digest'].split(':')[1]
            require(name in rows and rows[name].isfile() and rows[name].size==row['size'],'image_archive_descriptor_changed')
            referenced.add(name);return name
        for entry in manifests:
            identifier=entry['digest'];name=descriptor(entry,{MANIFEST});image=load(name)
            require(image.get('schemaVersion')==2 and image.get('mediaType')==MANIFEST and type(image.get('layers')) is list,
                    'image_archive_manifest')
            config_name=descriptor(image['config'],{CONFIG});config=load(config_name)
            require(config.get('os')=='linux' and config.get('architecture')=='amd64' and
                    config.get('rootfs',{}).get('type')=='layers','image_archive_platform')
            layer_names=[descriptor(row,LAYERS) for row in image['layers']]
            require(len(layer_names)==len(config['rootfs'].get('diff_ids',[])),'image_archive_layer_configuration')
            for layer_name,layer,expected in zip(layer_names,image['layers'],config['rootfs']['diff_ids']):
                require(type(expected) is str and re.fullmatch('sha256:[a-f0-9]{64}',expected),'image_archive_diff_id')
                if layer_name not in uncompressed:
                    raw=archive.extractfile(rows[layer_name]);sha=hashlib.sha256()
                    stream=gzip.GzipFile(fileobj=raw) if layer['mediaType']!='application/vnd.oci.image.layer.v1.tar' else raw
                    with stream:
                        while chunk:=stream.read(1024**2):
                            expanded+=len(chunk);require(expanded<=4*before.st_size,'image_archive_expansion_limit');sha.update(chunk)
                    uncompressed[layer_name]='sha256:'+sha.hexdigest()
                require(uncompressed[layer_name]==expected,'image_archive_layer_diff_changed')
            configurations[identifier]=config;layers[identifier]=layer_names;config_blobs[identifier]=config_name
        legacy=load('manifest.json');require(type(legacy) is list and len(legacy)==2,'image_archive_docker_manifest')
        require({row.get('Config') for row in legacy}==set(config_blobs.values()),'image_archive_docker_configurations')
        for row in legacy:
            identifier=next(key for key,value in config_blobs.items() if value==row['Config'])
            require(row.get('Layers')==layers[identifier] and type(row.get('RepoTags')) is list and
                    all(type(tag) is str and re.fullmatch(r'[a-z0-9][a-z0-9./_-]*:[A-Za-z0-9_.-]+',tag) for tag in row['RepoTags']),
                    'image_archive_docker_layers_or_tags')
            for tag in row['RepoTags']:
                require(tag not in tags,'image_archive_duplicate_tag');tags[tag]=identifier
        for entry in manifests:
            allowed={normalized_tag(tag) for tag,value in tags.items() if value==entry['digest']}
            annotations=entry.get('annotations',{})
            require(set(annotations)<={'io.containerd.image.name','org.opencontainers.image.ref.name'} and
                    ('io.containerd.image.name' not in annotations or annotations['io.containerd.image.name'] in allowed) and
                    ('org.opencontainers.image.ref.name' not in annotations or annotations['org.opencontainers.image.ref.name'] in
                     allowed|{tag.rsplit(':',1)[1] for tag in allowed}), 'image_archive_tag_alias_changed')
        require({name for name in rows if name.startswith('blobs/') and rows[name].isfile()}==referenced,
                'image_archive_unreferenced_blob')
    require(stable_stat(path.lstat())==stable_stat(before),'image_archive_changed')
    record=file_record(path.parent,path.name)
    return dict(archive='offline/images.tar',sha256=record['sha256'],bytes=record['bytes'],selected=selected,
                tags=tags,configurations=configurations)


def validate_binding(manifest):
    row=manifest['images']
    require(set(row)=={'archive','sha256','bytes','selected','tags','configurations'} and row['archive']=='offline/images.tar' and
            manifest['files'].get(row['archive'])==dict(sha256=row['sha256'],bytes=row['bytes'],mode=0o600),
            'release_image_archive_binding')
    require(not row['tags'],'release_image_tags_forbidden')
    require(row['selected']==dict(coordinator=manifest['coordinator_image'],worker=manifest['worker_environment']['image_id']) and
            set(row['configurations'])==set(row['selected'].values()),'release_image_selection_changed')


def tag_guard(binding,existing):
    """An import may add tags or reaffirm them, never redirect an existing tag."""
    actual={normalized_tag(tag):identifier for tag,identifier in existing.items()}
    require(all(actual.get(normalized_tag(tag),identifier)==identifier for tag,identifier in binding['tags'].items()),
            'image_import_would_replace_existing_tag')


def installed(binding,inspect):
    rows={}
    for role,identifier in binding['selected'].items():
        row=inspect(identifier);expected=binding['configurations'][identifier]
        require(row['Id']==identifier and row['Os']=='linux' and row['Architecture']=='amd64' and
                all(row.get('Config',{}).get(key)==value for key,value in expected.get('config',{}).items()),
                'installed_image_configuration_changed')
        rows[role]=dict(id=identifier,configuration_sha256=digest(canonical(expected)))
    return rows


def without_tags(source,destination,selected):
    """Preserve image IDs while removing all load-time repository-tag writes."""
    inspect_archive(source,selected)
    source=Path(source);source,before=regular_path(source.parent,source.name)
    destination=Path(destination)
    require(not any(parent.is_symlink() for parent in destination.parents),'image_archive_destination_symlink')
    with destination.open('xb') as output,tarfile.open(source,'r:') as archive,tarfile.open(fileobj=output,mode='w') as target:
        for row in archive.getmembers():
            if row.isdir():target.addfile(row);continue
            stream=archive.extractfile(row)
            if row.name in ('index.json','manifest.json'):
                import io
                value=json.loads(stream.read())
                if row.name=='index.json':
                    for entry in value['manifests']:entry.pop('annotations',None)
                else:
                    for entry in value:entry['RepoTags']=[]
                data=canonical(value);row.size=len(data);stream=io.BytesIO(data)
            target.addfile(row,stream)
    require(stable_stat(source.lstat())==stable_stat(before),'image_archive_changed')
    result=inspect_archive(destination,selected)
    require(not result['tags'],'image_archive_tag_removal_failed')
    return result
