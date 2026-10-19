"""Absolute monotonic deadlines shared by diagnostic operations and subprocesses."""
from contextlib import contextmanager
import contextvars
import math
import time

_CURRENT = contextvars.ContextVar('diagnostic_deadline', default=None)


def remaining(deadline, ceiling, *, clock=time.monotonic):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('Absolute finite monotonic deadline required')
    if type(ceiling) not in (int, float) or not math.isfinite(ceiling) or ceiling <= 0:
        raise ValueError('Finite positive operation ceiling required')
    available = deadline - clock()
    if available <= 0:
        raise TimeoutError('Absolute diagnostic deadline exhausted')
    return min(ceiling, available)


@contextmanager
def bounded(deadline):
    previous = _CURRENT.get()
    if previous is not None:
        deadline = min(previous, deadline)
    remaining(deadline, 1)
    token = _CURRENT.set(deadline)
    try:
        yield deadline
    finally:
        _CURRENT.reset(token)


def timeout(ceiling):
    deadline = _CURRENT.get()
    return ceiling if deadline is None else remaining(deadline, ceiling)


@contextmanager
def interrupt_at(deadline):
    """Bound direct helper calls as well as owned commands, in the main thread.

    Native-only. The independent supervisor remains authoritative if a helper
    catches the timeout; this guard does not replace terminal ownership barriers.
    """
    import signal
    import threading
    if threading.current_thread() is not threading.main_thread():
        raise ValueError('Process deadline guard requires main thread')
    seconds = remaining(deadline, 3000)
    previous = signal.getsignal(signal.SIGALRM)
    old_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    def expired(_signal, _frame):
        raise TimeoutError('Absolute diagnostic process deadline exhausted')
    signal.signal(signal.SIGALRM, expired)
    previous_deadline = _CURRENT.get()
    token = _CURRENT.set(min(previous_deadline, deadline) if previous_deadline is not None else deadline)
    # Existing independent cleanup steps catch BaseException. Repeat expiration
    # while unwinding; nested operations also use the shared absolute deadline.
    signal.setitimer(signal.ITIMER_REAL, min(seconds, old_timer[0]) if old_timer[0] else seconds, .05)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        _CURRENT.reset(token)
        signal.signal(signal.SIGALRM, previous)
        if old_timer[0]:
            signal.setitimer(signal.ITIMER_REAL, max(.001, old_timer[0]-(time.monotonic()-started)), old_timer[1])


def release_setup():
    """Diagnostic engine only: setup is complete, phase guards now take over."""
    import signal
    signal.setitimer(signal.ITIMER_REAL, 0)
    _CURRENT.set(None)
