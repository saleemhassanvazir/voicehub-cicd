# VoiceHub CI/CD – Step-by-step setup guide

Total time: about 1.5–2 hours the first time. Do the parts in order.
Everything below uses region **Asia Pacific (Mumbai) `ap-south-1`** – keep it the same everywhere.

> **Never** put AWS keys or the `.pem` file inside the project folder or commit them. They only go into GitHub Secrets.

---

## Part 1 – Put the code on GitHub (15 min)

1. Unzip `voicehub-cicd.zip` somewhere simple, e.g. `Documents\voicehub-cicd`.
2. Create a GitHub account at github.com if you don't have one.
3. Install **GitHub Desktop** (desktop.github.com) and sign in with your GitHub account.
4. In GitHub Desktop: **File → Add local repository** → choose the `voicehub-cicd` folder.
   It will say "this directory does not appear to be a Git repository" → click **create a repository** → **Create repository**.
5. Click **Publish repository**. Name: `voicehub-cicd`. **Untick "Keep this code private"** (the setup command in Part 4 needs it public, and your teacher needs to see it). Click **Publish**.
6. GitHub will immediately try to run the pipeline and it will **fail** at "Build" – that's expected, AWS isn't set up yet. The security scan and tests should already be green ✅.

## Part 2 – AWS safety first (5 min)

1. Sign in to the AWS Console as the root user.
2. Search **Billing and Cost Management → Budgets → Create budget → Use a template → Zero spend budget**, enter your email → Create.
   You'll get an email if anything starts costing money.

## Part 3 – S3 bucket + IAM user for GitHub (15 min)

**S3 bucket**
1. Search **S3** → **Create bucket**.
2. Name: `voicehub-builds-19762` (must be unique worldwide; add more numbers if taken). Region: `ap-south-1`.
3. Leave **Block all public access** ON. Click **Create bucket**.

