"""Gated streaming Docker client in an independently owned operator domain."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from deploy import owned_client


def spawn(argv, owner, accounting_parent, *, phase="attach", receipt_file=None):
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
    entry = dict(id=uuid.uuid4().hex,pid=None,finished=False,phase=phase,receipt_file=receipt_file,
                 expected_cmdline_sha256=hashlib.sha256(b'\0'.join(os.fsencode(arg) for arg in argv)+b'\0').hexdigest())
    def save():
        owner.mutation('host_client_domain', **entry)
    domain = owned_client.prepare_domain(entry,parent)
    save()
    read_fd = write_fd = None
    process = None
    release_uncertain = False
    try:
        domain.mkdir()
        owned_client.secure_created_domain(entry,domain)
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
        owner.mutation('host_client_release_intent', **entry)
        release_uncertain = True
        os.write(write_fd,b'1')
        os.close(write_fd);write_fd=None
        return process,entry
    except BaseException as error:
        for descriptor in (read_fd,write_fd):
            if descriptor is not None:
                try: os.close(descriptor)
                except OSError as cleanup: error.add_note('Gate close failed: '+repr(cleanup))
        if not release_uncertain or phase == 'attach':
            try: owned_client.stop(entry)
            except BaseException as cleanup: error.add_note('Client domain cleanup failed: '+repr(cleanup))
        if process is not None:
            try:
                if not release_uncertain or phase == 'attach':
                    if process.poll() is None: process.kill()
                    process.wait(timeout=15)
            except BaseException as cleanup: error.add_note('Bootstrap cleanup failed: '+repr(cleanup))
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    try: stream.close()
                    except BaseException as cleanup: error.add_note('Independent bootstrap pipe cleanup failed: '+repr(cleanup))
        raise


def mutation(argv, owner, parent, manifest, operation):
    """Independent guardian receipt precedes every subsequent lifecycle phase."""
    import json
    import time
    receipt_file=owner.record['generation']+'-'+operation+'-'+uuid.uuid4().hex+'.json'
    owner.mutation('daemon_mutation_intent',operation_name=operation,receipt_file=receipt_file,
                   daemon_epoch=manifest['epoch'])
    command=[sys.executable,'-m','research.cpu_measurement.guardian','--receipt',
             str(owner.directory/receipt_file),'--epoch',manifest['epoch'],
             '--operation',operation,*argv]
    process,entry=spawn(command,owner,parent,phase=operation,receipt_file=receipt_file)
    try:
        deadline=time.monotonic()+45
        path=owner.directory/receipt_file
        while not path.exists():
            if process.poll() is not None or time.monotonic()>deadline:
                # Never kill a potentially submitted creator here. Reconciliation
                # must stop the dedicated daemon epoch before cancelling guardian.
                raise RuntimeError('Mutation guardian acknowledgement incomplete')
            time.sleep(.05)
        from research.cpu_measurement.mutations import receipt as read_receipt
        receipt=read_receipt(owner.directory,receipt_file,operation=operation,epoch=manifest['epoch'])
        errors=[]
        try: process.wait(timeout=15)
        except BaseException as error: errors.append(repr(error))
        try: owned_client.stop(entry)
        except BaseException as error: errors.append(repr(error))
        if errors: raise RuntimeError('Acknowledged mutation client cleanup failed: '+repr(errors))
        owner.mutation('daemon_mutation_acknowledged',operation_name=operation,
                       receipt_file=receipt_file,container_id=receipt['container_id'],daemon_epoch=manifest['epoch'])
        return receipt['container_id']
    finally:
        cleanup_errors=[]
        for stream in (process.stdin,process.stdout,process.stderr):
            if stream is not None:
                try: stream.close()
                except BaseException as error: cleanup_errors.append(repr(error))
        if cleanup_errors:
            current=sys.exception()
            if current is not None: current.add_note('Guardian parent stream cleanup failed: '+repr(cleanup_errors))
            else: raise RuntimeError('Guardian parent stream cleanup failed: '+repr(cleanup_errors))
