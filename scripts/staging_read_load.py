"""Bounded read-only staging load gate; never submits solver work."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


def percentile(values, quantile):
    import math
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def run(server, token, health, duration=300, progress=None, request_open=None):
    if not 0 < duration <= 300:
        raise ValueError('Maximum load duration is five minutes')
    request_open = urllib.request.urlopen if request_open is None else request_open
    latencies, failures, floors = [], [], []
    lock = threading.Lock()
    def read(path, authenticated=False):
        started = time.monotonic()
        failed = False
        error_type = None
        http_status = None
        request = urllib.request.Request(server.rstrip('/') + path,
            headers={'Authorization': 'Bearer ' + token} if authenticated else {})
        try:
            with request_open(request, timeout=2) as response:
                response.read(1024 * 1024)
                if response.status != 200:
                    raise RuntimeError()
        except Exception as error:
            failed = True
            # Retain bounded classifications, never URLs, headers or messages.
            error_type = type(error).__name__[:80]
            if isinstance(error, urllib.error.HTTPError) and type(error.code) is int and 100 <= error.code <= 599:
                http_status = error.code
            with lock:
                failures.append('read_failed')
        finally:
            with lock:
                finished = time.monotonic()
                elapsed = finished - started
                latencies.append(elapsed)
            if progress is not None:
                row = dict(route=path, seconds=elapsed, failed=failed,
                           started_after_seconds=started - phase_started,
                           finished_after_seconds=finished - phase_started)
                if failed:
                    row.update(error_type=error_type, http_status=http_status)
                progress(row)
    phase_started = time.monotonic()
    max_scheduling_lag = 0
    futures = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for index in range(int(duration * 5)):
            delay = phase_started + index / 5 - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            max_scheduling_lag = max(max_scheduling_lag, time.monotonic() - (phase_started + index / 5))
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
            'duration_seconds': duration, 'elapsed_seconds': time.monotonic() - phase_started,
            'max_scheduling_lag_seconds': max_scheduling_lag, 'solver_jobs_submitted': 0}


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
