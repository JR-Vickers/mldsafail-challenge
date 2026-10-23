"""Durable substep observations; interrupted resources are never replayed.

These records describe what happened, not permission to adopt an unacknowledged
resource. The containing installation intent remains blocked until reconciliation.
"""
from mldsafail.evaluator.native_workload import require


def mutate(journal, resource, observe, action, *, fault=None, step_id=None,
           expected_effect=None, validate=None):
    require(journal is not None, 'mutation_journal_required')
    require(not any(row.get('resource') == resource and row['event'] == 'mutation_intent'
                    for row in journal.rows), 'mutation_already_attempted_reconcile_required')
    if step_id is None:
        pending=next((row for row in reversed(journal.rows) if row['event']=='intent'),None)
        step_id=pending['step'] if pending else None
    binding=dict(step_id=step_id,expected_effect=expected_effect)
    before = observe()
    journal.append('mutation_intent', resource=resource, before=before,**binding)
    if fault: fault(resource, 'intent')
    try:
        result = action()
        if fault: fault(resource, 'applied')
        after = observe()
        if validate is not None:
            require(validate(after),'mutation_effect_not_verified')
    except BaseException as error:
        # A failure is not an acknowledgement of successful creation or cleanup.
        # Preserve observations even if the command mutated and then failed.
        try:
            after = observe()
            observation_error = None
        except BaseException as observation_failure:
            after = None
            observation_error = dict(type=type(observation_failure).__name__, message=str(observation_failure))
        journal.append('mutation_failed', resource=resource, observed=after,
                       error=dict(type=type(error).__name__, message=str(error)),
                       observation_error=observation_error,**binding)
        raise
    journal.append('mutation_outcome', resource=resource, observed=after,**binding)
    if fault: fault(resource, 'outcome')
    return result


def classify(journal, resource, actual):
    """Classify actual observations without mutating, adopting or deleting them."""
    rows = [row for row in journal.rows if row.get('resource') == resource
            and row['event'] in ('mutation_intent', 'mutation_outcome', 'mutation_failed')]
    require(rows and rows[0]['event'] == 'mutation_intent', 'mutation_intent_missing')
    intent = rows[0]
    outcome = next((row for row in reversed(rows) if row['event'] == 'mutation_outcome'), None)
    if outcome:
        return 'completed' if actual == outcome['observed'] else 'replaced'
    # Unchanged observations alone cannot establish absence of side effects.
    # Only an explicitly absent resource can be classified absent.
    if actual == intent['before'] and isinstance(actual, dict) and actual.get('state') == 'absent':
        return 'absent'
    if isinstance(actual, dict) and actual.get('state') == 'absent':
        return 'partially_completed'
    return 'ambiguous'
