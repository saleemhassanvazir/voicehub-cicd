#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 EC2 server for VoiceHub.
# Run on the server:  curl -fsSL <raw GitHub URL of this file> | sudo bash
set -euo pipefail

APP=/opt/voicehub
echo "==> Installing packages"
apt-get update -y
apt-get install -y python3-venv python3-pip postgresql nginx unzip curl

echo "==> App user and folders"
id voicehub >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin voicehub
mkdir -p "$APP/releases" "$APP/uploads"

echo "==> Settings file (passwords generated here, never stored in GitHub)"
if [ ! -f "$APP/voicehub.env" ]; then
  DB_PASS=$(openssl rand -hex 16)
  cat > "$APP/voicehub.env" <<EOF
DB_HOST=localhost
DB_PORT=5432
DB_USER=voicehub
DB_PASSWORD=$DB_PASS
DB_NAME=voicehub
SECRET_KEY=$(openssl rand -hex 32)
UPLOAD_DIR=$APP/uploads
EOF
  chmod 600 "$APP/voicehub.env"
fi
# shellcheck disable=SC1091
source "$APP/voicehub.env"

echo "==> PostgreSQL database"
systemctl enable --now postgresql
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='voicehub'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE voicehub LOGIN CREATEDB PASSWORD '$DB_PASSWORD'"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='voicehub'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE voicehub OWNER voicehub"

echo "==> Python environment"
[ -d "$APP/venv" ] || python3 -m venv "$APP/venv"
chown -R voicehub:voicehub "$APP"

echo "==> systemd service (gunicorn)"
cat > /etc/systemd/system/voicehub.service <<EOF
[Unit]
Description=VoiceHub web app
After=network.target postgresql.service

[Service]
User=voicehub
WorkingDirectory=$APP/current
EnvironmentFile=$APP/voicehub.env
ExecStart=$APP/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable voicehub

echo "==> nginx (port 80 -> app)"
cat > /etc/nginx/sites-available/voicehub <<'EOF'
server {
    listen 80 default_server;
    client_max_body_size 20M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
ln -sf /etc/nginx/sites-available/voicehub /etc/nginx/sites-enabled/voicehub
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "==> Server ready. Push to GitHub to deploy the first build."
