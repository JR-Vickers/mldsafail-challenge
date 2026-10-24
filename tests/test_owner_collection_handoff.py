"""Preparation-only handoff tests; no root execution or host access."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.prepare_owner_collection_handoff import prepare


def inputs(tmp_path):
    plan = tmp_path/'plan.json'
    plan.write_text(json.dumps(dict(runtime_account='mldsafail', reviewed_paths=[],
        reviewed_sha256={}, output_paths=[])))
    dossier = tmp_path/'dossier.json'
    dossier.write_text(json.dumps(dict(schema='mldsafail.private-host-readiness-dossier.v1',
        execution_authority=False, prerequisites=dict(
            delegation=dict(status='blocked', reason='missing_permissions'),
            original_reader=dict(status='evidenced', evidence='private-original')))))
    return plan, dossier, hashlib.sha256(plan.read_bytes()).hexdigest()


def test_handoff_is_private_preserves_blockers_and_freezes_artifact(tmp_path):
    plan, dossier, digest = inputs(tmp_path)
    root = Path(__file__).resolve().parents[1]
    a = prepare(root, tmp_path/'first', plan, dossier, reviewed_plan_sha256=digest)
    b = prepare(root, tmp_path/'second', plan, dossier, reviewed_plan_sha256=digest)
    assert a['artifact']['sha256'] == b['artifact']['sha256']
    assert a['instructions_sha256'] == b['instructions_sha256']
    assert a['missing_facts'] == dict(delegation=dict(status='blocked', reason='missing_permissions'))
    assert a['original_installation']['disposition'] == 'preserve_unchanged'
    assert not a['installed'] and not a['transferred'] and not a['execution_authority']
    assert 'exact_source_and_artifact_independent_review_required' in a['blockers']
    assert (tmp_path/'first').stat().st_mode & 0o777 == 0o700
    for item in (tmp_path/'first').iterdir():
        assert item.stat().st_mode & 0o777 == 0o600
    instructions = (tmp_path/'first/ADMINISTRATOR.md').read_text()
    assert a['artifact']['sha256'] in instructions
    assert 'set -eu' in instructions and 'visudo -c' in instructions
    assert 'sudo -n '+a['artifact']['command'] in instructions
    with pytest.raises(FileExistsError):
        prepare(root, tmp_path/'first', plan, dossier, reviewed_plan_sha256=digest)


def test_substituted_plan_refused_before_creating_packet(tmp_path):
    plan, dossier, digest = inputs(tmp_path)
    plan.write_text(plan.read_text()+'\n')
    with pytest.raises(ValueError, match='reviewed_plan_identity_changed'):
        prepare('.', tmp_path/'out', plan, dossier, reviewed_plan_sha256=digest)
    assert not (tmp_path/'out').exists()


def test_authority_bearing_or_unknown_dossier_refused(tmp_path):
    plan, dossier, digest = inputs(tmp_path)
    contents = json.loads(dossier.read_bytes()); contents['execution_authority'] = True
    dossier.write_text(json.dumps(contents))
    with pytest.raises(ValueError, match='private_readiness_dossier_required'):
        prepare('.', tmp_path/'out', plan, dossier, reviewed_plan_sha256=digest)
