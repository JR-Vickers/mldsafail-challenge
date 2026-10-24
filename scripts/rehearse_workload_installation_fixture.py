"""Fixed disposable-fixture cases; synthetic authority is never VPS authority."""
import argparse
import json
import time
import uuid
from pathlib import Path

from deploy.workload_installation import Journal, exclusive, private
from deploy.workload_release import canonical, digest
from mldsafail.evaluator.native_workload import require
from scripts.workload_installation_fixture import CASES, Fixture, lifecycle_lock, prepare

REVIEW_FILES = ('deploy/workload_fixture_resources.py','deploy/workload_installation.py','deploy/workload_log.py',
                'deploy/workload_observation.py','scripts/workload_vm_fixture.py',
                'scripts/prepare_installation_fixture_recipe.py',
                'scripts/provision_installation_fixture_guest.py',
                'scripts/workload_fixture_worker.py','scripts/workload_installation_fixture.py',
                'scripts/rehearse_workload_installation_fixture.py')


def component_review(fixture):
    _,component = private(fixture.root/'inputs/component_review')
    require(component.get('decision')=='approved' and component.get('scope')=='disposable_fixture_components_only' and
            component.get('reviewed_by') != component.get('implemented_by') and component.get('reviewed_by') and
            component.get('implemented_by') and
            all(component.get('source_sha256',{}).get(name)==fixture.manifest['source_hashes'][name] for name in REVIEW_FILES),
            'fixture_independent_component_review_required')
    return component


def inputs(fixture, phase, *, reconciliation=False):
    """Make explicitly synthetic engine-schema inputs after component review.

    The fixture task authorizes disposable runs only. These inputs retain the
    engine's exact-byte/review/expiry/nonce checks and are generation-scoped.
    They do not represent independent review of a production proposal.
    """
    fixture.require_target()
    component = component_review(fixture)
    raw,_ = fixture.proposal()
    scope = dict(fixture_only=True,fixture_generation=fixture.manifest['generation'],fixture_manifest_sha256=fixture.binding,
                 scope='synthetic_fixture_inputs_not_production_proposal_approval')
    review = dict(scope,decision='approved',implemented_by=component['implemented_by'],reviewed_by=component['reviewed_by'],
                  proposal_sha256=digest(raw),component_review_sha256=digest(private(fixture.root/'inputs/component_review',parse=False)[0]))
    token = uuid.uuid4().hex
    review_path = fixture.root/'artifacts'/('review-'+token+'.json')
    exclusive(review_path,canonical(review))
    now = time.time()
    authority = dict(scope,schema='mldsafail.workload-installation-authority.v3',authorized_by='owner',
                     proposal_sha256=digest(raw),review_sha256=digest(canonical(review)),phase=phase,
                     issued_at=now,expires_at=now+min(290,fixture.deadline()),nonce=uuid.uuid4().hex)
    if reconciliation:authority['reconcile']=True
    authority_path = fixture.root/'artifacts'/('authority-'+token+'.json')
    exclusive(authority_path,canonical(authority))
    return dict(review=review_path,authority=authority_path)


def protocol(fixture):
    case = fixture.manifest['case']
    fixture.transition('provision')
    _,proposal = fixture.proposal()
    engine_root = proposal['identities']['recipe']['journal_root']
    binding = digest(canonical(proposal))
    def journal():return Journal(engine_root,binding)
    def run(phase, *, reconciliation=False):
        authority = inputs(fixture,phase,reconciliation=reconciliation)
        return fixture.transition('reconcile' if reconciliation else phase,engine_phase=phase,**authority)
    def interrupt(phase, expected):
        try:run(phase)
        except Exception:
            _,marker = private(fixture.root/'fault-fired.json')
            require(marker['point']==expected and marker['generation']==fixture.manifest['generation'],
                    'fixture_unexpected_interruption')
        else:require(False,'fixture_expected_interruption_missing')
    if case in ('partial-snapshots','partial-configurations'):
        action = 'snapshot' if case=='partial-snapshots' else 'configurations'
        expected = 'first_snapshot_acknowledgement' if action=='snapshot' else 'first_configuration_acknowledgement'
        interrupt('install',expected)
        acknowledgements = [row for row in journal().rows if row['event']=='mutation_outcome' and row.get('step_id')=='install:'+action]
        require(len(acknowledgements)==1,'fixture_partial_acknowledgement_count')
        before = [row for row in journal().rows if row['event'].startswith('mutation_')]
        run('install',reconciliation=True)
        require(before==[row for row in journal().rows if row['event'].startswith('mutation_')], 'fixture_reconciliation_mutated')
        require(journal().outcome('install:'+action)['event']=='reconciled_partial','fixture_partial_reconciliation_missing')
        run('install')
        matching = [row for row in journal().rows if row['event']=='mutation_outcome' and row.get('resource')==acknowledgements[0]['resource']]
        require(matching==acknowledgements,'fixture_acknowledged_file_replayed')
    elif case=='unacknowledged-images':
        interrupt('install','install:images:unacknowledged')
        before = [row for row in journal().rows if row['event'].startswith('mutation_')]
        try:run('install',reconciliation=True)
        except Exception:
            observations = [row for row in journal().rows if row['event']=='reconciliation_observation' and row.get('step_id')=='install:images']
            require(observations and observations[-1]['status']=='ambiguous','fixture_image_ambiguity_not_observed')
        else:require(False,'fixture_unacknowledged_image_blindly_adopted')
        require(before==[row for row in journal().rows if row['event'].startswith('mutation_')],'fixture_unacknowledged_image_replayed')
        return dict(expected_behavior_verified=True,disposition='conservatively_blocked_unacknowledged_images',
                    transactions_resolved=False,complete_rehearsal=False)
    else:
        run('install')
    inspection = fixture.inspect()
    if case=='interrupted-rollback':
        interrupt('rollback','rollback:restore_activation:unacknowledged')
        run('rollback',reconciliation=True)
        require(journal().outcome('rollback:restore_activation')['event']=='reconciled','fixture_rollback_identity_not_proven')
    run('rollback')
    require(any(row['event']=='phase_complete' and row.get('phase')=='rollback' for row in journal().rows),'fixture_rollback_not_complete')
    return dict(expected_behavior_verified=True,disposition='installation_inspection_rollback_verified',
                transactions_resolved=True,complete_rehearsal=True,inspection=inspection)


def rehearse(root, recipe, case):
    prepare(root,recipe=recipe,case=case)
    with lifecycle_lock(root) as fd:
        fixture = Fixture(root); fixture.lock_fd = fd
        result = dict(fixture_only=True,generation=fixture.manifest['generation'],case=case,
                      complete_rehearsal=False,expected_behavior_verified=False)
        try:result.update(protocol(fixture))
        except Exception as error:
            result['failure'] = dict(type=type(error).__name__,message=str(error))
        finally:
            try:
                fixture.transition('cleanup')
                result['cleanup_verified'] = True
            except Exception as error:
                result['cleanup_verified'] = False
                result['cleanup_failure'] = dict(type=type(error).__name__,message=str(error))
                result['complete_rehearsal'] = False
            result['journal_head'] = fixture.journal.head
            fixture.artifact('case-result',result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--recipe',type=Path,required=True)
    parser.add_argument('--case',choices=CASES,required=True)
    args = parser.parse_args()
    result = rehearse(args.root,args.recipe,args.case)
    print(json.dumps(result,sort_keys=True))
    if not result['expected_behavior_verified'] or not result['cleanup_verified']:raise SystemExit(1)


if __name__=='__main__':main()
