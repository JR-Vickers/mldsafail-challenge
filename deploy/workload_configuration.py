"""Private configuration artifacts with narrowly permitted birth substitutions.

Only the native adapter's heavy_birth can reference the proposed heavy resource.
All other bytes derive from frozen private templates; no arbitrary configuration
or secret is inferred from installed observations.
"""
from copy import deepcopy
import json
from deploy.workload_release import canonical,digest
from mldsafail.evaluator.native_workload import require


def templates(source):
    rows=source['recipe']['configuration_templates']
    require(set(rows)==set(source['manifest']['configurations']),'configuration_templates_missing')
    result={}
    for role,hex_data in rows.items():
        raw=bytes.fromhex(hex_data)
        require(digest(raw)==source['manifest']['configurations'][role]['sha256'],'configuration_template_changed')
        data=json.loads(raw)
        require(canonical(data)==raw and type(data) is dict,'configuration_template_not_canonical')
        result[role]=data
    return result


def materialize(source,resources):
    rows=templates(source)
    for role,data in rows.items():
        # A marker anywhere except the exact reviewed heavy_birth position fails.
        allowed=role=='native' and data.get('heavy_birth')=={'$birth':'delegation'}
        if allowed:
            require(source['resources']['delegation']['state']=='proposed','configuration_unexpected_birth_transition')
            birth=resources['delegation']
            require(birth['state']=='observed' and all(type(birth[k]) is int for k in ('device','inode')) and birth['inode']>0,
                    'configuration_materialized_birth_missing')
            data['heavy_birth']={k:birth[k] for k in ('path','device','inode')}
        require('$birth' not in canonical(data).decode(),'configuration_birth_marker_not_allowed')
    return {role:canonical(data) for role,data in rows.items()}


def hashes(source,resources):
    return {role:digest(data) for role,data in materialize(source,resources).items()}
