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


def measured_resources(source):
    """Fresh kernel births, including systemd-created slice ancestors."""
    from deploy.workload_installation import identity
    result=deepcopy(source['resources'])
    for name,row in result.items():
        actual=identity(row['path'],content=False)
        for key in ('state','device','inode'):
            if key in actual:row[key]=actual[key]
        if row.get('state')=='observed':row.pop('creation',None);row.pop('preserve',None)
        if name=='delegation':
            for parent in row['ancestors']:
                actual=identity(parent['path'],content=False)
                for key in ('state','device','inode'):
                    if key in actual:parent[key]=actual[key]
                if parent.get('state')=='observed':parent.pop('creation',None);parent.pop('preserve',None)
    return result


def materialize(source,resources):
    rows=templates(source)
    for role,data in rows.items():
        allowed=role=='native' and data.get('heavy_birth')=={'$birth':'delegation'}
        if allowed:
            require(source['resources']['delegation']['state']=='proposed','configuration_unexpected_birth_transition')
            birth=resources['delegation']
            require(birth['state']=='observed' and all(type(birth[k]) is int for k in ('device','inode')) and birth['inode']>0,
                    'configuration_materialized_birth_missing')
            data['heavy_birth']={k:birth[k] for k in ('path','device','inode')}
        if role=='native' and data.get('ancestors')=={'$ancestor_chain':'delegation'}:
            chain=[resources['delegation'],*resources['delegation']['ancestors']]
            expected=[source['resources']['delegation']['path'],*[p['path'] for p in source['resources']['delegation']['ancestors']]]
            require([row['path'] for row in chain]==expected,'configuration_ancestor_paths_changed')
            require(all(row['state']=='observed' and type(row.get('inode')) is int and row['inode']>0 for row in chain),
                    'configuration_observed_ancestor_birth_missing')
            data['ancestors']=[{key:row[key] for key in ('path','device','inode')} for row in chain]
        def reserved(value):
            if isinstance(value,dict):return any(key in ('$birth','$ancestor_chain') or reserved(item) for key,item in value.items())
            if isinstance(value,list):return any(reserved(item) for item in value)
            return False
        require(not reserved(data),'configuration_birth_marker_not_allowed')
    return {role:canonical(data) for role,data in rows.items()}


def hashes(source,resources):
    return {role:digest(data) for role,data in materialize(source,resources).items()}
