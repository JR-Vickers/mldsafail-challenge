"""Bounded read-only staging load gate; never submits solver work."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
import urllib.request


def percentile(values, quantile):
    import math
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def run(server, token, health, duration=300):
    if not 0 < duration <= 300:
        raise ValueError('Maximum load duration is five minutes')
    latencies, failures, floors = [], [], []
    lock = threading.Lock()
    def read(path, authenticated=False):
        started = time.monotonic()
        request = urllib.request.Request(server.rstrip('/') + path,
            headers={'Authorization': 'Bearer ' + token} if authenticated else {})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                response.read(1024 * 1024)
                if response.status != 200:
                    raise RuntimeError()
        except Exception:
            with lock:
                failures.append('read_failed')
        finally:
            with lock:
                latencies.append(time.monotonic() - started)
    started = time.monotonic()
    futures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for index in range(int(duration * 5)):
            delay = started + index / 5 - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            # Five aggregate anonymous requests/sec; authenticated one/5 seconds.
            futures.append(pool.submit(read, '/' if index % 2 else '/health/ready'))
            if index % 25 == 0:
                futures.append(pool.submit(read, '/api/v1/me', True))
                if not health():
                    floors.append('host_floor_failed')
        for future in futures:
            future.result()
    p95, p99 = percentile(latencies, .95), percentile(latencies, .99)
    return {'passed': not failures and not floors and p95 < 1 and p99 < 2,
            'requests': len(latencies), 'read_failures': len(failures),
            'host_floor_violations': len(floors), 'p95_seconds': p95, 'p99_seconds': p99,
            'duration_seconds': duration, 'solver_jobs_submitted': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from hosted_vps_failure_acceptance import private_token
    # Run on the native host; floors cannot be inferred from remote HTTP latency.
    def health():
        import shutil
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        return available >= 128 * 1024**2 and shutil.disk_usage('/srv').free >= 5 * 1024**3
    if not health():
        raise SystemExit('Preflight host floor failed')
    result = run(args.server, private_token(args.token_file), health)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
    raise SystemExit(0 if result['passed'] else 1)

if __name__ == '__main__':
    main()
