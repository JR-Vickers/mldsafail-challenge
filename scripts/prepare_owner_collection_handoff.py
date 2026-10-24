"""Prepare a private, local-only successor collector handoff; installs nothing."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.prepare_owner_collection_access import ROOT as ORIGINAL_ROOT, RULE as ORIGINAL_RULE
from scripts.prepare_owner_collection_successor import build


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2)+'\n').encode()


def prepare(source, output, plan_path, dossier_path, *, reviewed_plan_sha256):
    """Freeze the previously reviewed allowlist, preserving unresolved host facts.

    Review of this resulting archive is a separate gate. A matching plan digest
    does not claim source/artifact review, host completeness or execution authority.
    """
    plan_raw = Path(plan_path).read_bytes()
    dossier_raw = Path(dossier_path).read_bytes()
    if sha(plan_raw) != reviewed_plan_sha256:
        raise ValueError('reviewed_plan_identity_changed')
    plan, dossier = json.loads(plan_raw), json.loads(dossier_raw)
    if (dossier.get('schema') != 'mldsafail.private-host-readiness-dossier.v1' or
            dossier.get('execution_authority') is not False or
            type(dossier.get('prerequisites')) is not dict):
        raise ValueError('private_readiness_dossier_required')
    output = Path(output)
    # An exclusive private directory prevents overwriting older packets or readers.
    output.mkdir(mode=0o700)
    os.chmod(output, 0o700)
    artifact = build(source, output/'collector.pyz', plan)
    missing = {key: value for key, value in sorted(dossier['prerequisites'].items())
               if value.get('status') != 'evidenced'}
    packet = dict(schema='mldsafail.owner-collection-handoff.v1',
        artifact=artifact, plan_sha256=sha(plan_raw), dossier_sha256=sha(dossier_raw),
        missing_facts=missing, blockers=['exact_source_and_artifact_independent_review_required',
            'administrator_installation_not_authorized', 'fresh_privileged_observations_required',
            'recursive_reference_and_retained_resource_review_required'],
        original_installation=dict(root=ORIGINAL_ROOT, sudoers_path=ORIGINAL_RULE,
                                   disposition='preserve_unchanged'),
        private_output='/root/mldsafail-owner-observation-20261024-v2/collection.json',
        transferred=False, installed=False, execution_authority=False)
    instructions = administrator_instructions(artifact, packet['private_output'])
    (output/'ADMINISTRATOR.md').write_text(instructions)
    packet['instructions_sha256'] = sha(instructions.encode())
    (output/'handoff.json').write_bytes(canonical(packet))
    for item in output.iterdir():
        item.chmod(0o600)
    return packet


def administrator_instructions(artifact, private_output):
    root, rule = artifact['root'], artifact['sudoers_path']
    rule_hash = sha(artifact['sudoers'].encode())
    return f'''# Preparation only: separate review and owner authority required

Nothing in this packet authorizes transfer, installation or collection. Preserve
the original collector and sudo fragment. Existing destinations are blockers.
The administrator stages the independently reviewed archive at the exact private
path /root/mldsafail-owner-facts-20261024-v2-reviewed.pyz by a separately authorized
transfer. Before execution, compare SHA-256 with {artifact['sha256']} and inspect
every installation ancestor for root ownership and absence of group/other writes.

After exact review and owner authorization, in the root console:

```sh
set -eu
umask 077
printf '%s  %s\\n' '{artifact['sha256']}' '/root/mldsafail-owner-facts-20261024-v2-reviewed.pyz' | sha256sum -c -
mkdir -m 700 {root}
install -o root -g root -m 600 /root/mldsafail-owner-facts-20261024-v2-reviewed.pyz {root}/collector.pyz
printf '%s  %s\\n' '{artifact['sha256']}' '{root}/collector.pyz' | sha256sum -c -
/usr/bin/python3 -I -B {root}/collector.pyz --install-rule
```

Stop on any failed command; never reuse an existing directory or sudo fragment.
Run only `sudo -n {artifact['command']}` under the exact sudo rule.
For authorized collection, the runtime account uses an exclusively created 0700
private directory on existing storage and noclobber output. Its owner-private
local output location must be fixed in the separately authorized collection run.
Root-console capture may use `{private_output}` after exclusively creating its
parent with mode 0700; preserve failures and hash the output. Never commit raw data.

Revocation is separate administrator action. Verify that `{rule}` is a root-owned
regular non-symlink file, its ancestors remain trusted, and SHA-256 is exactly
`{rule_hash}`. If identity or bytes differ, preserve it and stop. With replacement
excluded by the administrator's maintenance boundary, remove only that fragment
and run `/usr/sbin/visudo -c`. Preserve both archives and the original fragment
until their separate ownership/retention review. Do not remove ambiguous resources.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--reviewed-plan-sha256', required=True)
    parser.add_argument('--dossier', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(Path(__file__).resolve().parents[1], args.output, args.plan,
                     args.dossier, reviewed_plan_sha256=args.reviewed_plan_sha256)
    print(json.dumps(dict(packet=str(args.output/'handoff.json'),
        artifact_sha256=result['artifact']['sha256'], installed=False,
        execution_authority=False), sort_keys=True))


if __name__ == '__main__':
    main()
