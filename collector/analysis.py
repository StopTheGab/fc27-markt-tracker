"""Signal computation. Pure functions over price series + small state handling in SQLite.

Gap handling: all averages use hourly buckets (mean per hour, then mean over the hours that
actually have data). Missing hours (PC off) therefore neither count as zero nor get extra weight;
changes over 1 h / 24 h are only computed when a data point exists near the reference time.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta

from . import calendar_ctx, db
from .config import ROOT

RULES_PATH = ROOT / "rules.json"


def load_rules() -> dict:
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


R_DEFAULT = {
    "ea_tax": 0.05, "buy_threshold_pct": 15.0, "min_profit_coins": 1000, "min_profit_pct": 3.0,
    "low_confidence_days": 3.0, "min_data_hours_for_signal": 6, "coverage_min_for_high": 0.6,
    "confirm_points": 2, "outlier_step_drop_pct": 30.0, "trend_drop_pct_72h": 10.0,
    "price_floor_margin_pct": 5.0, "crash_mild_median_24h_pct": -8.0,
    "crash_severe_median_24h_pct": -15.0, "crash_buy_share": 0.35, "crash_min_cards": 20,
    "promo_window_hours": 48, "rearm_hours": 2, "tip_max_days": 7, "sell_display_hours": 6,
    "stale_price_hours": 0.75, "trim_pct": 5.0, "crash_breadth_share": 0.6, "crash_breadth_pct": -5.0,
    "release_phase_end": "2026-11-06", "min_buy_price": 700, "cv_max": 0.25, "liq_stop_changes": 4,
    "liq_warn_changes": 7, "promo_min_price": 10000,
}


def rules() -> dict:
    r = dict(R_DEFAULT)
    r.update({k: v for k, v in load_rules().items() if not k.startswith("_")})
    return r


def hourly_buckets(series: list[tuple[datetime, int]]) -> dict[datetime, float]:
    buckets: dict[datetime, list[int]] = {}
    for ts, p in series:
        key = ts.replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(key, []).append(p)
    return {k: sum(v) / len(v) for k, v in buckets.items()}


def value_near(series: list[tuple[datetime, int]], target: datetime, tolerance: timedelta) -> int | None:
    best = None
    for ts, p in series:
        d = abs((ts - target).total_seconds())
        if d <= tolerance.total_seconds() and (best is None or d < best[0]):
            best = (d, p)
    return best[1] if best else None


def pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return round((a - b) / b * 100, 2)


def card_metrics(series: list[tuple[datetime, int]], now: datetime, trim: float = 5.0) -> dict:
    """Metrics from the last 7 days of a card's price series (sorted ascending)."""
    window = [(t, p) for t, p in series if t >= now - timedelta(days=7)]
    if not window:
        return {"price": None, "price_ts": None, "avg_7d": None, "data_days": 0.0, "coverage": 0.0,
                "change_1h_pct": None, "change_24h_pct": None, "trend_72h_pct": None, "recent": []}
    buckets = hourly_buckets(window)
    vals = sorted(buckets.values())
    k = int(len(vals) * trim / 100)
    core = vals[k:len(vals) - k] if len(vals) - 2 * k >= 3 else vals
    avg = sum(core) / len(core)  # trimmed mean (R-ROBUST) of hourly means
    first, last = window[0][0], window[-1][0]
    span_h = max((last - first).total_seconds() / 3600, 0)
    expected_buckets = max(int(span_h) + 1, 1)
    price_ts, price = window[-1]
    p1h = value_near(window, price_ts - timedelta(hours=1), timedelta(minutes=20))
    p24 = value_near(window, price_ts - timedelta(hours=24), timedelta(hours=2))
    # Trend: mean of last 24 h vs mean of 48-72 h ago (hourly buckets)
    recent = [v for k, v in buckets.items() if k >= price_ts - timedelta(hours=24)]
    older = [v for k, v in buckets.items() if price_ts - timedelta(hours=72) <= k < price_ts - timedelta(hours=48)]
    trend = pct(sum(recent) / len(recent), sum(older) / len(older)) if recent and older else None
    last72 = [v for k2, v in buckets.items() if k2 >= price_ts - timedelta(hours=72)]
    day = [p for t, p in window if t >= price_ts - timedelta(hours=24)]
    changes_24h = sum(1 for a, b in zip(day, day[1:]) if a != b)
    cv = (statistics.pstdev(vals) / (sum(vals) / len(vals))) if len(vals) >= 6 else None
    return {
        "price": price,
        "price_ts": price_ts,
        "avg_7d": round(avg),
        "data_days": round(span_h / 24, 2),
        "data_hours": span_h,
        "coverage": round(min(len(buckets) / expected_buckets, 1.0), 2),
        "change_1h_pct": pct(price, p1h),
        "change_24h_pct": pct(price, p24),
        "trend_72h_pct": trend,
        "recent": [p for _, p in window[-4:]],
        "avg_72h": round(sum(last72) / len(last72)) if last72 else None,
        "changes_24h": changes_24h,
        "cv": round(cv, 3) if cv is not None else None,
    }


