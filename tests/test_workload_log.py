"""Log bounds must not cap offline installers' resource files."""
import subprocess
import sys

import pytest

from deploy.workload_log import LogPipe, OutputLimit


def test_large_resource_is_independent_of_log_limit(tmp_path):
    resource = tmp_path/'library.so'
    log = tmp_path/'log'
    with log.open('xb') as stream, LogPipe(stream,1024) as pipe:
        command = [sys.executable,'-I','-c',
                   'import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b"x"*(3*1024**2));print("installed")',str(resource)]
        process = subprocess.Popen(command,stdout=pipe.write_fd,stderr=subprocess.STDOUT)
        assert pipe.wait(process,5)==0
    assert resource.stat().st_size==3*1024**2
    assert log.read_bytes()==b'installed\n'


def test_flood_log_stops_at_bound_and_reader_is_reaped(tmp_path):
    process = None
    with pytest.raises(OutputLimit):
        with (tmp_path/'log').open('xb') as stream, LogPipe(stream,1024) as pipe:
            process = subprocess.Popen([sys.executable,'-I','-c','import os;os.write(1,b"x"*4096)'],
                                       stdout=pipe.write_fd,stderr=subprocess.STDOUT)
            pipe.wait(process,5)
    if process.poll() is None:process.kill()
    process.wait(timeout=2)
    assert (tmp_path/'log').stat().st_size==1024
    assert not pipe.thread.is_alive()


def test_launch_failure_does_not_leave_reader_or_descriptors(tmp_path):
    with pytest.raises(FileNotFoundError):
        with (tmp_path/'log').open('xb') as stream, LogPipe(stream,1024) as pipe:
            subprocess.Popen([str(tmp_path/'absent-command')],stdout=pipe.write_fd)
    assert not pipe.thread.is_alive()
