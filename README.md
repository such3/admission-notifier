# Admission Notifier

Scrapes IIT / NIT / IIIT pages for JRF, PhD, M.Tech/MS/MSc admission and fellowship notices,
builds a searchable webpage (`index.html`) and emails a digest (Nodemailer) at 10:00 and 18:00 IST.
Sender: ceynman@gmail.com. Recipient: sucheendra3@gmail.com.

## Quick start (5 minutes)
1. Install Node 20+, Python 3.10+, git and the GitHub CLI (https://cli.github.com).
2. `npm install && pip install -r requirements.txt`
3. **Test the email locally first:** `npm run mail:test`  (sends a short test mail; check the inbox/spam)
4. **Deploy everything:** `./setup.sh`
   It creates the GitHub repo, uploads the Gmail secrets from `.env`, enables Pages, sets `PAGE_URL`
   and starts the first run. After that it runs by itself at 10:00 and 18:00 IST.

`.env` holds the Gmail credentials and is gitignored. Never commit it or share it.

## Manual deploy (without setup.sh)
Push the folder to GitHub (include the hidden `.github` folder), then add Actions secrets
`GMAIL_USER`, `GMAIL_APP_PASSWORD`, optional `MAIL_TO`; set Settings → Pages → Source = GitHub Actions;
add a variable `PAGE_URL`; run *Actions → scrape-and-mail → Run workflow*.

## Notes
- Cron is in UTC (04:30 and 12:30). GitHub may delay scheduled runs by 5 to 30 minutes.
- The first run treats everything currently on the pages as new, so that email is capped at 60 items.
- Emails go out only when something new was found. Set `SEND_EMPTY=1` to always send.
- State lives in `seen.db`, `notifications.json`, `mail_state.json`; the workflow commits them back.
- Edit `sites.yaml` to add institutes or tune keywords. Point each `url` at the real notices page.
- Sites that load notices with JavaScript need Playwright (not included).
- GitHub disables scheduled workflows in repos with no activity for 60 days. Re-enable from the Actions tab if that happens.

## Commands
    python scraper.py --dry-run     # scrape without saving state
    python scraper.py               # scrape + write index.html
    npm run mail:dry                # preview the email (preview-email.html)
    npm run mail:test               # send a test email
    npm run mail                    # send the real digest
Cron alternative: `30 10,18 * * * cd /path/to/folder && python scraper.py && node mailer.js`
