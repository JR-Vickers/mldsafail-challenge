#!/bin/sh
set -eu
used=$(df --output=pcent / | tail -1 | tr -dc '0-9')
if [ "$used" -ge 85 ]; then
    echo "Host disk usage exceeds 85 percent." >&2
    exit 1
fi
systemctl is-active --quiet user@1000.service
test -S /run/user/1000/docker.sock
test -f /srv/mlweswap