def fmt(n: float | int | None) -> str:
    if n is None:
        return "–"
    return f"{round(n):,}".replace(",", ".")


def evaluate_buy(card: dict, m: dict, now: datetime, ctx: dict, r: dict) -> dict | None:
    """Return a buy-signal dict or None. `ctx` holds week phase / promo info."""
    price, avg = m["price"], m["avg_7d"]
    if price is None or avg is None or m.get("stale"):
        return None
    if card.get("_available") is False:
        return None
    if m.get("data_hours", 0) < r["min_data_hours_for_signal"]:
        return None
    dev = pct(price, avg)
    if dev is None or dev > -r["buy_threshold_pct"]:
        return None
    if price <= r["min_buy_price"]:
        return None  # R-UNTERGRENZE fallback: at/near the absolute floor
    pmin = card.get("_price_min")
    if pmin and price <= pmin * (1 + r["price_floor_margin_pct"] / 100):
        return None  # at the EA price floor: no room / probably no real discount
    if m.get("data_hours", 0) >= 24 and m.get("changes_24h", 99) < r["liq_stop_changes"]:
        return None  # R-LIQUIDITAET: price hardly moves -> illiquid or stale quote
    target = avg
    release = now.date().isoformat() <= r["release_phase_end"]
    if release and m.get("avg_72h") and m["avg_72h"] < avg:
        target = m["avg_72h"]  # R-RELEASE: prices trend down after launch, aim lower
    profit = round(target * (1 - r["ea_tax"]) - price)
    if profit < r["min_profit_coins"] or profit / price * 100 < r["min_profit_pct"]:
        return None

    reasons = [f"{abs(dev):.1f} % unter 7-Tage-Schnitt ({fmt(price)} statt {fmt(avg)})",
               *([f"Release-Phase: Verkaufsziel = 72-h-Schnitt {fmt(target)} statt 7-Tage-Schnitt"] if target != avg else []),
               f"Erwarteter Gewinn nach 5 % Steuer: {fmt(profit)} Coins ({profit / price * 100:.1f} %)"]
    rules_hit = ["base_15pct", "tax_profit"]
    level = 2  # 2 = hoch, 1 = mittel, 0 = gering

    if m["data_days"] < r["low_confidence_days"]:
        level = 0
        reasons.append(f"Nur {m['data_days']:.1f} Tage Daten – geringe Sicherheit")
        rules_hit.append("low_data")
    if m["coverage"] < r["coverage_min_for_high"]:
        level = min(level, 1)
        reasons.append(f"Datenlücken: nur {round(m['coverage'] * 100)} % der Stunden mit Messwert")
        rules_hit.append("gaps")
    # Confirmation: last N points all below threshold
    recent = m.get("recent") or []
    confirm = recent[-r["confirm_points"]:]
    if len(confirm) < r["confirm_points"] or any(pct(p, avg) > -r["buy_threshold_pct"] for p in confirm):
        level = min(level, 1)
        reasons.append("Noch nicht durch zweiten Messpunkt bestätigt")
        rules_hit.append("unconfirmed")
    if len(recent) >= 2 and pct(recent[-1], recent[-2]) is not None and pct(recent[-1], recent[-2]) <= -r["outlier_step_drop_pct"]:
        level = 0
        reasons.append("Sprung um mehr als 30 % in 15 min – möglicher Ausreißer/Datenfehler")
        rules_hit.append("outlier")
    if m.get("trend_72h_pct") is not None and m["trend_72h_pct"] <= -r["trend_drop_pct_72h"]:
        level = min(level, 1)
        reasons.append(f"Fallender Trend: letzte 24 h {m['trend_72h_pct']:.1f} % unter dem Niveau von vor 2–3 Tagen")
        rules_hit.append("downtrend")
    if release:
        level = min(level, 1) if level == 2 and target != avg else level
        rules_hit.append("release_phase")
    if m.get("cv") is not None and m["cv"] > r["cv_max"]:
        level = min(level, 1)
        reasons.append(f"Sehr schwankender Preis (Variationskoeffizient {m['cv'] * 100:.0f} %)")
        rules_hit.append("volatile")
    if m.get("data_hours", 0) >= 24 and m.get("changes_24h", 99) < r["liq_warn_changes"]:
        level = min(level, 1)
        reasons.append(f"Wenig Preisbewegung ({m['changes_24h']} Änderungen in 24 h) – evtl. schwer handelbar")
        rules_hit.append("low_liquidity")
    phase = ctx.get("phase")
    if phase and phase.get("price_tendency") == "down":
        reasons.append(f"Wochenphase „{phase.get('label')}“: Preise fallen oft noch weiter – evtl. später kaufen")
        rules_hit.append("weekday_cycle")
    elif phase and phase.get("price_tendency") == "up":
        reasons.append(f"Wochenphase „{phase.get('label')}“: Erholung typisch – Kaufzeitpunkt günstig")
        rules_hit.append("weekday_cycle")
    promo = ctx.get("promo")
    if promo and card.get("category") in ("meta", "trading", "promo", None) and price >= r["promo_min_price"]:
        level = min(level, 1)
        reasons.append(f"Promo „{promo['name']}“ in ca. {promo['hours']} h – Meta-Karten fallen dann oft")
        rules_hit.append("promo_ahead")

    return {
        "card_id": card["id"], "name": card.get("name"), "type": "buy",
        "price": price, "avg_7d": avg, "deviation_pct": dev,
        "expected_sell": target, "expected_profit": profit,
        "confidence": ["gering", "mittel", "hoch"][level],
        "reasons": reasons, "rules": rules_hit,
    }


