"""Context from market_calendar.json: current week phase and upcoming events (Europe/Berlin)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import CALENDAR_PATH, TZ_LOCAL

TZ = ZoneInfo(TZ_LOCAL)
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def load_calendar() -> dict:
    try:
        return json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _minutes(weekday: int, hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    return (weekday - 1) * 1440 + h * 60 + m


def week_phase(now_utc: datetime, cal: dict | None = None) -> dict | None:
    cal = cal if cal is not None else load_calendar()
    phases = cal.get("week_phases") or []
    local = now_utc.astimezone(TZ)
    cur = local.isoweekday() * 1440 - 1440 + local.hour * 60 + local.minute
    for p in phases:
        try:
            start = _minutes(int(p["from"]["weekday"]), p["from"]["time"])
            end = _minutes(int(p["to"]["weekday"]), p["to"]["time"])
        except (KeyError, ValueError, TypeError):
            continue
        inside = start <= cur < end if start <= end else (cur >= start or cur < end)
        if inside:
            return {
                "id": p.get("id"),
                "label": p.get("label"),
                "note": p.get("note"),
                "price_tendency": p.get("tendency"),
                "weekday": WEEKDAYS_DE[local.isoweekday() - 1],
            }
    return None


def upcoming_events(now_utc: datetime, days: int = 14, cal: dict | None = None) -> list[dict]:
    cal = cal if cal is not None else load_calendar()
    today = now_utc.astimezone(TZ).date()
    out = []
    for e in cal.get("events") or []:
        try:
            d = date.fromisoformat(str(e.get("date"))[:10])
        except ValueError:
            continue
        if today <= d <= today + timedelta(days=days):
            out.append({
                "date": d.isoformat(),
                "name": e.get("name"),
                "type": e.get("type"),
                "certainty": e.get("certainty"),
                "impact": e.get("impact") or e.get("expected_effect"),
            })
    out.sort(key=lambda x: x["date"])
    return out


def promo_within(now_utc: datetime, hours: int, cal: dict | None = None) -> dict | None:
    """Next promo/event of type promo starting within `hours` (date-level precision, 19:00 local assumed)."""
    cal = cal if cal is not None else load_calendar()
    local_now = now_utc.astimezone(TZ)
    best = None
    candidates = [e for e in (cal.get("events") or []) if e.get("type") == "promo"
                  and "TOTW" not in str(e.get("name")).upper()]  # weekly TOTW is no promo start
    candidates += [{"date": p.get("start"), "name": p.get("name"), "certainty": p.get("certainty")}
                   for p in (cal.get("promos") or []) if p.get("status") == "erwartet"]
    for e in candidates:
        try:
            d = date.fromisoformat(str(e.get("date"))[:10])
        except ValueError:
            continue
        start = datetime(d.year, d.month, d.day, 19, 0, tzinfo=TZ)  # promo start Fr 19:00 MESZ
        delta = (start - local_now).total_seconds() / 3600
        if 0 <= delta <= hours and (best is None or delta < best[0]):
            best = (delta, e)
    if best:
        return {"name": best[1].get("name"), "hours": round(best[0]), "certainty": best[1].get("certainty")}
    return None
