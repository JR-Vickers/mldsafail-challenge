"""Untrusted contestant adapter; emits no authoritative accounting claims."""
import importlib.util
import json
import sys
from mldsafail.benchmark_v050.constants import MAX_SERIALIZED_BYTES
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.worker import limits


def main():
    limits()
    try:
        raw = sys.stdin.buffer.read(MAX_SERIALIZED_BYTES + 1)
        if len(raw) > MAX_SERIALIZED_BYTES:
            raise ValueError('Public input exceeds fixed cap')
        request = json.loads(raw)
        if set(request) != {'instance','solver'} or request['solver'] != 'contestant':
            raise ValueError('Only approved contestant execution is supported')
        instance = instance_from_dict(request['instance'])
        spec = importlib.util.spec_from_file_location('contestant','/solver/solver.py')
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0,'/solver')
        spec.loader.exec_module(module)
        candidate = module.solve(json.loads(json.dumps(instance.to_dict())))
        try:
            candidate = json.loads(json.dumps(candidate, allow_nan=False))
        except (TypeError, ValueError, OverflowError):
            candidate = {'invalid_unserializable_candidate':True}
        response = {'candidate':candidate}
    except MemoryError:
        response = {'error':'MemoryError'}
    except Exception as error:
        response = {'error':type(error).__name__}
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(',',':'), allow_nan=False))


if __name__ == '__main__':
    main()
