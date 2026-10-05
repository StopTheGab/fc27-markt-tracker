"""Write the JSON files defined in docs/DATA_CONTRACT.md into export/."""
from __future__ import annotations

import json
import shutil
from datetime import timedelta
from pathlib import Path

from . import db
from .config import EXPORT_DIR, VERSION


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def compress_history(series, now):
    """<= 14 days; points older than 48 h condensed to hourly means."""
    cutoff = now - timedelta(hours=48)
    hourly: dict = {}
    out = []
    for ts, p in series:
        if ts < now - timedelta(days=14):
            continue
        if ts < cutoff:
            key = ts.replace(minute=0, second=0, microsecond=0)
            hourly.setdefault(key, []).append(p)
        else:
            out.append([db.iso(ts), p])
    old = [[db.iso(k), round(sum(v) / len(v))] for k, v in sorted(hourly.items())]
    return old + out


def gaps(con, now, days: int = 7, min_minutes: int = 40, current: str | None = None) -> list[dict]:
    rows = con.execute("SELECT started_at FROM runs WHERE ok=1 AND started_at>=? ORDER BY started_at",
                       (db.iso(now - timedelta(days=days)),)).fetchall()
    stamps = sorted({r["started_at"] for r in rows} | ({current} if current else set()))
    out = []
    prev = None
    for ts in stamps:
        t = db.parse(ts)
        if prev and (t - prev) > timedelta(minutes=min_minutes):
            out.append({"from": db.iso(prev), "to": db.iso(t), "minutes": round((t - prev).total_seconds() / 60)})
        prev = t
    if prev and (now - prev) > timedelta(minutes=min_minutes):
        out.append({"from": db.iso(prev), "to": None, "minutes": round((now - prev).total_seconds() / 60)})
    return out[-20:]


def export_all(con, cards: list[dict], result: dict | None, source_info: dict, run_errors: list[str],
               current_ok: str | None = None, interval: int = 15) -> None:
    now = db.utcnow()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    last_ok = con.execute("SELECT MAX(started_at) FROM runs WHERE ok=1 AND prices>0").fetchone()[0]
    if current_ok and (last_ok is None or current_ok > last_ok):
        last_ok = current_ok  # B6: the running run is not marked ok yet
    metrics = (result or {}).get("metrics", {})
    with_price = sum(1 for m in metrics.values() if m.get("price") is not None and not m.get("stale"))

    _write(EXPORT_DIR / "status.json", {
        "generated_at": db.iso(now),
        "last_successful_fetch": last_ok,
        "source": source_info,
        "collector_version": VERSION,
        "interval_minutes": interval,
        "cards_tracked": len(cards),
        "cards_with_price": with_price,
        "data_days": (result or {}).get("data_days", 0.0),
        "gaps": gaps(con, now, current=current_ok),
        "errors_last_run": run_errors[:20],
    })

    if result is None:
        return

    assessment = db.latest_assessment(con)
    if assessment and now - db.parse(assessment["created_at"]) > timedelta(hours=6):
        assessment_out = {"text": result["rule_text"], "generated_at": db.iso(now), "author": "Regeln",
                          "previous_round": {"text": assessment["text"], "generated_at": assessment["created_at"],
                                             "author": assessment["author"]}}
    elif assessment:
        assessment_out = {"text": assessment["text"], "generated_at": assessment["created_at"],
                          "author": assessment["author"], "rules_text": result["rule_text"]}
    else:
        assessment_out = {"text": result["rule_text"], "generated_at": db.iso(now), "author": "Regeln"}

    _write(EXPORT_DIR / "market.json", {
        "generated_at": db.iso(now),
        **result["market"],
        "crash": result["crash"],
        "suppressed_buy_signals": result["suppressed_by_crash"],
        "week_phase": result["phase"],
        "upcoming_events": result["events"],
        "promo_ahead": result["promo"],
        "assessment": assessment_out,
        "hit_rate": result["hit_rate"],
    })

    out_cards = []
    for c in cards:
        m = metrics.get(c["id"], {})
        sig = result["signals"].get(c["id"])
        out_cards.append({
            "id": c["id"], "ea_id": c.get("ea_id"), "name": c.get("name"), "version": c.get("version"),
            "rating": c.get("rating"), "position": c.get("position"), "league": c.get("league"),
            "club": c.get("club"), "nation": c.get("nation"), "category": c.get("category"),
            "price": m.get("price"), "price_updated_at": db.iso(m.get("price_ts")),
            "available": c.get("_available"), "stale": m.get("stale", False),
            "price_min": c.get("_price_min"), "price_max": c.get("_price_max"),
            "avg_7d": m.get("avg_7d"), "change_1h_pct": m.get("change_1h_pct"),
            "change_24h_pct": m.get("change_24h_pct"),
            "deviation_pct": (round((m["price"] - m["avg_7d"]) / m["avg_7d"] * 100, 2)
                              if m.get("price") and m.get("avg_7d") else None),
            "data_days": m.get("data_days", 0.0), "coverage": m.get("coverage"),
            "signal": sig["type"] if sig else None,
            "watch_reason": c.get("reason"), "image": c.get("image"),
            "link": c.get("futgg_url"),
        })
    _write(EXPORT_DIR / "cards.json", {"generated_at": db.iso(now), "cards": out_cards})

    sigs = sorted(result["signals"].values(), key=lambda s: (s["type"] != "buy", -(s.get("expected_profit") or 0)))
    _write(EXPORT_DIR / "signals.json", {
        "generated_at": db.iso(now),
        "crash_active": result["crash"]["active"],
        "signals": [{k: v for k, v in s.items()} for s in sigs],
    })

    # B5: overwrite in place and delete orphans (no rmtree+mkdir race on Windows)
    hist_dir = EXPORT_DIR / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    wanted = {f"{c['id']}.json" for c in cards}
    for f in hist_dir.glob("*.json"):
        if f.name not in wanted:
            try:
                f.unlink()
            except OSError:
                pass
    for c in cards:
        series = result["series"].get(c["id"]) or []
        _write(hist_dir / f"{c['id']}.json", {
            "card_id": c["id"],
            "price_min": c.get("_price_min"), "price_max": c.get("_price_max"),
            "points": compress_history(series, now),
        })
