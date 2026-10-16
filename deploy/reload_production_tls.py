"""Certbot deploy hook: reload only the explicitly configured production proxy."""
import argparse
import subprocess
from pathlib import Path

from deploy.production_preflight import read_private_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--checkout', type=Path, required=True)
    args = parser.parse_args()
    environment = read_private_env(args.env_file)
    host = environment['MLDSAFAIL_DOMAIN']
    certificate = Path(environment['PRODUCTION_TLS_ROOT']) / 'live' / host / 'fullchain.pem'
    subprocess.run(['openssl', 'x509', '-in', str(certificate), '-noout', '-checkend', '3600'],
                   check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'compose', '--project-name', 'mldsafail-production',
                    '--env-file', str(args.env_file), '-f', str(args.checkout / 'compose.production.yaml'),
                    'exec', '-T', 'proxy', 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile'],
                   check=True, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
