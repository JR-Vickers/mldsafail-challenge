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


def validate_runtime_templates(source):
    """Bind executable configuration edges and retained private signing material."""
    from pathlib import Path
    from mldsafail.evaluator.native_workload import NativeRuntime
    rows=templates(source);native=rows['native'];supervisor=rows['supervisor'];controller=rows['controller']
    paths={role:row['path'] for role,row in source['manifest']['configurations'].items()}
    installation=source['installation'];recipe=source['recipe']
    NativeRuntime(native)  # Structural validation only; no command or mutation.
    require(set(supervisor)=={'root','socket','helper','roles'} and
            supervisor['root']==installation['gate_root'] and supervisor['socket']==source['resources']['socket']['path'] and
            supervisor['helper']==[installation['python'],'-m','mldsafail.evaluator.native_workload','--configuration',paths['native']] and
            supervisor['roles'] and all(name in native['roles'] and value=={'role':name} for name,value in supervisor['roles'].items()),
            'configuration_supervisor_edges_changed')
    require(set(controller)=={'native_configuration','identity','epoch_path','worker_image','signing_key'} and
            controller['native_configuration']==paths['native'] and controller['worker_image']==source['manifest']['worker_environment']['image_id'] and
            native['controller_configuration']==paths['controller'] and
            native['controller_configuration_sha256']==source['manifest']['configurations']['controller']['sha256'] and
            native['root']==installation['gate_root'] and native['heavy']==installation['heavy_path'] and
            native['output']==source['resources']['output']['path'] and native['python']==installation['python'] and
            native['python_sha256']==recipe['interpreter']['sha256'] and
            native['worker']['image']==source['manifest']['worker_environment']['image_id'] and
            native['boot_id']==source['host']['boot_id'] and native['daemon_id']==source['host']['daemon_id'] and
            native['docker']==['/usr/bin/docker','--host','unix://'+source['host']['runtime_identity']['socket_birth']['path']] and
            native['retained_services']=={role:row['id'] for role,row in source['retained_services'].items()} and
            controller['identity'].get('benchmark_version')=='0.5.0' and
            controller['identity'].get('evaluator_fingerprint')==source['manifest']['evaluator_fingerprint'],
            'configuration_native_controller_edges_changed')
    from deploy.workload_dependencies import entrypoint_code
    wrapper=entrypoint_code(installation['release'],installation['python'],'mldsafail.evaluator.workload_router','main')
    require(source['manifest']['files'].get('bin/docker')==dict(sha256=digest(wrapper),bytes=len(wrapper),mode=0o700),
            'configuration_router_artifact_missing')
    require(native['router']==str(Path(installation['release'])/'bin/docker') and
            native['environment'].get('PYTHONPATH')==installation['release']+'/src:'+installation['release'],
            'configuration_frozen_execution_paths_changed')
    require(set(recipe.get('private_artifacts',{}))==set(source['manifest'].get('private_artifacts',{}))=={'signing_key'},
            'configuration_private_artifact_missing')
    key=recipe['private_artifacts']['signing_key'];public=source['manifest']['private_artifacts']['signing_key']
    require(key.get('state')=='observed' and key.get('path')==controller['signing_key'] and
            key.get('uid')==source['host']['uid'] and key.get('mode')==0o600 and
            all(key.get(name)==public[name] for name in ('sha256','bytes')) and
            all(type(key.get(name)) is int and key[name]>=0 for name in ('device','inode')) and key['inode']>0,
            'configuration_private_artifact_not_bound')


def verify_private_artifacts(source):
    from pathlib import Path
    from deploy.workload_installation import identity
    from deploy.workload_release import regular
    for role,expected in source['recipe'].get('private_artifacts',{}).items():
        path=Path(expected['path']);data,mode=regular(path.parent,path.name);actual=identity(path)
        require(all(actual.get(key)==expected[key] for key in ('device','inode','uid','mode','sha256')) and
                len(data)==expected['bytes'] and mode==0o600,'configuration_private_artifact_changed')
    require(source['origin']=='synthetic' or set(source['recipe'].get('private_artifacts',{}))=={'signing_key'},
            'configuration_private_artifact_missing')
