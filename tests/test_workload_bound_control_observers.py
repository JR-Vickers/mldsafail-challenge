"""Synthetic observer regression tests; never native acceptance evidence."""
from pathlib import Path

import pytest

from deploy import workload_bound_control_observers as observers
from mldsafail.evaluator.workload import WorkloadBlocked


def test_process_observations_measure_kernel_rows_and_detect_outside_scope(tmp_path, monkeypatch):
    inventory = [dict(pid=pid, start_ticks=pid+10) for pid in (100, 101, 102)]
    real_path = Path
    for item in inventory:
        path = tmp_path/str(item['pid']); path.mkdir()
        (path/'cgroup').write_text('0::/owned/child\n' if item['pid'] != 102 else '0::/other\n')
    def path(value):
        return tmp_path if str(value) == '/proc' else real_path(value)
    monkeypatch.setattr(observers, 'Path', path)
    monkeypatch.setattr(observers, 'process_birth', lambda pid: dict(pid=pid, start_ticks=pid+10))
    raw = observers.process_placement(real_path('/sys/fs/cgroup/owned'), inventory)
    assert raw['inspected_processes'] == 3 and raw['outside_heavy'] == 1
    assert raw['processes'][0]['raw_cgroup'] == '0::/owned/child\n'


def test_replaced_process_is_rejected_before_read(tmp_path, monkeypatch):
    monkeypatch.setattr(observers, 'process_birth', lambda pid: dict(pid=pid, start_ticks=999))
    with pytest.raises(WorkloadBlocked, match='process_replaced'):
        observers.process_placement(Path('/sys/fs/cgroup/owned'),
            [dict(pid=pid, start_ticks=pid) for pid in (100, 101, 102)])


def test_kernel_observer_refuses_nonlinux_or_ordinary_file_namespace(monkeypatch):
    monkeypatch.setattr(observers.sys, 'platform', 'darwin')
    with pytest.raises(WorkloadBlocked, match='requires_linux'):
        observers.kernel_scope(dict(fixture_cgroup='/sys/fs/cgroup/owned'))
    monkeypatch.setattr(observers.sys, 'platform', 'linux')
    with pytest.raises(WorkloadBlocked, match='fixture_scope_required'):
        observers.kernel_scope(dict(fixture_cgroup='/tmp/fake-cgroup'))


def test_synthetic_packet_cannot_promote_observer_origin(monkeypatch):
    monkeypatch.setattr(observers, 'validate', lambda packet: packet)
    with pytest.raises(WorkloadBlocked, match='installed_context_required'):
        observers.observe(dict(stage='installed', protocol=dict(origin='synthetic')),
            'delegation', 'inspected_limits')


def test_scope_replacement_invalidates_raw_observations(monkeypatch):
    monkeypatch.setattr(observers, 'validate', lambda packet: packet)
    monkeypatch.setattr(observers, 'kernel_scope', lambda protocol: Path('/sys/fs/cgroup/owned'))
    births = iter([dict(inode=1), dict(inode=2)])
    monkeypatch.setattr(observers, 'birth', lambda scope: next(births))
    monkeypatch.setattr(observers, 'cgroup_observation', lambda scope: dict(limits={}))
    monkeypatch.setattr(observers, 'values', lambda scope: dict(populated=0))
    with pytest.raises(WorkloadBlocked, match='fixture_replaced'):
        observers.observe(dict(stage='installed', protocol=dict(origin='local_linux')),
            'delegation', 'inspected_limits')


def test_nested_ordinary_mount_cannot_masquerade_as_kernel_scope(monkeypatch):
    from types import SimpleNamespace
    real_path = Path
    mounts = ('1 0 0:42 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n'
              '2 1 0:43 / /sys/fs/cgroup/owned rw - tmpfs tmpfs rw\n')
    monkeypatch.setattr(observers.sys, 'platform', 'linux')
    monkeypatch.setattr(observers, 'Path', lambda value: SimpleNamespace(read_text=lambda: mounts)
        if str(value) == '/proc/self/mountinfo' else real_path(value))
    with pytest.raises(WorkloadBlocked, match='cgroup2_mount_required'):
        observers.kernel_scope(dict(fixture_cgroup='/sys/fs/cgroup/owned/child'))
