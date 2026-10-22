"""Exact native case/deadline authorization and durable single-use claim.

Claim ambiguity is fail-closed: a pending claim requires manual reconciliation,
never replay. This module executes no fixture or cleanup command.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

from mldsafail.evaluator.native_workload import require

CASES = ('lifecycle', 'parent_oom', 'supervisor_death','ancestor_limit_change','log_exhaustion','controller_exit')
DEFAULT_SEQUENCE = [dict(case='lifecycle', seconds=45), dict(case='parent_oom', seconds=60),
                    dict(case='supervisor_death', seconds=60)]


def validate(sequence, total_seconds):
    require(type(sequence) is list and sequence and type(total_seconds) is int and
            0 < total_seconds <= 180, 'native_case_allowance_invalid')
    names = []
    for row in sequence:
        require(type(row) is dict and set(row) == {'case', 'seconds'} and row['case'] in CASES and
                type(row['seconds']) is int and 0 < row['seconds'] <= total_seconds,
                'native_case_not_allowlisted')
        names.append(row['case'])
    require(len(set(names)) == len(names) and sum(row['seconds'] for row in sequence) <= total_seconds,
            'native_case_sequence_invalid')
    return sequence


def bind(packet, authority):
    protocol = packet['native_acceptance']
    sequence = validate(protocol['sequence'], protocol['timeout_seconds'])
    cleanup = packet['deployment']['commands'].get('cleanup')
    require(type(cleanup) is list and cleanup and all(type(c) is str and c for c in cleanup),
            'native_cleanup_commands_missing')
    expected = dict(sequence=sequence, timeout_seconds=protocol['timeout_seconds'], cleanup=cleanup)
    require(authority.get('native_protocol') == expected, 'native_exact_protocol_authority_missing')
    return expected


def claim(authorization_path, protocol, *, expected_sha256=None, journal_root=None):
    """Fsync an exclusive intent before the first mutating fixture request."""
    path = Path(authorization_path).absolute()
    for parent in (path.parent, *path.parent.parents):
        require(not parent.is_symlink(), 'native_claim_parent_symlink')
    parent = path.parent.stat()
    require(parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) & 0o077 == 0,
            'native_claim_private_parent_required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
            stat.S_IMODE(before.st_mode) & 0o077 == 0, 'native_authority_file_invalid')
    raw = path.read_bytes()
    require(path.lstat() == before and
            (expected_sha256 is None or hashlib.sha256(raw).hexdigest() == expected_sha256),
            'native_authority_changed')
    journal = Path(journal_root).absolute() if journal_root is not None else path.parent
    for parent_path in (journal, *journal.parents):
        require(not parent_path.is_symlink(), 'native_claim_parent_symlink')
    journal_stat = journal.stat()
    require(stat.S_ISDIR(journal_stat.st_mode) and journal_stat.st_uid == os.getuid() and
            stat.S_IMODE(journal_stat.st_mode) & 0o077 == 0, 'native_claim_private_parent_required')
    consumed = journal/('native-authority-'+hashlib.sha256(raw).hexdigest()+'.consumed')
    try:
        fd = os.open(consumed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        require(False, 'native_authority_consumed_reconcile_required')
    with os.fdopen(fd, 'wb') as stream:
        stream.write(json.dumps(dict(schema='mldsafail.native-authorization-intent.v3',
                                    authorization_sha256=hashlib.sha256(raw).hexdigest(),
                                    protocol=protocol, disposition='claimed_requires_final_receipt_or_reconciliation'),
                                sort_keys=True).encode())
        stream.flush(); os.fsync(stream.fileno())
    directory = os.open(journal, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    return consumed
