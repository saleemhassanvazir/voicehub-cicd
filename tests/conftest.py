"""Test setup: every test runs against a fresh copy of a separate test database."""
import os
import sys
import tempfile
from pathlib import Path

# Use a separate database and upload folder so tests never touch real data.
os.environ.setdefault("DB_NAME", "voicehub_test")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="voicehub-test-uploads-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import setup_db  # noqa: E402
from app import app as flask_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    setup_db.create_database()


@pytest.fixture(autouse=True)
def fresh_data():
    """Wipe and re-create the sample data before each test."""
    setup_db.create_tables(reset=True)
    setup_db.add_sample_data()


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def login(client, role, uid):
    return client.post(f"/demo/{role}/{uid}", follow_redirects=True)
