"""Durable, conservative diagnostic budget journal. No provisioning authority.

The caller must hold the host-wide serialization lock as well as this journal's
lock. Immutable start records consume slots even if publication or setup fails.
Only independent postflight can release the second generation's cleanup fence.
"""
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import stat
import time
import uuid

from deploy import owned_daemon
from scripts import production_diagnostic as diagnostic

SCHEMA = 'mldsafail.diagnostic-budget.v1'
SLOTS = ('preflight', 'baseline', 'post-fix')
LIMITS = (300, 3000, 3000)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def create(root):
    """Explicit one-time initialization; never repairs, overwrites or resets."""
    root = owned_daemon._canonical(root)
    root.mkdir(mode=0o700)  # Existing/partially initialized roots are terminal.
    owned_daemon.publish(root / 'identity.json', dict(schema=SCHEMA, id=uuid.uuid4().hex,
        initial_debit_seconds=diagnostic.INITIAL_DEBIT))
    return root


@contextmanager
def locked(root):
    root = owned_daemon._canonical(root)
    identity = owned_daemon._private_directory(root)
    fd = os.open(root / 'budget.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise ValueError('Private exclusive budget lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if owned_daemon._private_directory(root) != identity:
            raise ValueError('Budget root identity changed')
        yield Budget(root)
    finally:
        os.close(fd)


def _exclusive(path, value):
    """A failed write remains a consumed, unreadable slot; never replace it."""
    import json
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Budget:
    def __init__(self, root):
        self.root = Path(root)
        self.identity = owned_daemon.read_private_json(self.root / 'identity.json')
        if (self.identity.get('schema') != SCHEMA
                or self.identity.get('initial_debit_seconds') != diagnostic.INITIAL_DEBIT
                or not isinstance(self.identity.get('id'), str) or not self.identity['id']):
            raise ValueError('Existing debit and budget identity required')

    def inspect(self):
        continuation_names = ['preflight-continuation', 'correct-target-preflight', 'artifact-preflight']
        valid_names = set(SLOTS) | set(continuation_names)
        for suffix in ('-start.json', '-terminal.json'):
            if any(path.name[:-len(suffix)] not in valid_names for path in self.root.glob('*'+suffix)):
                raise ValueError('Unknown budget operation record')
        actual_continuations = [name for name in continuation_names if (self.root/(name+'-start.json')).exists()]
        if (actual_continuations or (self.root/'preflight-resolution.json').exists()) and not all(
                (self.root/('preflight'+suffix)).exists() for suffix in ('-start.json','-terminal.json')):
            raise ValueError('Original failed preflight history required')
        if any((self.root/(name+'-terminal.json')).exists() and name not in actual_continuations for name in continuation_names):
            raise ValueError('Continuation terminal without start')
        rows = []
        for index, (slot, limit) in enumerate(zip(SLOTS, LIMITS)):
            path = self.root / (slot + '-start.json')
            terminal = self.root / (slot + '-terminal.json')
            if not path.exists():
                if terminal.exists() or any((self.root / (later + suffix)).exists() for later in SLOTS[index+1:] for suffix in ('-start.json', '-terminal.json')):
                    raise ValueError('Nonsequential diagnostic history')
                break
            start = owned_daemon.read_private_json(path)
            if (set(start) != {'budget_id', 'slot', 'boot_id', 'monotonic_started', 'limit_seconds'}
                    or start.get('budget_id') != self.identity['id'] or start.get('slot') != slot
                    or start.get('limit_seconds') != limit or not finite(start.get('monotonic_started'))
                    or not isinstance(start.get('boot_id'), str) or not start['boot_id']):
                raise ValueError('Ambiguous generation start')
            row = dict(slot=slot, start=start, charged_seconds=limit, complete=False, cleanup_verified=False)
            if terminal.exists():
                end = owned_daemon.read_private_json(terminal)
                elapsed = end.get('elapsed_seconds')
                charge = end.get('charged_seconds')
                if (set(end) != {'start_sha256', 'elapsed_seconds', 'charged_seconds', 'complete',
                                 'cleanup_verified', 'cleanup_receipt_path', 'cleanup_receipt_sha256'}
                        or end.get('start_sha256') != diagnostic.digest(start) or not finite(elapsed)
                        or type(charge) is not int or charge != math.ceil(elapsed)
                        or type(end.get('complete')) is not bool or type(end.get('cleanup_verified')) is not bool):
                    raise ValueError('Ambiguous diagnostic terminal record')
                receipt = self.receipt(end['cleanup_receipt_path'])
                if (diagnostic.digest(receipt) != end.get('cleanup_receipt_sha256')
                        or receipt.get('budget_start_sha256') != diagnostic.digest(start)
                        or receipt.get('independent') is not True or receipt.get('passed') is not True):
                    raise ValueError('Retained independent cleanup evidence changed')
                row.update(end)
                if charge > limit:
                    row.update(complete=False, cleanup_verified=False)
            if slot == 'preflight' and (self.root/'preflight-resolution.json').exists():
                resolution = owned_daemon.read_private_json(self.root/'preflight-resolution.json')
                if set(resolution) != {'original_terminal_sha256','continuations','authorization'} or not resolution['authorization']:
                    raise ValueError('Explicit append-only preflight reconciliation required')
                if diagnostic.file_digest(terminal) != resolution['original_terminal_sha256'] or row['complete']:
                    raise ValueError('Original failed preflight must remain immutable')
                expected_names = continuation_names
                if (resolution['continuations'] != actual_continuations or
                        resolution['continuations'] != expected_names[:len(resolution['continuations'])] or not resolution['continuations']):
                    raise ValueError('Ordered bounded preflight continuations required')
                total = row['charged_seconds']
                complete = False
                for name in resolution['continuations']:
                    if name not in ('preflight-continuation', 'correct-target-preflight', 'artifact-preflight'):
                        raise ValueError('Unknown preflight continuation')
                    began = owned_daemon.read_private_json(self.root/(name+'-start.json'))
                    if not (self.root/(name+'-terminal.json')).exists():
                        total = 300
                        complete = False
                        break  # An interrupted start reserves the remaining preflight allocation.
                    ended = owned_daemon.read_private_json(self.root/(name+'-terminal.json'))
                    receipt = self.receipt(ended['cleanup_receipt_path'])
                    if (not finite(began.get('monotonic_started')) or not finite(began.get('limit_seconds'))
                            or began['limit_seconds'] <= 0 or type(ended.get('charged_seconds')) is not int
                            or type(ended.get('complete')) is not bool
                            or began['limit_seconds'] > 300-total or not began.get('boot_id')
                            or ended['start_sha256'] != diagnostic.digest(began)
                            or not finite(ended['elapsed_seconds'])
                            or ended['charged_seconds'] != math.ceil(ended['elapsed_seconds'])
                            or ended['charged_seconds'] > began['limit_seconds']
                            or receipt.get('budget_start_sha256') != diagnostic.digest(began)
                            or diagnostic.digest(receipt) != ended['cleanup_receipt_sha256']
                            or receipt.get('independent') is not True or receipt.get('passed') is not True
                            or ended['cleanup_verified'] is not True):
                        raise ValueError('Unverified preflight continuation')
                    total += ended['charged_seconds']
                    complete = ended['complete'] is True
                if len(resolution['continuations']) != len(set(resolution['continuations'])) or total > 300:
                    raise ValueError('Preflight allocation exceeded or duplicated')
                row.update(charged_seconds=total, complete=complete, cleanup_verified=complete)
            elif slot == 'preflight' and actual_continuations:
                row.update(charged_seconds=300, complete=False, cleanup_verified=False)
            rows.append(row)
        return dict(initial_debit_seconds=900, slots=rows,
                    charged_seconds=900 + sum(row['charged_seconds'] for row in rows))

    def receipt(self, path):
        # A portable private evidence bundle retains original absolute references.
        # Relocated bytes must still match the immutable terminal's receipt digest.
        original = Path(path)
        return owned_daemon.read_private_json(original if original.exists() else self.root.parent/original.name)

    def start(self, slot, *, boot_id, clock=time.monotonic):
        state = self.inspect()
        index = len(state['slots'])
        if index >= len(SLOTS) or slot != SLOTS[index]:
            raise ValueError('No retry, reset or third generation permitted')
        if any(not row['complete'] or not row['cleanup_verified'] for row in state['slots']):
            raise ValueError('Verified prior completion and cleanup required')
        if state['charged_seconds'] + LIMITS[index] > diagnostic.AGGREGATE_SECONDS:
            raise ValueError('Aggregate budget exhausted')
        started = clock()
        if not finite(started) or not isinstance(boot_id, str) or not boot_id:
            raise ValueError('Unambiguous boot and monotonic clock required')
        entry = dict(budget_id=self.identity['id'], slot=slot, boot_id=boot_id,
                     monotonic_started=started, limit_seconds=LIMITS[index])
        _exclusive(self.root / (slot + '-start.json'), entry)
        return diagnostic.Allowance(started, LIMITS[index], 0 if index == 0 else 900, clock=clock)

    def finish(self, slot, *, boot_id, complete, cleanup_receipt, clock=time.monotonic):
        state = self.inspect()
        if not state['slots'] or state['slots'][-1]['slot'] != slot:
            raise ValueError('Only active final slot can terminate')
        start = state['slots'][-1]['start']
        elapsed = clock() - start['monotonic_started']
        if boot_id != start['boot_id'] or not finite(elapsed) or type(complete) is not bool:
            raise ValueError('Ambiguous elapsed time; retain full reserved charge')
        # Bind actual independent evidence rather than accepting a caller boolean.
        receipt = owned_daemon.read_private_json(cleanup_receipt)
        if (receipt.get('budget_start_sha256') != diagnostic.digest(start)
                or receipt.get('independent') is not True or receipt.get('passed') is not True):
            raise ValueError('Independent start-bound cleanup receipt required')
        entry = dict(start_sha256=diagnostic.digest(start), elapsed_seconds=elapsed,
            charged_seconds=math.ceil(elapsed), complete=complete,
            cleanup_verified=True, cleanup_receipt_path=str(owned_daemon._canonical(cleanup_receipt)),
            cleanup_receipt_sha256=diagnostic.digest(receipt))
        _exclusive(self.root / (slot + '-terminal.json'), entry)
        return self.inspect()
