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
    if journal.recovery_protocol in (3, 4):
        from deploy.workload_release import canonical, digest
        parent = next((row for row in reversed(journal.rows)
                       if row.get('step') == step_id and row['event'] == 'intent'), None)
        require(parent is not None, 'mutation_parent_intent_required')
        binding.update(parent_intent_sha256=digest(canonical(parent)),
                       operation=(expected_effect or {}).get('effect', resource))
    before = observe()
    if journal.recovery_protocol == 4:
        # Bind identity and transition independently of the operation's label.
        binding.update(resource_identity=before,
                       expected_transition=expected_effect or dict(effect=resource,
                           postcondition='operation_specific_observation_required'))
    journal.append('mutation_intent', resource=resource, before=before,**binding)
    if journal.recovery_protocol in (3, 4):
        from deploy.workload_release import canonical, digest
        binding['mutation_intent_sha256'] = digest(canonical(journal.rows[-1]))
    from deploy.workload_fixture_faults import dispatch_mutation
    dispatch_mutation(journal, resource, 'intent')
    if fault: fault(resource, 'intent')
    try:
        result = action()
        dispatch_mutation(journal, resource, 'applied')
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
    dispatch_mutation(journal, resource, 'outcome')
    if fault: fault(resource, 'outcome')
    return result


def classify(journal, resource, actual):
    """Classify actual observations without mutating, adopting or deleting them."""
    rows = [row for row in journal.rows if row.get('resource') == resource
            and row['event'] in ('mutation_intent', 'mutation_outcome', 'mutation_failed')]
    require(rows and rows[0]['event'] == 'mutation_intent', 'mutation_intent_missing')
    intent = rows[0]
    outcome = next((row for row in reversed(rows) if row['event'] == 'mutation_outcome'), None)
    if journal.recovery_protocol in (3, 4):
        from deploy.workload_release import canonical, digest
        parent = next((row for row in journal.rows if row['event'] == 'intent' and
                       digest(canonical(row)) == intent.get('parent_intent_sha256')), None)
        require(parent is not None and parent.get('step') == intent.get('step_id'),
                'mutation_parent_binding_invalid')
        require(len([row for row in rows if row['event'] == 'mutation_intent']) == 1,
                'mutation_duplicate_intent')
        for row in rows[1:]:
            require(row.get('mutation_intent_sha256') == digest(canonical(intent)) and
                    all(row.get(key) == intent.get(key) for key in
                        (('step_id', 'expected_effect', 'parent_intent_sha256', 'operation') +
                         (('resource_identity', 'expected_transition') if journal.recovery_protocol == 4 else ()))),
                    'mutation_receipt_binding_invalid')
        require(len([row for row in rows if row['event'] == 'mutation_outcome']) <= 1,
                'mutation_duplicate_outcome')
    if journal.recovery_protocol == 4:
        require(intent.get('resource_identity') == intent['before'] and
                intent.get('expected_transition') == (intent.get('expected_effect') or dict(
                    effect=resource, postcondition='operation_specific_observation_required')),
                'mutation_transition_binding_invalid')
    if outcome:
        return 'completed' if actual == outcome['observed'] else 'replaced'
    # Unchanged observations alone cannot establish absence of side effects.
    # Only an explicitly absent resource can be classified absent.
    if actual == intent['before'] and isinstance(actual, dict) and actual.get('state') == 'absent':
        return 'absent'
    if isinstance(actual, dict) and actual.get('state') == 'absent':
        return 'partially_completed'
    return 'ambiguous'
