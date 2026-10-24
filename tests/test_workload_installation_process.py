"""Real Linux subprocess failure receipts, separate from runtime rehearsal."""
import sys
import pytest
from deploy.workload_installation import LinuxBackend, Journal
from deploy.workload_v3_fixture import inspection
from deploy.workload_v3 import bootstrap
from mldsafail.evaluator.workload import WorkloadBlocked

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Linux subreaper containment')


def backend(tmp_path):
    root=tmp_path/'journal';root.mkdir(mode=0o700)
    instance=LinuxBackend(bootstrap(inspection(),now=1100))
    instance.journal=Journal(root,'a'*64)
    return instance


def test_nonzero_command_retains_durable_outcome(tmp_path):
    instance=backend(tmp_path)
    with pytest.raises(WorkloadBlocked,match='subcommand_failed'):
        instance.command([sys.executable,'-c','print("failed");raise SystemExit(23)'])
    row=instance.journal.rows[-1]
    assert row['event']=='subcommand_outcome' and row['containment']['returncode']==23
    assert not row['cleanup_errors'] and row['log']['sha256']


def test_escaped_child_retains_birth_and_blocks_even_after_cleanup(tmp_path):
    instance=backend(tmp_path)
    code='import subprocess,sys;subprocess.Popen([sys.executable,"-c","import os,time;os.setsid();time.sleep(30)"])'
    with pytest.raises(WorkloadBlocked,match='containment_unverified'):
        instance.command([sys.executable,'-c',code])
    row=instance.journal.rows[-1]
    assert row['event']=='subcommand_outcome' and row['containment']['descendants']
    assert row['descendant_births'] and not row['containment']['remaining']


def test_command_timeout_retains_failure_and_births(tmp_path):
    import time
    instance=backend(tmp_path);instance.deadline=time.monotonic()+.6
    with pytest.raises(WorkloadBlocked,match='subcommand_failed'):
        instance.command([sys.executable,'-c','import time;time.sleep(30)'])
    row=instance.journal.rows[-1]
    assert row['containment']['timed_out'] and row['descendant_births']


def test_large_installer_resource_is_not_limited_by_log_cap(tmp_path):
    instance=backend(tmp_path);resource=tmp_path/'library.so'
    result=instance.command([sys.executable,'-I','-c',
        'import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"x"*(3*1024**2));print("installed")',str(resource)])
    assert resource.stat().st_size==3*1024**2 and result==b'installed\n'
    assert not instance.journal.rows[-1]['cleanup_errors']
    assert not instance.journal.rows[-1]['containment']['remaining']
