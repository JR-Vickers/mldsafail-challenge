"""Agent-editable toy arithmetic implementations."""
"""Small, dependency-free arithmetic primitives for toy lattice instances."""

from .lattice import is_invertible, mat_vec_mul, solve_linear_system
from .modular import add_mod, inverse_mod, multiply_mod, normalize
from .polynomial import add_polynomials, multiply_negacyclic

__all__ = [
    "add_mod",
    "add_polynomials",
    "inverse_mod",
    "is_invertible",
    "mat_vec_mul",
    "multiply_mod",
    "multiply_negacyclic",
    "normalize",
    "solve_linear_system",
]
