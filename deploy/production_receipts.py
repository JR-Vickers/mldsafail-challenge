"""Validate private inspection evidence, never return inspected configuration values."""
import hashlib
import json
import time
from pathlib import Path

from deploy.production_preparation import IMAGES, SOURCE, FINGERPRINT, read_manifest


def require(condition):
    if not condition:
        raise ValueError('production_binding_or_prerequisite_invalid')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()



def read_receipt(path):
    """Resolve private bundle references without changing hashed receipt bytes."""
    receipt = read_manifest(path)
    root = Path(path).absolute().parent
    def resolve(value):
        from deploy.recovery_journal import safe_path
        return str(safe_path(root / value))
    for key in ('inspection', 'artifact_inventory', 'retained_inventory', 'final_binding'):
        if key in receipt:
            receipt[key] = resolve(receipt[key])
    receipt['retained_environments'] = [resolve(p) for p in receipt['retained_environments']]
    receipt['retained_sha256'] = {resolve(p): v for p, v in receipt['retained_sha256'].items()}
    if 'unstarted_trial_evidence' in receipt:
        for key in ('cleanup_inventory', 'withdrawal_record'):
            receipt['unstarted_trial_evidence'][key] = resolve(receipt['unstarted_trial_evidence'][key])
    return receipt

def validate_receipt(environment, candidate, receipt_path, *, preparation, now=None):
    try:
        receipt = read_receipt(receipt_path)
        host = read_manifest(receipt['inspection'])
        require(receipt['schema'] == 'mldsafail.production-inspection.v1')
        require(receipt['candidate_sha256'] == digest(candidate))
        require(receipt['inspection_sha256'] == digest(receipt['inspection']))
        require(receipt['source'] == SOURCE)
        require(0 <= (time.time() if now is None else now) - host['time'] <= 86400)
        require(host['uid'] == 1000 and host['account'] == 'mldsafail')
        require(host['info']['ID'] == receipt['daemon_id'])
        require(any('rootless' in x for x in host['info']['SecurityOptions']))
        socket = next(p for p in host['paths'] if p['path'] == environment['ROOTLESS_DOCKER_SOCKET'])
        import stat
        require(socket['uid'] == 1000 and stat.S_ISSOCK(socket['mode']) and not socket['symlinks'])
        require(receipt['artifact_inventory_sha256'] == digest(receipt['artifact_inventory']))
        artifacts = read_manifest(receipt['artifact_inventory'])
        for key, index in IMAGES.items():
            image = next(i for i in host['images'] if i['Id'] == 'sha256:' + index)
            require(image['Os'] == 'linux' and image['Architecture'] == 'amd64')
            if key in ('WEB_IMAGE', 'COORDINATOR_IMAGE'):
                require(image['Config']['Labels']['org.mldsafail.source'] == SOURCE)
            identity = receipt['images'][key]
            require(identity['index'] == image['Id'])
            artifact = next(a for a in artifacts if a['image'] == image['Id'])
            require(artifact['whole_hash_matches'] and not artifact['bad_blobs'] and not artifact['descriptor_errors'])
            require(identity['platform_manifest'] in [d['digest'] for d in artifact['descriptors'] if d.get('platform') == {'architecture': 'amd64', 'os': 'linux'}])
            require(identity['configuration'] in ['sha256:' + c['digest'].split('/')[-1] for c in artifact['configs'] if c['architecture'] == 'amd64' and c['os'] == 'linux'])
            require(all(__import__('re').fullmatch('sha256:[a-f0-9]{64}', identity[k])
                       for k in ('index', 'platform_manifest', 'configuration')))
        require(next(i for i in host['images'] if i['Id'] == 'sha256:' + IMAGES['WORKER_IMAGE'])['Config']['Labels']['org.mldsafail.trusted'] == FINGERPRINT)
        require(receipt['retained_inventory_sha256'] == digest(receipt['retained_inventory']))
        inventory = read_manifest(receipt['retained_inventory'])
        require({x['root'] for x in inventory} == {'/tmp/pr-261016-a/state', '/tmp/pr-261017-b/state', '/tmp/pr-261017-c/state', '/tmp/pr-261018-c/state'})
        for item in inventory:
            if item['exists']:
                require(item['compose']['name'] != 'mldsafail-production')
                require(not any(v.get('name', '').startswith('mldsafail-production_') for v in item['compose'].get('volumes', {}).values()))
            else:
                require(item['root'] == '/tmp/pr-261017-c/state')
                disposition = receipt['unstarted_trial_evidence']
                require(disposition['cleanup_sha256'] == digest(disposition['cleanup_inventory']))
                cleanup = read_manifest(disposition['cleanup_inventory'])
                trial = next(t for t in cleanup['trial_roots'] if t['path'] == '/home/mldsafail/.mlf-production-rehearsal-20261017-c')
                require(trial['journals'] == [] and trial['daemon_roots'] == [])
                require(disposition['withdrawal_sha256'] == digest(disposition['withdrawal_record']))
                withdrawal = read_manifest(disposition['withdrawal_record'])
                require('approval was withdrawn before execution' in withdrawal['text'] and 'No C epoch has been generated.' in withdrawal['text'])
        # Recompare actual retained values; a readiness boolean cannot substitute.
        from deploy.production_preflight import read_private_env
        retained = [read_private_env(p) for p in receipt['retained_environments']]
        require(retained)
        require(receipt['retained_sha256'] == {p: digest(p) for p in receipt['retained_environments']})
        retained += [dict(line.split('=', 1) for line in x['environment'].splitlines() if '=' in line) for x in inventory if x['exists']]
        retained += [dict(v.split('=', 1) for v in c['Config']['Env'] if '=' in v) for c in host['containers']]
        if not preparation:
            require(not any(e.get('MLDSAFAIL_MLWE_EPOCH_ID') == environment.get('MLDSAFAIL_MLWE_EPOCH_ID') for e in retained))
        for key in ('POSTGRES_PASSWORD', 'MLDSAFAIL_SECRET_KEY'):
            require(len(environment[key]) >= 32)
            require(not any(environment[key] == value for e in retained
                           for k, value in e.items() if k in ('POSTGRES_PASSWORD', 'MLDSAFAIL_SECRET_KEY')))
        roots = [environment[k] for k in ('PRODUCTION_EVALUATOR_ROOT', 'PRODUCTION_TLS_ROOT', 'PRODUCTION_ACME_WEBROOT')]
        expected_paths = roots + [roots[0] + '/jobs', roots[0] + '/secrets/signing.key']
        paths = [p for p in host['paths'] if p['path'] in expected_paths]
        require(len(paths) == 5 and all(not p['symlinks'] and p['path'] == p['resolved'] for p in paths))
        retained_mounts = [v['source'] for item in inventory if item['exists'] for service in item['compose']['services'].values() for v in service.get('volumes', []) if v.get('type') == 'bind']
        forbidden = retained_mounts + receipt['retained_roots'] + [m['Source'] for c in host['containers'] for m in c['Mounts']]
        def overlap(a, b):
            return Path(a).is_relative_to(b) or Path(b).is_relative_to(a)
        require(not any(overlap(a, b) for a in roots for b in forbidden if b != environment['ROOTLESS_DOCKER_SOCKET']))
        # Reject bind aliases at or below candidate roots, including currently absent children.
        mounts = [line.split(' - ', 1)[0].split()[4].replace('\\040', ' ') for line in host['mountinfo'].splitlines()]
        require(not any(Path(m).is_relative_to(r) for m in mounts for r in roots))
        mount_fields = [line.split(' - ', 1)[0].split() for line in host['mountinfo'].splitlines()]
        require(not any(f[3] != '/' and Path(r).is_relative_to(f[4].replace('\\040', ' ')) for f in mount_fields for r in roots))
        expected = {'mldsafail-production_' + n for n in ('postgres_data', 'caddy_data', 'caddy_config')}
        require(not expected.intersection(v['Name'] for v in host['volumes']))
        require(not any(c['Config'].get('Labels', {}).get('com.docker.compose.project') == 'mldsafail-production' for c in host['containers']))
        require(receipt['compose_sha256'] == digest('compose.production.yaml'))
        if not preparation:
            final = read_manifest(receipt['final_binding'])
            require(final['epoch_id'] == environment['MLDSAFAIL_MLWE_EPOCH_ID'])
            require(final['audited'] is True and final['reference_cases'] == 100)
            require(final['candidate_sha256'] == digest(candidate))
            require(final['seal_sha256'] == digest(Path(final['epoch']) / 'COMPLETE.json'))
            verify_seal(final['epoch'])
            require(final['manifest_sha256'] == digest(Path(final['epoch']) / 'manifest.json'))
            require(final['reference_sha256'] == digest(Path(final['epoch']) / 'reference-costs.json'))
            manifest = read_manifest(Path(final['epoch']) / 'manifest.json')
            require(manifest['id'] == final['epoch_id'] and manifest['environment'] == final['environment'])
        return []
    except (AssertionError, KeyError, ValueError, OSError, TypeError, StopIteration):
        return ['inspection_receipt_invalid_or_stale']


