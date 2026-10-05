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
    import json
    rows=json.loads(journal.command(['docker','image','inspect',proof['image']],kind='read',timeout=30).stdout)
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):raise ValueError('One immutable application image required')
    image=rows[0];config=image.get('Config',{});labels=config.get('Labels',{})
    if (image.get('Id')!=proof['image'] or image.get('Architecture')!='amd64'
            or config.get('User')!='0:0' or config.get('Volumes')
            or config.get('Entrypoint')!=['/app/.venv/bin/python','-m','candidate_runtime']
            or labels.get('org.mldsafail.candidate')!='private-unapproved'
            or labels.get('org.mldsafail.protocol')!='0.6.0' or labels.get('org.mldsafail.default')!='0.5.0'):
        raise ValueError('Rootless UID0 private inert application configuration required')
    return proof
