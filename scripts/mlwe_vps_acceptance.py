"""Native public-fixture worker gate without pytest or private epoch access."""
import argparse
import json
from pathlib import Path
import tempfile

from mldsafail.benchmark_v050.execution import environment, invoke
from mldsafail.benchmark_v050.generator import generate_mlwe


ISOLATION = '''import os, socket
from pathlib import Path
def solve(x):
    assert os.getuid() == 65534
    assert set(x) == {'schema_version','study_version','track','profile','ring','dimensions','eta','A','t','instance_id'}
    for p in ['/epoch','/results','/var/run/docker.sock','/srv/mldsafail-evaluator','/worker/mldsafail/benchmark_v050/generator.py']:
        try:
            assert not Path(p).exists()
        except PermissionError:
            pass
    assert not any(k.startswith(('MLDSAFAIL','GITHUB','POSTGRES')) for k in os.environ)
    try:
        socket.create_connection(('1.1.1.1',443),timeout=1)
    except OSError:
        pass
    else:
        raise AssertionError('network reachable')
    try:
        Path('/worker/write-test').write_text('probe')
    except OSError:
        pass
    else:
        raise AssertionError('writable root')
    return None
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    env = environment(args.image)
    if env["artifacts"]["architecture"] != "x86_64":
        raise SystemExit("Native VPS acceptance requires the x86_64 image.")
    instance = generate_mlwe("small", 0, 1).public
    baseline = invoke(instance, "primal-lll", env["image_id"])
    assert baseline["status"] == "success"
    probes = [
        ("isolation", ISOLATION, "no_candidate"),
        ("invalid", "def solve(x): return {'tag':'recovered_secret','s1':[],'s2':[]}\n", "invalid_answer"),
        ("crash", "def solve(x): raise RuntimeError('probe')\n", "crash"),
        ("memory", "def solve(x): return bytearray(3 * 1024**3)\n", "memory_failure"),
        ("output", "def solve(x):\n    print('x' * 3000000)\n    return None\n", "crash"),
        ("timeout", "def solve(x):\n    while True: pass\n", "timeout"),
    ]
    statuses = {"baseline": "success"}
    for name, code, expected in probes:
        with tempfile.TemporaryDirectory(prefix="worker-probe-", dir="/srv/mldsafail-evaluator/jobs") as temporary:
            source = Path(temporary)
            source.chmod(0o755)
            (source / "solver.py").write_text(code)
            print(json.dumps({"probe_started": name}), flush=True)
            result = invoke(instance, "contestant", env["image_id"], source)
            assert result["status"] == expected, name
            if name == "timeout":
                assert 60 <= result["evaluator_wall_seconds"] < 75
            statuses[name] = result["status"]
    print(json.dumps({"native_worker_acceptance": True, "statuses": statuses}), flush=True)


if __name__ == "__main__":
    main()