**IAM user (can only touch this bucket)**
1. Search **IAM** → **Users** → **Create user** → name `github-actions-voicehub` → Next.
2. Choose **Attach policies directly** → click **Create policy** (opens a new tab) → **JSON** tab, paste this (change the bucket name if yours is different):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::voicehub-builds-19762/*" },
    { "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::voicehub-builds-19762" }
  ]
}
```
3. Next → name `VoiceHubS3Deploy` → **Create policy**. Go back to the first tab, refresh the list, tick `VoiceHubS3Deploy` → Next → **Create user**.
4. Open the user → **Security credentials** → **Create access key** → choose **Application running outside AWS** → Create.
   Copy the **Access key ID** and **Secret access key** into Notepad for now (you can't see the secret again).

## Part 4 – EC2 web server (20 min)

1. Search **EC2** → **Launch instance**.
2. Name: `voicehub-production`. Image: **Ubuntu Server 24.04 LTS** (Free tier eligible).
3. Instance type: **t3.micro** (or t2.micro – whichever says Free tier eligible).
4. Key pair: **Create new key pair** → name `voicehub-key`, type RSA, format **.pem** → it downloads. Keep it safe, **not** in the project folder.
5. Network settings → **Edit**:
   - Allow SSH traffic from: **Anywhere (0.0.0.0/0)** – GitHub Actions connects from changing IPs.
   - Tick **Allow HTTP traffic from the internet**.
6. Storage: 8 GB is fine → **Launch instance**.
7. Open the instance and copy its **Public IPv4 address** (e.g. `13.233.45.67`).
   Tip: the IP changes if you stop/start the instance – then update the `EC2_HOST` variable.
8. Click **Connect** → **EC2 Instance Connect** → **Connect**. A black terminal opens in the browser. Paste (replace `YOUR_GITHUB_USERNAME`):

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/voicehub-cicd/main/deploy/server_setup.sh | sudo bash
```
   Wait 2–3 minutes until it prints **"Server ready."**

## Part 5 – Connect GitHub to AWS (10 min)

On GitHub, open your repo → **Settings → Secrets and variables → Actions**.

**Secrets tab → New repository secret** (three times):

| Name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | access key ID from Part 3 |
| `AWS_SECRET_ACCESS_KEY` | secret access key from Part 3 |
| `EC2_SSH_KEY` | open `voicehub-key.pem` in Notepad, copy **everything** including the `-----BEGIN` and `-----END` lines |

**Variables tab → New repository variable** (three times):

| Name | Value |
|---|---|
| `AWS_REGION` | `ap-south-1` |
| `S3_BUCKET` | `voicehub-builds-19762` (your bucket name) |
| `EC2_HOST` | the EC2 public IP, e.g. `13.233.45.67` |

Now delete the keys from Notepad.

## Part 6 – First real deployment (10 min)

1. On GitHub: **Actions** tab → **VoiceHub CI/CD** → **Run workflow** → Run.
2. Watch the 5 boxes go green: Security scan → Unit tests → Build and upload to S3 → Deploy to EC2 → Verify live production. (~4 min)
3. Open `http://YOUR_EC2_IP` – VoiceHub is live. The login page shows **v1.0.0**, the footer shows the build number.
4. In S3, open the bucket → `builds/` – you'll see the zip and `latest.txt`.

**If something is red**, click the red job and read the last lines:
- `Could not resolve host` / `Connection timed out` in Deploy → wrong `EC2_HOST`, or port 22 not open.
- `Permission denied (publickey)` → `EC2_SSH_KEY` not pasted fully.
- `AccessDenied` in Build → bucket name in the policy doesn't match `S3_BUCKET`.

## Part 7 – Prove the pipeline stops on failing tests (5 min, do before recording)

1. Open `tests/test_app.py`, in `test_health_check_reports_version_and_database` change `== 200` to `== 201`.
2. GitHub Desktop: summary "Break a test on purpose" → **Commit to main** → **Push origin**.
3. In Actions the run stops at **Unit tests** ❌ and Build/Deploy are **skipped** – the live site is untouched.
4. Change it back to `== 200`, commit "Fix test", push → everything green again.

Now the failed run is in your Actions history to show in the video.

## Part 8 – Record the 2-minute demo

Have these tabs open: VS Code/Notepad with the project, GitHub Desktop, GitHub Actions, S3 bucket, the live site.

| Time | Show | Say (roughly) |
|---|---|---|
| 0:00–0:15 | Live site, login page (v1.0.0) | "This is VoiceHub running on AWS EC2, version 1.0.0. I'll push a change and the pipeline will deploy it automatically." |
| 0:15–0:35 | Edit `VERSION` → `1.1.0`, and `WHATS_NEW` in `config.py` (e.g. "Actors can now see their ratings on their dashboard.") | "I change the version and release note." |
| 0:35–0:45 | GitHub Desktop → commit → Push origin | "Commit and push to main – this triggers GitHub Actions." |
| 0:45–1:20 | Actions run; click through jobs: security scan, 14 tests passing, build, S3 upload | "First the DevSecOps scan: Bandit, pip-audit and Gitleaks. Then 14 unit tests against PostgreSQL. Then it builds the zip and uploads it to S3." *(cut/speed up the waiting)* |
| 1:20–1:35 | S3 bucket `builds/` – new `build` zip and `latest.txt` | "The artifact is stored in S3 and marked as the latest successful build." |
| 1:35–1:50 | Deploy + Verify logs, then refresh live site → **v1.1.0** and new build number in footer | "The deploy job pulls the latest build from S3 onto EC2, and verify checks the live version. The site now shows 1.1.0." |
| 1:50–2:00 | The earlier red run from Part 7 | "And if a test fails, the pipeline stops – nothing is built or deployed." |

## Part 9 – What to submit

- **GitHub repo URL:** `https://github.com/YOUR_GITHUB_USERNAME/voicehub-cicd`
- **Workflow file:** `.github/workflows/cicd.yml` (link: repo URL + `/blob/main/.github/workflows/cicd.yml`)
- **Demo video** (≤ 2 min)
- **Bonus:** the `security-scan` job (SAST = Bandit, dependency scan = pip-audit, secret scan = Gitleaks)

## Part 10 – After grading (don't skip)

- EC2 → select instance → **Instance state → Terminate** (stopping still bills storage after the free tier).
- IAM → user `github-actions-voicehub` → delete its access key (or the user).
- S3 → empty and delete the bucket.

## Demo logins on the live site

All sample accounts use password **`demo123`**, or use the one-click demo buttons on the login page.
Clients: `bilal@pixelstudios.pk`, `ayesha@techtalk.pk` · Voice actors: `ali@voicehub.pk` and others.