def detect_crash(metrics: dict[str, dict], buy_candidates: int, r: dict) -> dict:
    ch24 = [m["change_24h_pct"] for m in metrics.values() if m.get("change_24h_pct") is not None]
    with_data = [m for m in metrics.values() if m.get("avg_7d")]
    result = {"active": False, "severity": "none", "drop_pct": None, "reason": None}
    if len(ch24) >= r["crash_min_cards"]:
        med = round(statistics.median(ch24), 2)
        result["drop_pct"] = med
        if med <= r["crash_severe_median_24h_pct"]:
            result.update(active=True, severity="severe",
                          reason=f"Median der Watchlist {med:.1f} % in 24 h – starker Marktcrash")
        elif med <= r["crash_mild_median_24h_pct"]:
            result.update(active=True, severity="mild",
                          reason=f"Median der Watchlist {med:.1f} % in 24 h – Markt fällt breit")
    if not result["active"] and len(ch24) >= r["crash_min_cards"]:
        share = sum(1 for x in ch24 if x <= r["crash_breadth_pct"]) / len(ch24)
        if share >= r["crash_breadth_share"]:
            result.update(active=True, severity="mild",
                          reason=f"{share * 100:.0f} % der Karten ≥ {abs(r['crash_breadth_pct']):.0f} % gefallen in 24 h – breiter Rückgang")
    if not result["active"] and len(with_data) >= r["crash_min_cards"] and buy_candidates / len(with_data) >= r["crash_buy_share"]:
        result.update(active=True, severity="mild",
                      reason=f"{buy_candidates} von {len(with_data)} Karten gleichzeitig ≥ 15 % unter Schnitt – marktweiter Rückgang")
    return result


def market_summary(metrics: dict[str, dict]) -> dict:
    c1 = [m["change_1h_pct"] for m in metrics.values() if m.get("change_1h_pct") is not None]
    c24 = [m["change_24h_pct"] for m in metrics.values() if m.get("change_24h_pct") is not None]
    rel = [m["price"] / m["avg_7d"] * 100 for m in metrics.values()
           if m.get("price") and m.get("avg_7d") and not m.get("stale")]
    return {
        "trend_1h_pct": round(statistics.median(c1), 2) if len(c1) >= 5 else None,
        "trend_24h_pct": round(statistics.median(c24), 2) if len(c24) >= 5 else None,
        "index_value": round(statistics.mean(rel), 1) if len(rel) >= 5 else None,
    }