def render(environment, *, preparation=False, runner=None):
    """Render in memory only. Synthetic epoch is never persisted as an env file."""
    import os
    import subprocess
    values = dict(environment)
    if preparation:
        values['MLDSAFAIL_MLWE_EPOCH_ID'] = 'SYNTHETIC_RENDER_ONLY_NOT_AN_EPOCH'
    try:
        result = (runner or subprocess.run)(['docker', 'compose', '--env-file', '/dev/null',
            '-f', 'compose.production.yaml', '-p', 'mldsafail-production', 'config', '--format', 'json'],
            env={**{k: v for k, v in os.environ.items() if k in ('PATH', 'HOME')}, **values},
            capture_output=True, text=True, timeout=30, check=True)
        data = json.loads(result.stdout)
        require(data['name'] == 'mldsafail-production')
        require({v['name'] for v in data['volumes'].values()} == {
            'mldsafail-production_' + n for n in ('postgres_data', 'caddy_data', 'caddy_config')})
        require(data['services']['db']['environment']['POSTGRES_DB'] == 'mldsafail')
        require(data['services']['web']['environment']['MLDSAFAIL_DATABASE_URL'].endswith('@db/mldsafail'))
        return []
    except (OSError, ValueError, KeyError, AssertionError, subprocess.SubprocessError):
        return ['private_compose_render_failed']


def verify_seal(epoch):
    """Check existing frozen seal bytes without modifying or resealing evidence."""
    from deploy.recovery_journal import safe_path
    root = safe_path(epoch)
    marker = read_manifest(root / 'COMPLETE.json')
    actual = {}
    for p in root.rglob('*'):
        safe_path(p)
        if p.is_file() and p.name != 'COMPLETE.json':
            if p.stat().st_nlink != 1 or p.stat().st_uid != __import__('os').getuid():
                raise ValueError('private_epoch_file_required')
            actual[str(p.relative_to(root))] = digest(p)
    if marker.get('benchmark_version') != '0.5.0' or marker.get('files') != actual:
        raise ValueError('epoch_seal_changed')
