"""Disposable helper processes only; no Docker or workload execution."""
import sys
import time

import pytest

from mldsafail.evaluator.runtime_io import RuntimeTransport
from mldsafail.evaluator.workload import WorkloadBlocked


def transport(code, **kwargs):
    return RuntimeTransport([sys.executable, '-c', code], **kwargs)


def test_helper_roundtrip():
    helper = transport('import json,sys; r=json.load(sys.stdin); print(json.dumps({"result":r}))')
    assert helper.call('sample', {'id': 'synthetic'}) == {'method': 'sample', 'argument': {'id': 'synthetic'}}


@pytest.mark.parametrize('code,reason', [
    ('import time; time.sleep(60)', 'runtime_helper_deadline'),
    ('print("x"*70000)', 'runtime_response_limit'),
    ('print("invalid")', 'runtime_response_invalid'),
    ('print("{}")', 'runtime_response_invalid'),
    ('raise SystemExit(1)', 'runtime_helper_failed'),
])
def test_helper_failure_is_bounded(code, reason):
    helper = transport(code, timeout=.2)
    start = time.monotonic()
    try:
        with pytest.raises(WorkloadBlocked, match=reason): helper.call('sample', {})
        assert time.monotonic() - start < 1
    finally:
        for process in helper.pending: process.wait(timeout=2)


def test_request_and_method_bounds():
    helper = transport('raise SystemExit(99)', max_bytes=100)
    with pytest.raises(ValueError): helper.call('arbitrary_command', {})
    with pytest.raises(WorkloadBlocked, match='runtime_request_limit'): helper.call('sample', 'a'*101)
