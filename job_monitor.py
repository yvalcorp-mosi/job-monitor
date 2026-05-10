#!/usr/bin/env python3
"""
job_monitor.py — Personal cybersecurity job monitor for Paul Simo.

What this does:
  1. Hits the PUBLIC Greenhouse and Lever JSON APIs for ~35 companies.
     These APIs return live job data straight from each company's ATS —
     no cached HTML, no stale aggregator data. If a job appears here,
     it is open right now.
  2. Filters for senior cybersecurity roles that are remote and ideally
     mention "shift" / "2nd" / "swing" / "afternoon" in the title or text.
  3. Deduplicates against a local SQLite database so you only see NEW jobs.
  4. Writes a Markdown report at ./reports/jobs_YYYY-MM-DD.md you can open
     in any editor, and a single ./reports/latest.md that always has the
     most recent run.
  5. (Optional) Emails you the report via SMTP if you set SMTP_* env vars.

Setup:
  $ python3 -m venv venv && source venv/bin/activate
  $ pip install requests
  $ python3 job_monitor.py

Run on a schedule (Mac/Linux):
  $ crontab -e
  # add this line to run daily at 7 AM:
  0 7 * * * cd /path/to/this/folder && /path/to/venv/bin/python job_monitor.py

Run on a schedule (Windows):
  Use Task Scheduler. Action: Start a program. Program/script: python.
  Add arguments: job_monitor.py. Start in: the folder where this file lives.

Run on a schedule (free, no server needed):
  Push this folder to GitHub, add a .github/workflows/daily.yml workflow
  with a cron trigger. GitHub Actions has a generous free tier.

API references (so you can verify the data sources yourself):
  Greenhouse:  https://developers.greenhouse.io/job-board.html
               GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs
  Lever:       https://github.com/lever/postings-api
               GET https://api.lever.co/v0/postings/{company}?mode=json

Version: 1.0  (May 9, 2026)
"""

import json
import os
import re
import smtplib
import sqlite3
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these to tune the search to your needs
# ─────────────────────────────────────────────────────────────────────────────

# Greenhouse-hosted companies. The slug is the {token} in their board URL.
# To verify a company uses Greenhouse: visit boards.greenhouse.io/{slug}
# To find more: search Google for site:boards.greenhouse.io "<company>"
GREENHOUSE_COMPANIES = [
    "appian",          # SaaS — has confirmed 2nd shift InfoSec Analyst role pattern
    "vectranetworks",  # Vectra AI — confirmed 2nd/3rd shift Sr Security Analyst
    "huntress",        # MDR pure-play, hires 24/7 SOC
    "redcanary",       # MDR, Detection-as-Code shop
    "cloudflare",      # CDN/security, large security org
    "datadog",         # Observability, in-house security team
    "snowflake",       # Data cloud, enterprise security roles
    "discord",         # Trust & Safety + InfoSec
    "coinbase",        # Crypto exchange, mature security org
    "stripe",          # Payments, top-tier security team
    "plaid",           # Fintech, regulated security
    "robinhood",       # Fintech, 24/7 ops
    "chainalysis",     # Blockchain analytics, threat intel heavy
    "affirm",          # BNPL fintech
    "brex",            # Corporate cards, security regulated
    "asana",           # SaaS, growing security team
    "notion",          # Productivity SaaS
    "figma",           # Design SaaS
    "airbnb",          # Marketplace, large security team
    "doordash",        # Delivery, 24/7 ops
    "twilio",          # Communications APIs
    "hashicorp",       # Infrastructure security
    "elastic",         # ELK / Elastic Security
    "gitlab",          # Remote-first, all-remote security team
    "reddit",          # Trust & Safety + InfoSec
    "dbtlabsinc",      # dbt Labs — modern data stack
    "boxinc",          # Box, enterprise content
    "mongodb",         # Database, large security team
    "confluent",       # Kafka company, regulated SaaS
    "wiz",             # Cloud security vendor
    "recordedfuture",  # Threat intel pure-play
    "anthropic",       # AI safety company (Claude's maker)
    "deelinc",         # Deel — global payroll
    "ramp",            # Fintech, fast-growing
    "instacart",       # Marketplace
]

# Lever-hosted companies. Slug = the {company} in their job URL.
# To verify: visit jobs.lever.co/{slug}
LEVER_COMPANIES = [
    "netflix",         # Media, large security org
    "eventbrite",      # Events platform
    "yelp",            # Local search
    "khanacademy",     # Education non-profit
    "motive",          # Fleet management (formerly KeepTruckin)
    "ridgelinemkt",    # Ridgeline — fintech for asset managers
    "attentive",       # Marketing SaaS
]

# Title MUST contain at least one of these (case-insensitive).
# Add or remove keywords to broaden / narrow the filter.
SENIORITY_KEYWORDS = [
    "senior", "sr.", "sr ", "staff", "principal", "lead",
    "architect", "manager",
]

