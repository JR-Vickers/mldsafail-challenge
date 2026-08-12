"""Agent-editable solver implementations."""
"""Reference solvers.

Optimization work is expected to replace or improve :func:`solve` while
preserving its deliberately small public contract.
"""

from .baseline import SolverError, solve

__all__ = ["SolverError", "solve"]
