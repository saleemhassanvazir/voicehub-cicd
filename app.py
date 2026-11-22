"""VoiceHub - a marketplace for voice actors (Flask + PostgreSQL).

Run:   py app.py      then open http://localhost:5000
"""
import uuid
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
import db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
UPLOADS = config.UPLOAD_DIR
AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".ogg", ".aac"}

INDUSTRIES = ["Advertising", "Animation", "Gaming", "YouTube", "E-learning", "Radio", "Other"]
CATEGORIES = ["Commercial", "Animation", "Video game", "Audiobook", "YouTube", "E-learning", "Documentary", "Other"]
AGE_RANGES = ["Child", "Young adult", "Adult", "Senior"]
# Table names in SQL below always come from this fixed dictionary, never from user input (hence "nosec B608").
TABLE = {"actor": ("voice_actors", "actor_id"), "client": ("clients", "client_id")}


# ---------------------------------------------------------------- helpers

def me():
    """The logged-in user's row, or None."""
    role, uid = session.get("role"), session.get("uid")
    if role not in TABLE:
        return None
    table, key = TABLE[role]
    return db.query_one(f"SELECT * FROM {table} WHERE {key} = %s", (uid,))  # nosec B608


def require(role):
    user = me()
    if not user or session.get("role") != role:
        return None
    return user


@app.context_processor
def inject_user():
    return {"user": me(), "role": session.get("role"), "version": config.VERSION,
            "whats_new": config.WHATS_NEW, "build": config.BUILD}


@app.route("/health")
def health():
    """Used by the pipeline to check the deployment worked."""
    db.query_one("SELECT 1 AS ok")   # proves the database connection works
    return {"status": "ok", "version": config.VERSION, **config.BUILD}


def log_in(role, uid):
    session.clear()
    session["role"], session["uid"] = role, uid


# ---------------------------------------------------------------- login / sign up

