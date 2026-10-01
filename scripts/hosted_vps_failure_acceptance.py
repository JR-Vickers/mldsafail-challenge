"""Transport a bounded acceptance run to private staging; never fetch evidence."""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
import re
import shutil
import stat
import subprocess

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/hosted-failures"


def export_fixtures(destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("reference", "invalid", "crash", "hang"):
        shutil.copytree(FIXTURES / name, destination / name)
    subprocess.run(["git", "init", "-b", "main", str(destination)], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(destination), "add", "."], check=True)
    subprocess.run(["git", "-C", str(destination), "commit", "-m",
                    "Add reviewed synthetic staging failure fixtures"], check=True)


def private_token(path: Path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
        raise ValueError("Token files must be private regular files (mode 0600).")
    value = path.read_text().strip()
    if not value or any(c.isspace() for c in value):
        raise ValueError("Token file must contain one bearer token.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-fixtures", type=Path)
    parser.add_argument("--fixture-url")
    parser.add_argument("--fixture-sha")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--revoked-token-file", type=Path)
    parser.add_argument("--ssh-identity", type=Path)
    parser.add_argument("--host", default="mldsafail@178.128.17.58")
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--rollback-manifest", type=Path)
    parser.add_argument("--deployment", default="/srv/mldsafail")
    parser.add_argument("--env-file", default="/srv/mldsafail/secrets/staging.env")
    parser.add_argument("--run-id", required=False)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if args.export_fixtures:
        export_fixtures(args.export_fixtures)
        return
    required = (args.fixture_url, args.fixture_sha, args.token_file, args.ssh_identity,
                args.release_manifest, args.rollback_manifest, args.run_id)
    if not all(required):
        parser.error("Native runs require fixture URL/SHA, token, identity, both manifests and run-id.")
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.fixture_url):
        parser.error("Fixture URL must be a public GitHub HTTPS repository URL.")
    if not re.fullmatch(r"[0-9a-f]{40}", args.fixture_sha):
        parser.error("Fixture SHA must be a full immutable commit SHA.")
    if not re.fullmatch(r"[a-z0-9-]{1,48}", args.run_id):
        parser.error("run-id must use lowercase letters, digits and hyphens.")
    config = vars(args).copy()
    for key in ("export_fixtures", "token_file", "revoked_token_file", "ssh_identity"):
        config.pop(key)
    config["token"] = private_token(args.token_file)
    config["revoked_token"] = private_token(args.revoked_token_file) if args.revoked_token_file else None
    for key in ("release_manifest", "rollback_manifest"):
        config[key] = json.loads(getattr(args, key).read_text())
    if not config["rollback_manifest"]["source_commit"].startswith("b4d212d"):
        parser.error("Rollback must retain the known-good b4d212d release.")
    config["fixture_files"] = {str(p.relative_to(FIXTURES)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in FIXTURES.rglob("*.py")}
    config["driver"] = Path(__file__).with_name("hosted_vps_failure_driver.py").read_text()
    config["probe"] = Path(__file__).with_name("hosted_vps_failure_probe.py").read_text()
    bootstrap = '''import json,os,pathlib,subprocess,sys
c=json.load(sys.stdin)
p=pathlib.Path.home()/('.mldsafail-acceptance-'+c['run_id'])
p.mkdir(mode=0o700,exist_ok=True)
if p.is_symlink() or p.stat().st_mode & 0o077: raise SystemExit('Unsafe private run directory')
for name in ('driver','probe'):
 f=p/(name+'.py'); f.write_text(c.pop(name)); f.chmod(0o600)
c['directory']=str(p)
r=subprocess.run(['python3',str(p/'driver.py')],input=json.dumps(c),text=True)
sys.exit(r.returncode)
'''
    import shlex
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", str(args.ssh_identity),
                             args.host, "python3 -c " + shlex.quote(bootstrap)],
                            input=json.dumps(config), text=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