# Title MUST contain at least one of these (case-insensitive).
# This list is deliberately broad to catch vendor-specific naming
# (e.g. "Active Defense" at CrowdStrike, "Concierge Security" at Arctic Wolf).
DOMAIN_KEYWORDS = [
    "security", "soc", "cyber", "detection", "incident", "threat",
    "falcon", "mdr", "siem", "secops", "appsec", "cloud security",
    "infosec", "infrastructure security", "trust", "defense",
    "vulnerability", "pentest", "penetration test", "red team",
    "blue team", "purple team", "iam", "identity", "grc",
    "fraud", "abuse", "concierge", "forensic",
]

# Location MUST contain at least one of these (case-insensitive).
# Set to [] to disable location filtering.
LOCATION_KEYWORDS = [
    "remote", "united states", "usa", "us-", "anywhere",
    "nationwide", "north america", "americas",
]

# BONUS keywords — if title OR location contains any, the job is highlighted
# in the report as a top match. Set to [] to disable bonus highlighting.
SHIFT_KEYWORDS = [
    "shift", "2nd shift", "second shift", "swing", "afternoon",
    "evening", "3rd shift", "third shift", "night",
    "24/7", "24x7", "rotating",
]

# Where to store the dedup DB and reports.
DB_PATH = Path("seen_jobs.db")
REPORTS_DIR = Path("reports")

# Optional: email config. Set these env vars to enable email delivery.
# export SMTP_HOST=smtp.gmail.com
# export SMTP_PORT=587
# export SMTP_USER=you@gmail.com
# export SMTP_PASS=your-app-password   # for Gmail, use an App Password
# export EMAIL_TO=you@gmail.com
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
EMAIL_TO = os.environ.get("EMAIL_TO")

# Polite throttle between API calls.
THROTTLE_SECONDS = 0.5

# HTTP timeout per request, in seconds.
HTTP_TIMEOUT = 15

# User-Agent — be a good citizen and identify yourself.
USER_AGENT = "PaulSimo-JobMonitor/1.0 (personal job search; contact: paulsimov@gmail.com)"

# ─────────────────────────────────────────────────────────────────────────────
# CORE CODE — you should not need to edit below this line
# ─────────────────────────────────────────────────────────────────────────────


def init_db() -> sqlite3.Connection:
    """Create the SQLite DB if missing. Returns an open connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen (
            source     TEXT NOT NULL,
            company    TEXT NOT NULL,
            job_id     TEXT NOT NULL,
            title      TEXT,
            url        TEXT,
            location   TEXT,
            first_seen TEXT NOT NULL,
            PRIMARY KEY (source, company, job_id)
        )
        """
    )
    conn.commit()
    return conn


