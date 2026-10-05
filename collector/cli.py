"""Helper commands.

python -m collector.cli status                     # Zustand: läuft?, letzter Lauf, Signale, Mails
python -m collector.cli assess --author "Analyse-Runde" --text "…"   # Einschätzung speichern (Dashboard + Stunden-Mail)
python -m collector.cli test-mail                  # Testmail über den konfigurierten Anbieter
python -m collector.cli tips                       # bisherige Tipps und Trefferquote
python -m collector.cli report --hours 2           # kompakte Auswertung für die Analyse-Runde (JSON)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

from . import analysis, db, mailer
from .config import HEARTBEAT_FILE, PID_FILE, Settings
from .main import pid_alive


def cmd_status(_args) -> None:
    con = db.connect()
    pid = PID_FILE.read_text().strip() if PID_FILE.exists() else None
    running = bool(pid and pid.isdigit() and pid_alive(int(pid)))
    print(f"Collector läuft: {'ja (PID ' + pid + ')' if running else 'nein'}")
    if HEARTBEAT_FILE.exists():
        print("Heartbeat:", HEARTBEAT_FILE.read_text().strip())
    for r in con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5"):
        print(f"Lauf {r['id']}: {r['started_at']} ok={r['ok']} Preise={r['prices']} Quelle={r['source']} "
              f"Fehler={len(json.loads(r['errors'] or '[]'))}")
    n = con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    print(f"Preispunkte gesamt: {n}")
    for s in con.execute("SELECT * FROM signal_state WHERE type IS NOT NULL"):
        print(f"Signal {s['type']}: {s['card_id']} seit {s['since']}")
    for m in con.execute("SELECT * FROM mail_log ORDER BY id DESC LIMIT 5"):
        print(f"Mail {m['kind']} {m['sent_at']} ok={m['ok']} {m['subject']} {m['error'] or ''}")


def cmd_assess(args) -> None:
    con = db.connect()
    con.execute("INSERT INTO assessments(created_at,author,text) VALUES(?,?,?)",
                (db.iso(db.utcnow()), args.author, args.text.strip()))
    con.commit()
    print("Einschätzung gespeichert – erscheint nach dem nächsten Lauf im Dashboard.")


def cmd_test_mail(_args) -> None:
    settings = Settings()
    con = db.connect()
    ok = mailer.send(con, settings, "test", "[FC27 Update] Testmail",
                     "Testmail des FC27-Collectors. Wenn du das liest, funktioniert der Versand.\n"
                     f"Dashboard: {settings.dashboard_link}",
                     mailer._wrap("Testmail", "<p>Wenn du das liest, funktioniert der Versand.</p>", settings))
    row = con.execute("SELECT * FROM mail_log ORDER BY id DESC LIMIT 1").fetchone()
    print("Gesendet." if ok else f"Nicht gesendet: {row['error'] if row else 'kein Anbieter konfiguriert'}")
    sys.exit(0 if ok else 1)


def cmd_notify(args) -> None:
    """Push a short note to the user's phone (ntfy). Used by the analysis round for important news."""
    settings = Settings()
    con = db.connect()
    ok = mailer.push(con, settings, "signal" if args.important else "hourly", args.title, args.text)
    print("Push gesendet." if ok else "Push nicht gesendet (NTFY_TOPIC fehlt oder Fehler, siehe Log).")


def cmd_tips(_args) -> None:
    con = db.connect()
    for t in con.execute("SELECT * FROM tips ORDER BY id DESC LIMIT 50"):
        print(dict(t))
    print("Trefferquote:", analysis.hit_rate(con, db.utcnow()))


def cmd_report(args) -> None:
    """Compact JSON for the hourly analysis round (market/news/learning agents)."""
    con = db.connect()
    now = db.utcnow()
    cards = db.active_cards(con)
    since = db.iso(now - timedelta(hours=args.hours))
    out = {"now": db.iso(now), "cards": len(cards), "movers": [], "signals": [], "tips": []}
    for c in cards:
        s = db.price_series(con, c["id"], db.iso(now - timedelta(days=7)))
        m = analysis.card_metrics(s, now)
        recent = [p for t, p in s if t >= db.parse(since)]
        if m["price"] is None:
            continue
        out["movers"].append({"id": c["id"], "name": c.get("name"), "price": m["price"], "avg_7d": m["avg_7d"],
                              "chg_1h": m["change_1h_pct"], "chg_24h": m["change_24h_pct"],
                              "dev": analysis.pct(m["price"], m["avg_7d"]), "days": m["data_days"],
                              "window_min": min(recent) if recent else None, "window_max": max(recent) if recent else None})
    out["movers"].sort(key=lambda x: abs(x["chg_1h"] or 0), reverse=True)
    out["movers"] = out["movers"][: args.top]
    out["signals"] = [dict(r) for r in con.execute("SELECT * FROM signal_state WHERE type IS NOT NULL")]
    out["tips"] = [dict(r) for r in con.execute("SELECT * FROM tips ORDER BY id DESC LIMIT 30")]
    out["hit_rate"] = analysis.hit_rate(con, now)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = sub.add_parser("assess")
    a.add_argument("--text", required=True)
    a.add_argument("--author", default="Analyse-Runde")
    a.set_defaults(fn=cmd_assess)
    sub.add_parser("test-mail").set_defaults(fn=cmd_test_mail)
    sub.add_parser("tips").set_defaults(fn=cmd_tips)
    n = sub.add_parser("notify")
    n.add_argument("--title", required=True)
    n.add_argument("--text", required=True)
    n.add_argument("--important", action="store_true")
    n.set_defaults(fn=cmd_notify)
    r = sub.add_parser("report")
    r.add_argument("--hours", type=int, default=2)
    r.add_argument("--top", type=int, default=40)
    r.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
