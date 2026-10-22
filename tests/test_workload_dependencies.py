from pathlib import Path
import pytest
from deploy.workload_dependencies import ENV,closure,marker,satisfies,wheel_candidates
from mldsafail.evaluator.workload import WorkloadBlocked


def test_existing_lock_has_complete_target_wheel_candidates():
    lock=Path('uv.lock').read_bytes();packages,_=closure(lock)
    assert len(packages)==35
    assert set(wheel_candidates(lock))==set(packages)
    assert 'pytest' not in packages and 'psycopg-binary' in packages
    assert 'pywin32-ctypes' not in packages


@pytest.mark.parametrize('expression,expected',[("python_full_version < '3.9'",False),
    ("python_full_version < '3.13'",True),("sys_platform == 'linux' and platform_machine == 'x86_64'",True),
    ("extra == 'binary'",False)])
def test_markers_use_target_environment(expression,expected):
    assert marker(expression,ENV)==expected


def test_unsupported_marker_cannot_execute_code():
    with pytest.raises(WorkloadBlocked): marker("__import__('os').system('false')",ENV)


@pytest.mark.parametrize('selected,specifier,result',[('2.10','>=2.9,<3',True),('3.0','<3',False),
    ('3.2.8','~=3.2',True),('4.0','~=3.2',False),('3.2.8','==3.2.*',True)])
def test_requirement_versions(selected,specifier,result):
    assert satisfies(selected,specifier)==result


def test_installed_interpreter_and_environment_configuration_are_verified(tmp_path):
    from deploy.workload_dependencies import installed_inventory
    python=tmp_path/'python';python.write_bytes(b'bound interpreter')
    other=tmp_path/'other';other.write_bytes(b'different interpreter')
    venv=tmp_path/'venv';(venv/'bin').mkdir(parents=True)
    executable=venv/'bin/python';executable.symlink_to(python)
    config=venv/'pyvenv.cfg';config.write_text('include-system-site-packages = false\n')
    original=installed_inventory(venv,interpreter=python)
    assert 'pyvenv.cfg' in original
    config.write_text('include-system-site-packages = true\n')
    assert installed_inventory(venv,interpreter=python)!=original
    executable.unlink();executable.symlink_to(other)
    with pytest.raises(WorkloadBlocked,match='interpreter_changed'):installed_inventory(venv,interpreter=python)


def test_generated_router_style_entrypoint_executes_at_final_path_without_bytecode(tmp_path):
    import json,subprocess,sys
    from deploy.workload_dependencies import entrypoint_code
    bundle=tmp_path/'bundle';(bundle/'src').mkdir(parents=True)
    (bundle/'src'/'fixture_router.py').write_text('import json,sys\ndef main():\n print(json.dumps(dict(bytecode=sys.dont_write_bytecode,python=sys.executable)))\n')
    wrapper=bundle/'docker';wrapper.write_bytes(entrypoint_code(bundle,sys.executable,'fixture_router','main'));wrapper.chmod(0o700)
    result=json.loads(subprocess.check_output([str(wrapper)],text=True))
    assert result['bytecode'] is True and Path(result['python']).resolve()==Path(sys.executable).resolve()
    assert not (bundle/'src'/'__pycache__').exists()
