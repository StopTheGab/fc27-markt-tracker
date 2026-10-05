"""FC27 collector: every 15 minutes fetch prices, analyse, export JSON, push to `data`, send mails.

Run:  python -m collector.main            (loop, normally started via scripts/start.ps1)
      python -m collector.main --once     (single run)
Stop: create data/STOP (scripts/stop.ps1 does this) – the loop exits cleanly within seconds.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import sys
import time
import traceback
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from . import analysis, db, export, mailer, publish
from .config import (HEARTBEAT_FILE, LOG_DIR, PID_FILE, STOP_FILE, WATCHLIST_PATH, Settings, ensure_dirs)

log = logging.getLogger("collector")
STALE_SOURCE_HOURS = 6  # source timestamp older than this -> price not stored (B7)


def setup_logging(console: bool) -> None:
    ensure_dirs()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(LOG_DIR / "collector.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if console and sys.stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)


def pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return code.value == 259  # STILL_ACTIVE


def load_watchlist() -> list[dict]:
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        return [c for c in data.get("cards", []) if c.get("id")]
    except (OSError, ValueError) as e:
        log.error("watchlist.json nicht lesbar: %s", e)
        return []


def get_source(settings: Settings):
    try:
        from . import sources
        return sources.get_source(settings.env)
    except Exception as e:
        log.error("Quellenmodul fehlt/defekt: %s", e)
        return None


def run_once(settings: Settings) -> None:
    started = db.utcnow()
    con = db.connect()
    errors: list[str] = []
    run_id = con.execute("INSERT INTO runs(started_at) VALUES(?)", (db.iso(started),)).lastrowid
    con.commit()
    n_prices = 0
    source_info = {"id": None, "name": None, "url": None, "ok": False, "message": ""}
    result = None
    try:
        wl = load_watchlist()
        if wl:
            db.sync_watchlist(con, wl)
        cards = db.active_cards(con)
        if not cards:
            source_info["message"] = "Watchlist leer oder fehlt (watchlist.json)."
        src = get_source(settings)
        if src is None:
            source_info["message"] = source_info["message"] or "Keine regelkonforme Preisquelle verfügbar – siehe STATUS.md."
        else:
            source_info.update(id=src.id, name=src.name, url=src.url)
            ok, msg = True, "ok"
            last_ok = con.execute("SELECT ok FROM runs WHERE id<? ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
            if last_ok is None or not last_ok["ok"]:
                ok, msg = src.check()
            source_info.update(ok=ok, message=msg)
            if ok and cards:
                quotes = src.fetch_prices(cards)
                for q in quotes:
                    if q.error:
                        errors.append(f"{q.card_id}: {q.error}")
                    ts = db.iso(q.fetched_at.replace(second=0))
                    stale_src = bool(q.source_updated_at and
                                     db.utcnow() - q.source_updated_at > timedelta(hours=STALE_SOURCE_HOURS))
                    if q.price is not None and stale_src:
                        # B7: source has not refreshed this card for hours -> not a current market price
                        errors.append(f"{q.card_id}: Quellpreis veraltet (Stand {db.iso(q.source_updated_at)})")
                    elif q.price is not None:
                        if db.insert_price(con, q.card_id, ts, int(q.price), "live", src.id, db.iso(q.source_updated_at)):
                            n_prices += 1
                    sets, vals = [], []
                    if q.price_min is not None:
                        sets.append("price_min=?"); vals.append(q.price_min)
                    if q.price_max is not None:
                        sets.append("price_max=?"); vals.append(q.price_max)
                    if q.available is not None:
                        sets.append("available=?"); vals.append(int(q.available))
                    if sets:
                        con.execute(f"UPDATE cards SET {','.join(sets)} WHERE card_id=?", (*vals, q.card_id))
                con.commit()
                if n_prices == 0:
                    source_info.update(ok=False, message=f"Quelle lieferte keine Preise ({len(errors)} Fehler)")
                # Import price history for cards that do not have it yet (a few per run)
                todo = [c for c in cards if not c.get("_history_imported_at")][: settings.history_imports_per_run]
                for c in todo:
                    try:
                        pts = src.fetch_history(c) or []
                        for ts, p in pts:
                            db.insert_price(con, c["id"], db.iso(ts), int(p), "history", src.id)
                        con.execute("UPDATE cards SET history_imported_at=? WHERE card_id=?",
                                    (db.iso(db.utcnow()), c["id"]))
                        con.commit()
                    except Exception as e:
                        errors.append(f"Historie {c['id']}: {e}")
                cards = db.active_cards(con)
        if cards:
            result = analysis.analyze(con, cards, db.utcnow())
        # B4: mails first - signal state is already persisted, a later export error must not swallow them
        if result is not None:
            try:
                if n_prices > 0:
                    mailer.signal_mail(con, settings, result)
            except Exception as e:
                log.exception("Signal-Mail fehlgeschlagen")
                errors.append(f"Signal-Mail: {e}")
            try:
                mailer.hourly_mail(con, settings, result, cards)
            except Exception as e:
                log.exception("Stunden-Mail fehlgeschlagen")
                errors.append(f"Stunden-Mail: {e}")
        current_ok = db.iso(started) if n_prices > 0 else None
        export.export_all(con, cards, result, source_info, errors, current_ok=current_ok,
                          interval=settings.interval_minutes)
        ok_pub, msg_pub = publish.publish(settings, f"data {db.iso(db.utcnow())}")
        if not ok_pub:
            errors.append(msg_pub)
            log.error(msg_pub)
    except Exception as e:
        log.error("Lauf fehlgeschlagen: %s\n%s", e, traceback.format_exc())
        errors.append(f"Lauf fehlgeschlagen: {e}")
    finally:
        con.execute("UPDATE runs SET finished_at=?, ok=?, source=?, cards=?, prices=?, errors=? WHERE id=?",
                    (db.iso(db.utcnow()), int(n_prices > 0), source_info.get("id"),
                     len(db.active_cards(con)), n_prices, json.dumps(errors[:50], ensure_ascii=False), run_id))
        con.commit()
        con.close()
        log.info("Lauf fertig: %s Preise, %s Fehler, Quelle=%s (%s)", n_prices, len(errors),
                 source_info.get("id"), source_info.get("message"))


def next_slot(now, minutes: int):
    base = now.replace(second=0, microsecond=0)
    m = (base.minute // minutes + 1) * minutes
    return base.replace(minute=0) + timedelta(minutes=m)


def loop(settings: Settings) -> None:
    if PID_FILE.exists():
        try:
            old = int(PID_FILE.read_text().strip())
            if old != os.getpid() and pid_alive(old):
                log.warning("Collector läuft bereits (PID %s) – beende mich.", old)
                return
        except ValueError:
            pass
    PID_FILE.write_text(str(os.getpid()))
    if STOP_FILE.exists():
        STOP_FILE.unlink()
    log.info("Collector gestartet (PID %s, Intervall %s min)", os.getpid(), settings.interval_minutes)
    try:
        last = None
        try:
            con = db.connect()
            last = con.execute("SELECT MAX(started_at) FROM runs").fetchone()[0]
            con.close()
            last_dt = db.parse(last)
        except Exception:
            log.exception("Datenbank beim Start nicht lesbar – versuche es im nächsten Takt")
            last_dt = db.utcnow()
        if last_dt is None or db.utcnow() - last_dt > timedelta(minutes=settings.interval_minutes - 1):
            if last_dt:
                log.info("Letzter Lauf %s – Lücke von %.0f min, mache sofort weiter.", last,
                         (db.utcnow() - last_dt).total_seconds() / 60)
            try:
                run_once(Settings())
            except Exception:
                log.exception("Nachhol-Lauf fehlgeschlagen – weiter im normalen Takt")
        while True:
            target = next_slot(db.utcnow(), settings.interval_minutes)
            while db.utcnow() < target:
                if STOP_FILE.exists():
                    log.info("Stopp-Datei gefunden – Collector beendet sich sauber.")
                    return
                try:
                    HEARTBEAT_FILE.write_text(db.iso(db.utcnow()) + f" next={db.iso(target)}")
                except OSError:
                    pass  # e.g. file briefly locked by a virus scanner
                time.sleep(5)
            try:
                run_once(Settings())  # re-read .env each run
            except Exception:
                log.exception("Unerwarteter Fehler im Lauf – weiter mit nächstem Intervall")
    finally:
        try:
            if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
            if STOP_FILE.exists():
                STOP_FILE.unlink()
        except OSError:
            pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    setup_logging(console=True)
    settings = Settings()
    if args.once:
        run_once(settings)
    else:
        loop(settings)


if __name__ == "__main__":
    main()
