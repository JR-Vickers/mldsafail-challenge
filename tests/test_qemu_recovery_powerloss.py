import pytest

from deploy.qemu_recovery_powerloss import run, ssh_argv


def test_loopback_only_task_owned_ssh(tmp_path):
    argv = ssh_argv(tmp_path, 22345)
    assert argv[-1] == 'ubuntu@127.0.0.1'
    assert 'IdentitiesOnly=yes' in argv
    assert str(tmp_path / 'key') in argv
    assert 'UserKnownHostsFile=' + str(tmp_path / 'known_hosts') in argv


def test_private_output_gate_before_network(tmp_path, monkeypatch):
    tmp_path.chmod(0o755)
    monkeypatch.setattr('deploy.qemu_recovery_powerloss.command',
                        lambda *args: pytest.fail('Invalid output must not download or start VM'))
    with pytest.raises(ValueError, match='Private'):
        run(tmp_path, tmp_path)
