# IP-based production preparation — 2026-10-13

The selected origin is `https://178.128.17.58`; the GitHub OAuth callback is
`https://178.128.17.58/auth/callback`. No listener, account, certificate request,
OAuth registration or timer was activated during integration. Fresh production
credentials, separate volumes/evaluator roots, audited epoch and exact images
remain required. Use the explicit project name `mldsafail-production` throughout.

The [production preflight](../deploy/production_preflight.py) accepts a globally
routable IPv4 or DNS host and checks HTTPS origin consistency. Secure cookies
remain enabled. Never accept an insecure TLS client override or self-signed
production certificate. Certificate validity and OAuth acceptance still need
native receipts; parsing tests cannot establish them.

Use Certbot **5.4 or later** for webroot IP support. IP certificates use the
six-day `shortlived` profile, and require frequent automated renewal plus a
deploy hook to reload Caddy. See [Let's Encrypt's Certbot instructions](https://letsencrypt.org/2026/03/11/shorter-certs-certbot).

After separate owner activation approval, serve only the HTTP ACME challenge
using `deploy/Caddyfile.acme-bootstrap` initially. Mount the same host webroot
into Caddy at `/var/www/acme`. Keep all other paths at 404 while provisioning.
Request a staging certificate first in a **separate staging certificate root**:

```sh
certbot certonly --staging --preferred-profile shortlived --webroot \
  --webroot-path /srv/mldsafail-production-acme --ip-address 178.128.17.58 \
  --config-dir /srv/mldsafail-production-tls-staging \
  --work-dir /srv/mldsafail-production/certbot-staging-work \
  --logs-dir /srv/mldsafail-production/certbot-staging-logs
```

For trusted issuance, omit `--staging` and use the production certificate root
`/srv/mldsafail-production-tls`, with separate work/log paths. Certbot's account
email/terms choices belong to the owner. Never mount staging certificates into
production. The production Compose mount includes **both live and archive**
directories read-only so Certbot's relative symlinks resolve. Keep keys private
to the deployment account; verify Caddy can read them in its rootless namespace.

Switch to `deploy/Caddyfile.production` after validating the certificate's IP SAN,
chain and lifetime. HTTP serves challenges and redirects other requests to HTTPS.
The inactive `mldsafail-certbot` service/timer checks renewal every six hours and
reloads only the named production proxy via `deploy.reload_production_tls`.
Before enabling, align paths/interpreter/account with retained release identities;
test `certbot renew --dry-run` in the isolated rehearsal and an actual trusted
renewal/reload without downtime. Verify the served chain and IP with a trusted
client and check headers, secure cookies and `/auth/callback`. No `--insecure`.

Private rehearsal uses a unique Compose project, loopback-bound ports and new
synthetic state. Public CA validation cannot be completed over loopback alone;
public HTTP validation and real OAuth remain dependent on owner activation.
