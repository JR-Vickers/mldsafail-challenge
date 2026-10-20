"""Continuous bounded investigation monitoring and hash-bound phase coverage."""
from contextlib import contextmanager
import hashlib
import gzip
import json
import os
from pathlib import Path
import threading
import time

from deploy.capacity_investigation import output_budget
from deploy.capacity_sampler import SCOPES, require
from deploy.production_preparation import read_manifest
from deploy.recovery_journal import atomic_json, safe_path

PHASES = ('setup', 'create', 'audit', 'cleanup')


class LimitedOutput:
    def __init__(self, raw):
        self.raw=raw
    def write(self, data):
        require(self.raw.tell()+len(data) <= 64*1024**2, 'sample_output_exhausted')
        return self.raw.write(data)
    def flush(self):
        return self.raw.flush()
    def tell(self):
        return self.raw.tell()


class Monitor:
    """One sampler owns the stream. Identity/health callbacks are read-only.

    A blackholed callback latches failure after 800ms. A surviving reader thread
    makes cleanup incomplete; it can never authorize launch or restoration.
    """
    def __init__(self, root, sampler, identity, health, *, operation_id, logs=(), additional_roots=(), maximum_duration=8000):
        self.root = safe_path(Path(root).absolute())
        self.sampler, self.identity, self.health = sampler, identity, health
        import re
        require(re.fullmatch('[a-f0-9]{32}', operation_id), 'monitor_operation_identity_missing')
        self.operation_id = operation_id
        self.additional_roots = tuple(safe_path(Path(p).absolute()) for p in additional_roots)
        self.logs, self.maximum_duration = tuple(logs), maximum_duration
        require(0 < maximum_duration <= 8000, 'monitor_duration_invalid')
        self.phase, self.events = None, []
        self.failed, self.stopping = threading.Event(), threading.Event()
        self.mutex = threading.RLock()
        self.error, self.thread = None, None
        self.last_sample_ns = None
        self.stream = None
        self.active_readers = []
        self.byte_count = 0

    def start(self):
        require(self.thread is None and self.stream is None, 'monitor_already_started')
        self.raw = (self.root / 'samples.jsonl.gz').open('xb')
        os.chmod(self.raw.name, 0o600)
        self.stream = gzip.GzipFile(filename='',fileobj=LimitedOutput(self.raw),mode='wb',mtime=0)
        self.started = time.monotonic()
        self.transition('setup')
        self.thread = threading.Thread(target=self._loop, name='capacity-sampler', daemon=True)
        self.thread.start()
        return self

    @contextmanager
    def locked(self):
        require(self.mutex.acquire(timeout=.8), 'monitor_mutex_deadline')
        try:
            yield
        finally:
            self.mutex.release()

    def bounded(self, callback):
        result, errors = [], []
        done = threading.Event()
        def read():
            try:
                result.append(callback())
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        reader = threading.Thread(target=read, name='capacity-evidence-reader', daemon=True)
        self.active_readers = [t for t in self.active_readers if t.is_alive()]
        self.active_readers.append(reader)
        reader.start()
        if not done.wait(.8):
            self.failed.set()
            raise ValueError('monitor_read_deadline')
        if errors:
            self.failed.set()
            raise errors[0]
        return result[0]

    def _write_sample(self):
        require(not self.failed.is_set(), 'monitor_failed')
        require(time.monotonic() - self.started <= self.maximum_duration, 'monitor_duration_exceeded')
        phase = self.phase
        def capture():
            require(self.identity() is True and self.health() is True, 'monitor_identity_or_health')
            row = self.sampler.sample(phase)
            row['live_identity_verified'] = True
            row['operation_id'] = self.operation_id
            data = (json.dumps(row, sort_keys=True) + '\n').encode()
            require(self.raw.tell() < 64 * 1024**2, 'sample_output_exhausted')
            total=output_budget(self.root, self.logs, [Path(self.raw.name)])
            for root in self.additional_roots:
                if root.exists():
                    total+=output_budget(root,[],[])
            require(total <= 1024**3, 'investigation_generation_output_limit')
            self.stream.write(data)
            self.stream.flush()
            return row, len(data)
        row, count = self.bounded(capture)
        self.byte_count += count
        self.last_sample_ns = row['monotonic_ns']

    def _loop(self):
        tick = time.monotonic() + .25
        try:
            while not self.stopping.wait(max(0, tick - time.monotonic())):
                with self.locked():
                    self._write_sample()
                tick += .25
        except BaseException as error:
            self.error = type(error).__name__
            self.failed.set()

    def transition(self, phase):
        require(phase in PHASES, 'monitor_unknown_phase')
        with self.locked():
            if self.phase is not None:
                self._write_sample()
                self.events[-1]['end_ns'] = time.monotonic_ns()
            require(phase not in [e['phase'] for e in self.events], 'monitor_phase_repeated')
            self.phase = phase
            self.events.append(dict(phase=phase, start_ns=time.monotonic_ns()))
            self.bounded(lambda: atomic_json(self.root / 'coverage.json', dict(operation_id=self.operation_id, complete=False, phases=self.events)))
            try:
                self._write_sample()
            except BaseException:
                self.failed.set()
                raise

    def guard(self):
        with self.locked():
            require(not self.failed.is_set() and self.thread is not None and self.thread.is_alive(), 'monitor_failed')
            require(self.last_sample_ns is not None and time.monotonic_ns() - self.last_sample_ns <= 1_000_000_000,
                    'monitor_stale')
        return True

    def finish(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=2)
        require(self.thread is not None and not self.thread.is_alive(), 'monitor_thread_remains')
        with self.locked():
            try:
                require(not self.failed.is_set(), 'monitor_failed')
                self._write_sample()
                self.events[-1]['end_ns'] = time.monotonic_ns()
                require(tuple(e['phase'] for e in self.events) == PHASES, 'monitor_incomplete_phases')
                require(not any(t.is_alive() for t in self.active_readers), 'monitor_reader_remains')
                def finish_io():
                    self.stream.close()
                    self.raw.flush()
                    os.fsync(self.raw.fileno())
                    self.raw.close()
                    atomic_json(self.root / 'coverage.json', dict(operation_id=self.operation_id, complete=True, phases=self.events))
                self.bounded(finish_io)
            finally:
                if self.stream and not any(t.is_alive() for t in self.active_readers):
                    self.bounded(lambda:(self.stream.close(),self.raw.close()))

    def abort(self):
        """Preserve partial evidence; never promote incomplete coverage."""
        self.failed.set()
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError('monitor_reconciliation_required')
        if self.stream and not self.stream.closed and not any(t.is_alive() for t in self.active_readers):
            self.bounded(lambda:(self.stream.close(),self.raw.close()))
        self.bounded(lambda: atomic_json(self.root / 'coverage.json', dict(operation_id=self.operation_id, complete=False, phases=self.events,
                                                     reader_remains=any(t.is_alive() for t in self.active_readers[:-1]))))


