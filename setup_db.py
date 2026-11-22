"""Creates the 'voicehub' database, its tables, and sample data.

    py setup_db.py           create anything missing; add sample data only if empty
                             (safe to run on every deployment - never deletes data)
    py setup_db.py --reset   delete everything and start again with sample data
"""
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg
from werkzeug.security import generate_password_hash

import config
import db

BASE = Path(__file__).resolve().parent
UPLOADS = config.UPLOAD_DIR
DEMO_PASSWORD = "demo123"


def create_database():
    with db.connect(dbname="postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.DB_NAME,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{config.DB_NAME}"')
            print(f"Created database '{config.DB_NAME}'")


def create_tables(reset=False):
    with db.connect() as conn:
        if reset:
            conn.execute("DROP TABLE IF EXISTS reviews, contracts, auditions, projects, voice_actors, clients CASCADE")
        conn.execute((BASE / "database" / "schema.sql").read_text())
    print("Tables ready: clients, voice_actors, projects, auditions, contracts, reviews")


def is_empty():
    return db.query_one("SELECT COUNT(*) AS n FROM clients")["n"] == 0


def add_sample_data():
    pw = generate_password_hash(DEMO_PASSWORD)
    soon = date.today() + timedelta(days=14)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    for name in ["sample_sana.wav", "sample_usman.wav"]:
        shutil.copy(BASE / "sample_audition.wav", UPLOADS / name)

    with db.transaction() as tx:
        sql = """INSERT INTO clients (full_name, email, password_hash, company_name, client_type, industry, phone, city)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        tx.execute(sql, ("Bilal Ahmed", "bilal@pixelstudios.pk", pw, "Pixel Studios", "Company", "Animation", "0300-1234567", "Lahore"))
        tx.execute(sql, ("Ayesha Siddiqui", "ayesha@techtalk.pk", pw, "TechTalk PK", "Individual", "YouTube", "0321-7654321", "Karachi"))

        sql = """INSERT INTO voice_actors (full_name, email, password_hash, gender, voice_age_range, voice_style,
                     languages, experience_years, rate_pkr, city, is_available, bio)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        tx.execute(sql, ("Ali Raza", "ali@voicehub.pk", pw, "Male", "Adult", "Deep and warm", "Urdu, English",
                         5, 12000, "Lahore", True, "Radio presenter turned voice actor. Home studio."))
        tx.execute(sql, ("Sana Khan", "sana@voicehub.pk", pw, "Female", "Young adult", "Bright and energetic",
                         "Urdu, English, Punjabi", 3, 9000, "Karachi", True, "Cartoon and YouTube voices."))
        tx.execute(sql, ("Usman Tariq", "usman@voicehub.pk", pw, "Male", "Senior", "Calm narrator", "Urdu",
                         12, 20000, "Islamabad", False, "Documentary and audiobook narrator."))

        sql = """INSERT INTO projects (client_id, title, category, script, language_required, gender_preference,
                     budget_pkr, deadline, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        tx.execute(sql, (1, "Robot cartoon: friendly narrator", "Animation",
                         "Once upon a time, in a city of lights, lived a very curious robot.",
                         "Urdu", "Any", 40000, soon, "Open"))
        tx.execute(sql, (2, "YouTube channel intro", "YouTube",
                         "Welcome back to TechTalk, where gadgets get real!", "English", "Female", 8000, soon, "Open"))
        tx.execute(sql, (1, "Game trailer: villain voice", "Video game",
                         "You thought you could escape me? Nobody escapes the Shadow King.",
                         "English", "Male", 25000, soon, "Open"))
        tx.execute(sql, (2, "Documentary narration", "Documentary",
                         "The Indus has shaped life in this land for five thousand years.",
                         "Urdu", "Male", 20000, date.today() - timedelta(days=20), "Completed"))

        tx.execute("INSERT INTO auditions (project_id, actor_id, audio_file, note) VALUES (%s, %s, %s, %s)",
                   (2, 2, "sample_sana.wav", "Recorded with a USB mic, can do a few retakes."))
        tx.execute("INSERT INTO auditions (project_id, actor_id, audio_file, note, status) VALUES (%s, %s, %s, %s, %s)",
                   (4, 3, "sample_usman.wav", "Slow, calm read as requested.", "Hired"))
        tx.execute("""INSERT INTO contracts (project_id, audition_id, client_id, actor_id, amount_pkr, payment_status, paid_at)
                      VALUES (4, 2, 2, 3, 20000, 'Paid', NOW() - INTERVAL '10 days')""")
        tx.execute("INSERT INTO reviews (contract_id, client_id, actor_id, rating, comment) VALUES (1, 2, 3, 5, %s)",
                   ("Beautiful narration, delivered early.",))
        tx.execute("UPDATE voice_actors SET rating = 5.0 WHERE actor_id = 3")
    print(f"Added sample data (every demo account's password is '{DEMO_PASSWORD}')")


if __name__ == "__main__":
    try:
        create_database()
    except psycopg.OperationalError as error:
        raise SystemExit(f"\nCould not connect to PostgreSQL.\nCheck that it is running and that DB_PASSWORD "
                         f"in config.py is the password you chose when installing it.\n\nDetails: {error}")
    reset = "--reset" in sys.argv
    create_tables(reset=reset)
    if reset or is_empty():
        add_sample_data()
    else:
        print("Existing data kept.")
    print("\nDone. Now run:  py app.py")
