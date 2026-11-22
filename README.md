# VoiceHub – CI/CD with GitHub Actions and AWS

VoiceHub is a small marketplace where **clients** post casting calls and **voice actors** send audio auditions.
Clients hire, pay and review actors. Built with **Flask + PostgreSQL**.

This repository delivers it automatically to AWS on every push to `main`.

## Pipeline

```
Code change → git push → Security scan → Unit tests → Build → Artifact → AWS S3 → Deploy to EC2 → Verify live
```

| Job | What it does | Fails when |
|---|---|---|
| **security-scan** (DevSecOps) | Bandit (SAST), pip-audit (dependency CVEs), Gitleaks (secrets in git history) | a vulnerability or leaked secret is found |
| **test** | 14 pytest unit tests against a real PostgreSQL service container | any test fails – nothing after it runs |
| **build** | Zips the app as `voicehub-v<VERSION>-build<N>.zip` with `build_info.json`, saves it as a GitHub artifact, uploads it to `s3://<bucket>/builds/` and updates `builds/latest.txt` | upload fails |
| **deploy** | Reads `latest.txt`, creates a 10-minute presigned S3 link, SSHes into EC2 and runs `deploy/deploy.sh` | the app does not start on the server |
| **verify** | Calls `http://<EC2>/health` and checks the live version and build number match this run | production is not running this build |

Workflow file: [`.github/workflows/cicd.yml`](.github/workflows/cicd.yml)

## AWS architecture

```
GitHub Actions ──(IAM user, S3 only)──► S3 bucket  builds/voicehub-v1.0.0-build12.zip, latest.txt
       │                                    │ presigned URL (expires in 10 min)
       └──── SSH (key in GitHub Secrets) ──► EC2 Ubuntu 24.04
                                              nginx :80 → gunicorn :8000 → Flask app → PostgreSQL
                                              /opt/voicehub/releases/<build>  (last 5 kept)
                                              /opt/voicehub/current → newest release
```

- The server never holds AWS keys; it downloads the build through a short-lived presigned URL.
- Database password and Flask secret key are generated on the server (`/opt/voicehub/voicehub.env`), not stored in GitHub.
- Uploads and data live outside the release folders, so a new deploy keeps all existing data.

## Project layout

```
app.py, db.py, config.py, setup_db.py   Flask app and database code
database/schema.sql, queries.sql        6 tables: clients, voice_actors, projects, auditions, contracts, reviews
templates/, static/                     Web pages
tests/                                  Unit tests (pytest)
deploy/server_setup.sh                  One-time EC2 setup (PostgreSQL, nginx, systemd)
deploy/deploy.sh                        Runs on EC2 for every deployment
VERSION                                 Release number shown on the site and checked by the pipeline
```

## Run locally

```bash
pip install -r requirements-dev.txt
python setup_db.py          # creates the voicehub database with sample data (add --reset to start over)
python app.py               # http://localhost:5000
pytest -v                   # run the unit tests
```

Set `DB_PASSWORD` (and other `DB_*` variables) if your local PostgreSQL password is not `postgres`.

## Configuration in GitHub

| Type | Name | Value |
|---|---|---|
| Secret | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | IAM user limited to the S3 bucket |
| Secret | `EC2_SSH_KEY` | contents of the EC2 key pair `.pem` |
| Variable | `AWS_REGION` | e.g. `ap-south-1` |
| Variable | `S3_BUCKET` | bucket name |
| Variable | `EC2_HOST` | EC2 public IP |