def validate_capture(root):
    """Streaming validation rejects gaps, missing boundary coverage and identity drift."""
    root = safe_path(Path(root).absolute())
    coverage = read_manifest(root / 'coverage.json')
    attempt = read_manifest(root / 'attempt.json')
    require(attempt.get('state') == 'terminated' and attempt.get('capture_complete') is True
            and attempt.get('operation_id') == coverage.get('operation_id'), 'measurement_attempt_incomplete')
    require(coverage['complete'] is True and tuple(e['phase'] for e in coverage['phases']) == PHASES,
            'measurement_phase_coverage_incomplete')
    windows = {p['phase']: p for p in coverage['phases']}
    require(all(type(p['start_ns']) is int and type(p['end_ns']) is int and p['start_ns'] < p['end_ns']
                for p in windows.values()), 'measurement_phase_bounds_invalid')
    require(all(a['end_ns'] <= b['start_ns'] and b['start_ns'] - a['end_ns'] <= 1_000_000_000
                for a, b in zip(coverage['phases'], coverage['phases'][1:])), 'measurement_phase_gap')
    seen, previous, boot = {}, None, None
    operation_peak = retained_peak = 0
    available_min = None
    physical_ram = swap = hostname = None
    identities_verified = True
    ancestor_limits = set()
    ancestor_peaks = {}
    shared_ancestors = None
    digest = hashlib.sha256()
    count = 0
    candidates=[root/name for name in ('samples.jsonl','samples.jsonl.gz') if (root/name).exists()]
    require(len(candidates)==1, 'measurement_raw_file_ambiguous')
    path=candidates[0]
    with path.open('rb') as raw_stream:
        for block in iter(lambda:raw_stream.read(65536),b''):
            digest.update(block)
    require(path.stat().st_size <= 64 * 1024**2, 'sample_output_exhausted')
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rb') as stream:
        decoded_bytes=0
        for line in iter(lambda:stream.readline(1024**2+1),b''):
            decoded_bytes+=len(line)
            require(decoded_bytes <= 1024**3 and len(line) <= 1024**2, 'measurement_decoded_output_limit')
            row = json.loads(line)
            require(row.get('operation_id') == coverage['operation_id'], 'measurement_operation_changed')
            identities_verified = identities_verified and row.get('live_identity_verified') is True
            require(row['hostname'] and (hostname is None or hostname == row['hostname']), 'measurement_host_changed')
            hostname = row['hostname']
            require(row['host']['MemAvailable'] >= 256 * 1024**2 and row['filesystem_available'] >= 2 * 1024**3, 'measurement_emergency_floor')
            if previous:
                require(row['host']['SwapFree'] >= previous['host']['SwapFree'], 'measurement_host_swap_growth')
            require(row['phase'] in windows and row['boot_id'], 'measurement_identity_missing')
            boot = boot or row['boot_id']
            require(row['boot_id'] == boot, 'measurement_boot_changed')
            timestamp = row['monotonic_ns']
            require(type(timestamp) is int and timestamp >= 0, 'measurement_timestamp_invalid')
            require(previous is None or 0 < timestamp - previous['monotonic_ns'] <= 1_000_000_000, 'sampling_gap')
            phase = windows[row['phase']]
            require(phase['start_ns'] <= timestamp <= phase['end_ns'], 'measurement_sample_outside_phase')
            require(set(row['scopes']) == set(SCOPES.values()) - {'host_available_excluding_retained_usage'}, 'measurement_scopes_missing')
            all_paths = [Path(p) for group in row['scopes'].values() for p in group]
            require(all(row['scopes'].values()) and all_paths and not any(a.is_relative_to(b) or b.is_relative_to(a)
                    for i, a in enumerate(all_paths) for b in all_paths[i+1:]), 'measurement_scope_overlap')
            require(set(map(str, all_paths)) == set(row['cgroups']), 'measurement_scope_missing')
            if previous:
                require(row['scopes'] == previous['scopes'] and row['ancestors'].keys() == previous['ancestors'].keys(), 'measurement_scope_changed')
            root_path = Path(row['cgroup_root'])
            expected_ancestors = set()
            for path_value in all_paths:
                require(path_value.is_absolute() and path_value != root_path and path_value.is_relative_to(root_path)
                        and '..' not in path_value.parts, 'measurement_scope_outside_root')
                for ancestor in (path_value, *path_value.parents):
                    if not ancestor.is_relative_to(root_path):
                        break
                    expected_ancestors.add(str(ancestor))
            require(expected_ancestors == set(row['ancestors']), 'measurement_ancestor_coverage_incomplete')
            if shared_ancestors is None:
                shared_ancestors = set.intersection(*[{str(a) for a in (p,*p.parents) if a.is_relative_to(root_path)} for p in all_paths])
            for cg, values in row['cgroups'].items():
                require(values['inode'] and values['birth'] and set(values['gauges']) == {'memory.current','memory.swap.current','pids.current'}, 'measurement_identity_missing')
                require(set(values['counters']) == {'memory.events','memory.swap.events','cpu.stat','io.stat'}, 'measurement_counters_missing')
                require(all(type(v) is int and v >= 0 for v in values['gauges'].values())
                        and all(type(v) is int and v >= 0 for c in values['counters'].values() for v in c.values()), 'measurement_counter_invalid')
                require({'oom','oom_kill'} <= set(values['counters']['memory.events'])
                        and 'usage_usec' in values['counters']['cpu.stat'], 'measurement_counters_missing')
                if previous:
                    old = previous['cgroups'][cg]
                    require(values['inode'] == old['inode'] and values['birth'] == old['birth'], 'measurement_identity_changed')
                    require(old.get('memory.peak') is None or (values.get('memory.peak') is not None and values['memory.peak'] >= old['memory.peak']), 'measurement_counter_reset')
                    for field, counters in old['counters'].items():
                        require(counters.keys() == values['counters'][field].keys()
                                and all(values['counters'][field][k] >= v for k, v in counters.items()), 'measurement_counter_reset')
            for cg, values in row['ancestors'].items():
                require(set(values['limits']) == {'memory.max','memory.high','memory.swap.max','cpu.max','pids.max'}
                        and set(values['events']) == {'memory.events','memory.swap.events'}, 'measurement_ancestor_counters_missing')
                require(values['inode'], 'measurement_ancestor_identity_missing')
                for field, gauge, fraction in (('memory.max','memory.current',.95), ('pids.max','pids.current',.9)):
                    limit = values['limits'][field]
                    require(limit == 'max' or (int(limit) > 0 and values['gauges'][gauge] <= int(limit)*fraction), 'measurement_abort_threshold')
                if previous:
                    old = previous['ancestors'][cg]
                    require(values['inode'] == old['inode'] and values['limits'] == old['limits']
                            and values.get('absent_controls',[]) == old.get('absent_controls',[]), 'measurement_ancestor_changed')
                    require(values['gauges']['memory.swap.current'] <= old['gauges']['memory.swap.current'], 'measurement_swap_growth')
                    require(values['events'] == old['events'], 'measurement_memory_events')
                limit = values['limits']['memory.max']
                if cg in shared_ancestors:
                    ancestor_limits.add(limit if limit == 'max' else int(limit))
                ancestor_peaks[cg]=dict(limit=limit,shared=cg in shared_ancestors,
                    peak=max(values['gauges']['memory.current'],ancestor_peaks.get(cg,{}).get('peak',0)))
            operation = sum(row['cgroups'][p]['gauges']['memory.current'] for p in row['scopes']['operation_resources'])
            retained = sum(row['cgroups'][p]['gauges']['memory.current'] for p in row['scopes']['retained_services_excluding_operation'])
            operation_peak = max(operation_peak, operation)
            # Store simultaneous maximum demand; never sum independent peaks.
            if operation + retained > seen.get('simultaneous_peak', -1):
                seen.update(simultaneous_peak=operation + retained, operation=operation, retained=retained, peak_ns=timestamp)
            retained_peak = max(retained_peak, retained)
            available_min = min(available_min if available_min is not None else row['host']['MemAvailable'], row['host']['MemAvailable'])
            if physical_ram is not None:
                require(physical_ram == row['host']['MemTotal'] and swap == row['host']['SwapTotal'], 'measurement_host_changed')
            physical_ram, swap = row['host']['MemTotal'], row['host']['SwapTotal']
            seen.setdefault(row['phase'], []).append(timestamp)
            previous, count = row, count + 1
    require(count > 0, 'measurement_empty')
    for name, window in windows.items():
        times = seen.get(name, [])
        require(len(times) >= 2 and times[0] - window['start_ns'] <= 1_000_000_000
                and window['end_ns'] - times[-1] <= 1_000_000_000, 'measurement_boundary_coverage_missing')
    return dict(measurement=path.name, measurement_sha256=digest.hexdigest(),
                coverage='coverage.json', coverage_sha256=hashlib.sha256((root/'coverage.json').read_bytes()).hexdigest(),
                measurement_scopes=SCOPES, operation_id=coverage['operation_id'], samples=count, boot_id=boot,
                hostname=hostname, identities_verified=identities_verified,
                physical_ram=physical_ram, swap=swap, available_ram=available_min,
                observed_simultaneous_peak=seen['operation'], retained_services_peak=seen['retained'],
                simultaneous_peak_ns=seen['peak_ns'], operation_peak=operation_peak,
                retained_independent_peak=retained_peak, ancestor_applicability=ancestor_peaks, ancestor_memory_limits=sorted(ancestor_limits, key=str))


