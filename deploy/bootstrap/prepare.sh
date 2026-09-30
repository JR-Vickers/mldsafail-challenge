#!/bin/sh
# Run from this template directory as root on a fresh Ubuntu 24.04 amd64 VPS.
# SSH hardening is intentionally a separate step after both new logins work.
set -eu
[ "$(id -u)" = 0 ]
[ "$(. /etc/os-release; echo "$VERSION_ID")" = 24.04 ]
[ "$(dpkg --print-architecture)" = amd64 ]
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get install -y ca-certificates curl gnupg git uidmap dbus-user-session slirp4netns ufw unattended-upgrades sysstat
for account in mldsafail mldsafail-admin; do
    if ! id "$account" >/dev/null 2>&1; then
        useradd --create-home --shell /bin/bash "$account"
    fi
    install -d -m 0700 -o "$account" -g "$account" "/home/$account/.ssh"
    install -m 0600 -o "$account" -g "$account" /root/.ssh/authorized_keys "/home/$account/.ssh/authorized_keys"
done
visudo -cf mldsafail-admin.sudoers
install -m 0440 mldsafail-admin.sudoers /etc/sudoers.d/mldsafail-admin
install -d -m 0700 -o mldsafail -g mldsafail /srv/mldsafail /srv/mldsafail-evaluator
if [ ! -e /srv/mlweswap ]; then
    fallocate -l 2G /srv/mlweswap
    chmod 0600 /srv/mlweswap
    mkswap /srv/mlweswap
fi
install -m 0644 srv-mlweswap.swap /etc/systemd/system/srv-mlweswap.swap
systemctl daemon-reload
systemctl enable --now srv-mlweswap.swap
install -m 0644 52mldsafail-automatic /etc/apt/apt.conf.d/52mldsafail-automatic
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
install -m 0644 docker.sources /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
# Only the service user's rootless daemon will manage the application.
systemctl disable --now docker.service docker.socket
loginctl enable-linger mldsafail
systemctl enable --now sysstat
echo 'Prepared. Verify SSH as mldsafail and mldsafail-admin before hardening.'
