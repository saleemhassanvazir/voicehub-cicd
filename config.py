"""Settings, read from environment variables.

On your laptop the defaults below are used. On the AWS server the values
come from /opt/voicehub/voicehub.env (created by deploy/server_setup.sh),
so no password is ever stored in the code.
"""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")   # laptop: your PostgreSQL password
DB_NAME = os.environ.get("DB_NAME", "voicehub")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE / "uploads"))

# ---- Release information (shown on the website) ----------------------------
# For the demo: change VERSION and WHATS_NEW, commit and push.
VERSION = (BASE / "VERSION").read_text().strip()
WHATS_NEW = "Clients can now hire, pay and review voice actors in one place."

# build_info.json is written by the GitHub Actions build job (build number, commit).
_build_file = BASE / "build_info.json"
BUILD = json.loads(_build_file.read_text()) if _build_file.exists() else {"build": "local", "commit": "dev"}