def update_signal_state(con, active: dict[str, dict], now: datetime, r: dict) -> list[dict]:
    """Persist signal state; return the signals that count as NEW (for mail).

    New = card had no signal of this type at the previous run, and the same type did not
    vanish less than `rearm_hours` ago.
    """
    rows = {row["card_id"]: dict(row) for row in con.execute("SELECT * FROM signal_state")}
    new: list[dict] = []
    now_s = db.iso(now)
    for cid, sig in active.items():
        st = rows.get(cid)
        if st and st["type"] == sig["type"]:
            sig["since"] = st["since"]
            continue
        cleared = db.parse(st["last_cleared_at"]) if st else None
        rearmed = (cleared is None or st.get("last_cleared_type") != sig["type"]
                   or now - cleared >= timedelta(hours=r["rearm_hours"]))
        sig["since"] = now_s
        if st and st["type"] and st["type"] != sig["type"]:
            # type switch (e.g. buy -> sell): old one ends now
            pass
        if rearmed:
            new.append(sig)
        con.execute(
            "INSERT INTO signal_state(card_id,type,since) VALUES(?,?,?) "
            "ON CONFLICT(card_id) DO UPDATE SET type=excluded.type, since=excluded.since",
            (cid, sig["type"], now_s))
    for cid, st in rows.items():
        if st["type"] and cid not in active:
            con.execute("UPDATE signal_state SET type=NULL, since=NULL, last_cleared_at=?, last_cleared_type=? "
                        "WHERE card_id=?", (now_s, st["type"], cid))
    con.commit()
    return new


def open_tips(con) -> dict[str, dict]:
    rows = con.execute("SELECT * FROM tips WHERE closed_at IS NULL ORDER BY id").fetchall()
    return {r["card_id"]: dict(r) for r in rows}


def record_new_tips(con, new_buys: list[dict], now: datetime) -> None:
    tips = open_tips(con)
    for s in new_buys:
        if s["card_id"] in tips:
            continue
        con.execute(
            "INSERT INTO tips(card_id,created_at,buy_price,avg_7d,expected_profit,confidence,reasons) "
            "VALUES(?,?,?,?,?,?,?)",
            (s["card_id"], db.iso(now), s["price"], s["avg_7d"], s["expected_profit"], s["confidence"],
             json.dumps(s["reasons"], ensure_ascii=False)))
    con.commit()


def close_tip(con, tip: dict, price: int, now: datetime, r: dict) -> None:
    realized = round(price * (1 - r["ea_tax"]) - tip["buy_price"])
    con.execute("UPDATE tips SET closed_at=?, close_price=?, realized_profit=?, outcome=? WHERE id=?",
                (db.iso(now), price, realized, "hit" if realized > 0 else "miss", tip["id"]))


def hit_rate(con, now: datetime, window_days: int = 14) -> dict | None:
    since = db.iso(now - timedelta(days=window_days))
    rows = con.execute("SELECT outcome FROM tips WHERE closed_at IS NOT NULL AND closed_at>=?", (since,)).fetchall()
    open_n = con.execute("SELECT COUNT(*) FROM tips WHERE closed_at IS NULL").fetchone()[0]
    if not rows and not open_n:
        return None
    hits = sum(1 for r in rows if r["outcome"] == "hit")
    return {"evaluated": len(rows), "hits": hits, "rate": round(hits / len(rows), 2) if rows else None,
            "open": open_n, "window_days": window_days}


def market_text(market: dict, crash: dict, phase: dict | None, n_buy: int, n_sell: int, data_days: float) -> str:
    parts = []
    t24, t1 = market.get("trend_24h_pct"), market.get("trend_1h_pct")
    if crash.get("active"):
        parts.append(f"Achtung Marktcrash: {crash.get('reason')}. Einzelne Kaufsignale sind ausgesetzt, bis der Markt sich stabilisiert.")
    elif t24 is not None:
        word = "steigt" if t24 > 1 else "fällt" if t24 < -1 else "ist seitwärts"
        parts.append(f"Der Markt {word} (Median der Watchlist {t24:+.1f} % in 24 h"
                     + (f", {t1:+.1f} % in der letzten Stunde)." if t1 is not None else ")."))
    elif data_days < 1:
        parts.append(f"Erst {data_days * 24:.0f} h Daten gesammelt – Trends und Signale werden mit der Zeit belastbarer.")
    if phase:
        parts.append(f"Wochenphase: {phase.get('label')} – {phase.get('note')}")
    parts.append(f"Offene Signale: {n_buy} Kauf, {n_sell} Verkauf.")
    return " ".join(p for p in parts if p)


