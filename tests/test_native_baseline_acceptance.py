import hashlib
from pathlib import Path
import pytest
from scripts.native_baseline_acceptance import build_context


def test_frozen_build_context_is_minimal_and_preserves_scientific_bytes(tmp_path,monkeypatch):
    from mldsafail.benchmark_v050 import execution
    wheels=tmp_path/'input';wheels.mkdir()
    pins={'cysignals-1.12.5-cp312-cp312-manylinux2014_x86_64.whl':'eccbcfd762de37daf4a01a0a77ef653561a153c48c2db9104916d36ebbd3cf24',
        'fpylll-0.6.4-cp312-cp312-manylinux2014_x86_64.whl':'05f43362f2803207a8a6dfe5bad41c64df2479cded1338490bad773ca78b5ba1'}
    real=hashlib.sha256
    from types import SimpleNamespace
    mapping={name.encode():checksum for name,checksum in pins.items()}
    class Hash:
        def __init__(self,data=b''):self.data=data
        def update(self,data):self.data+=data
        def hexdigest(self):return mapping[self.data] if self.data in mapping else real(self.data).hexdigest()
    monkeypatch.setattr(hashlib,'sha256',Hash)
    for name in pins:(wheels/name).write_bytes(name.encode())
    context=tmp_path/'context';files=build_context(context,wheels,pins,'sha256:'+'a'*64,architecture='amd64')
    source=Path(execution.__file__).parent
    assert set(path.name for path in (context/'mldsafail/benchmark_v050').iterdir())==set(execution.WORKER_FILES)
    for name in execution.WORKER_FILES:assert (context/'mldsafail/benchmark_v050'/name).read_bytes()==(source/name).read_bytes()
    assert not any('generator' in name or 'evidence' in name or '.venv' in name for name in files)
    assert (context/'Dockerfile').read_text().split('\n',1)[1]==(source/'Dockerfile').read_text().split('\n',1)[1]


def test_changed_dependency_inventory_is_rejected(tmp_path):
    wheels=tmp_path/'input';wheels.mkdir();(wheels/'unexpected.whl').write_bytes(b'changed')
    with pytest.raises(ValueError,match='AMD64 wheel'):
        build_context(tmp_path/'context',wheels,{'expected.whl':'b'*64},'sha256:'+'a'*64,architecture='amd64')


def test_callback_rejects_unloaded_image_before_host_operation(monkeypatch,tmp_path):
    from scripts import native_baseline_acceptance as native, baseline_production_rehearsal
    from types import SimpleNamespace
    called=[]
    monkeypatch.setattr(native,'protocol',lambda *args:{'rehearsal':{'images':{'web':'sha256:'+'a'*64}}})
    monkeypatch.setattr(baseline_production_rehearsal,'execute',lambda *args:called.append('host'))
    with pytest.raises(ValueError,match='pinned driver artifacts'):
        native.baseline_callback(SimpleNamespace(path=tmp_path/'driver.json'),{}, {'loaded_images':[]})
    assert called==[]


def test_base_provenance_requires_original_registry_mapping(monkeypatch,tmp_path):
    from scripts.native_baseline_acceptance import verify_base_provenance
    from deploy import owned_daemon
    from mldsafail.benchmark_v050 import execution
    from types import SimpleNamespace
    source=Path(execution.__file__).parent/'Dockerfile'
    registry=source.read_text().splitlines()[0].removeprefix('FROM ')
    image='sha256:'+'a'*64
    proof=dict(schema='mldsafail.native-image-provenance.v1',status='passed',native_executed=True,
        registry_reference=registry,image=image,architecture='amd64',image_archive_sha256='b'*64,
        source_dockerfile_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),evidence_refs=['original-private-inspection'],
        original_image_inspection={'Id':image,'Architecture':'amd64','RepoDigests':['wrong@sha256:'+'c'*64]})
    monkeypatch.setattr(owned_daemon,'read_private_json',lambda path:proof)
    called=[]
    journal=SimpleNamespace(path=tmp_path/'driver.json',command=lambda *args,**kwargs:called.append('host'))
    with pytest.raises(ValueError,match='registry digest/image mapping'):
        verify_base_provenance({'base_image':image,'base_provenance':'private'},
            {'image':image,'image_archive_sha256':'b'*64,'image_archive':'private.tar'},journal)
    assert called==[]


