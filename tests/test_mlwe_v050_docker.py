"""Real isolation/failure tests; opt in with MLWE_DOCKER_TESTS=1 after building."""
import os
from pathlib import Path
import pytest
from mldsafail.benchmark_v050.execution import environment, invoke
from mldsafail.benchmark_v050.generator import generate_mlwe

pytestmark = pytest.mark.skipif(os.environ.get('MLWE_DOCKER_TESTS') != '1', reason='explicit Docker acceptance suite')


@pytest.fixture(scope='module')
def image():
    return environment()['image_id']


@pytest.mark.parametrize('code,status', [
    ('''import os, socket
from pathlib import Path
def solve(public_instance):
    assert set(public_instance) == {'schema_version','study_version','track','profile','ring','dimensions','eta','A','t','instance_id'}
    for p in ['/study','/solver/secret.json','/worker/research','/worker/mldsafail/benchmark_v050/generator.py','/var/run/docker.sock','/root/.aws','/Users/jarrett/dev/mldsafail-challenge','/epoch','/results']:
        try:
            assert not Path(p).exists(), p
        except PermissionError:
            pass
    assert os.getuid() == 65534
    assert not any('NONCE' in k or 'TOKEN' in k or 'SEED' in k and k != 'PYTHONHASHSEED' for k in os.environ)
    try:
        socket.create_connection(('1.1.1.1',443), timeout=1)
    except OSError:
        pass
    else:
        raise AssertionError('network accessible')
    try:
        Path('/worker/write-test').write_text('bad')
    except OSError:
        pass
    else:
        raise AssertionError('writable root')
    return None
''', 'no_candidate'),
    ('def solve(x):\n    raise RuntimeError("probe crash")\n', 'crash'),
    ('import os\ndef solve(x):\n    os._exit(3)\n', 'crash'),
    ('def solve(x):\n    return {"tag":"recovered_secret","s1":[],"s2":[]}\n', 'invalid_answer'),
    ('def solve(x):\n    return {"tag":"recovered_secret","s1":[[float("nan")]],"s2":[]}\n', 'invalid_answer'),
    ('def solve(x):\n    return bytearray(3 * 1024**3)\n', 'memory_failure'),
    ('def solve(x):\n    print("x" * 3000000)\n    return None\n', 'crash'),
])
def test_real_container(tmp_path, image, code, status):
    (tmp_path / 'solver.py').write_text(code)
    result = invoke(generate_mlwe('small', 0, 1).public, 'contestant', image, tmp_path)
    assert result['status'] == status, result
    assert len(result['stdout'].encode()) <= 2_000_000
    assert len(result['stderr'].encode()) <= 2_000_000


def test_real_sixty_second_timeout(tmp_path, image):
    (tmp_path / 'solver.py').write_text('def solve(x):\n    while True: pass\n')
    result = invoke(generate_mlwe('small', 0, 1).public, 'contestant', image, tmp_path)
    assert result['status'] == 'timeout'
    assert 60 <= result['evaluator_wall_seconds'] < 75
    assert not result.get('memory_limit')
