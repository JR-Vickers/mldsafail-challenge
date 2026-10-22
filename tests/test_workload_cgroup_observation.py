"""Temporary files test observation bindings; they are not Linux cgroup proof."""
import os

import pytest

from deploy.workload_installed import CGROUP_LIMITS,cgroup_observation,verify_ancestor_observations
from mldsafail.evaluator.workload import WorkloadBlocked


def fixture(path):
    (path/'cgroup.controllers').write_text('cpu memory pids\n')
    (path/'cgroup.subtree_control').write_text('cpu memory pids\n')
    (path/'cgroup.procs').write_text('')
    for key in CGROUP_LIMITS:(path/key).write_text('max\n')
    return cgroup_observation(path)


def test_observation_binds_subtree_allowances_and_control_permissions(tmp_path):
    row=fixture(tmp_path)
    assert row['subtree_control']==['cpu','memory','pids']
    assert row['control_permissions']['cgroup.procs']['uid']==os.getuid()
    source=dict(resources=dict(delegation=dict(ancestors=[row])))
    verify_ancestor_observations(source)
    (tmp_path/'cgroup.subtree_control').write_text('cpu pids\n')
    with pytest.raises(WorkloadBlocked,match='ancestor_changed'):verify_ancestor_observations(source)


def test_permission_drift_blocks_even_with_unchanged_limits(tmp_path):
    row=fixture(tmp_path);source=dict(resources=dict(delegation=dict(ancestors=[row])))
    target=tmp_path/'cgroup.procs';target.chmod(target.stat().st_mode^0o020)
    with pytest.raises(WorkloadBlocked,match='ancestor_changed'):verify_ancestor_observations(source)


def test_symlink_control_is_not_a_delegation_permission(tmp_path):
    fixture(tmp_path);target=tmp_path/'cgroup.procs';target.unlink();target.symlink_to(tmp_path/'memory.max')
    with pytest.raises(WorkloadBlocked,match='control_symlink'):cgroup_observation(tmp_path)
