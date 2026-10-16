import io
import os
import subprocess
import sys
import time
import pytest
from deploy import owned_vm


@pytest.mark.skipif(sys.platform != 'darwin', reason='Native macOS ownership gate')
def test_failed_identity_publication_prevents_command_and_reaps_bootstrap(tmp_path):
    rows = []
    def publish(entry):
        rows.append(dict(entry))
        if entry['pid'] is not None:
            raise OSError('injected durable receipt failure')
    with pytest.raises(OSError, match='durable receipt'):
        owned_vm.spawn(['/usr/bin/touch', str(tmp_path / 'mutation')], publish, subprocess.DEVNULL)
    assert not (tmp_path / 'mutation').exists()
    with pytest.raises(ProcessLookupError):
        owned_vm.identity(rows[-1]['pid'])


@pytest.mark.skipif(sys.platform != 'darwin', reason='Native macOS ownership gate')
def test_native_owned_vm_stop_is_exact_and_idempotent():
    rows = []
    process, entry = owned_vm.spawn(['/bin/sleep', '30'], lambda row: rows.append(dict(row)), subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 5
        while owned_vm.identity(process.pid)['command_sha256'] != entry['expected_command_sha256']:
            assert time.monotonic() < deadline
            time.sleep(.01)
        wrong = dict(entry, start_usec=entry['start_usec'] + 1)
        with pytest.raises(RuntimeError, match='identity mismatch'):
            owned_vm.stop(wrong)
        assert process.poll() is None
        owned_vm.stop(entry)
        process.wait(timeout=5)
        owned_vm.stop(entry)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
