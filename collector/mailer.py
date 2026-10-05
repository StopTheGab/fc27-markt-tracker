"""E-mail: signal mail (new signals, bundled per update) and hourly update.

Providers: `resend` (HTTPS API, free tier) or `smtp` (any SMTP server with password/app password).
A failure is logged and recorded in mail_log – it never stops the collector.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

import requests

from . import db
from .analysis import fmt
from .calendar_ctx import TZ
from .config import Settings

log = logging.getLogger("mail")


def _send(settings: Settings, subject: str, text: str, html_body: str) -> tuple[bool, str]:
    p = settings.mail_provider
    if p == "resend":
        if not settings.resend_api_key:
            return False, "RESEND_API_KEY fehlt in .env"
        r = requests.post("https://api.resend.com/emails", timeout=30,
                          headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                          json={"from": settings.mail_from, "to": [settings.mail_to],
                                "subject": subject, "text": text, "html": html_body})
        if r.status_code >= 300:
            return False, f"Resend HTTP {r.status_code}: {r.text[:300]}"
        return True, "ok"
    if p == "smtp":
        if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
            return False, "SMTP_HOST/SMTP_USER/SMTP_PASSWORD fehlen in .env"
        msg = EmailMessage()
        name, addr = parseaddr(settings.mail_from)
        msg["From"] = formataddr((name or "FC27 Tracker", addr if "@" in addr else settings.smtp_user))
        msg["To"] = settings.mail_to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html_body, subtype="html")
        ctx = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, 465, context=ctx, timeout=30) as s:
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
                if settings.smtp_starttls:
                    s.starttls(context=ctx)
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        return True, "ok"
    return False, "Kein Mail-Anbieter konfiguriert (MAIL_PROVIDER=none)"


def send(con, settings: Settings, kind: str, subject: str, text: str, html_body: str) -> bool:
    now = db.utcnow()
    if settings.mail_provider in ("", "none"):
        log.info("Mail übersprungen (kein Anbieter): %s", subject)
        return False
    day_start = now.astimezone(TZ).replace(hour=0, minute=0, second=0)
    sent_today = con.execute("SELECT COUNT(*) FROM mail_log WHERE ok=1 AND sent_at>=?",
                             (db.iso(day_start),)).fetchone()[0]
    if kind != "test" and sent_today >= settings.mail_daily_cap:
        log.warning("Tageslimit %s Mails erreicht – %s nicht gesendet", settings.mail_daily_cap, subject)
        return False
    try:
        ok, info = _send(settings, subject, text, html_body)
    except Exception as e:
        ok, info = False, f"{type(e).__name__}: {e}"
    con.execute("INSERT INTO mail_log(kind,sent_at,subject,ok,error) VALUES(?,?,?,?,?)",
                (kind, db.iso(now), subject, int(ok), None if ok else info[:500]))
    con.commit()
    if ok:
        log.info("Mail gesendet: %s", subject)
    else:
        log.error("Mail fehlgeschlagen (%s): %s", subject, info)
    return ok


def _wrap(title: str, body_html: str, settings: Settings) -> str:
    return (
        "<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;line-height:1.45;"
        "color:#111;max-width:560px\">"
        f"<h2 style=\"font-size:18px;margin:0 0 10px\">{html.escape(title)}</h2>{body_html}"
        f"<p style=\"margin-top:16px\"><a href=\"{settings.dashboard_link}\" "
        "style=\"background:#16a34a;color:#fff;padding:9px 14px;border-radius:6px;text-decoration:none\">"
        "Zum Dashboard</a></p>"
        "<p style=\"color:#666;font-size:12px\">Automatisch vom FC27-Collector. Keine Anlageberatung – "
        "Signale beruhen auf Preisstatistik und können falsch sein.</p></div>"
    )


_KIND = {"buy": "Kauf-Tipp", "sell": "Verkaufs-Tipp", "market": "Marktanalyse", "info": "Video"}


def _signal_lines(s: dict) -> list[str]:
    typ = "KAUFEN" if s["type"] == "buy" else "VERKAUFEN"
    lines = [
        f"{typ}: {s.get('name')} ({s['card_id']})",
        f"Preis {fmt(s['price'])} | 7-Tage-Schnitt {fmt(s['avg_7d'])} | Abweichung {s['deviation_pct']:+.1f} %",
        f"Erwarteter Gewinn nach Steuer: {fmt(s['expected_profit'])} Coins | Sicherheit: {s['confidence']}",
        "Begründung: " + "; ".join(s.get("reasons", [])[:4]),
    ]
    return lines


def signal_mail(con, settings: Settings, result: dict) -> None:
    if not settings.mail_signals_enabled:
        return
    new = result["new_signals"]
    crash_new = result.get("crash_new")
    # New tip videos of the main creator (priority 1) count as a signal; others go into the hourly update
    tips = [p for p in result.get("new_creator_posts", [])
            if p["creator"].get("priority") == 1 and p["kind"] in ("buy", "sell", "market")]
    lives = result.get("live_started", [])
    if not new and not crash_new and not tips and not lives:
        return
    buys = [s for s in new if s["type"] == "buy"]
    sells = [s for s in new if s["type"] == "sell"]
    if lives and not new and not crash_new and not tips:
        subject = f"[FC27 SIGNAL] {lives[0]['creator']['name']} ist LIVE: {lives[0]['title'][:60]}"
    elif tips and not new and not crash_new:
        subject = f"[FC27 SIGNAL] {tips[0]['creator']['name']}: {tips[0]['title'][:70]}"
    elif crash_new and not new:
        subject = f"[FC27 SIGNAL] Marktcrash erkannt ({result['crash'].get('drop_pct') or ''} %)"
    elif len(new) == 1:
        s = new[0]
        subject = f"[FC27 SIGNAL] {'Kauf' if s['type'] == 'buy' else 'Verkauf'}: {s.get('name')} {s['deviation_pct']:+.0f} %"
    else:
        subject = f"[FC27 SIGNAL] {len(buys)} Kauf / {len(sells)} Verkauf"
    blocks = []
    if crash_new:
        blocks.append([f"MARKTCRASH: {result['crash'].get('reason')}",
                       f"{result.get('suppressed_by_crash', 0)} Einzel-Kaufsignale werden deshalb nicht gemeldet."])
    for s in sells + buys:
        blocks.append(_signal_lines(s))
    names = result.get("metrics", {})
    for lv in lives:
        blocks.append([f"LIVE: {lv['creator']['name']} streamt gerade – {lv['title']}", lv["url"],
                       "Tipp: reinschauen und wichtige Aussagen im Chat an Claude weitergeben – dann werden sie mit Datum erfasst."])
    for p in tips:
        lines = [f"NEUES VIDEO von {p['creator']['name']} ({_KIND.get(p['kind'], p['kind'])}): {p['title']}",
                 f"Veröffentlicht: {db.parse(p['published']).astimezone(TZ):%d.%m. %H:%M} – {p['url']}"]
        if p["cards"]:
            lines.append("Erwähnte Karten: " + ", ".join(
                f"{cid} ({fmt((names.get(cid) or {}).get('price'))})" for cid in p["cards"][:6]))
        else:
            lines.append("Karten nicht im Titel/Beschreibung genannt – Tipps stehen im Video.")
        blocks.append(lines)
    text = "\n\n".join("\n".join(b) for b in blocks) + f"\n\nDashboard: {settings.dashboard_link}\n"
    body = "".join("<p style=\"margin:0 0 12px\">" + "<br>".join(html.escape(x) for x in b) + "</p>" for b in blocks)
    send(con, settings, "signal", subject, text, _wrap(subject.replace("[FC27 SIGNAL] ", ""), body, settings))


def hourly_due(con, now) -> str | None:
    key = now.astimezone(TZ).strftime("%Y-%m-%d %H")
    return None if db.kv_get(con, "hourly_last") == key else key


def hourly_mail(con, settings: Settings, result: dict, cards: list[dict]) -> None:
    if not settings.mail_hourly_enabled:
        return
    now = result["now"]
    key = hourly_due(con, now)
    if key is None:
        return
    local = now.astimezone(TZ)
    subject = f"[FC27 Update] {local:%H}:00"
    names = {c["id"]: c.get("name") for c in cards}
    movers = sorted(((cid, m["change_1h_pct"]) for cid, m in result["metrics"].items()
                     if m.get("change_1h_pct") is not None), key=lambda x: abs(x[1]), reverse=True)[:5]
    sigs = sorted(result["signals"].values(), key=lambda s: -(s.get("expected_profit") or 0))
    assessment = db.latest_assessment(con)
    lines = ["Marktlage: " + result["rule_text"]]
    if result.get("phase"):
        lines.append(f"Wochenzyklus: {result['phase'].get('label')} ({result['phase'].get('weekday')})")
    if sigs:
        lines.append("Offene Signale:")
        for s in sigs[:6]:
            lines.append(f"- {'Kauf' if s['type'] == 'buy' else 'Verkauf'} {s.get('name')}: {fmt(s['price'])} "
                         f"({s['deviation_pct']:+.1f} %), Gewinn {fmt(s['expected_profit'])}, {s['confidence']}")
        if len(sigs) > 6:
            lines.append(f"- … und {len(sigs) - 6} weitere im Dashboard")
    else:
        lines.append("Offene Signale: keine")
    if movers:
        lines.append("Größte Bewegungen (1 h):")
        for cid, ch in movers:
            lines.append(f"- {names.get(cid, cid)}: {ch:+.1f} % ({fmt(result['metrics'][cid]['price'])})")
    try:
        posts = con.execute(
            "SELECT p.*, p.creator_id AS cid FROM creator_posts p WHERE first_seen>=? AND published>=? "
            "ORDER BY published DESC", (db.iso(now - timedelta(minutes=65)), db.iso(now - timedelta(hours=48)))).fetchall()
    except Exception:
        posts = []
    if posts:
        lines.append("Neue Creator-Videos:")
        for p in posts[:4]:
            lines.append(f"- {p['cid']}: {p['title'][:80]} ({_KIND.get(p['kind'], p['kind'])}) {p['url']}")
    if assessment and now - db.parse(assessment["created_at"]) < timedelta(hours=6):
        lines.append(f"Einschätzung ({assessment['author']}): {assessment['text']}")
    text = "\n".join(lines) + f"\n\nDashboard: {settings.dashboard_link}\n"
    body = ""
    for ln in lines:
        body += f"<div style=\"margin:{'8px 0 2px' if ln.endswith(':') else '0 0 4px'}\">{html.escape(ln)}</div>"
    if send(con, settings, "hourly", subject, text, _wrap(f"Stunden-Update {local:%H}:00", body, settings)):
        db.kv_set(con, "hourly_last", key)
    else:
        # do not retry every 15 min if provider is broken: mark the hour as handled after a failure too
        db.kv_set(con, "hourly_last", key)
