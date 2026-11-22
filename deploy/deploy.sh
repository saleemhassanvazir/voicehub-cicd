#!/usr/bin/env bash
# Called by GitHub Actions on the EC2 server:  sudo bash deploy.sh <presigned S3 URL> <build file name>
# Downloads the build from S3, installs it as a new release, switches to it and restarts the app.
set -euo pipefail

URL="$1"
NAME="$2"
APP=/opt/voicehub
RELEASE="$APP/releases/${NAME%.zip}"

echo "==> Downloading $NAME from S3"
curl -fsSL "$URL" -o "/tmp/$NAME"

echo "==> Unpacking to $RELEASE"
rm -rf "$RELEASE"
mkdir -p "$RELEASE"
unzip -q "/tmp/$NAME" -d "$RELEASE"
rm -f "/tmp/$NAME"
chown -R voicehub:voicehub "$RELEASE"

echo "==> Installing Python packages"
sudo -u voicehub "$APP/venv/bin/pip" install -q -r "$RELEASE/requirements.txt"

echo "==> Updating database tables (existing data is kept)"
cd "$RELEASE"
sudo -u voicehub bash -c "set -a; source $APP/voicehub.env; set +a; $APP/venv/bin/python setup_db.py"

echo "==> Switching to the new release"
ln -sfn "$RELEASE" "$APP/current"
systemctl restart voicehub

echo "==> Health check"
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8000/health; then echo; break; fi
  [ "$i" = 10 ] && { echo "App did not start"; journalctl -u voicehub -n 30 --no-pager; exit 1; }
  sleep 2
done

echo "==> Keeping the 5 newest releases"
ls -1dt "$APP"/releases/*/ | tail -n +6 | xargs -r rm -rf
echo "==> Deployed $NAME"
