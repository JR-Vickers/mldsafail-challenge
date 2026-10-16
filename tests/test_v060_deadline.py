import signal
import time
import pytest
from mldsafail.benchmark_v060.deadline import deadline,EvaluationDeadlineExceeded


def test_deadline_interrupts_blocked_evaluation_and_restores_process_timer():
    previous=signal.getsignal(signal.SIGALRM)
    with pytest.raises(EvaluationDeadlineExceeded,match='no score'):
        with deadline(.02): time.sleep(1)
    assert signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0)
    assert signal.getsignal(signal.SIGALRM)==previous


def test_deadline_refuses_competing_timer_without_overwriting_it():
    signal.setitimer(signal.ITIMER_REAL,10)
    try:
        with pytest.raises(RuntimeError,match='conflicts'):
            with deadline(1): pass
        assert signal.getitimer(signal.ITIMER_REAL)[0]>9
    finally: signal.setitimer(signal.ITIMER_REAL,0)


def test_complete_evaluation_installs_fixed_platform_ceiling(monkeypatch):
    from contextlib import contextmanager
    from mldsafail.benchmark_v060 import evaluation
    from mldsafail.benchmark_v060 import deadline as module
    observed=[]
    @contextmanager
    def fake_deadline(seconds):
        observed.append(seconds)
        yield lambda:None
    monkeypatch.setattr(module,'deadline',fake_deadline)
    monkeypatch.setattr(evaluation,'_evaluate',lambda **kwargs:kwargs['checkpoint']() or 'result')
    assert evaluation.evaluate()=='result'
    assert observed==[1200]