def assess(root, compatibility, *, host, source, configured_limits, headroom):
    """Only complete capture plus independently bound compatibility reaches validator."""
    evidence = validate_capture(root)
    from deploy.production_maintenance import capacity
    require(compatibility.get('source_compatible') is True and compatibility.get('reviewed_by')
            and compatibility.get('measurement_sha256') == evidence['measurement_sha256']
            and compatibility.get('coverage_sha256') == evidence['coverage_sha256']
            and compatibility.get('host') == host and compatibility.get('source') == source
            and evidence['hostname'] == host and evidence['identities_verified'] is True
            and compatibility.get('all_host_ancestors_visible') is True
            and compatibility.get('operation_accounting_complete') is True
            and compatibility.get('timer_coverage_complete') is True, 'measurement_compatibility_incomplete')
    bound = compatibility.get('production_retained_evidence')
    require(isinstance(bound, dict) and set(bound) == {'path','sha256'}, 'measurement_production_evidence_unbound')
    retained_path = safe_path(Path(bound['path']).absolute())
    require(hashlib.sha256(retained_path.read_bytes()).hexdigest() == bound['sha256'], 'measurement_production_evidence_changed')
    retained = read_manifest(retained_path)
    # This assessor admits same-host simultaneous measurements only. An isolated
    # host cannot borrow production availability/retained-service observations.
    require(retained.get('host') == host and retained.get('source') == source
            and retained.get('boot_id') == evidence['boot_id']
            and retained.get('measurement_sha256') == evidence['measurement_sha256']
            and retained.get('measurement_scopes') == SCOPES
            and retained.get('coverage_sha256') == evidence['coverage_sha256'], 'measurement_production_evidence_incompatible')
    require(isinstance(configured_limits, dict) and configured_limits, 'measurement_configured_limits_missing')
    provisional = max(256 * 1024**2, (evidence['observed_simultaneous_peak'] + evidence['retained_services_peak'] + 4)//5)
    require(type(headroom.get('bytes')) is int and headroom['bytes'] >= provisional and headroom.get('rationale'), 'measurement_headroom_incomplete')
    evidence.update(host=host, source=source, source_compatible=True, configured_limits=configured_limits,
                    headroom=headroom['bytes'], headroom_rationale=headroom['rationale'], compatibility=compatibility)
    for path, bound in evidence['ancestor_applicability'].items():
        if not bound['shared'] and bound['limit'] != 'max':
            reserve=headroom.get('ancestor_bytes',{}).get(path)
            require(type(reserve) is int and reserve >= 0, 'measurement_ancestor_headroom_missing')
            if bound['peak'] + reserve > int(bound['limit']):
                evidence.update(capacity='resize_decision_required', limiting_ancestor=path)
                return evidence
    evidence['capacity'] = capacity(evidence)
    if evidence['operation_peak'] + evidence['headroom'] > evidence['available_ram']:
        evidence['capacity'] = 'resize_decision_required'
    return evidence
