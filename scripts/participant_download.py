"""Build a deterministic allowlisted unpublished participant download candidate."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

from mldsafail.benchmark_v050.generator import generate_mlwe


def digest(data):
    return hashlib.sha256(data).hexdigest()


# Source export is deliberately based on Git objects, never the broad worktree.
SDIST_FILES = ('pyproject.toml', 'examples/mlwe/primal-lll/solver.py')
SDIST_DOCS = ('PRIMITIVE_SELECTION_SPEC.md', 'MLWE_LOCAL.md', 'MLWE_PILOT.md',
              'MLWE_REPRODUCTION.md', 'AGENT_WORKFLOW.md')


def prepare_source(source, revision, destination):
    """Stage historical package bytes with separately identified packaging overlays.

    Run the normal PEP 517 build on this directory; this is not a second backend.
    """
    source, destination = Path(source), Path(destination)
    if destination.exists() or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('New destination and full historical revision required')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args])
    listing = git('ls-tree', '-r', revision).decode().splitlines()
    selected = []
    for row in listing:
        attributes, name = row.split('\t', 1)
        if name.startswith('src/mldsafail/') or name in SDIST_FILES or name in {
                'docs/' + doc for doc in SDIST_DOCS}:
            if attributes.split()[0] != '100644':
                raise ValueError('Only regular source files allowed: ' + name)
            selected.append(name)
    if not set(SDIST_FILES).issubset(selected):
        raise ValueError('Required historical source missing')
    destination.mkdir(mode=0o700, parents=True)
    original = {}
    for name in selected:
        data = git('show', revision + ':' + name)
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        original[name] = digest(data)
        if name.startswith('docs/'):
            presentation = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                                  lambda m: m.group(0) if re.match(r'https?://|#', m.group(2)) else m.group(1),
                                  data.decode())
            path.write_text(presentation)
    metadata = destination / 'pyproject.toml'
    metadata.write_text(metadata.read_text() + '\n[tool.hatch.build.targets.sdist]\nexclude = ["/.gitignore"]\ninclude = ["/src/mldsafail", "/examples/mlwe/primal-lll/solver.py", "/docs", "/README.md", "/LICENSE", "/pyproject.toml", "/SOURCE.json"]\n')
    (destination / 'README.md').write_text(
        '# Participant source distribution 0.5.1 / benchmark 0.5.0\n\n'
        'This is an unpublished allowlisted source export. SOURCE.json records the\n'
        'historical package source and separately identified packaging overlays.\n'
        'Build with Python 3.12.10 using `python -m build --wheel`. Package payload\n'
        'equality requires verification; wheel archive equality is not claimed.\n'
        'The companion download bundle contains the selected wheel, installer and\n'
        'participant quickstart. Docker and a compatible reviewed worker are required\n'
        'for evaluation, which is separate from installation checks.\n')
    identity = {'wheel_source_commit': revision, 'historical_files_sha256': original,
                'packaging_source_commit': git('rev-parse', 'HEAD').decode().strip(),
                'overlays': ['pyproject.toml: explicit sdist allowlist',
                             'README.md: source quickstart', 'docs: local links rendered as text', 'SOURCE.json: provenance'],
                'wheel_reproduction_claim': 'package payload comparison required; archive equality not claimed'}
    (destination / 'SOURCE.json').write_text(json.dumps(identity, sort_keys=True, indent=2) + '\n')
    return identity


def build(source, wheel, destination, expected_wheel_sha256, wheel_manifest):
    source, wheel, destination = map(Path, (source, wheel, destination))
    if destination.exists():
        raise ValueError('Download candidate destination must be new')
    if subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']).strip():
        raise ValueError('Participant download requires clean frozen source')
    if wheel.is_symlink() or wheel.name != 'mldsafail_challenge-0.5.1-py3-none-any.whl':
        raise ValueError('Verified participant 0.5.1 regular wheel required')
    if digest(wheel.read_bytes()) != expected_wheel_sha256:
        raise ValueError('Participant wheel checksum mismatch')
    if (not re.fullmatch(r'[a-f0-9]{40}', wheel_manifest.get('source_commit', ''))
            or wheel_manifest.get('wheel_sha256') != expected_wheel_sha256):
        raise ValueError('Separately verified wheel-source manifest required')
    identity = {'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD']).decode().strip(),
                'source_tree': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD^{tree}']).decode().strip(),
                'wheel_source_commit': wheel_manifest['source_commit'],
                'package_version': '0.5.1', 'benchmark_version': '0.5.0', 'wheel_sha256': digest(wheel.read_bytes())}
    identity['archive_documentation_source_commit'] = identity['source_commit']
    identity['archive_documentation_source_tree'] = identity['source_tree']
    files = {wheel.name: wheel.read_bytes(), 'README.md': (source / 'docs/PARTICIPANT_DOWNLOAD_README.md').read_bytes()}
    for relative in ('examples/mlwe/primal-lll/solver.py', 'scripts/install.sh'):
        path = source / relative
        if path.is_symlink():
            raise ValueError('Source symlinks forbidden')
        files[relative] = path.read_bytes()
    original_spec = (source / 'docs/PRIMITIVE_SELECTION_SPEC.md').read_bytes()
    # Keep the complete frozen prose while removing repository-context local
    # links to omitted historical/private operator documents. External citations
    # and all participant archive links remain intact.
    spec = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda match: match.group(0)
                  if re.match(r'https?://', match.group(2)) else match.group(1), original_spec.decode())
    files['docs/PRIMITIVE_SELECTION_SPEC.md'] = spec.encode()
    fixtures = [generate_mlwe(profile, 0, eta).public.to_dict()
                for profile in ('small', 'medium', 'large') for eta in (1, 2)]
    files['public-fixtures.json'] = (json.dumps(fixtures, sort_keys=True, indent=2) + '\n').encode()
    identity.update(starter_sha256=digest(files['examples/mlwe/primal-lll/solver.py']),
                    original_contract_sha256=digest(original_spec),
                    included_contract_sha256=digest(files['docs/PRIMITIVE_SELECTION_SPEC.md']))
    files['SOURCE.json'] = (json.dumps(identity, sort_keys=True, indent=2) + '\n').encode()
    for relative, data in files.items():
        if relative.endswith('.md'):
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', data.decode()):
                if re.match(r'https?://|#', target):
                    continue
                resolved = str(Path(relative).parent / target)
                if resolved not in files:
                    raise ValueError('Broken participant documentation link')
    checksums = {name: digest(data) for name, data in sorted(files.items())}
    files['SHA256SUMS'] = ''.join(f'{value}  {name}\n' for name, value in checksums.items()).encode()
    destination.mkdir(mode=0o700, parents=True)
    archive = destination / 'participant-download-candidate.tar.gz'
    with archive.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w') as output:
        for name, data in sorted(files.items()):
            entry = tarfile.TarInfo('mldsafail-participant-0.5.1/' + name)
            entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
            output.addfile(entry, io.BytesIO(data))
    manifest = {**identity, 'archive_sha256': digest(archive.read_bytes()), 'public_files_sha256': checksums,
                'publication_approved': False, 'independent_archive_review_pending': True,
                'native_reproduction_gate_pending': True}
    (destination / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    archive.chmod(0o400)
    (destination / 'manifest.json').chmod(0o400)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--wheel-sha256', required=True)
    parser.add_argument('--wheel-manifest', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.wheel, args.destination, args.wheel_sha256, json.loads(args.wheel_manifest.read_text()))
    print(json.dumps({'source_commit': result['source_commit'], 'archive_sha256': result['archive_sha256'], 'publication_approved': False}))
