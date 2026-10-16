"""Source-bound private application image admission, distinct from worker gates."""
import re
from deploy import owned_daemon


def require_image(journal,path,*,expected_source,loaded_images):
    proof=owned_daemon.read_private_json(path,cap=4*1024*1024)
    if (not isinstance(proof,dict) or proof.get('schema')!='mldsafail.private-candidate-image-build.v1'
            or proof.get('passed') is not True or proof.get('native_executed') is not True
            or proof.get('candidate_only') is not True or proof.get('production_adopted') is not False
            or proof.get('default_changed') is not False or proof.get('source_commit')!=expected_source
            or not isinstance(proof.get('image'),str) or not re.fullmatch('sha256:[0-9a-f]{64}',proof['image'])
            or proof['image'] not in loaded_images or not re.fullmatch('[0-9a-f]{64}',proof.get('context_sha256',''))):
        raise ValueError('Exact private application image provenance required')
    if (not re.fullmatch('[0-9a-f]{40}',proof.get('wheel_source_commit',''))
            or not re.fullmatch('[0-9a-f]{64}',proof.get('wheel_sha256',''))
            or proof.get('outer_cleanup_required') is not True or not isinstance(proof.get('owned_driver_journal'),str)
            or not re.fullmatch('[0-9a-f]{32}',proof.get('owned_driver_id',''))
            or not re.fullmatch('[0-9a-f]{40}',proof.get('operator_source_commit',''))
            or not re.fullmatch('[0-9a-f]{64}',proof.get('acceptance_source_sha256',''))
            or not isinstance(proof.get('artifact_path'),str)):
        raise ValueError('Exact completed native artifact owner receipt required')
    driver=owned_daemon.read_private_json(proof['owned_driver_journal'],cap=16*1024*1024)
    acceptance=driver.get('operator_acceptance',{})
    if (driver.get('schema')!='mldsafail.cpu-native-driver-state.v1' or driver.get('id')!=proof['owned_driver_id']
            or driver.get('native_acceptance_passed') is not True or driver.get('cleanup',{}).get('cleanup_complete') is not True
            or driver.get('config',{}).get('source_commit')!=proof['operator_source_commit']
            or driver.get('config',{}).get('acceptance_source_sha256')!=proof['acceptance_source_sha256']
            or acceptance.get('passed') is not True or acceptance.get('source_sha256')!=proof['acceptance_source_sha256']
            or proof['artifact_path'] not in acceptance.get('evidence_refs',[])):
        raise ValueError('Native artifact acceptance and whole-owner cleanup have not completed')
    import json
    rows=json.loads(journal.command(['docker','image','inspect',proof['image']],kind='read',timeout=30).stdout)
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):raise ValueError('One immutable application image required')
    image=rows[0];config=image.get('Config',{});labels=config.get('Labels',{})
    if (image.get('Id')!=proof['image'] or image.get('Architecture')!='amd64'
            or config.get('User')!='0:0' or config.get('Volumes')
            or config.get('Entrypoint')!=['/app/.venv/bin/python','-m','candidate_runtime']
            or labels.get('org.mldsafail.candidate')!='private-unapproved'
            or labels.get('org.mldsafail.protocol')!='0.6.0' or labels.get('org.mldsafail.default')!='0.5.0'
            or labels.get('org.mldsafail.candidate.source_commit')!=proof['source_commit']
            or labels.get('org.mldsafail.candidate.wheel_source_commit')!=proof.get('wheel_source_commit')
            or labels.get('org.mldsafail.candidate.wheel_sha256')!=proof.get('wheel_sha256')):
        raise ValueError('Rootless UID0 private inert application configuration required')
    return proof
