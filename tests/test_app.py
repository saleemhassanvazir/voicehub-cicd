"""Unit tests for VoiceHub. The pipeline stops if any of these fail.

Sample data (from setup_db.py):
  clients:      1 Bilal Ahmed (Pixel Studios), 2 Ayesha Siddiqui (TechTalk PK)
  voice actors: 1 Ali Raza, 2 Sana Khan, 3 Usman Tariq
  projects:     1 Robot cartoon (client 1), 2 YouTube intro (client 2),
                3 Game trailer (client 1), 4 Documentary (client 2, completed)
"""
import io

import config
import db
from tests.conftest import login


def wav_file(name="take.wav"):
    data = (config.BASE / "sample_audition.wav").read_bytes()
    return (io.BytesIO(data), name)


# ---------------------------------------------------------------- basics

def test_health_check_reports_version_and_database(client):
    response = client.get("/health")
    assert response.status_code == 201
    assert response.json["status"] == "ok"
    assert response.json["version"] == config.VERSION


def test_login_page_shows_both_sides_and_version(client):
    page = client.get("/login").get_data(as_text=True)
    assert "I'm a voice actor" in page
    assert "I'm hiring a voice" in page
    assert f"v{config.VERSION}" in page


def test_wrong_password_is_rejected(client):
    page = client.post("/login", data={"role": "actor", "email": "ali@voicehub.pk", "password": "wrong"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Wrong email or password" in page


def test_correct_password_logs_in(client):
    page = client.post("/login", data={"role": "client", "email": "bilal@pixelstudios.pk", "password": "demo123"},
                       follow_redirects=True).get_data(as_text=True)
    assert "My casting calls" in page


def test_pages_require_login(client):
    response = client.get("/client")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------- sign up

def test_signup_saves_voice_actor_with_hashed_password(client):
    client.post("/signup/actor", data={
        "full_name": "Hira Malik", "email": "hira@example.com", "password": "secret12", "city": "Multan",
        "gender": "Female", "voice_age_range": "Adult", "voice_style": "Soft", "languages": "Urdu, Saraiki",
        "experience_years": "2", "rate_pkr": "7000", "bio": ""})
    actor = db.query_one("SELECT * FROM voice_actors WHERE email = 'hira@example.com'")
    assert actor["full_name"] == "Hira Malik"
    assert actor["password_hash"] != "secret12"          # never stored as plain text
    assert actor["bio"] is None                           # empty fields saved as NULL


def test_signup_rejects_duplicate_email(client):
    page = client.post("/signup/client", data={
        "full_name": "Someone", "email": "bilal@pixelstudios.pk", "password": "secret12", "phone": "",
        "company_name": "", "client_type": "Individual", "industry": "Other", "city": ""},
        follow_redirects=True).get_data(as_text=True)
    assert "already exists" in page
    assert db.query_one("SELECT COUNT(*) AS n FROM clients")["n"] == 2


# ---------------------------------------------------------------- client posts, actor auditions

def test_client_posts_casting_call(client):
    login(client, "client", 1)
    client.post("/client/projects", data={
        "title": "Radio ad: juice", "category": "Commercial", "script": "Thanda thanda!",
        "language_required": "Urdu", "gender_preference": "Any", "budget_pkr": "10000", "deadline": "2030-01-01"})
    project = db.query_one("SELECT * FROM projects WHERE title = 'Radio ad: juice'")
    assert project["client_id"] == 1
    assert project["status"] == "Open"


def test_actor_sends_audition(client):
    login(client, "actor", 1)
    client.post("/actor/audition/1", data={"audio": wav_file(), "note": "First take"},
                content_type="multipart/form-data")
    audition = db.query_one("SELECT * FROM auditions WHERE project_id = 1 AND actor_id = 1")
    assert audition["status"] == "Submitted"
    assert (config.UPLOAD_DIR / audition["audio_file"]).exists()


def test_actor_cannot_audition_twice_for_same_project(client):
    login(client, "actor", 2)    # Sana already auditioned for project 2 in the sample data
    client.post("/actor/audition/2", data={"audio": wav_file()}, content_type="multipart/form-data")
    assert db.query_one("SELECT COUNT(*) AS n FROM auditions WHERE project_id = 2 AND actor_id = 2")["n"] == 1


def test_non_audio_files_are_rejected(client):
    login(client, "actor", 1)
    client.post("/actor/audition/1", data={"audio": (io.BytesIO(b"hello"), "virus.exe")},
                content_type="multipart/form-data")
    assert db.query_one("SELECT COUNT(*) AS n FROM auditions WHERE project_id = 1")["n"] == 0


# ---------------------------------------------------------------- hire, pay, review

def test_hiring_creates_contract_and_updates_statuses(client):
    login(client, "client", 2)
    client.post("/client/hire/1")          # audition 1 = Sana for project 2
    assert db.query_one("SELECT status FROM auditions WHERE audition_id = 1")["status"] == "Hired"
    assert db.query_one("SELECT status FROM projects WHERE project_id = 2")["status"] == "Hired"
    contract = db.query_one("SELECT * FROM contracts WHERE project_id = 2")
    assert contract["actor_id"] == 2
    assert contract["amount_pkr"] == 8000
    assert contract["payment_status"] == "Pending"


def test_payment_and_review_update_actor_rating(client):
    login(client, "client", 2)
    client.post("/client/hire/1")
    contract_id = db.query_one("SELECT contract_id FROM contracts WHERE project_id = 2")["contract_id"]
    client.post(f"/client/pay/{contract_id}")
    client.post(f"/client/review/{contract_id}", data={"rating": "4", "comment": "Great energy"})
    assert db.query_one("SELECT payment_status FROM contracts WHERE contract_id = %s",
                        (contract_id,))["payment_status"] == "Paid"
    assert db.query_one("SELECT status FROM projects WHERE project_id = 2")["status"] == "Completed"
    assert float(db.query_one("SELECT rating FROM voice_actors WHERE actor_id = 2")["rating"]) == 4.0


def test_client_cannot_hire_on_someone_elses_project(client):
    login(client, "client", 1)             # Bilal does not own project 2
    client.post("/client/hire/1")
    assert db.query_one("SELECT COUNT(*) AS n FROM contracts WHERE project_id = 2")["n"] == 0
