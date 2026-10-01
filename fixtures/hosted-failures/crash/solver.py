"""Deliberate immediate failure for staging acceptance."""
def solve(public_instance):
    raise RuntimeError("synthetic acceptance crash")
