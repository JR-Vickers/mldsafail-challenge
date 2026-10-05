import hashlib
import io
import json
import os
import tarfile
import pytest
from scripts import native_participant_v060_install as install


def sha(data):return hashlib.sha256(data).hexdigest()


def fixture(tmp_path):
    source='b'*40;wheel=b'reviewed-wheel'
    files={'candidate.whl':wheel,'SOURCE.json':json.dumps({'source_commit':source}).encode(),
           'examples/mlwe/primal-lll/solver.py':b'starter','public-fixtures.json':b'[]'}
    checks={name:sha(data) for name,data in files.items()};files['SHA256SUMS']=''.join(value+'  '+name+'\n' for name,value in sorted(checks.items())).encode()
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for name,data in files.items():
            info=tarfile.TarInfo('mldsafail-v060-candidate/'+name);info.size=len(data)
            archive.addfile(info,io.BytesIO(data))
    manifest=dict(schema='mldsafail.participant-candidate.v1',source_commit=source,package_version='0.5.1',
        benchmark_protocol='0.6.0',candidate_only=True,contract_adopted=False,production_default_approved=False,
        publication_approved=False,wheel_sha256=sha(wheel),archive_sha256=sha(stream.getvalue()),files_sha256=checks)
    review=dict(author_source_commit=source,source_review_passed=True,archive_review_passed=True,
                wheel_sha256=manifest['wheel_sha256'],archive_sha256=manifest['archive_sha256'])
    for name,data in [('candidate.whl',wheel),('archive.tar.gz',stream.getvalue()),('dependency.whl',b'dependency'),
                      ('manifest.json',json.dumps(manifest).encode()),('review.json',json.dumps(review).encode())]:
        path=tmp_path/name;path.write_bytes(data);path.chmod(0o400)
    protocol=dict(schema='mldsafail.participant-native-install-protocol.v1',participant_source_commit=source,
        participant_source=str(tmp_path/'source'),manifest=str(tmp_path/'manifest.json'),review=str(tmp_path/'review.json'),
        archive=str(tmp_path/'archive.tar.gz'),wheel=str(tmp_path/'candidate.whl'),
        dependency_wheels=[dict(path=str(tmp_path/'dependency.whl'),sha256=sha(b'dependency'))])
    return protocol,manifest


def test_admission_binds_separate_source_wheel_archive_review_and_dependencies(tmp_path):
    protocol,manifest=fixture(tmp_path)
    assert install.admission(protocol)[0]==manifest
    protocol['participant_source_commit']='c'*40
    with pytest.raises(ValueError,match='Separately bound'):install.admission(protocol)


@pytest.mark.parametrize('change',['wheel','dependency','review','archive'])
def test_admission_rejects_changed_retained_material(tmp_path,change):
    protocol,_=fixture(tmp_path)
    if change=='review':
        path=tmp_path/'review.json';path.chmod(0o600)
        review=json.loads(path.read_text());review['archive_review_passed']=False;path.write_text(json.dumps(review))
    else:
        path=tmp_path/({'wheel':'candidate.whl','dependency':'dependency.whl','archive':'archive.tar.gz'}[change])
        path.chmod(0o600);path.write_bytes(b'changed');path.chmod(0o400)
    with pytest.raises(ValueError):install.admission(protocol)


def test_sealed_reader_rejects_links_writable_and_fifo_without_blocking(tmp_path):
    path=tmp_path/'file';path.write_bytes(b'x')
    with pytest.raises(ValueError):install.retained_bytes(path,sha(b'x'))
    path.chmod(0o400);link=tmp_path/'link';link.symlink_to(path)
    with pytest.raises(OSError):install.retained_bytes(link,sha(b'x'))
    os.link(path,tmp_path/'hardlink')
    with pytest.raises(ValueError):install.retained_bytes(path,sha(b'x'))
    fifo=tmp_path/'fifo';os.mkfifo(fifo)
    with pytest.raises(ValueError):install.retained_bytes(fifo,sha(b'x'))


def callback_fixture(tmp_path,monkeypatch):
    from types import SimpleNamespace
    protocol,manifest=fixture(tmp_path);protocol['python']='/retained/python'
    (tmp_path/'participant-install-protocol.json').write_text(json.dumps(protocol));(tmp_path/'participant-install-protocol.json').chmod(0o600)
    calls=[]
    def command(argv,**kwargs):
        calls.append((argv,kwargs))
        output=b''
        if argv[:1]==['git'] and argv[-1]=='HEAD':output=(protocol['participant_source_commit']+'\n').encode()
        elif 'clone' in argv:
            path=__import__('pathlib').Path(argv[-1]);path.mkdir()
            if '0.6.0' in argv:
                (path/'solver').mkdir();(path/'solver/solver.py').write_bytes(b'starter')
        elif 'run' in argv:output=b'{"score":3901}'
        elif '-I' in argv:output=b'{"passed":true,"installed_package":"0.5.1","public_fixtures_verified":2,"unsupported_server_preflight":true,"submission_post_count":0}'
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr(install.platform,'system',lambda:'Linux');monkeypatch.setattr(install.platform,'machine',lambda:'x86_64')
    journal=SimpleNamespace(path=tmp_path/'driver.json',command=command)
    config={'source_commit':'a'*40,'acceptance_source_sha256':'c'*64}
    return journal,config,calls


def test_callback_offline_private_home_proof_separates_outer_cleanup(tmp_path,monkeypatch):
    journal,config,calls=callback_fixture(tmp_path,monkeypatch)
    result=install.callback(journal,config,{})
    proof=json.loads((tmp_path/'participant-install/artifact.json').read_text())
    assert result['passed'] and proof['outer_cleanup_required']
    assert proof['native_accounting_passed'] is False and proof['native_reproduction_passed'] is False
    pip=[(argv,options) for argv,options in calls if argv[:3]==['uv','pip','install']][0]
    assert '--offline' in pip[0] and '--no-index' in pip[0]
    assert pip[1]['env']['HOME']==str(tmp_path/'participant-install/home')
    assert pip[1]['env']['PYTHON_KEYRING_BACKEND']=='keyring.backends.null.Keyring'
    assert not any('--system-site-packages' in argv for argv,_ in calls)


def test_ambiguous_positive_publication_is_retracted(tmp_path,monkeypatch):
    journal,config,_=callback_fixture(tmp_path,monkeypatch)
    publish=install.owned_daemon.publish;count=0
    def failed(path,value):
        nonlocal count
        publish(path,value);count+=1
        if count==1:raise OSError('post-rename fsync failure')
    monkeypatch.setattr(install.owned_daemon,'publish',failed)
    with pytest.raises(OSError,match='fsync'):install.callback(journal,config,{})
    proof=json.loads((tmp_path/'participant-install/artifact.json').read_text())
    assert not proof['passed'] and proof['publication_incomplete'] and count==2
