"""Bounded Linux cgroup-v2 evidence capture; importing never samples or mutates."""
import hashlib
import json
import os
from pathlib import Path
import time

SCOPES = {
    'observed_simultaneous_peak': 'operation_resources',
    'retained_services_peak': 'retained_services_excluding_operation',
    'available_ram': 'host_available_excluding_retained_usage',
}
COUNTERS = ('memory.events', 'memory.swap.events', 'cpu.stat', 'io.stat')
LIMITS = ('memory.max', 'memory.high', 'memory.swap.max', 'cpu.max', 'pids.max')
GAUGES = ('memory.current', 'memory.swap.current', 'pids.current')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def counters(text):
    result = {}
    for line in text.splitlines():
        words = line.split()
        if len(words) == 2 and '=' not in words[1]:
            result[words[0]] = int(words[1])
        else:
            for word in words[1:]:
                key, value = word.split('=')
                result[words[0] + ':' + key] = int(value)
    return result


class Sampler:
    """Caller supplies inspected birth identities; all scopes must be disjoint.

    The operation parent must include helpers, clients, sampler, tmpfs and page
    cache. Scope membership certification remains an independent review gate.
    """
    def __init__(self, scopes, identities, filesystem, *, cgroup='/sys/fs/cgroup', proc='/proc'):
        self.root = Path(cgroup).resolve(strict=True)
        self.proc = Path(proc)
        require(set(scopes) == {'operation_resources', 'retained_services_excluding_operation'}, 'scopes_missing')
        self.scopes = {k: [Path(p).resolve(strict=True) for p in v] for k, v in scopes.items()}
        paths = [p for group in self.scopes.values() for p in group]
        require(all(self.scopes.values()), 'empty_scope')
        require(all(p != self.root and p.is_relative_to(self.root) for p in paths), 'scope_outside_root')
        require(not any(a.is_relative_to(b) or b.is_relative_to(a)
                        for i, a in enumerate(paths) for b in paths[i+1:]), 'overlapping_scopes')
        require(set(identities) == {str(p) for p in paths}, 'birth_identity_missing')
        require(all(v.get('container_id') and v.get('pid') and v.get('start_ticks') for v in identities.values()), 'birth_identity_missing')
        self.identities = identities
        self.filesystem = filesystem
        self.previous = None
        self.inodes = {str(p): p.stat().st_ino for p in paths}
        self.boot = (self.proc / 'sys/kernel/random/boot_id').read_text().strip()
        require(bool(self.boot), 'boot_identity_missing')

    def sample(self, phase, *, now=None):
        require(phase in {'setup', 'stop', 'create', 'audit', 'inspection', 'cleanup', 'restoration'}, 'unknown_phase')
        now = time.monotonic_ns() if now is None else now
        require(self.previous is None or 0 < now - self.previous['monotonic_ns'] <= 1_000_000_000, 'sampling_gap')
        require((self.proc / 'sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot_changed')
        rows, ancestors = {}, {}
        for paths in self.scopes.values():
            for path in paths:
                key = str(path)
                require(path.resolve(strict=True) == path and path.stat().st_ino == self.inodes[key], 'cgroup_replaced')
                birth = self.identities[key]
                fields = (self.proc / str(birth['pid']) / 'stat').read_text().rsplit(')', 1)[1].split()
                require(int(fields[19]) == birth['start_ticks'], 'process_replaced')
                membership = (self.proc / str(birth['pid']) / 'cgroup').read_text().splitlines()
                require('0::/' + str(path.relative_to(self.root)) in membership, 'process_scope_changed')
                row = dict(inode=self.inodes[key], birth=birth,
                           gauges={f: int((path / f).read_text()) for f in GAUGES},
                           counters={f: counters((path / f).read_text()) for f in COUNTERS})
                peak = path / 'memory.peak'
                row['memory.peak'] = int(peak.read_text()) if peak.exists() else None
                rows[key] = row
                for ancestor in (path, *path.parents):
                    if not ancestor.is_relative_to(self.root):
                        break
                    if ancestor == self.root:
                        ancestors[str(ancestor)] = dict(inode=ancestor.stat().st_ino,
                            limits={f: 'max' for f in LIMITS}, gauges={f: 0 for f in GAUGES},
                            events={f: {} for f in ('memory.events', 'memory.swap.events')},
                            disposition='cgroup_root_host_constraints_apply')
                        continue
                    ancestors[str(ancestor)] = dict(inode=ancestor.stat().st_ino,
                        limits={f: (ancestor / f).read_text().strip() for f in LIMITS},
                        gauges={f: int((ancestor / f).read_text()) for f in GAUGES},
                        events={f: counters((ancestor / f).read_text()) for f in ('memory.events', 'memory.swap.events')})
        memory = counters((self.proc / 'meminfo').read_text().replace(':', '').replace(' kB', ''))
        memory = {k: v * 1024 for k, v in memory.items()}
        fs = os.statvfs(self.filesystem)
        sample = dict(boot_id=self.boot, monotonic_ns=now, phase=phase, scopes=self.scopes,
                      cgroups=rows, ancestors=ancestors, host=memory,
                      filesystem_available=fs.f_bavail * fs.f_frsize)
        require(memory['MemAvailable'] >= 256 * 1024**2, 'host_memory_floor')
        require(sample['filesystem_available'] >= 2 * 1024**3, 'filesystem_floor')
        for key, row in ancestors.items():
            for field, gauge, fraction in (('memory.max', 'memory.current', .95), ('pids.max', 'pids.current', .9)):
                limit = row['limits'][field]
                require(limit == 'max' or row['gauges'][gauge] <= int(limit) * fraction, 'ancestor_abort_threshold')
            require(not row['events']['memory.events'].get('oom', 0)
                    and not row['events']['memory.events'].get('oom_kill', 0), 'oom_evidence')
        if self.previous:
            require(ancestors.keys() == self.previous['ancestors'].keys(), 'ancestor_changed')
            for key, row in ancestors.items():
                old = self.previous['ancestors'][key]
                require(row['inode'] == old['inode'] and row['limits'] == old['limits'], 'ancestor_changed')
                require(row['gauges']['memory.swap.current'] <= old['gauges']['memory.swap.current'], 'swap_growth')
                for field, values in row['events'].items():
                    require(values == old['events'][field], 'memory_event_changed')
            for key, row in rows.items():
                for field, values in row['counters'].items():
                    old = self.previous['cgroups'][key]['counters'][field]
                    require(values.keys() == old.keys() and all(values[k] >= old[k] for k in old), 'counter_reset')
        # JSON contains paths as strings, never interpreter-specific objects.
        sample['scopes'] = {k: [str(p) for p in v] for k, v in self.scopes.items()}
        self.previous = sample
        return sample


def capture(sampler, stream, phases, *, health, identity, duration, max_bytes=64 * 1024**2):
    """250 ms monotonic schedule; output exhaustion and every callback fail closed.

    stream must be an exclusively created private binary evidence file. phases,
    health and identity must themselves provide bounded I/O in the supervisor.
    """
    require(0 < duration <= 8000 and 0 < max_bytes <= 64 * 1024**2, 'capture_bounds')
    start = time.monotonic()
    tick, written = start, 0
    while time.monotonic() - start < duration:
        require(health() is True and identity() is True, 'service_or_identity_lost')
        row = sampler.sample(phases())
        data = (json.dumps(row, sort_keys=True) + '\n').encode()
        require(written + len(data) <= max_bytes, 'sample_output_exhausted')
        stream.write(data)
        stream.flush()
        written += len(data)
        tick += .25
        time.sleep(max(0, tick - time.monotonic()))
    return written


def receipt(raw, *, expected_phases, compatibility):
    """No validator invocation until coverage and compatibility are complete."""
    raw = Path(raw)
    require(raw.stat().st_size <= 64 * 1024**2, 'sample_output_exhausted')
    rows = [json.loads(line) for line in raw.read_bytes().splitlines()]
    require(rows and set(r['phase'] for r in rows) == set(expected_phases), 'incomplete_phase_coverage')
    require(all(0 < b['monotonic_ns'] - a['monotonic_ns'] <= 1_000_000_000 for a, b in zip(rows, rows[1:])), 'sampling_gap')
    return dict(schema='mldsafail.capacity-measurement.v1', measurement=raw.name,
                measurement_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                measurement_scopes=SCOPES, compatibility=compatibility,
                source_compatible=False, capacity='unresolved',
                limitation='Raw capture requires independent scope, phase-boundary and production compatibility review before capacity validation')
