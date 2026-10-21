from copy import deepcopy

import pytest

from deploy.workload_native_protocol import DEFAULT_SEQUENCE, bind, claim, validate
from mldsafail.evaluator.workload import WorkloadBlocked


def test_bound_sequence_and_cleanup():
    protocol = dict(sequence=deepcopy(DEFAULT_SEQUENCE), timeout_seconds=180, cleanup=['exact cleanup'])
    packet = dict(native_acceptance=protocol, deployment=dict(commands=dict(cleanup=protocol['cleanup'])))
    assert bind(packet, dict(native_protocol=protocol)) == protocol
    changed = deepcopy(protocol); changed['sequence'].reverse()
    with pytest.raises(WorkloadBlocked): bind(packet, dict(native_protocol=changed))
    changed = deepcopy(protocol); changed['cleanup'] = ['other cleanup']
    with pytest.raises(WorkloadBlocked): bind(packet, dict(native_protocol=changed))


@pytest.mark.parametrize('sequence,seconds', [([dict(case='unknown', seconds=1)], 180),
    (DEFAULT_SEQUENCE, 181), (DEFAULT_SEQUENCE, 120),
    ([dict(case='lifecycle', seconds=True)], 180),
    ([dict(case='lifecycle', seconds=1)]*2, 180), ([], 180)])
def test_invalid_allowances(sequence, seconds):
    with pytest.raises(WorkloadBlocked): validate(sequence, seconds)


def test_interrupted_intent_cannot_replay(tmp_path):
    tmp_path.chmod(0o700)
    authority = tmp_path/'authorization.json'
    authority.write_text('{}'); authority.chmod(0o600)
    intent = claim(authority, dict(sequence=DEFAULT_SEQUENCE))
    assert intent.exists() and intent.stat().st_mode & 0o777 == 0o600
    with pytest.raises(WorkloadBlocked, match='reconcile'): claim(authority, {})


def test_public_parent_cannot_store_authority(tmp_path):
    tmp_path.chmod(0o755)
    authority = tmp_path/'authorization.json'; authority.write_text('{}'); authority.chmod(0o600)
    with pytest.raises(WorkloadBlocked): claim(authority, {})


def test_copied_authorization_cannot_replay_in_bound_journal(tmp_path):
    tmp_path.chmod(0o700)
    first = tmp_path/'first.json'; first.write_text('{}'); first.chmod(0o600)
    second = tmp_path/'second.json'; second.write_text('{}'); second.chmod(0o600)
    claim(first, {}, journal_root=tmp_path)
    with pytest.raises(WorkloadBlocked, match='reconcile'): claim(second, {}, journal_root=tmp_path)
