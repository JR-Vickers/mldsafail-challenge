"""Gated streaming Docker client in an independently owned operator domain."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from deploy import owned_client


def spawn(argv, owner, accounting_parent):
    parent = os.environ.get('MLDSAFAIL_OPERATOR_CLIENT_CGROUP_ROOT')
    if parent is None:
        raise RuntimeError('Separate delegated operator client root required')
    parent, accounting_parent = Path(parent), Path(accounting_parent)
    if (parent == accounting_parent or parent in accounting_parent.parents or accounting_parent in parent.parents):
        raise RuntimeError('Operator clients must be outside the measured accounting domain')
    executable = shutil.which(argv[0])
    if executable is None:
        raise FileNotFoundError('Docker client unavailable')
    argv = [executable, *argv[1:]]
    entry = dict(id=uuid.uuid4().hex,pid=None,finished=False,
                 expected_cmdline_sha256=hashlib.sha256(b'\0'.join(os.fsencode(arg) for arg in argv)+b'\0').hexdigest())
    def save():
        owner.mutation('host_client_domain', **entry)
    domain = owned_client.prepare_domain(entry,parent)
    save()
    read_fd = write_fd = None
    process = None
    try:
        domain.mkdir()
        entry['cgroup']=owned_client.domain_identity(domain)
        if domain.stat().st_uid != os.getuid() or domain.stat().st_mode & 0o022:
            raise RuntimeError('Client domain lacks exclusive write access')
        if not all((domain/name).is_file() for name in ('cgroup.procs','cgroup.events','cgroup.kill')):
            raise RuntimeError('Client domain lacks kernel cleanup controls')
        save()
        read_fd,write_fd=os.pipe()
        code='import os,sys;fd=int(sys.argv[1]);gate=os.read(fd,1);os.close(fd);os.execv(sys.argv[2],sys.argv[2:]) if gate==b"1" else sys.exit(0)'
        process=subprocess.Popen([sys.executable,'-I','-c',code,str(read_fd),*argv],
                    pass_fds=(read_fd,),start_new_session=True,
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        os.close(read_fd);read_fd=None
        current=owned_client.identity(process.pid)
        entry.update(current,bootstrap_cmdline_sha256=current['cmdline_sha256'])
        entry.pop('cmdline_sha256')
        (domain/'cgroup.procs').write_text(str(process.pid))
        if process.pid not in [int(value) for value in (domain/'cgroup.procs').read_text().split()]:
            raise RuntimeError('Gated bootstrap membership unproven')
        save()  # All exact kernel/process identities are durable before exec.
        os.write(write_fd,b'1')
        os.close(write_fd);write_fd=None
        return process,entry
    except BaseException as error:
        for descriptor in (read_fd,write_fd):
            if descriptor is not None:
                try: os.close(descriptor)
                except OSError as cleanup: error.add_note('Gate close failed: '+repr(cleanup))
        try: owned_client.stop(entry)
        except BaseException as cleanup: error.add_note('Client domain cleanup failed: '+repr(cleanup))
        if process is not None:
            try:
                if process.poll() is None: process.kill()
                process.wait(timeout=15)
            except BaseException as cleanup: error.add_note('Bootstrap cleanup failed: '+repr(cleanup))
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try: stream.close()
                    except BaseException as cleanup: error.add_note('Independent bootstrap pipe cleanup failed: '+repr(cleanup))
        raise
