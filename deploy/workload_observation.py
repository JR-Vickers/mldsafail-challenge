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

MAX_BIRTHS = 4096
MAX_EVIDENCE_BYTES = 1024**2


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
    os.fchmod(progress.fileno(),0o600)
    progress_bytes = 0
    def retain(row):
        nonlocal progress_bytes
        raw = json.dumps(row)+'\n'
        if len(observed)>=MAX_BIRTHS or progress_bytes+len(raw.encode())>MAX_EVIDENCE_BYTES:
            raise RuntimeError('descendant_lifetime_evidence_limit')
        progress.write(raw);progress.flush();os.fsync(progress.fileno())
        progress_bytes += len(raw.encode())
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
    except BaseException as error:
        errors.append(dict(error=type(error).__name__,detail=str(error)[:256]))
    finally:
        escaped = bool(children())
        deadline = time.monotonic()+cleanup_seconds
        # Cleanup must run even when sampling/evidence allocation failed. An
        # unreaped direct child cannot have its PID reused; waitpid supplies
        # authority to signal it even after the evidence capacity is exhausted.
        unrecorded_observations = 0
        blocked=set()
        while children() and time.monotonic() < deadline:
            for pid in children():
                if time.monotonic()>=deadline:break
                if pid in blocked:continue
                try:
                    row=child_birth(pid);key=(row['pid'],row['start_ticks'])
                    if key not in observed:
                        try:
                            retain(dict(event='descendant',birth=row));observed[key]=row
                        except RuntimeError:
                            unrecorded_observations += 1
                    waited, status = os.waitpid(pid, os.WNOHANG)
                    if waited==process.pid:process.returncode=os.waitstatus_to_exitcode(status)
                    if waited == 0:os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError,FileNotFoundError):pass
                except OSError as error:
                    if len(errors)<MAX_BIRTHS:errors.append(dict(pid=pid,error=type(error).__name__))
                    if len(blocked)<MAX_BIRTHS:blocked.add(pid)
                    else:break
            if all(pid in blocked for pid in children()):break
            time.sleep(.005)
        remaining=[]
        final_children=children()
        if len(final_children)>MAX_BIRTHS:errors.append(dict(error='remaining_children_evidence_limit'))
        for pid in final_children[:MAX_BIRTHS]:
            try:remaining.append(child_birth(pid))
            except FileNotFoundError:pass
        progress.close()
        result = dict(returncode=process.returncode,timed_out=timed_out,
                      descendants=escaped,remaining=remaining,observed=list(observed.values()),errors=errors,
                      unrecorded_cleanup_observations=unrecorded_observations)
        raw = json.dumps(result)
        if len(raw.encode())>MAX_EVIDENCE_BYTES:
            result.update(remaining=remaining[:256],observed=list(observed.values())[:256],
                          errors=[dict(error='final_evidence_limit',ownership='unresolved')])
            raw = json.dumps(result)
        with open(report, 'x') as stream:
            os.fchmod(stream.fileno(),0o600)
            stream.write(raw)
            stream.flush();os.fsync(stream.fileno())


if __name__ == '__main__':main()
