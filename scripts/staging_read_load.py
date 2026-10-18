"""Bounded read-only staging load gate; never submits solver work."""
import argparse
from concurrent.futures import wait

from scripts.read_load_observer import Observer, RequestPool
import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request


DRAIN_SECONDS = 5


def percentile(values, quantile):
    import math
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)]


def run(server, token, health, duration=300, progress=None, request_open=None, *, read_only_health=False):
    # Older callers mutate lifecycle journals from health(); never thread those
    # callbacks silently. Reviewed callers explicitly bind read-only observation.
    if read_only_health is not True:
        raise ValueError('Read-only asynchronous health callback review required')
    if not 0 < duration <= 300:
        raise ValueError('Maximum load duration is five minutes')
    request_open = urllib.request.urlopen if request_open is None else request_open
    floors = []
    lock = threading.Lock()
    records = {}
    evidence_errors = []
    phase_closed = threading.Event()
    def read(identifier, path, authenticated, scheduled, dispatched):
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
        finally:
            finished = time.monotonic()
            elapsed = finished - started
            row = dict(request_id=identifier, route=path, seconds=elapsed, failed=failed,
                       scheduled_after_seconds=scheduled - phase_started,
                       dispatched_after_seconds=dispatched - phase_started,
                       queue_delay_seconds=started - dispatched,
                       started_after_seconds=started - phase_started,
                       finished_after_seconds=finished - phase_started)
            if failed:
                row.update(error_type=error_type, http_status=http_status)
            with lock:
                if phase_closed.is_set():
                    return
                records[identifier] = row
            if progress is not None and not phase_closed.is_set():
                try:
                    progress(dict(row))
                except Exception as error:
                    with lock:
                        evidence_errors.append(type(error).__name__[:80])
    observer = Observer(health)
    observation_valid = observer.start()
    phase_started = time.monotonic()
    max_scheduling_lag = 0.0
    pacing_valid = True
    expected = int(duration * 5) + len(range(0, int(duration * 5), 25))
    futures, submitted = [], []
    pool = RequestPool(max_workers=10)
    try:
        for index in range(int(duration * 5)):
            deadline = phase_started + index / 5
            while observation_valid and time.monotonic() < deadline:
                observation_valid = observer.valid()
                time.sleep(min(.02, max(0, deadline - time.monotonic())))
            observation_valid = observation_valid and observer.valid()
            if not observation_valid:
                floors.append('host_floor_failed')
                break
            dispatched = time.monotonic()
            lag = max(0, dispatched - deadline)
            max_scheduling_lag = max(max_scheduling_lag, lag)
            if lag > .1:
                pacing_valid = False
                break
            routes = [('/' if index % 2 else '/health/ready', False)]
            if index % 25 == 0:
                routes.append(('/api/v1/me', True))
            for path, authenticated in routes:
                dispatched = time.monotonic()
                lag = max(0, dispatched - deadline)
                max_scheduling_lag = max(max_scheduling_lag, lag)
                if lag > .1:
                    pacing_valid = False
                    break
                if not observer.valid():
                    observation_valid = False
                    break
                identifier = len(submitted)
                submitted.append(dict(request_id=identifier, route=path,
                    scheduled_after_seconds=deadline - phase_started,
                    dispatched_after_seconds=dispatched - phase_started))
                futures.append(pool.submit(read, identifier, path, authenticated, deadline, dispatched))
            if not pacing_valid or not observation_valid:
                break
        end = phase_started + duration
        if observation_valid and pacing_valid and len(submitted) == expected:
            while time.monotonic() < end:
                observation_valid = observation_valid and observer.valid()
                if not observation_valid:
                    break
                time.sleep(min(.02, max(0, end - time.monotonic())))
        drain_deadline = time.monotonic() + DRAIN_SECONDS
        pending = set(futures)
        while pending and time.monotonic() < drain_deadline:
            observation_valid = observation_valid and observer.valid()
            _, pending = wait(pending, timeout=min(.02, max(0, drain_deadline - time.monotonic())))
        observation_valid = observation_valid and observer.valid()
    finally:
        workers_stopped = pool.shutdown()
        observer_stopped = observer.close()
    elapsed = time.monotonic() - phase_started
    with lock:
        phase_closed.set()
        rows = [dict(records[item['request_id']]) if item['request_id'] in records else
                dict(item, incomplete=True) for item in submitted]
        measured = [row['seconds'] for row in rows if not row.get('incomplete')]
        failure_count = sum(bool(row.get('failed')) for row in rows)
        evidence_failures = list(evidence_errors)
    if progress is not None:
        for row in rows:
            if row.get('incomplete'):
                try:
                    progress(row)
                except Exception as error:
                    evidence_failures.append(type(error).__name__[:80])
    incomplete = sum(bool(row.get('incomplete')) for row in rows)
    terminated = observer_stopped and workers_stopped and not pending
    p95 = percentile(measured, .95) if measured else None
    p99 = percentile(measured, .99) if measured else None
    if not observation_valid and not floors:
        floors.append('host_floor_failed')
    return {'passed': (observation_valid and pacing_valid and terminated and not incomplete
                       and len(measured) == expected and not failure_count and not floors and not evidence_failures
                       and p95 is not None and p95 < 1 and p99 < 2),
            'requests': len(measured), 'expected_requests': expected,
            'dispatched_requests': len(submitted), 'incomplete_requests': incomplete,
            'undispatched_requests': expected - len(submitted),
            'evidence_error_types': evidence_failures,
            'read_failures': failure_count, 'host_floor_violations': len(floors),
            'p95_seconds': p95, 'p99_seconds': p99,
            'pacing_valid': pacing_valid, 'observation_valid': observation_valid,
            'termination_complete': terminated, 'observations': [dict(row,
                started_after_seconds=row['started'] - phase_started,
                finished_after_seconds=row['finished'] - phase_started) for row in observer.evidence()],
            'duration_seconds': duration, 'elapsed_seconds': elapsed,
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
    result = run(args.server, private_token(args.token_file), health, read_only_health=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
    raise SystemExit(0 if result['passed'] else 1)

if __name__ == '__main__':
    main()
