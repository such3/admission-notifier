// Sends one digest email with every notification not yet mailed.
// Env (or .env file): GMAIL_USER, GMAIL_APP_PASSWORD   (required unless DRY_RUN=1)
//   MAIL_TO (default below), MAIL_FROM_NAME, PAGE_URL (link to hosted page)
//   SEND_EMPTY=1 (send even when nothing is new), DRY_RUN=1 (preview only)
// Flags: --test  sends a short test email and exits
import "dotenv/config";
import fs from "fs";
import crypto from "crypto";
import nodemailer from "nodemailer";

const TO = process.env.MAIL_TO || "sucheendra3@gmail.com";
const FROM_NAME = process.env.MAIL_FROM_NAME || "Admission Notifier";
const MAX_ITEMS = 60;
const DRY = process.env.DRY_RUN === "1";
const TEST = process.argv.includes("--test");

const id = (n) =>
  crypto.createHash("sha256").update(`${n.institute}|${n.url}|${n.title}`).digest("hex");
const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const readJson = (p, fallback) => {
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch { return fallback; }
};

if (!DRY && !(process.env.GMAIL_USER && process.env.GMAIL_APP_PASSWORD)) {
  console.error("Set GMAIL_USER and GMAIL_APP_PASSWORD (in .env or the environment), or use DRY_RUN=1.");
  process.exit(1);
}

const transporter = DRY
  ? nodemailer.createTransport({ jsonTransport: true })
  : nodemailer.createTransport({
      service: "gmail",
      auth: { user: process.env.GMAIL_USER, pass: process.env.GMAIL_APP_PASSWORD.replace(/\s+/g, "") },
    });
const from = `"${FROM_NAME}" <${process.env.GMAIL_USER || "notifier@example.com"}>`;

if (TEST) {
  const info = await transporter.sendMail({
    from, to: TO,
    subject: "Admission Notifier: test email",
    text: "If you can read this, Gmail sending works. Real digests go out at 10:00 and 18:00 IST.",
  });
  console.log(DRY ? "DRY RUN test composed." : `Test email sent to ${TO}: ${info.messageId}`);
  process.exit(0);
}

const all = readJson("notifications.json", []);
const state = readJson("mail_state.json", { sent: [] });
const sent = new Set(state.sent);
const fresh = all.filter((n) => !sent.has(id(n)));

if (!fresh.length && process.env.SEND_EMPTY !== "1") {
  console.log("Nothing new to mail.");
  process.exit(0);
}

const shown = fresh.slice(0, MAX_ITEMS);
const extra = fresh.length - shown.length;
const order = ["PhD", "JRF", "Masters", "Project/RA", "Other"];
const groups = Object.fromEntries(order.map((c) => [c, shown.filter((n) => (n.category || "Other") === c)]));

const counts = order.filter((c) => groups[c].length).map((c) => `${c} ${groups[c].length}`).join(", ");
const subject = fresh.length
  ? `Admission alerts: ${fresh.length} new (${counts})`
  : "Admission alerts: nothing new this time";

let html = `<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:640px;margin:auto;color:#1c1c1a">
<h2 style="margin:0 0 4px">Admission &amp; fellowship notifications</h2>
<p style="color:#6b6b66;margin:0 0 16px">${fresh.length} new since the last email.</p>`;
for (const c of order) {
  if (!groups[c].length) continue;
  html += `<h3 style="border-bottom:1px solid #e4e4df;padding-bottom:4px">${esc(c)}</h3>`;
  for (const n of groups[c]) {
    html += `<p style="margin:10px 0"><span style="font-size:12px;color:#6b6b66">[${esc(n.kind)}] ${esc(n.institute)}</span><br>
<a href="${esc(n.url)}" style="color:#2f5bea;font-weight:600;text-decoration:none">${esc(n.title)}</a></p>`;
  }
}
if (extra > 0) html += `<p style="color:#6b6b66">…and ${extra} more. See the full list on the page.</p>`;
if (process.env.PAGE_URL) {
  html += `<p><a href="${esc(process.env.PAGE_URL)}" style="color:#2f5bea">Open the full searchable page</a></p>`;
}
html += `</div>`;

const text =
  shown.map((n) => `[${n.kind}] ${n.institute}\n${n.title}\n${n.url}\n`).join("\n") +
  (extra > 0 ? `\n…and ${extra} more.\n` : "");

const info = await transporter.sendMail({ from, to: TO, subject, text, html });

if (DRY) {
  fs.writeFileSync("preview-email.html", html);
  console.log(`DRY RUN. Subject: ${subject}\nTo: ${TO}\nPreview written to preview-email.html`);
} else {
  // mark everything in `fresh` (including overflow) as mailed so it isn't repeated
  fs.writeFileSync("mail_state.json", JSON.stringify({ sent: [...sent, ...fresh.map(id)] }));
  console.log(`Sent to ${TO}: ${info.messageId}`);
}
