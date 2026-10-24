"""Guest bootstrap pins and scope gates, without privileged operations."""
import pytest

from mldsafail.evaluator.workload import WorkloadBlocked
from scripts.provision_installation_fixture_guest import REQUIRED, package_arguments, provision


def test_guest_packages_require_explicit_complete_version_pins():
    pins={name:'1:2.3-ubuntu1' for name in REQUIRED}
    result=package_arguments(pins)
    assert result==[name+'=1:2.3-ubuntu1' for name in sorted(REQUIRED)]


@pytest.mark.parametrize('pins', [{}, {'postgresql':'17'}, {'docker.io':'latest --allow-unauthenticated'},
                                {name:True for name in REQUIRED}])
def test_missing_unrelated_or_injected_package_pins_are_refused(pins):
    with pytest.raises(WorkloadBlocked):package_arguments(pins)


def test_guest_provider_cannot_mutate_an_unsupported_host(tmp_path,monkeypatch):
    from pathlib import Path
    import tempfile
    monkeypatch.setattr('scripts.provision_installation_fixture_guest.environment',lambda:dict(blockers=['unsupported']))
    with tempfile.TemporaryDirectory(prefix='env-',dir=Path('/tmp').resolve()) as short:
        root=Path(short)/'guest'
        with pytest.raises(WorkloadBlocked,match='owned_qemu_guest_required'):
            provision(root,tmp_path/'spec',tmp_path/'review')
        assert not root.exists()


def test_unsafe_unit_path_is_rejected_before_any_guest_effect(tmp_path):
    with pytest.raises(WorkloadBlocked,match='unit_path_invalid'):
        provision(tmp_path/'bad\nExecStart=evil',tmp_path/'spec',tmp_path/'review')
    assert not (tmp_path/'bad\nExecStart=evil').exists()
