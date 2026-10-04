"""Version-specific authenticated evidence, with no legacy interpretation."""
import hashlib
import hmac
import json

SCHEMA = 'mldsafail.mlwe-v060-envelope.v1'


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sign(payload, key):
    if len(key) < 32:
        raise ValueError('Private signing key must contain at least 32 bytes')
    if payload.get('schema') != SCHEMA or payload.get('benchmark_version') != '0.6.0':
        raise ValueError('Explicit v060 envelope required')
    return {'payload': payload, 'signature': hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()}


def verify(envelope, key, *, cohort_id, source_sha256):
    if set(envelope) != {'payload', 'signature'}:
        raise ValueError('Invalid signed evidence')
    payload = envelope['payload']
    expected = sign(payload, key)['signature']
    if not isinstance(envelope['signature'], str) or not hmac.compare_digest(expected, envelope['signature']):
        raise ValueError('Evidence authentication failed')
    if payload.get('cohort_id') != cohort_id or payload.get('source_sha256') != source_sha256:
        raise ValueError('Evidence source/cohort mismatch')
    return payload


def independently_audited_case(records, *, directory, cohort, source_sha256,
                               worker_image, supervisor_source_sha256):
    """Re-read durable records; caller records cannot authenticate themselves."""
    from research.cpu_measurement.audit import audit_journal, case_cost
    trusted = []
    for record in records:
        generation = record['generation']
        audit_journal(directory, generation)
        # audit_journal returns a decision, so load the immutable record only
        # after its source tree and generation ownership were audited.
        from pathlib import Path
        path = Path(directory) / (generation + '.json')
        import os
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError('Evidence record exceeds cap')
        retained = json.loads(raw)
        binding = retained['binding']
        expected = {'source_sha256': source_sha256, 'image': worker_image,
                    'supervisor_source_sha256': supervisor_source_sha256,
                    'epoch': cohort.epoch_id}
        if any(binding.get(key) != value for key, value in expected.items()):
            raise ValueError('Untrusted source/worker/supervisor/epoch binding')
        if retained != record:
            raise ValueError('Caller record differs from audited durable evidence')
        trusted.append(retained)
    decision = case_cost(trusted)
    return dict(schema=SCHEMA, benchmark_version='0.6.0', cohort_id=cohort.public_id,
                source_sha256=source_sha256, worker_image=worker_image,
                supervisor_source_sha256=supervisor_source_sha256,
                epoch_id=cohort.epoch_id, decision=decision,
                evidence_sha256=[hashlib.sha256(canonical(record)).hexdigest() for record in trusted])
