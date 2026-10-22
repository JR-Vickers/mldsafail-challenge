import io,json,tarfile
import pytest
from deploy.workload_images import inspect_archive,tag_guard,MANIFEST,CONFIG
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked


def fixture(path,*,architecture='amd64',tamper=False,alias=False,extra=False):
    blobs={};manifests=[];legacy=[];selected={}
    def blob(data):
        name='blobs/sha256/'+digest(data);blobs[name]=data;return name
    for role in ('coordinator','worker'):
        layer=blob((role+' layer').encode())
        config=blob(canonical(dict(os='linux',architecture=architecture,config=dict(Labels=dict(role=role)),
                                  rootfs=dict(type='layers',diff_ids=['sha256:'+digest(blobs[layer])]))))
        descriptor=lambda name,kind:dict(mediaType=kind,digest='sha256:'+name.rsplit('/',1)[1],size=len(blobs[name]))
        image=blob(canonical(dict(schemaVersion=2,mediaType=MANIFEST,config=descriptor(config,CONFIG),
                                  layers=[descriptor(layer,'application/vnd.oci.image.layer.v1.tar')])) )
        identifier='sha256:'+image.rsplit('/',1)[1];selected[role]=identifier
        entry=descriptor(image,MANIFEST)
        if alias:entry['annotations']={'io.containerd.image.name':'docker.io/library/retained:latest'}
        manifests.append(entry);legacy.append(dict(Config=config,Layers=[layer],RepoTags=['fixture-'+role+':1']))
    if tamper:blobs[next(iter(blobs))]=b'tampered'
    if extra:blob(b'unapproved extra blob')
    blobs.update({'oci-layout':canonical(dict(imageLayoutVersion='1.0.0')),
                  'index.json':canonical(dict(schemaVersion=2,manifests=manifests)),
                  'manifest.json':canonical(legacy)})
    with tarfile.open(path,'w') as archive:
        for name,data in blobs.items():
            row=tarfile.TarInfo(name);row.size=len(data);archive.addfile(row,io.BytesIO(data))
    return selected


def test_complete_two_image_closure_and_tag_guards(tmp_path):
    path=tmp_path/'images.tar';selected=fixture(path);bound=inspect_archive(path,selected)
    assert bound['selected']==selected
    tag_guard(bound,{})
    tag_guard(bound,{'docker.io/library/fixture-coordinator:1':selected['coordinator']})
    with pytest.raises(WorkloadBlocked,match='replace_existing_tag'):
        tag_guard(bound,{'fixture-coordinator:1':'sha256:'+'f'*64})


@pytest.mark.parametrize('options,reason',[({'tamper':True},'blob_changed'),({'architecture':'arm64'},'platform'),
    ({'alias':True},'tag_alias_changed'),({'extra':True},'unreferenced_blob')])
def test_unapproved_archive_content_is_rejected(tmp_path,options,reason):
    path=tmp_path/'images.tar';selected=fixture(path,**options)
    with pytest.raises(WorkloadBlocked,match=reason):inspect_archive(path,selected)


def test_tag_free_archive_preserves_exact_image_identities(tmp_path):
    from deploy.workload_images import without_tags
    original=tmp_path/'original.tar';selected=fixture(original)
    bound=without_tags(original,tmp_path/'frozen.tar',selected)
    assert bound['selected']==selected and bound['tags']=={}
    assert inspect_archive(tmp_path/'frozen.tar',selected)==bound