def analyze(con, cards: list[dict], now: datetime) -> dict:
    """Compute metrics + signals for all active cards. Returns dict for export/mail."""
    r = rules()
    cal = calendar_ctx.load_calendar()
    phase = calendar_ctx.week_phase(now, cal)
    promo = calendar_ctx.promo_within(now, r["promo_window_hours"], cal)
    ctx = {"phase": phase, "promo": promo}
    since = db.iso(now - timedelta(days=14))
    metrics: dict[str, dict] = {}
    series_all: dict[str, list] = {}
    for c in cards:
        s = db.price_series(con, c["id"], since)
        series_all[c["id"]] = s
        m = card_metrics(s, now, r["trim_pct"])
        m["stale"] = bool(m["price_ts"] and now - m["price_ts"] > timedelta(hours=r["stale_price_hours"]))
        metrics[c["id"]] = m

    candidates = {}
    for c in cards:
        sig = evaluate_buy(c, metrics[c["id"]], now, ctx, r)
        if sig:
            candidates[c["id"]] = sig
    crash = detect_crash(metrics, len(candidates), r)

    active: dict[str, dict] = {}
    if not crash["active"]:
        active.update(candidates)

    # Sell signals: only for cards with an open buy tip (we do not track holdings otherwise)
    tips = open_tips(con)
    by_id = {c["id"]: c for c in cards}
    prev_state = {row["card_id"]: dict(row) for row in con.execute("SELECT * FROM signal_state")}
    for cid, tip in tips.items():
        m = metrics.get(cid)
        if not m or m["price"] is None or m["avg_7d"] is None or m.get("stale"):
            continue
        created = db.parse(tip["created_at"])
        profit = round(m["price"] * (1 - r["ea_tax"]) - tip["buy_price"])
        if m["price"] >= m["avg_7d"] and profit > 0:  # B3: no "sell" signal that realises a loss
            active[cid] = {
                "card_id": cid, "name": by_id.get(cid, {}).get("name"), "type": "sell",
                "price": m["price"], "avg_7d": m["avg_7d"], "deviation_pct": pct(m["price"], m["avg_7d"]),
                "expected_sell": m["price"], "expected_profit": profit,
                "confidence": "hoch" if m["data_days"] >= r["low_confidence_days"] else "gering",
                "reasons": [f"Preis wieder am/über 7-Tage-Schnitt ({fmt(m['price'])} ≥ {fmt(m['avg_7d'])})",
                            f"Kaufsignal vom {created.astimezone(calendar_ctx.TZ):%d.%m. %H:%M} bei {fmt(tip['buy_price'])}",
                            f"Gewinn nach Steuer: {fmt(profit)} Coins"],
                "rules": ["base_sell_avg"], "buy_price": tip["buy_price"],
            }
            close_tip(con, tip, m["price"], now, r)
        elif now - created > timedelta(days=r["tip_max_days"]):
            close_tip(con, tip, m["price"], now, r)
    # Keep sell signals visible for a while after the tip closed
    for cid, st in prev_state.items():
        if st["type"] == "sell" and cid not in active and cid not in candidates:
            since_dt = db.parse(st["since"])
            m = metrics.get(cid)
            if since_dt and now - since_dt < timedelta(hours=r["sell_display_hours"]) and m and m["price"] and m["avg_7d"] and m["price"] >= m["avg_7d"]:
                last = con.execute("SELECT * FROM tips WHERE card_id=? AND closed_at IS NOT NULL ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
                profit = round(m["price"] * (1 - r["ea_tax"]) - last["buy_price"]) if last else 0
                if last and profit > 0:
                    active[cid] = {
                        "card_id": cid, "name": by_id.get(cid, {}).get("name"), "type": "sell",
                        "price": m["price"], "avg_7d": m["avg_7d"], "deviation_pct": pct(m["price"], m["avg_7d"]),
                        "expected_sell": m["price"], "expected_profit": profit, "confidence": "hoch",
                        "reasons": [f"Preis weiterhin am/über 7-Tage-Schnitt",
                                    f"Gekauft laut Signal bei {fmt(last['buy_price'])} – Gewinn nach Steuer {fmt(profit)}"],
                        "rules": ["base_sell_avg"], "buy_price": last["buy_price"],
                    }
    con.commit()

    new = update_signal_state(con, active, now, r)
    record_new_tips(con, [s for s in active.values() if s["type"] == "buy"], now)

    crash_prev = db.kv_get(con, "crash_active", False)
    crash_new = crash["active"] and not crash_prev
    db.kv_set(con, "crash_active", crash["active"])

    market = market_summary(metrics)
    data_days = max((m["data_days"] for m in metrics.values()), default=0.0)
    n_buy = sum(1 for s in active.values() if s["type"] == "buy")
    n_sell = sum(1 for s in active.values() if s["type"] == "sell")
    return {
        "now": now, "rules": r, "metrics": metrics, "series": series_all, "signals": active,
        "new_signals": new, "crash": crash, "crash_new": crash_new, "suppressed_by_crash": len(candidates) if crash["active"] else 0,
        "phase": phase, "promo": promo, "market": market,
        "events": calendar_ctx.upcoming_events(now, 14, cal),
        "hit_rate": hit_rate(con, now), "data_days": data_days,
        "rule_text": market_text(market, crash, phase, n_buy, n_sell, data_days),
    }
