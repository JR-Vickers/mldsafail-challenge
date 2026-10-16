"""Bounded read-only lifecycle attribution, never an accounting substitute.

Process samples can miss short-lived tasks and use coarse kernel clock ticks.
Only the ordinary complete cpu.stat window supplies authoritative measurements.
"""
import os
import itertools
from pathlib import Path
import threading
import time


def process_sample(pid, proc_root=Path('/proc')):
    root=proc_root/str(pid)
    with (root/'stat').open() as stream:raw=stream.read(4097)
    if len(raw)>4096:raise RuntimeError('Process stat diagnostic cap exceeded')
    closing=raw.rfind(')')
    if closing<0:raise ValueError('Malformed process stat')
    fields=raw[closing+2:].split()
    return dict(pid=pid,start_ticks=int(fields[19]),user_ticks=int(fields[11]),
                system_ticks=int(fields[12]),uid=root.stat().st_uid,
                comm=raw[raw.index('(')+1:closing][:128])


class Sampler:
    """Read only the exact owned worker domain, with fixed memory/time caps."""
    def __init__(self,parent,*,interval=.01,maximum_samples=12000):
        if interval!=.01 or maximum_samples!=12000:
            raise ValueError('Fixed declared diagnostic sampling protocol required')
        self.parent=Path(parent)
        identity=self.parent.stat()
        self.identity=(identity.st_dev,identity.st_ino)
        self.interval=interval;self.maximum_samples=maximum_samples
        self.process_observations=0;self.samples=[];self.errors=[];self.stop=threading.Event();self.thread=None

    def sample(self):
        current=self.parent.stat()
        if (current.st_dev,current.st_ino)!=self.identity:
            raise RuntimeError('Diagnostic parent replaced')
        counters={key:int(value) for key,value in (row.split() for row in (self.parent/'cpu.stat').read_text().splitlines())}
        paths=list(itertools.islice(self.parent.rglob('cgroup.procs'),257))
        if len(paths)>256:raise RuntimeError('Diagnostic descendant domain cap exceeded')
        pids=set()
        for path in paths:
            try:
                with path.open() as stream:raw=stream.read(8193)
            except FileNotFoundError:continue
            if len(raw)>8192:raise RuntimeError('Diagnostic membership file cap exceeded')
            pids.update(int(value) for value in raw.split())
        if len(pids)>128:raise RuntimeError('Diagnostic process cap exceeded')
        processes=[];unavailable=[]
        for pid in sorted(pids):
            try:processes.append(process_sample(pid))
            except (FileNotFoundError,ProcessLookupError,PermissionError):unavailable.append(pid)
        return dict(monotonic=time.monotonic(),cpu_stat=counters,processes=processes,unavailable_pids=unavailable)

    def start(self):
        def collect():
            try:
                while not self.stop.is_set():
                    if len(self.samples)>=self.maximum_samples:raise RuntimeError('Diagnostic sample cap exceeded')
                    sample=self.sample()
                    self.process_observations+=len(sample['processes'])
                    if self.process_observations>12000:raise RuntimeError('Diagnostic total process observation cap exceeded')
                    self.samples.append(sample)
                    self.stop.wait(self.interval)
            except BaseException as error:self.errors.append(type(error).__name__)
        self.thread=threading.Thread(target=collect,name='owned-cpu-phase-diagnostic',daemon=True)
        self.thread.start()

    def finish(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(2)
            if self.thread.is_alive():raise RuntimeError('Diagnostic sampler cleanup incomplete')
        return dict(schema='mldsafail.cpu-phase-samples.v1',samples=self.samples,errors=self.errors,
                    interval_seconds=self.interval,maximum_samples=self.maximum_samples,maximum_process_observations=12000,
                    process_clock_ticks_per_second=os.sysconf('SC_CLK_TCK'),
                    attribution_complete=False,authoritative_cpu_replacement=False)
