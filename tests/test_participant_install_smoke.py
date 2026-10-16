import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('participant_install_smoke', Path(__file__).parents[1]/'scripts/participant_install_smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_python_source_environment_is_removed(monkeypatch):
    for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
        monkeypatch.setenv(name, '/untrusted/source')
    environment = smoke.isolated_environment()
    assert all(name not in environment for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'))
    assert environment['PYTHONNOUSERSITE'] == '1'


def test_import_and_prefix_must_both_belong_to_fresh_install(tmp_path):
    install = tmp_path/'installed'
    identity = {'package_path': str(install/'lib/python3.12/site-packages/mldsafail/__init__.py'), 'prefix': str(install)}
    smoke.validate_installed_identity(identity, install)
    with pytest.raises(RuntimeError, match='outside'):
        smoke.validate_installed_identity(dict(identity, package_path=str(tmp_path/'source/mldsafail/__init__.py')), install)
    with pytest.raises(RuntimeError, match='outside'):
        smoke.validate_installed_identity(dict(identity, prefix=str(tmp_path/'other')), install)


def test_symlinked_source_package_is_rejected(tmp_path):
    install = tmp_path/'installed'
    install.mkdir()
    source = tmp_path/'source'
    source.mkdir()
    (source/'__init__.py').write_text('')
    (install/'mldsafail').symlink_to(source, target_is_directory=True)
    with pytest.raises(RuntimeError, match='outside'):
        smoke.validate_installed_identity({'package_path': str(install/'mldsafail/__init__.py'), 'prefix': str(install)}, install)
