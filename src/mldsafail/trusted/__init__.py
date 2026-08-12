"""Trusted challenge generation and verification code."""
"""Trusted toy-instance generation and independent verification."""

from .generator import generate_instance, generate_instance_with_diagnostics, load_profiles
from .verifier import verify

__all__ = ["generate_instance", "generate_instance_with_diagnostics", "load_profiles", "verify"]
