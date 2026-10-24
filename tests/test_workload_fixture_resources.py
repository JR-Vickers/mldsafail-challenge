"""Ownership/inactivity boundaries for the concrete disposable resource adapter."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.workload_fixture_resources import Resources, resource_plan
from deploy.workload_installation import Journal, exclusive, identity
from deploy.workload_release import canonical
from mldsafail.evaluator.workload import WorkloadBlocked


@pytest.fixture
def resources(tmp_path):
    root = tmp_path/'fixture'; root.mkdir(mode=0o700)
    (root/'inputs').mkdir(mode=0o700); (root/'journal').mkdir(mode=0o700)
    unit_directory = str(Path.home()/'.config/systemd/user')
    settings = dict(coordinator_image='sha256:'+'1'*64,worker_environment={},evaluator_fingerprint='2'*64,
                    postgres_image='sha256:'+'3'*64,unit_directory=unit_directory,
                    daemon_pid_file='/run/user/1000/docker.pid',daemon_executable='/not-an-executable')
    exclusive(root/'inputs/settings',canonical(settings))
    fixture = SimpleNamespace(root=root,journal=Journal(root/'journal','a'*64),manifest=dict(
        generation='b'*32,inputs=dict(settings={}),resource_plan=resource_plan(root,1000,unit_directory)))
    fixture.command = lambda *args,**kwargs:pytest.fail('external command was not authorized by this test')
    result = Resources(fixture)
    result.plan['heavy'] = str(root/'absent-heavy')
    return result


def test_plans_are_distinct_and_preserve_required_artifacts(tmp_path):
    first = resource_plan(tmp_path/'first',1000,'/home/operator/.config/systemd/user')
    second = resource_plan(tmp_path/'second',1000,'/home/operator/.config/systemd/user')
    assert set(first['containers'].values()).isdisjoint(second['containers'].values())
    assert first['compute'] != second['compute']
    assert {'output','output.ext4','previous','engine-journal'}<=set(first['preserve'])


@pytest.mark.parametrize('path', ['/etc/passwd','relative','/tmp/../etc/passwd'])
def test_unplanned_paths_never_reach_mutations(resources,path):
    with pytest.raises(WorkloadBlocked):resources.create(Path(path),lambda:pytest.fail('foreign mutation'))


def test_private_root_is_not_a_blanket_resource_allowlist(resources):
    path = resources.root/'foreign-source'
    with pytest.raises(WorkloadBlocked,match='not_planned'):
        resources.create(path,lambda:path.write_bytes(b'foreign'))
    assert not path.exists()


def test_resource_parent_symlink_is_not_followed(resources,tmp_path):
    outside = tmp_path/'outside'; outside.mkdir()
    (resources.root/'release').symlink_to(outside,target_is_directory=True)
    with pytest.raises(WorkloadBlocked,match='parent_symlink'):
        resources.write(resources.root/'release/file',b'owned')
    assert not (outside/'file').exists()


def test_precomputation_replaced_directory_is_not_deleted(resources):
    root = resources.root/'release'; resources.mkdir(root)
    root.rename(resources.root/'saved-release');root.mkdir(mode=0o700)
    (root/'unknown').write_bytes(b'preserve')
    with pytest.raises(WorkloadBlocked,match='creation_identity_changed'):
        resources.retire_precomputation({}, {})
    assert (root/'unknown').read_bytes()==b'preserve'


def test_precomputation_unknown_empty_directory_is_not_adopted(resources,monkeypatch):
    from deploy.workload_release import digest
    root=resources.root/'release';resources.mkdir(root)
    for name in ('bundle','tools','.venv','config'):(root/name).mkdir(mode=0o700)
    configurations={}
    for role in ('supervisor','native','controller'):
        path=root/'config'/(role+'.json');exclusive(path,b'{}')
        configurations[role]=dict(path=str(path),sha256=digest(b'{}'))
    resources.journal.append('fixture_precomputation_inventory',root=identity(root),tree=resources.tree(root))
    (root/'bundle/unowned-empty').mkdir()
    monkeypatch.setattr('deploy.workload_fixture_resources.verify',lambda *args:None)
    monkeypatch.setattr('deploy.workload_artifacts.verify_installed_tools',lambda *args:None)
    monkeypatch.setattr('deploy.workload_dependencies.installed_inventory',lambda *args,**kwargs:{})
    with pytest.raises(WorkloadBlocked,match='inventory_changed'):
        resources.retire_precomputation(dict(configurations=configurations),{})
    assert (root/'bundle/unowned-empty').is_dir()


def test_daemon_change_blocks_before_external_command(resources,monkeypatch):
    resources._daemon_binding = dict(process='original')
    monkeypatch.setattr(resources,'daemon_birth',lambda:dict(process='replacement'))
    with pytest.raises(WorkloadBlocked,match='daemon_replaced'):
        resources.run(['external'])


def test_partial_cleanup_preserves_unacknowledged_resource(resources):
    path = resources.root/'output.ext4'; path.write_bytes(b'uncertain')
    resources.journal.append('fixture_resource_intent',path=str(path))
    result = resources.partial_cleanup()
    assert not result['cleanup_verified']
    assert result['unresolved']==[dict(path=str(path),reason='unacknowledged_resource')]
    assert path.read_bytes()==b'uncertain'


def test_partial_cleanup_preserves_unacknowledged_prerequisite(resources):
    resources.journal.append('mutation_intent',resource='output_mount_activation')
    result = resources.partial_cleanup()
    assert not result['cleanup_verified']
    assert result['unresolved'][0]['reason']=='unacknowledged_prerequisite_effect'


def test_partial_cleanup_rejects_replaced_unit_before_stop(resources,monkeypatch):
    directory = resources.root/'units';directory.mkdir()
    resources.plan['unit_directory'] = str(directory)
    path = directory/resources.plan['compute'];exclusive(path,b'original')
    resources.journal.append('fixture_resource_created',path=str(path),observed=identity(path))
    replacement = directory/'replacement';exclusive(replacement,b'original');replacement.replace(path)
    monkeypatch.setattr(resources,'unit',lambda *args:pytest.fail('replacement unit stopped'))
    with pytest.raises(WorkloadBlocked,match='unit_replaced'):resources.partial_cleanup()
    assert path.read_bytes()==b'original'


def test_existing_cgroup_blocks_before_service_creation(resources,monkeypatch):
    path = resources.root/'inherited-cgroup';path.mkdir()
    resources.plan['cgroups'] = [str(path)]
    monkeypatch.setattr(resources,'daemon',lambda:{})
    monkeypatch.setattr(resources,'services',lambda *args:pytest.fail('containers created before namespace proof'))
    with pytest.raises(WorkloadBlocked,match='inherited_resource_preserve'):resources.provision()
