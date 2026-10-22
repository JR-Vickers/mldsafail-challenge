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
    cleanup_seconds = 1.0
    if argv[:1] == ['--cleanup-seconds']:
        cleanup_seconds = float(argv[1]); argv = argv[2:]
        if not 0 < cleanup_seconds <= 1:
            raise ValueError('invalid cleanup budget')
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'subreaper unavailable')
    progress = open(report+'.births.jsonl', 'x')
    def retain(row):
        progress.write(json.dumps(row)+'\n');progress.flush();os.fsync(progress.fileno())
    observed = {}
    def snapshot():
        pending = children();seen=set()
        while pending:
            pid=pending.pop()
            if pid in seen:continue
            seen.add(pid)
            if len(seen)>4096:raise RuntimeError('descendant inventory bound')
            try:
                row=child_birth(pid)
                descendants=Path('/proc/'+str(pid)+'/task/'+str(pid)+'/children').read_text().split()
                if child_birth(pid)!=row:continue
                key=(row['pid'],row['start_ticks'])
                if key not in observed:
                    retain(dict(event='descendant',birth=row));observed[key]=row
                pending.extend(int(value) for value in descendants)
            except (ProcessLookupError,FileNotFoundError):pass
    process = subprocess.Popen(argv)
    timed_out = False; escaped = False; errors = []
    try:
        try:
            command_deadline=time.monotonic()+float(allowance)
            while True:
                snapshot()
                remaining=command_deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired(argv,float(allowance))
                try:
                    process.wait(timeout=min(.05,remaining));break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=command_deadline:raise
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=cleanup_seconds)
        escaped = bool(children())
        deadline = time.monotonic()+cleanup_seconds
        # An unreaped child PID cannot be reused. Record births before signals.
        while children() and time.monotonic() < deadline:
            for pid in children():
                try:
                    row=child_birth(pid);key=(row['pid'],row['start_ticks'])
                    if key not in observed:
                        retain(dict(event='descendant',birth=row));observed[key]=row
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
        progress.close()
        with open(report, 'x') as stream:
            json.dump(dict(returncode=process.returncode,timed_out=timed_out,
                           descendants=escaped,remaining=remaining,
                           observed=list(observed.values()),errors=errors),stream)
            stream.flush();os.fsync(stream.fileno())


if __name__ == '__main__':main()
