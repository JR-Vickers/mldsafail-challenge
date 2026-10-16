"""Fixed complete-evaluation platform deadline; cleanup retains its own fence."""
from contextlib import contextmanager
import signal
import threading
import time

COMPLETE_EVALUATION_SECONDS=20*60


class EvaluationDeadlineExceeded(RuntimeError):
    pass


@contextmanager
def deadline(seconds):
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal,'setitimer'):
        raise RuntimeError('Complete evaluation requires a dedicated native main-thread deadline executor')
    if type(seconds) not in (int,float) or seconds<=0 or seconds>COMPLETE_EVALUATION_SECONDS:
        raise ValueError('Positive bounded complete evaluation deadline required')
    if signal.getitimer(signal.ITIMER_REAL)!=(0.0,0.0):
        raise RuntimeError('Existing process timer conflicts with evaluation ownership')
    expires=time.monotonic()+seconds
    previous=signal.getsignal(signal.SIGALRM)
    def interrupt(*args):
        raise EvaluationDeadlineExceeded('Complete evaluation platform deadline exceeded; no score')
    def check():
        if time.monotonic()>=expires: interrupt()
    signal.signal(signal.SIGALRM,interrupt)
    try:
        signal.setitimer(signal.ITIMER_REAL,seconds)
        yield check
        check()
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