def test_base_provenance_accepts_native_untagged_official_digest(monkeypatch,tmp_path):
    import json
    from scripts.native_baseline_acceptance import verify_base_provenance
    from deploy import owned_daemon
    from mldsafail.benchmark_v050 import execution
    from types import SimpleNamespace
    source=Path(execution.__file__).parent/'Dockerfile'
    registry=source.read_text().splitlines()[0].removeprefix('FROM ')
    image='sha256:'+'a'*64
    proof=dict(schema='mldsafail.native-image-provenance.v1',status='passed',native_executed=True,
        registry_reference=registry,image=image,architecture='amd64',image_archive_sha256='b'*64,
        source_dockerfile_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),evidence_refs=['original-private-inspection'],
        original_image_inspection={'Id':image,'Architecture':'amd64','RepoDigests':['python@'+registry.rsplit('@',1)[1]]})
    monkeypatch.setattr(owned_daemon,'read_private_json',lambda path:proof)
    published=[]
    monkeypatch.setattr(owned_daemon,'publish',lambda *args:published.append(args))
    journal=SimpleNamespace(path=tmp_path/'driver.json',command=lambda *args,**kwargs:SimpleNamespace(stdout=json.dumps([{'Id':image,'Architecture':'amd64'}]).encode()))
    setup={'base_image':image,'base_provenance':'private'}
    config={'image':image,'image_archive_sha256':'b'*64,'image_archive':'private.tar'}
    verify_base_provenance(setup,config,journal)
    assert len(published)==1
    proof['original_image_inspection']['RepoDigests']=['attacker/python@'+registry.rsplit('@',1)[1]]
    with pytest.raises(ValueError,match='registry digest/image mapping'):verify_base_provenance(setup,config,journal)


def test_frozen_image_cannot_substitute_an_unreviewed_lookalike(monkeypatch,tmp_path):
    from scripts.native_baseline_acceptance import verify_frozen_provenance
    from deploy import owned_daemon
    from types import SimpleNamespace
    image='sha256:'+'a'*64
    monkeypatch.setattr(owned_daemon,'read_private_json',lambda path:dict(schema='mldsafail.native-worker-provenance.v1',
        status='passed',native_executed=True,source_review_passed=True,source_commit='b'*40,image=image,
        architecture='amd64',source_files_sha256={},evidence_refs=['public-output-match']))
    called=[]
    with pytest.raises(ValueError,match='reviewed frozen primitive worker'):
        verify_frozen_provenance({'frozen_image':image,'frozen_provenance':'private'}, {},
            SimpleNamespace(path=tmp_path/'driver.json',command=lambda *args,**kwargs:called.append('host')))
    assert called==[]


def test_native_context_rejects_arm_architecture_before_creation(tmp_path):
    with pytest.raises(ValueError,match='native base architecture'):
        build_context(tmp_path/'context',tmp_path,{},'sha256:'+'a'*64,architecture='arm64')
    assert not (tmp_path/'context').exists()


def test_driver_artifact_schema_normalizes_only_primary_archive():
    from scripts.native_baseline_acceptance import driver_artifacts
    additional={'image':'sha256:'+'b'*64,'archive':'base.tar','archive_sha256':'c'*64}
    assert driver_artifacts({'image':'sha256:'+'a'*64,'image_archive':'primary.tar',
        'image_archive_sha256':'d'*64,'additional_images':[additional]})==[
        {'image':'sha256:'+'a'*64,'archive':'primary.tar','archive_sha256':'d'*64},additional]
