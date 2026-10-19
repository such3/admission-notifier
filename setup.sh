#!/usr/bin/env bash
# One-shot setup: creates the GitHub repo, uploads secrets from .env, enables Pages, runs the first job.
# Needs: git + GitHub CLI (https://cli.github.com). Usage: ./setup.sh [repo-name]
# Repo is PUBLIC by default because GitHub Pages on free plans needs it. Your .env is gitignored,
# and secrets live in GitHub Actions secrets, so the password is never in the repo.
# For a private repo: VISIBILITY=private ./setup.sh   (Pages then needs a paid plan)
set -euo pipefail
REPO="${1:-admission-notifier}"
VIS="${VISIBILITY:-public}"

command -v gh >/dev/null  || { echo "Install GitHub CLI first: https://cli.github.com"; exit 1; }
command -v git >/dev/null || { echo "Install git first"; exit 1; }
[ -f .env ] || { echo "Missing .env (copy .env.example and fill it in)"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login

set -a; . ./.env; set +a
: "${GMAIL_USER:?GMAIL_USER missing in .env}" "${GMAIL_APP_PASSWORD:?GMAIL_APP_PASSWORD missing in .env}"

[ -d .git ] || git init -b main
git check-ignore -q .env || { echo ".env is not gitignored, aborting"; exit 1; }
git add -A
git commit -m "Initial commit" || true

gh repo create "$REPO" "--$VIS" --source=. --push
gh secret set GMAIL_USER --body "$GMAIL_USER"
gh secret set GMAIL_APP_PASSWORD --body "$GMAIL_APP_PASSWORD"
[ -n "${MAIL_TO:-}" ] && gh secret set MAIL_TO --body "$MAIL_TO"

OWNER="$(gh api user -q .login)"
gh api -X POST "repos/$OWNER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || true
gh variable set PAGE_URL --body "https://$OWNER.github.io/$REPO/"

sleep 5
gh workflow run notify.yml
echo
echo "Done. Watch the first run:  gh run watch"
echo "Page (live after first run): https://$OWNER.github.io/$REPO/"
