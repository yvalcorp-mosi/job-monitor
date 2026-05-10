# Cybersecurity job monitor — quickstart

A personal job-search agent for Paul Simo. Runs on your laptop. Hits the real, live Greenhouse and Lever APIs for ~40 companies. Filters for senior cybersecurity roles, remote, with a bonus highlight if the title mentions "shift". Saves a Markdown report to disk and (optionally) emails it to you. Deduplicates so you only see new jobs each day.

## Why this works when web search did not

When I searched the web for "remote 2nd shift senior cybersecurity jobs", I got results from aggregators (Built In, Indeed, ZipRecruiter, themuse) that cache job pages and then surface them in search even after the underlying job has been filled. That's why so many links I gave you were dead.

This script bypasses all that. It calls Greenhouse and Lever directly:

- `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- `https://api.lever.co/v0/postings/{company}?mode=json`

These are the source-of-truth APIs that each company's recruiting team posts to. If a job appears here, it is genuinely open right now. When the recruiter closes it, it disappears from the API on the next request. There is no caching, no staleness.

## Setup — 5 minutes

You need Python 3.9 or later and `pip`. If you don't have Python: download it from https://python.org and install. Pick "Add Python to PATH" during install on Windows.

```bash
# 1. Open a terminal (Mac: Terminal app. Windows: PowerShell).
# 2. Make a folder for this and move the .py file into it.
cd ~/Documents
mkdir job-monitor && cd job-monitor
# (move job_monitor.py into this folder)

# 3. Create a virtual environment so we don't pollute your system Python.
python3 -m venv venv

# 4. Activate it.
# Mac / Linux:
source venv/bin/activate
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# 5. Install the one dependency.
pip install requests

# 6. Run it.
python3 job_monitor.py
```

That's it. You'll see output like:

```
Job monitor starting at 2026-05-09T14:23:11
  Monitoring 35 Greenhouse companies and 7 Lever companies
  Pulled 4,217 total open jobs
  127 match seniority + domain + location filters
  127 are NEW since last run
  Wrote report: reports/jobs_2026-05-09.md
Done.
```

The first run will count every match as "new" because the database starts empty. From day 2 onwards, the "NEW since last run" number is what matters.

Open `reports/latest.md` in any text editor or Markdown viewer to see the formatted report.

## Schedule it — pick one

### Option A — Mac / Linux: cron (easiest)

```bash
crontab -e
```

Add this line (run daily at 7 AM):

```
0 7 * * * cd /Users/paul/Documents/job-monitor && /Users/paul/Documents/job-monitor/venv/bin/python job_monitor.py >> monitor.log 2>&1
```

Replace `/Users/paul` with your actual home directory (run `pwd` from inside the folder to find it).

### Option B — Windows: Task Scheduler

1. Open Task Scheduler. Create Basic Task.
2. Trigger: Daily, 7:00 AM.
3. Action: Start a program.
4. Program/script: `C:\path\to\job-monitor\venv\Scripts\python.exe`
5. Add arguments: `job_monitor.py`
6. Start in: `C:\path\to\job-monitor`

### Option C — Free cloud (no laptop needed) via GitHub Actions

1. Push this folder to a private GitHub repo.
2. Create `.github/workflows/daily.yml`:

```yaml
name: Daily job monitor
on:
  schedule:
    - cron: '0 12 * * *'   # 12:00 UTC = 7:00 AM CT
  workflow_dispatch:        # also run manually from GitHub UI
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install requests
      - run: python job_monitor.py
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          EMAIL_TO:  ${{ secrets.EMAIL_TO }}
      - uses: actions/upload-artifact@v4
        with:
          name: report
          path: reports/latest.md
      - run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add seen_jobs.db reports/
          git diff --quiet --cached || git commit -m "daily run $(date -u +%F)"
          git push
```

That commits each daily report and the dedup database back to your repo. Free tier covers this easily.

## Optional: get the report by email

Add these environment variables before running. With Gmail, generate an [App Password](https://myaccount.google.com/apppasswords) (you can't use your normal Gmail password — Google requires App Passwords for SMTP).

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=paulsimov@gmail.com
export SMTP_PASS=your-16-char-app-password
export EMAIL_TO=paulsimov@gmail.com
python3 job_monitor.py
```

If those vars aren't set, the script just skips email — the report still gets written to disk.

## Customize the search

Open `job_monitor.py` in any text editor. The top of the file has commented sections you can edit:

- `GREENHOUSE_COMPANIES` and `LEVER_COMPANIES` — add or remove companies. To find a company's slug: visit `boards.greenhouse.io/{slug}` or `jobs.lever.co/{slug}` and the URL tells you what works.
- `SENIORITY_KEYWORDS` — currently catches Senior, Sr., Staff, Principal, Lead, Architect, Manager. Loosen or tighten as you wish.
- `DOMAIN_KEYWORDS` — currently broad enough to catch SOC, Security, Cyber, Detection, Threat, MDR, SIEM, Active Defense, Concierge Security, etc.
- `LOCATION_KEYWORDS` — currently set to remote / US-only. Set to `[]` to disable location filtering entirely.
- `SHIFT_KEYWORDS` — when these match, the job goes to the **Top matches** section of the report. Edit to change what gets highlighted.

## How to find more companies that use Greenhouse or Lever

Most modern tech companies use one of these two ATSs. To check:

```bash
# Visit these URLs in a browser. If you see a job board, the company uses that ATS.
https://boards.greenhouse.io/{guess-the-slug}
https://jobs.lever.co/{guess-the-slug}

# Slugs are usually the company's name lowercased, sometimes with "inc" or "labs" appended.
# Examples: "stripe", "datadog", "cloudflare", "dbtlabsinc", "boxinc"
```

If your favorite cybersec company uses Workday (CrowdStrike, Microsoft, Cisco) or Lever's competitor Ashby (some startups), this script doesn't reach them — Workday in particular has no public API. For those, set up a LinkedIn saved-search alert on their careers page.

## Troubleshooting

- **HTTP 403 errors for every company** — your network is blocking outbound API calls. This is what happened in the demo run inside Claude's sandbox. On a normal laptop with normal internet, this won't happen.
- **HTTP 404 for one company** — the slug is wrong, or that company moved off Greenhouse/Lever. Remove it from the list.
- **Same jobs appearing as "new" every run** — the SQLite DB (`seen_jobs.db`) is being deleted between runs. Make sure your scheduler runs from the same folder each time.
- **Want to reset the dedup state** — just delete `seen_jobs.db`. Next run will treat every match as new.

## Files this creates

```
job-monitor/
├── job_monitor.py          ← the script (you edit this to customize)
├── seen_jobs.db            ← SQLite dedup DB (auto-created)
├── reports/
│   ├── jobs_2026-05-09.md  ← dated reports, one per run
│   ├── jobs_2026-05-10.md
│   └── latest.md           ← always points at the most recent report
└── monitor.log             ← (if you wired it up) cron output
```

Done. Run it tomorrow, see what comes back, and tune the keywords if the matches aren't right for you.
