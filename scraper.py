#!/usr/bin/env python3
"""Admission/JRF/PhD notification scraper for IITs, NITs, IIITs.

Usage:
  python scraper.py              # scrape once, print + notify new items
  python scraper.py --dry-run    # don't save "seen" state or send notifications
Env (optional, for Telegram alerts): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import argparse, hashlib, json, os, re, sqlite3, sys, time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import requests, yaml
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; AdmissionNotifierBot/1.0; +personal-project)"
DB = "seen.db"
OUT = "notifications.json"
DELAY = 2.0  # seconds between sites; be polite


def load_config(path="sites.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def allowed(url):
    """Respect robots.txt (fail open if robots.txt is unreachable)."""
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(UA, url)
    except Exception:
        return True


def fetch(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.text


def matches(text, include, exclude):
    t = text.lower()
    if any(x in t for x in exclude):
        return False
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t) for k in include)


def extract(site, html, include, exclude):
    soup = BeautifulSoup(html, "lxml")
    items, seen_urls = [], set()
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        # fall back to nearby text for icon-only / "click here" links
        if len(title) < 8 and a.parent:
            title = " ".join(a.parent.get_text(" ", strip=True).split())[:200]
        href = urljoin(site["url"], a["href"])
        if not title or href.startswith(("mailto:", "javascript:", "#")) or href in seen_urls:
            continue
        if matches(title + " " + href, include, exclude):
            seen_urls.add(href)
            items.append({"institute": site["name"], "kind": site["kind"],
                          "title": title[:300], "url": href})
    return items


def init_db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY, first_seen TEXT)")
    return con


def item_id(it):
    return hashlib.sha256(f"{it['institute']}|{it['url']}|{it['title']}".encode()).hexdigest()


def notify_telegram(items):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    for it in items:
        msg = f"[{it['kind']}] {it['institute']}\n{it['title']}\n{it['url']}"
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": msg,
                                "disable_web_page_preview": True}, timeout=15)
            time.sleep(0.5)
        except Exception as e:
            print(f"  telegram error: {e}", file=sys.stderr)


def classify(title):
    t = title.lower()
    if re.search(r"\bjrf\b|junior research fellow", t): return "JRF"
    if re.search(r"ph\.?\s?d|research scholar", t): return "PhD"
    if re.search(r"m\.?\s?tech|m\.?\s?sc\b|\bms\b|master", t): return "Masters"
    if re.search(r"project (associate|assistant|scientist)|research (associate|assistant)", t): return "Project/RA"
    return "Other"


def render_page(items, n_sites, out="index.html", template="template.html"):
    for i in items:
        i.setdefault("category", classify(i["title"]))
    html = open(template, encoding="utf-8").read()
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    meta = json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "sites": n_sites})
    open(out, "w", encoding="utf-8").write(html.replace("__DATA__", data).replace("__META__", meta))
    print(f"Page written: {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    include = [k.lower() for k in cfg["keywords"]]
    exclude = [k.lower() for k in cfg.get("exclude_keywords", [])]
    con = init_db()
    new_items, failed = [], []

    for site in cfg["sites"]:
        print(f"-> {site['name']}")
        try:
            if not allowed(site["url"]):
                print("   blocked by robots.txt, skipping")
                continue
            items = extract(site, fetch(site["url"]), include, exclude)
        except Exception as e:
            failed.append(site["name"])
            print(f"   FAILED: {e}", file=sys.stderr)
            continue
        fresh = [i for i in items if not con.execute(
            "SELECT 1 FROM seen WHERE id=?", (item_id(i),)).fetchone()]
        print(f"   {len(items)} matched, {len(fresh)} new")
        for i in fresh:
            i["found_at"] = datetime.now(timezone.utc).isoformat()
            new_items.append(i)
            if not args.dry_run:
                con.execute("INSERT INTO seen VALUES (?,?)", (item_id(i), i["found_at"]))
        time.sleep(DELAY)

    con.commit()
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except Exception:
        old = []
    for i in new_items:
        i["category"] = classify(i["title"])
    combined = new_items + old
    if new_items and not args.dry_run:
        json.dump(combined, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        notify_telegram(new_items)
    render_page(combined, len(cfg["sites"]))

    print(f"\n{len(new_items)} new notification(s).")
    for i in new_items:
        print(f"  [{i['kind']}] {i['institute']}: {i['title']}\n      {i['url']}")
    if failed:
        print(f"\nFailed sites (check URL / site may block bots): {', '.join(failed)}")


if __name__ == "__main__":
    main()
