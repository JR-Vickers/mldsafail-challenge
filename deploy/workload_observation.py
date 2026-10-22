"""Linux subreaper for bounded, nonhostile read-only observation clients.

This process owns only its command and descendants adopted from it. A failed
cleanup retains births for reconciliation, including unsignalable sudo children.
"""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def children():
    return [int(pid) for pid in Path('/proc/self/task/'+str(os.getpid())+'/children').read_text().split()]


def child_birth(pid):
    fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,start_ticks=int(fields[19]))


def main():
    report, allowance, *argv = sys.argv[1:]
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'subreaper unavailable')
    process = subprocess.Popen(argv)
    timed_out = False; escaped = False; errors = []; observed = {}
    try:
        try:
            process.wait(timeout=float(allowance))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=1)
        escaped = bool(children())
        deadline = time.monotonic()+1
        # An unreaped child PID cannot be reused. Record births before signals.
        while children() and time.monotonic() < deadline:
            for pid in children():
                try:
                    observed[pid]=child_birth(pid)
                    waited, _ = os.waitpid(pid, os.WNOHANG)
                    if waited == 0:os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError,FileNotFoundError):pass
                except OSError as error:
                    errors.append(dict(pid=pid,error=type(error).__name__))
            if errors:break
            time.sleep(.005)
    except BaseException as error:
        errors.append(dict(error=type(error).__name__))
    finally:
        remaining=[]
        for pid in children():
            try:remaining.append(child_birth(pid))
            except FileNotFoundError:pass
        with open(report, 'x') as stream:
            json.dump(dict(returncode=process.returncode,timed_out=timed_out,
                           descendants=escaped,remaining=remaining,
                           observed=list(observed.values()),errors=errors),stream)
            stream.flush();os.fsync(stream.fileno())


if __name__ == '__main__':main()
