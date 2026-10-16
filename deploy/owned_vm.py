"""Task-owned local macOS VM birth gate and restart cleanup identities."""
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def identity(pid):
    if sys.platform != 'darwin': raise RuntimeError('Local QEMU ownership currently requires macOS')
    class BSD(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint32) for name in (
            'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]
        _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
        _fields_ += [(name, ctypes.c_uint32) for name in ('nfiles', 'group', 'jobc', 'tdev', 'tpgid')]
        _fields_ += [('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]
    info = BSD()
    library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    function = library.proc_pidinfo
    function.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int)
    function.restype = ctypes.c_int
    count = function(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
    if count == 0: raise ProcessLookupError(pid)
    if count != ctypes.sizeof(info): raise RuntimeError('Unexpected native process identity layout')
    command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True, timeout=5).strip()
    boot = subprocess.check_output(['sysctl', '-n', 'kern.bootsessionuuid'], text=True, timeout=5).strip()
    return {'pid': pid, 'uid': info.uid, 'start_sec': info.start_sec, 'start_usec': info.start_usec,
            'boot_id': boot, 'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
            'status': info.status}


def spawn(argv, publish, log):
    argv = list(argv); argv[0] = shutil.which(argv[0])
    if argv[0] is None: raise FileNotFoundError('Owned VM executable unavailable')
    entry = {'pid': None, 'expected_command_sha256': hashlib.sha256(' '.join(argv).encode()).hexdigest()}
    publish(entry)
    read_fd, write_fd = os.pipe()
    process = None
    code = 'import os,sys;fd=int(sys.argv[1]);gate=os.read(fd,1);os.close(fd);os.execv(sys.argv[2],sys.argv[2:]) if gate==b"1" else sys.exit(0)'
    try:
        process = subprocess.Popen([sys.executable, '-I', '-c', code, str(read_fd), *argv],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, pass_fds=(read_fd,), start_new_session=True)
        os.close(read_fd); read_fd = None
        current = identity(process.pid)
        entry.update(current, bootstrap_command_sha256=current['command_sha256'])
        entry.pop('command_sha256'); entry.pop('status')
        publish(entry)
        os.write(write_fd, b'1'); os.close(write_fd); write_fd = None
        return process, entry
    except BaseException as original:
        for descriptor in (read_fd, write_fd):
            if descriptor is not None:
                try: os.close(descriptor)
                except BaseException as error: original.add_note('VM gate cleanup failed: ' + type(error).__name__)
        if process is not None:
            try:
                if process.poll() is None: process.kill()
            except BaseException as error: original.add_note('Owned VM signal failed: ' + type(error).__name__)
            try: process.wait(timeout=15)
            except BaseException as error: original.add_note('Owned VM wait failed: ' + type(error).__name__)
        raise


def stop(entry):
    if entry.get('pid') is None: return
    current_boot = subprocess.check_output(['sysctl', '-n', 'kern.bootsessionuuid'], text=True, timeout=5).strip()
    if current_boot != entry['boot_id']: return
    try: current = identity(entry['pid'])
    except ProcessLookupError: return
    if any(current[key] != entry[key] for key in ('pid', 'uid', 'start_sec', 'start_usec', 'boot_id')):
        raise RuntimeError('Owned VM process identity mismatch')
    if current['status'] == 5: return  # Kernel zombie cannot execute.
    if current['command_sha256'] not in {entry['bootstrap_command_sha256'], entry['expected_command_sha256']}:
        raise RuntimeError('Owned VM command identity mismatch')
    # macOS has no pidfd; require a second full native start-time/UID/boot/command
    # sample immediately before signalling. This is within the trusted host UID.
    if identity(entry['pid']) != current: raise RuntimeError('Owned VM changed before cancellation')
    os.kill(entry['pid'], signal.SIGKILL)
    deadline = time.monotonic() + 15
    while True:
        try: row = identity(entry['pid'])
        except ProcessLookupError: return
        if row['status'] == 5: return
        if any(row[key] != entry[key] for key in ('pid', 'uid', 'start_sec', 'start_usec', 'boot_id')):
            raise RuntimeError('Owned VM identity changed during exit proof')
        if time.monotonic() >= deadline: raise RuntimeError('Owned VM remains executable')
        time.sleep(.05)
