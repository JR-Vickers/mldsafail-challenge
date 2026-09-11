"""Interrupt a real contestant run after durable evidence, then audit its partial state."""
import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

from mldsafail.benchmark_v050 import evidence as ev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epoch', type=Path, required=True)
    parser.add_argument('--private-output', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    root = ev.directory(args.private_output)
    source = ev.directory(root / 'source')
    (source / 'solver.py').write_text('import time\ndef solve(public_instance):\n    time.sleep(2)\n    return None\n')
    output = root / 'run'
    with (root / 'interruption.log').open('x') as log:
        process = subprocess.Popen([sys.executable, '-m', 'mldsafail.benchmark_v050.cli', 'run',
            '--epoch', str(args.epoch), '--solver-dir', str(source), '--output', str(output)], stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 45
            while not (output / 'records' / '000-0.json').exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('run failed to persist its first warmup')
                time.sleep(.1)
            process.send_signal(signal.SIGINT)
            assert process.wait(timeout=20) != 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    assert not (output / 'COMPLETE.json').exists()
    audit = subprocess.run([sys.executable, '-m', 'mldsafail.benchmark_v050.cli', 'audit',
        '--epoch', str(args.epoch), '--run', str(output)], capture_output=True, text=True)
    assert audit.returncode == 1, audit.stderr
    result = json.loads(audit.stdout)
    assert result['verified_records'] >= 1 and result['missing_records'] > 0
    assert not result['ranking'] and not result['complete']
    ev.write(args.summary, {'real_interruption_preserved_evidence':True, 'audit':result})
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
