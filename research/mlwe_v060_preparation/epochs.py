"""Fresh private draft epochs only: no execution, references, seal or activation."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import uuid
from research.cpu_measurement.ownership import publish
from mldsafail.benchmark_v050.constants import STUDY_VERSION
from mldsafail.benchmark_v050.generator import generate_mlwe
from mldsafail.benchmark_v050.models import digest
from mldsafail.benchmark_v050.scoring import CHALLENGE_CELLS
from .contracts import Cohort

VERSION = '0.6.0'


def private_cases(nonce):
    if not isinstance(nonce, str) or len(nonce) != 64 or any(char not in '0123456789abcdef' for char in nonce):
        raise ValueError('Fresh 32-byte epoch nonce required')
    by_profile = {}
    for profile, eta in CHALLENGE_CELLS:
        if profile not in by_profile:
            seeds = []
            counter = 0
            while len(seeds) < 20:
                material = f'{STUDY_VERSION}\0validation\0{VERSION}\0{profile}\0{nonce}\0{counter}'.encode()
                seed = int.from_bytes(hashlib.sha256(material).digest()[:8], 'big')
                if seed not in seeds:
                    seeds.append(seed)
                counter += 1
            by_profile[profile] = seeds
    result = []
    for profile, eta in CHALLENGE_CELLS:
        for seed in by_profile[profile]:
            public = generate_mlwe(profile, seed, eta).public
            result.append(dict(profile=profile, eta=eta, seed=seed, instance_id=public.instance_id,
                               input_digest=digest(public.to_dict())))
    import random
    random.Random(f'{STUDY_VERSION}:{VERSION}:validation:{nonce}').shuffle(result)
    return result


def prepare_epoch(output, cohort, *, worker_artifact, forbidden_epoch_ids=()):
    if not isinstance(cohort, Cohort) or cohort.benchmark_version != VERSION:
        raise ValueError('Fresh 0.6.0 cohort required; no 0.5.0 conversion')
    if worker_artifact.get('benchmark_version') != VERSION or worker_artifact.get('measurement_method') != cohort.measurement_method:
        raise ValueError('Separately identified 0.6.0 worker artifact required')
    import re
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', worker_artifact.get('image', '')):
        raise ValueError('Immutable reviewed worker identity required')
    if cohort.epoch_id in forbidden_epoch_ids:
        raise ValueError('Existing epoch identity must not be reused')
    output = Path(output)
    if any(path.is_symlink() for path in (output.absolute(), *output.absolute().parents)):
        raise ValueError('Private epoch paths cannot contain symlinks')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    nonce = secrets.token_hex(32)
    manifest = dict(schema='mldsafail.mlwe-v060-epoch-draft.v1', benchmark_version=VERSION,
                    epoch_id=cohort.epoch_id, draft_id=uuid.uuid4().hex,
                    created_utc=datetime.now(timezone.utc).isoformat(), ready=False,
                    measurement_method=cohort.measurement_method, worker_artifact=worker_artifact,
                    cohort=__import__('dataclasses').asdict(cohort), cases=private_cases(nonce),
                    reference_costs_available=False,
                    next_gate='reviewed native reference evaluation and independent epoch audit')
    publish(output / 'secret.json', dict(benchmark_version=VERSION, nonce=nonce))
    publish(output / 'manifest.json', manifest)
    return manifest