@app.route("/")
def index():
    if session.get("role") == "actor":
        return redirect(url_for("actor_home"))
    if session.get("role") == "client":
        return redirect(url_for("client_home"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, password, role = request.form["email"].strip().lower(), request.form["password"], request.form["role"]
        table, key = TABLE[role]
        user = db.query_one(f"SELECT * FROM {table} WHERE email = %s", (email,))  # nosec B608
        if user and check_password_hash(user["password_hash"], password):
            log_in(role, user[key])
            return redirect(url_for("index"))
        flash("Wrong email or password.")
    actors = db.query("SELECT actor_id, full_name, email FROM voice_actors ORDER BY actor_id")
    clients = db.query("SELECT client_id, full_name, company_name, email FROM clients ORDER BY client_id")
    return render_template("login.html", actors=actors, clients=clients)


@app.post("/demo/<role>/<int:uid>")
def demo_login(role, uid):
    """One-click login for the demo accounts."""
    if role in TABLE:
        log_in(role, uid)
    return redirect(url_for("index"))


@app.route("/signup/<role>", methods=["GET", "POST"])
def signup(role):
    if role not in TABLE:
        return redirect(url_for("login"))
    if request.method == "POST":
        f = {k: (v.strip() or None) for k, v in request.form.items()}   # empty optional fields -> NULL
        email = f["email"].lower()
        table, key = TABLE[role]
        if db.query_one(f"SELECT 1 FROM {table} WHERE email = %s", (email,)):  # nosec B608
            flash("An account with this email already exists. Please log in.")
            return redirect(url_for("signup", role=role))
        pw = generate_password_hash(request.form["password"])
        if role == "actor":
            row = db.execute("""INSERT INTO voice_actors (full_name, email, password_hash, gender, voice_age_range,
                                    voice_style, languages, experience_years, rate_pkr, city, bio)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING actor_id""",
                             (f["full_name"], email, pw, f["gender"], f["voice_age_range"], f["voice_style"],
                              f["languages"], int(f["experience_years"] or 0), int(f["rate_pkr"] or 0),
                              f["city"], f["bio"]))
            log_in("actor", row["actor_id"])
        else:
            row = db.execute("""INSERT INTO clients (full_name, email, password_hash, company_name, client_type,
                                    industry, phone, city)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING client_id""",
                             (f["full_name"], email, pw, f["company_name"], f["client_type"], f["industry"],
                              f["phone"], f["city"]))
            log_in("client", row["client_id"])
        flash("Welcome to VoiceHub! Your account is ready.")
        return redirect(url_for("index"))
    return render_template(f"signup_{role}.html", industries=INDUSTRIES, age_ranges=AGE_RANGES)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- voice actor side

@app.route("/actor")
def actor_home():
    actor = require("actor")
    if not actor:
        return redirect(url_for("login"))
    projects = db.query("""
        SELECT p.*, c.company_name, c.full_name AS client_name,
               (SELECT COUNT(*) FROM auditions a WHERE a.project_id = p.project_id) AS audition_count,
               (SELECT a.status FROM auditions a WHERE a.project_id = p.project_id AND a.actor_id = %s) AS my_status
        FROM projects p JOIN clients c ON c.client_id = p.client_id
        WHERE p.status = 'Open' ORDER BY p.deadline""", (actor["actor_id"],))
    return render_template("actor_home.html", projects=projects)


@app.post("/actor/audition/<int:project_id>")
def send_audition(project_id):
    actor = require("actor")
    file = request.files.get("audio")
    if not actor or not file or not file.filename:
        flash("Choose your recording first.")
        return redirect(url_for("actor_home"))
    if Path(file.filename).suffix.lower() not in AUDIO_TYPES:
        flash("Please upload an audio file (WAV, MP3, M4A, OGG or AAC).")
        return redirect(url_for("actor_home"))
    if db.query_one("SELECT 1 FROM auditions WHERE project_id = %s AND actor_id = %s", (project_id, actor["actor_id"])):
        flash("You already sent an audition for this project.")
        return redirect(url_for("actor_home"))
    filename = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    UPLOADS.mkdir(parents=True, exist_ok=True)
    file.save(UPLOADS / filename)
    db.execute("INSERT INTO auditions (project_id, actor_id, audio_file, note) VALUES (%s, %s, %s, %s)",
               (project_id, actor["actor_id"], filename, request.form.get("note", "").strip()))
    flash("Audition sent. Good luck!")
    return redirect(url_for("actor_work"))


@app.route("/actor/work")
def actor_work():
    actor = require("actor")
    if not actor:
        return redirect(url_for("login"))
    auditions = db.query("""
        SELECT a.*, p.title, p.category, p.budget_pkr, c.company_name
        FROM auditions a JOIN projects p ON p.project_id = a.project_id
        JOIN clients c ON c.client_id = p.client_id
        WHERE a.actor_id = %s ORDER BY a.submitted_at DESC""", (actor["actor_id"],))
    contracts = db.query("""
        SELECT ct.*, p.title, c.company_name, r.rating AS review_rating, r.comment AS review_comment
        FROM contracts ct JOIN projects p ON p.project_id = ct.project_id
        JOIN clients c ON c.client_id = ct.client_id
        LEFT JOIN reviews r ON r.contract_id = ct.contract_id
        WHERE ct.actor_id = %s ORDER BY ct.created_at DESC""", (actor["actor_id"],))
    earned = sum(c["amount_pkr"] for c in contracts if c["payment_status"] == "Paid")
    return render_template("actor_work.html", auditions=auditions, contracts=contracts, earned=earned)


# ---------------------------------------------------------------- client side

@app.route("/client")
def client_home():
    client = require("client")
    if not client:
        return redirect(url_for("login"))
    projects = db.query("""
        SELECT p.*, COUNT(a.audition_id) AS audition_count
        FROM projects p LEFT JOIN auditions a ON a.project_id = p.project_id
        WHERE p.client_id = %s GROUP BY p.project_id ORDER BY p.created_at DESC""", (client["client_id"],))
    return render_template("client_home.html", projects=projects, categories=CATEGORIES)


@app.post("/client/projects")
def post_project():
    client = require("client")
    if not client:
        return redirect(url_for("login"))
    f = request.form
    db.execute("""INSERT INTO projects (client_id, title, category, script, language_required,
                      gender_preference, budget_pkr, deadline)
                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
               (client["client_id"], f["title"], f["category"], f["script"], f["language_required"],
                f["gender_preference"], int(f["budget_pkr"]), f["deadline"]))
    flash(f"Casting call \"{f['title']}\" is live.")
    return redirect(url_for("client_home"))


def own_project(client, project_id):
    return db.query_one("SELECT * FROM projects WHERE project_id = %s AND client_id = %s",
                        (project_id, client["client_id"]))


@app.route("/client/project/<int:project_id>")
def client_project(project_id):
    client = require("client")
    project = client and own_project(client, project_id)
    if not project:
        return redirect(url_for("client_home"))
    auditions = db.query("""
        SELECT a.*, va.full_name, va.gender, va.voice_age_range, va.voice_style, va.languages,
               va.experience_years, va.rate_pkr, va.rating, va.city
        FROM auditions a JOIN voice_actors va ON va.actor_id = a.actor_id
        WHERE a.project_id = %s ORDER BY a.submitted_at""", (project_id,))
    contract = db.query_one("""
        SELECT ct.*, va.full_name AS actor_name, r.rating AS review_rating, r.comment AS review_comment
        FROM contracts ct JOIN voice_actors va ON va.actor_id = ct.actor_id
        LEFT JOIN reviews r ON r.contract_id = ct.contract_id
        WHERE ct.project_id = %s""", (project_id,))
    return render_template("client_project.html", project=project, auditions=auditions, contract=contract)


@app.post("/client/hire/<int:audition_id>")
def hire(audition_id):
    client = require("client")
    audition = db.query_one("SELECT * FROM auditions WHERE audition_id = %s", (audition_id,))
    project = client and audition and own_project(client, audition["project_id"])
    if not project or project["status"] != "Open":
        return redirect(url_for("client_home"))
    with db.transaction() as tx:   # all four changes are saved together
        tx.execute("UPDATE auditions SET status = 'Hired' WHERE audition_id = %s", (audition_id,))
        tx.execute("UPDATE auditions SET status = 'Not selected' WHERE project_id = %s AND audition_id <> %s",
                   (project["project_id"], audition_id))
        tx.execute("UPDATE projects SET status = 'Hired' WHERE project_id = %s", (project["project_id"],))
        tx.execute("""INSERT INTO contracts (project_id, audition_id, client_id, actor_id, amount_pkr)
                      VALUES (%s, %s, %s, %s, %s)""",
                   (project["project_id"], audition_id, client["client_id"], audition["actor_id"], project["budget_pkr"]))
    flash("Actor hired. A contract has been created.")
    return redirect(url_for("client_project", project_id=project["project_id"]))


@app.post("/client/pay/<int:contract_id>")
def pay(contract_id):
    client = require("client")
    contract = db.query_one("SELECT * FROM contracts WHERE contract_id = %s AND client_id = %s",
                            (contract_id, client["client_id"] if client else -1))
    if not contract:
        return redirect(url_for("client_home"))
    with db.transaction() as tx:
        tx.execute("UPDATE contracts SET payment_status = 'Paid', paid_at = NOW() WHERE contract_id = %s", (contract_id,))
        tx.execute("UPDATE projects SET status = 'Completed' WHERE project_id = %s", (contract["project_id"],))
    flash("Payment recorded. The project is complete.")
    return redirect(url_for("client_project", project_id=contract["project_id"]))


@app.post("/client/review/<int:contract_id>")
def review(contract_id):
    client = require("client")
    contract = db.query_one("SELECT * FROM contracts WHERE contract_id = %s AND client_id = %s AND payment_status = 'Paid'",
                            (contract_id, client["client_id"] if client else -1))
    if not contract:
        return redirect(url_for("client_home"))
    with db.transaction() as tx:
        tx.execute("""INSERT INTO reviews (contract_id, client_id, actor_id, rating, comment)
                      VALUES (%s, %s, %s, %s, %s)""",
                   (contract_id, client["client_id"], contract["actor_id"], int(request.form["rating"]),
                    request.form.get("comment", "").strip()))
        tx.execute("""UPDATE voice_actors SET rating =
                          (SELECT ROUND(AVG(rating), 1) FROM reviews WHERE actor_id = %s)
                      WHERE actor_id = %s""", (contract["actor_id"], contract["actor_id"]))
    flash("Thanks! Your review was saved.")
    return redirect(url_for("client_project", project_id=contract["project_id"]))


@app.route("/uploads/<path:filename>")
def audio(filename):
    return send_from_directory(UPLOADS, filename)


if __name__ == "__main__":
    print("\n  VoiceHub is running. Open http://localhost:5000  (Ctrl+C to stop)")
    print("  Every SQL statement the app runs is shown below.\n")
    app.run(port=5000, debug=False)
