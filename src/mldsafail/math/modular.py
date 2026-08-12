"""Elementary modular arithmetic with explicit input validation."""


def _check_modulus(modulus: int) -> None:
    if isinstance(modulus, bool) or not isinstance(modulus, int) or modulus <= 1:
        raise ValueError("modulus must be an integer greater than one")


def normalize(value: int, modulus: int) -> int:
    """Return the canonical residue of ``value`` modulo ``modulus``."""
    _check_modulus(modulus)
    return value % modulus


def add_mod(left: int, right: int, modulus: int) -> int:
    _check_modulus(modulus)
    return (left + right) % modulus


def multiply_mod(left: int, right: int, modulus: int) -> int:
    _check_modulus(modulus)
    return (left * right) % modulus


def inverse_mod(value: int, modulus: int) -> int:
    """Return a multiplicative inverse, raising when none exists."""
    _check_modulus(modulus)
    try:
        return pow(value % modulus, -1, modulus)
    except ValueError as exc:
        raise ValueError(f"{value} has no inverse modulo {modulus}") from exc
