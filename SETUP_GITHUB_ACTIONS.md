# GitHub Actions setup — run your job monitor automatically, free, forever

This walks you through wiring up the daily workflow on GitHub's free tier. Total time: about 15 minutes. After this, the script runs every day at 7 AM Central without you doing anything.

## What you'll end up with

- A private GitHub repo containing the script and config
- A workflow that runs every day at 7 AM Central
- Daily Markdown reports committed back to the repo (so you can browse history right on github.com)
- An emailed copy of any new matches, every morning
- Manual "Run now" button on GitHub if you want to trigger it on demand

## What you need before you start

- A free GitHub account. If you don't have one: https://github.com/signup
- Git installed locally, OR willingness to upload files via GitHub's web interface (we'll cover both)
- A Gmail account (or any other email) for the daily report. Optional — you can skip email entirely and still get reports inside the repo.

---

## Step 1 — Generate a Gmail App Password (5 min)

Skip this step if you don't want email reports. The script will still work and save reports inside the repo.

Gmail does not let SMTP scripts log in with your normal password — you need an "App Password". This is a 16-character password that only works for app logins.

1. Go to https://myaccount.google.com/security
2. Make sure **2-Step Verification** is on. App Passwords require it. If it's off, turn it on now (takes 2 minutes — you can use SMS).
3. Go to https://myaccount.google.com/apppasswords
4. Under "App name", type `Job Monitor` and click **Create**.
5. Google shows you a 16-character password like `abcd efgh ijkl mnop`. **Copy it now** — Google won't show it again. The spaces are decorative; you can include them or strip them.
6. Save it somewhere temporarily (we'll paste it into GitHub in Step 4).

If you use Outlook, Yahoo, or another provider, look up "SMTP App Password [your provider]" — most have a similar flow.

---

## Step 2 — Create the GitHub repo (3 min)

1. Go to https://github.com/new
2. Repository name: `job-monitor` (anything works)
3. **Make it Private.** This matters — your dedup database isn't sensitive but there's no reason to make it public.
4. Check "Add a README file" so the repo is initialized.
5. Click **Create repository**.

You now have an empty private repo at `https://github.com/yourusername/job-monitor`.

---

## Step 3 — Upload the files (5 min)

You're going to put 4 files into the repo. Pick whichever upload method you prefer.

### What the final repo should look like

```
job-monitor/
├── .github/
│   └── workflows/
│       └── daily.yml          ← the workflow file
├── job_monitor.py             ← the script
├── requirements.txt           ← Python dependencies
└── .gitignore                 ← files to skip
```

### Method A — Web upload (no Git knowledge needed)

GitHub's web UI lets you drag-and-drop files. **One quirk: the web UI can't create folders directly. To make `.github/workflows/daily.yml`, you have to type the path with slashes when creating the file.**

1. On your repo page, click **Add file** → **Upload files**.
2. Drag `job_monitor.py`, `requirements.txt`, and `.gitignore` into the upload zone.
3. Scroll down, type a commit message like "Add monitor script", click **Commit changes**.
4. Now for the workflow file — click **Add file** → **Create new file** (NOT Upload).
5. In the file name box at the top, type exactly: `.github/workflows/daily.yml`
   - As you type each `/`, GitHub creates a folder.
6. Open `daily.yml` from the files I gave you, copy the entire contents, and paste into the editor.
7. Scroll down, commit message "Add daily workflow", click **Commit changes**.

### Method B — Command line (faster if you know Git)

```bash
cd ~/Documents
git clone https://github.com/yourusername/job-monitor.git
cd job-monitor

# Copy the 4 files from the outputs folder Claude gave you into here:
#   job_monitor.py            → ./
#   requirements.txt          → ./
#   .gitignore                → ./
#   daily.yml                 → ./.github/workflows/daily.yml

mkdir -p .github/workflows
cp /path/to/daily.yml .github/workflows/

git add .
git commit -m "Add monitor script and daily workflow"
git push
```

After either method, your repo file tree should match the diagram above. Click around in GitHub to confirm.

---

## Step 4 — Add your secrets (3 min)

This is where Gmail credentials live. They're encrypted and only the workflow can read them.

1. On your repo page, click **Settings** (top right of the repo nav, not your account settings).
2. In the left sidebar, click **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add each of these one at a time:

| Name        | Value                                             |
|-------------|---------------------------------------------------|
| `SMTP_HOST` | `smtp.gmail.com`                                  |
| `SMTP_PORT` | `587`                                             |
| `SMTP_USER` | your Gmail address, e.g. `paulsimov@gmail.com`    |
| `SMTP_PASS` | the 16-char App Password from Step 1              |
| `EMAIL_TO`  | the address you want reports sent to (can be the same Gmail) |

After adding all five, the secrets page should list 5 items. The values are write-only — GitHub won't show them back to you, you can only update or delete.

If you skipped Step 1 and don't want email: you can skip this entire step. The workflow will still run and commit reports back to the repo.

---

## Step 5 — Run it manually to test (2 min)

1. On your repo page, click the **Actions** tab.
2. If GitHub asks "Get started with GitHub Actions", click **I understand my workflows, go ahead and enable them**.
3. In the left sidebar, click **Daily job monitor**.
4. Click the **Run workflow** dropdown on the right, then **Run workflow** (the green button).
5. Wait ~30 seconds, then refresh. You should see a yellow circle (running) → green check (succeeded).
6. Click the run, then click the `monitor` job, and expand each step to see the output. The "Run job monitor" step should show output like:

   ```
   Job monitor starting at 2026-05-09T12:00:34
     Monitoring 35 Greenhouse companies and 7 Lever companies
     Pulled 4,217 total open jobs
     127 match seniority + domain + location filters
     127 are NEW since last run
     Wrote report: reports/jobs_2026-05-09.md
   Done.
   ```

7. Go back to the **Code** tab. You should see a new commit "Daily run 2026-05-09…" and a new `reports/` folder with `jobs_YYYY-MM-DD.md` and `latest.md` in it.
8. Click `reports/latest.md` to see your first report rendered.
9. If you set up email: check your inbox. You should have a message titled `[Job Monitor] N new cybersecurity matches`.

---

## Step 6 — You're done

The workflow now runs at 7 AM Central every day on its own. You don't need to do anything to keep it going.

### Each morning

- Email arrives if there are new matches.
- `reports/latest.md` in the repo always has the most recent run.
- Browse `reports/` in the repo to see history of every run.

### To change something later

| What | Where |
|------|-------|
| Add or remove monitored companies | Edit `job_monitor.py`, push the change. |
| Change the keyword filters | Same — top of `job_monitor.py`. |
| Change the run time | Edit the cron expression in `.github/workflows/daily.yml`. |
| Pause the workflow | In the Actions tab → Daily job monitor → "..." menu → Disable workflow. |
| Reset the dedup state (re-see all matches) | Delete `seen_jobs.db` from the repo and commit. |

### Cron expression cheat sheet

The format is `minute hour day month day-of-week`, in UTC.

| When you want it to run | Cron expression |
|-------------------------|-----------------|
| 7 AM Houston (CDT, summer) | `0 12 * * *` |
| 7 AM Houston (CST, winter) | `0 13 * * *` |
| 6 PM Houston | `0 23 * * *` |
| Twice daily, 7 AM and 6 PM CDT | `0 12,23 * * *` |
| Weekdays only at 7 AM CDT | `0 12 * * 1-5` |

---

## Troubleshooting

**Workflow fails on the "Run job monitor" step with HTTP 403 errors for every company**
That's the first run — there's nothing weird, this is what you'd see if the script ran on a network that blocks Greenhouse and Lever. GitHub's runners do not block these. If you see this on GitHub, paste the full error output and we'll debug together.

**Workflow fails on "Commit dedup database and reports back to repo"**
Most likely cause: missing `permissions: contents: write` block in the workflow file. The version I gave you has it. If you edited the workflow and removed it, the commit step fails. Add it back.

**No email arrives but the workflow shows green check**
- Check your spam folder first.
- Verify all 5 SMTP secrets are set correctly (Settings → Secrets and variables → Actions). The names are case-sensitive.
- If using Gmail, confirm 2-Step Verification is on and the App Password is the 16-character one (not your normal Gmail password).
- The script intentionally skips email if there are zero new matches. So if today's run found zero new jobs, no email is expected.

**Workflow runs but I get the same jobs as "new" every day**
Means the dedup DB isn't getting committed back. Check that `seen_jobs.db` exists in your repo after a run. If not, the commit step is failing — see above.

**I want to run more than once a day**
Edit the cron in `.github/workflows/daily.yml`. Be aware GitHub's free tier gives 2,000 workflow-minutes/month. This script uses ~1 minute per run, so even running every hour (24/day × 30 days = 720 minutes) fits comfortably.

**I want to stop using GitHub Actions and run it locally instead**
Disable the workflow in the Actions tab and follow the cron / Task Scheduler instructions in `README.md`.

---

## Files in this delivery

```
outputs/
├── job_monitor.py                    ← the script
├── requirements.txt                  ← Python deps
├── .gitignore                        ← Git ignore rules
├── README.md                         ← original local-run README
├── SETUP_GITHUB_ACTIONS.md           ← this file
└── .github/
    └── workflows/
        └── daily.yml                 ← the workflow
```

Drop all of these into your `job-monitor` repo, preserving the folder structure, and you're set.
