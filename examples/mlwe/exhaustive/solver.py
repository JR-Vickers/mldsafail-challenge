"""Frozen exhaustive example. Input and output are JSON objects."""
from mldsafail.benchmark_v050.models import instance_from_dict
from mldsafail.benchmark_v050.solvers import run_solver

def solve(public_instance):
    candidate, _, _ = run_solver('exhaustive', instance_from_dict(public_instance))
    return None if candidate is None else candidate.to_dict()