def fetch_greenhouse(company: str) -> list[dict]:
    """Fetch all open jobs for a Greenhouse-hosted company.

    Greenhouse only ever returns currently-open requisitions on this endpoint.
    A job that appears here is genuinely live.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        print(f"  [greenhouse:{company}] network error: {e}", file=sys.stderr)
        return []
    if r.status_code != 200:
        print(f"  [greenhouse:{company}] HTTP {r.status_code}", file=sys.stderr)
        return []
    try:
        data = r.json()
    except json.JSONDecodeError:
        print(f"  [greenhouse:{company}] invalid JSON", file=sys.stderr)
        return []

    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append({
            "source": "greenhouse",
            "company": company,
            "job_id": str(j.get("id")),
            "title": j.get("title", ""),
            "url": j.get("absolute_url", ""),
            "location": loc,
            "updated_at": j.get("updated_at", ""),
        })
    return jobs


def fetch_lever(company: str) -> list[dict]:
    """Fetch all open jobs for a Lever-hosted company.

    Lever's public postings endpoint also returns only currently-open roles.
    """
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        print(f"  [lever:{company}] network error: {e}", file=sys.stderr)
        return []
    if r.status_code != 200:
        print(f"  [lever:{company}] HTTP {r.status_code}", file=sys.stderr)
        return []
    try:
        data = r.json()
    except json.JSONDecodeError:
        print(f"  [lever:{company}] invalid JSON", file=sys.stderr)
        return []

    jobs = []
    for j in data:
        cats = j.get("categories", {}) or {}
        loc = cats.get("location", "")
        jobs.append({
            "source": "lever",
            "company": company,
            "job_id": j.get("id", ""),
            "title": j.get("text", ""),
            "url": j.get("hostedUrl", ""),
            "location": loc,
            "updated_at": j.get("createdAt", ""),
        })
    return jobs


def matches_filter(job: dict) -> bool:
    """Return True if a job matches our seniority + domain + location filters."""
    title = (job.get("title") or "").lower()
    loc = (job.get("location") or "").lower()

    if not any(k in title for k in SENIORITY_KEYWORDS):
        return False
    if not any(k in title for k in DOMAIN_KEYWORDS):
        return False
    if LOCATION_KEYWORDS and not any(k in loc for k in LOCATION_KEYWORDS):
        return False
    return True


def is_top_match(job: dict) -> bool:
    """Return True if the job mentions any shift keyword — these go to the top."""
    if not SHIFT_KEYWORDS:
        return False
    blob = ((job.get("title") or "") + " " + (job.get("location") or "")).lower()
    return any(k in blob for k in SHIFT_KEYWORDS)


def filter_new(conn: sqlite3.Connection, jobs: list[dict]) -> list[dict]:
    """Return only jobs we have not seen before. Mark new ones as seen."""
    new_jobs = []
    now = datetime.now().isoformat(timespec="seconds")
    for j in jobs:
        cur = conn.execute(
            "SELECT 1 FROM seen WHERE source=? AND company=? AND job_id=?",
            (j["source"], j["company"], j["job_id"]),
        )
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO seen (source, company, job_id, title, url, location, first_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (j["source"], j["company"], j["job_id"], j["title"], j["url"], j["location"], now),
            )
            new_jobs.append(j)
    conn.commit()
    return new_jobs


def write_report(new_jobs: list[dict], all_matched: list[dict]) -> Path:
    """Write a Markdown report. Returns the path to the dated report file."""
    REPORTS_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    top_new = [j for j in new_jobs if is_top_match(j)]
    other_new = [j for j in new_jobs if not is_top_match(j)]

    lines = []
    lines.append(f"# Cybersecurity job monitor — {date_str}")
    lines.append("")
    lines.append(f"_Run at {time_str}. {len(new_jobs)} new matches since last run, "
                 f"{len(all_matched)} total open matches across all monitored companies._")
    lines.append("")

    if top_new:
        lines.append(f"## Top matches (mention shift) — {len(top_new)} new")
        lines.append("")
        for j in top_new:
            lines.append(_format_job(j))
        lines.append("")

    if other_new:
        lines.append(f"## Other new matches — {len(other_new)} new")
        lines.append("")
        for j in other_new:
            lines.append(_format_job(j))
        lines.append("")

    if not new_jobs:
        lines.append("_No new matching jobs since last run. The script is working — "
                     "it's just that no matching reqs were posted in the interval._")
        lines.append("")

    if all_matched:
        lines.append(f"## All currently-open matches across all companies ({len(all_matched)})")
        lines.append("")
        lines.append("These are every matching open req on the monitored ATS endpoints "
                     "right now, including ones you've already seen. Use this as your "
                     "complete pipeline view.")
        lines.append("")
        for j in sorted(all_matched, key=lambda x: (x["company"], x["title"])):
            lines.append(_format_job(j))
        lines.append("")

    body = "\n".join(lines)

    dated_path = REPORTS_DIR / f"jobs_{date_str}.md"
    latest_path = REPORTS_DIR / "latest.md"
    dated_path.write_text(body, encoding="utf-8")
    latest_path.write_text(body, encoding="utf-8")
    return dated_path


def _format_job(j: dict) -> str:
    """Format one job as a Markdown bullet."""
    title = j.get("title") or "(untitled)"
    company = j.get("company") or ""
    loc = j.get("location") or ""
    url = j.get("url") or ""
    source = j.get("source") or ""
    return f"- **{company}** — [{title}]({url}) · {loc} · _via {source}_"


def maybe_send_email(report_path: Path, new_count: int) -> None:
    """Send the report by email if SMTP env vars are configured."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and EMAIL_TO):
        return  # Email not configured — that's fine, the file is on disk.
    if new_count == 0:
        return  # Don't email if there's nothing new.

    msg = EmailMessage()
    msg["Subject"] = f"[Job Monitor] {new_count} new cybersecurity matches"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.set_content(report_path.read_text(encoding="utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"  email sent to {EMAIL_TO}")
    except Exception as e:
        print(f"  email failed: {e}", file=sys.stderr)


def main() -> int:
    print(f"Job monitor starting at {datetime.now().isoformat(timespec='seconds')}")
    print(f"  Monitoring {len(GREENHOUSE_COMPANIES)} Greenhouse companies "
          f"and {len(LEVER_COMPANIES)} Lever companies")

    conn = init_db()

    all_jobs = []
    for c in GREENHOUSE_COMPANIES:
        all_jobs.extend(fetch_greenhouse(c))
        time.sleep(THROTTLE_SECONDS)
    for c in LEVER_COMPANIES:
        all_jobs.extend(fetch_lever(c))
        time.sleep(THROTTLE_SECONDS)

    print(f"  Pulled {len(all_jobs)} total open jobs")

    matched = [j for j in all_jobs if matches_filter(j)]
    print(f"  {len(matched)} match seniority + domain + location filters")

    new_jobs = filter_new(conn, matched)
    print(f"  {len(new_jobs)} are NEW since last run")

    report_path = write_report(new_jobs, matched)
    print(f"  Wrote report: {report_path}")

    maybe_send_email(report_path, len(new_jobs))

    conn.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
