import base64
import csv
import hashlib
import io
import zipfile

import pytest

from deploy.workload_wheels import inspect_wheel
from mldsafail.evaluator.workload import WorkloadBlocked


def wheel(tmp_path, *, tag='py3-none-any', missing=False, corrupt=False, requires='', prefix='fixture-1.0.dist-info'):
    path = tmp_path / ('fixture-1.0-'+tag+'.whl')
    files = {'fixture.py': b'value = 1\n',
             'fixture-1.0.dist-info/METADATA': b'Metadata-Version: 2.1\nName: fixture\nVersion: 1.0\n',
             'fixture-1.0.dist-info/WHEEL': ('Wheel-Version: 1.0\nTag: '+tag+'\n').encode()}
    files = {name.replace('fixture-1.0.dist-info', prefix): data for name, data in files.items()}
    files[prefix+'/METADATA'] += ('Requires-Python: '+requires+'\n').encode() if requires else b''
    rows = [[name, 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(), str(len(data))]
            for name, data in files.items()]
    if missing: rows.pop(0)
    if corrupt: files['fixture.py'] = b'changed'
    stream = io.StringIO(); writer = csv.writer(stream)
    writer.writerows(rows+[[prefix+'/RECORD', '', '']])
    files[prefix+'/RECORD'] = stream.getvalue().encode()
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in files.items(): archive.writestr(name, data)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_valid_wheel(tmp_path):
    path, sha = wheel(tmp_path)
    assert inspect_wheel(path, sha)['name'] == 'fixture'


@pytest.mark.parametrize('options', [dict(requires='>=3.13'), dict(prefix='unrelated-9.dist-info'), dict(tag='cp312-cp312-manylinux_999_999_x86_64'), dict(missing=True), dict(corrupt=True), dict(tag='cp312-cp312-macosx_11_0_arm64'), dict(tag='cp313-cp313-manylinux_2_28_x86_64')])
def test_invalid_wheels(tmp_path, options):
    path, sha = wheel(tmp_path, **options)
    with pytest.raises(WorkloadBlocked): inspect_wheel(path, sha)


def test_filename_shaped_bytes_fail(tmp_path):
    path = tmp_path/'fake-1.0-py3-none-any.whl'; path.write_bytes(b'not a wheel')
    with pytest.raises(WorkloadBlocked): inspect_wheel(path, hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.mark.parametrize('requirement', ['<=3.12.0', '!=3.12.5', '>=3.12.1', '==3.12'])
def test_uncertain_patch_constraints_are_rejected(requirement):
    from deploy.workload_wheels import python_requirement
    assert not python_requirement(requirement)


def test_python_family_constraint():
    from deploy.workload_wheels import python_requirement
    assert python_requirement('>=3.9,<3.13')
