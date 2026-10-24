from pathlib import Path

import pytest

from deploy.workload_installation import Journal,exclusive,identity
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.workload_installation_fixture import Fixture


def fixture(tmp_path):
    instance=object.__new__(Fixture);instance.root=tmp_path;instance.binding='a'*64
    instance.manifest={'generation':'b'*32}
    for name in ('runtime-journal','journal'):(tmp_path/name).mkdir(mode=0o700)
    instance.lifecycle_journal=Journal(tmp_path/'journal',instance.binding)
    runtime=Journal(tmp_path/'runtime-journal',instance.binding)
    return instance,runtime


def test_historical_uninvalidated_fixture_keeps_original_interpretation(tmp_path):
    instance,_=fixture(tmp_path)
    assert instance.require_control_inspection({'old':'reference'}) is None


def test_supervisor_shock_requires_exact_new_inspection(tmp_path):
    instance,runtime=fixture(tmp_path)
    runtime.append('fixture_installed_inspection_invalidated',generation=instance.manifest['generation'],process={'pid':1})
    with pytest.raises(WorkloadBlocked,match='fresh_installed_inspection_required'):instance.require_control_inspection()
    path=tmp_path/'inspection';exclusive(path,canonical({'synthetic':'test-only inspection'}));observed=identity(path)
    instance.lifecycle_journal.append('fixture_installed_inspection_refreshed',observed=observed,
        generation=instance.manifest['generation'],runtime_invalidation_sha256=digest(canonical(runtime.rows[-1])))
    reference=dict(path=str(path),sha256=observed['sha256'])
    instance.require_control_inspection(reference)
    with pytest.raises(WorkloadBlocked,match='packet_inspection_invalidated'):
        instance.require_control_inspection(dict(reference,sha256='c'*64))
    path.write_bytes(b'replacement')
    with pytest.raises(WorkloadBlocked,match='fresh_inspection_replaced'):instance.require_control_inspection(reference)


def test_second_shock_cannot_borrow_first_refresh(tmp_path):
    instance,runtime=fixture(tmp_path)
    runtime.append('fixture_installed_inspection_invalidated',process={'pid':1})
    path=tmp_path/'inspection';exclusive(path,b'first')
    instance.lifecycle_journal.append('fixture_installed_inspection_refreshed',observed=identity(path),
        generation=instance.manifest['generation'],runtime_invalidation_sha256=digest(canonical(runtime.rows[-1])))
    instance.require_control_inspection()
    runtime.append('fixture_installed_inspection_invalidated',process={'pid':2})
    with pytest.raises(WorkloadBlocked,match='fresh_installed_inspection_required'):instance.require_control_inspection()
