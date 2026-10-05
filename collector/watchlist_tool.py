"""Watchlist helper for the FC27 market tracker.

Usage:
    python -m collector.watchlist_tool validate watchlist.json [--today YYYY-MM-DD] [--max-age 14]
    python -m collector.watchlist_tool stats watchlist.json

`validate` checks schema, duplicate ids/cards, source dates (<= max-age days old,
not in the future), card count (100-200) and counts cards without id.
Exit code 0 = valid, 1 = errors found, 2 = file unreadable.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

CATEGORIES = {"meta", "promo", "trading", "fodder"}
ID_RE = re.compile(r"^27-\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_CARDS, MAX_CARDS = 100, 200

REQUIRED_TOP = {"generated_at": str, "game": str, "platform": str, "method": str, "cards": list}
# field -> allowed types (None allowed where the spec permits "unknown")
CARD_FIELDS = {
    "id": (str, type(None)),
    "ea_id": (int, type(None)),
    "resource_id": (int, type(None)),
    "name": (str,),
    "version": (str, type(None)),
    "rating": (int, type(None)),
    "position": (str, type(None)),
    "club": (str, type(None)),
    "league": (str, type(None)),
    "nation": (str, type(None)),
    "futgg_url": (str, type(None)),
    "category": (str,),
    "reason": (str,),
    "sources": (list,),
}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate(data: dict, today: dt.date, max_age: int) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, typ in REQUIRED_TOP.items():
        if not isinstance(data.get(key), typ):
            errors.append(f"top-level '{key}' missing or not {typ.__name__}")
    if data.get("game") not in (None, "FC27"):
        errors.append(f"game must be 'FC27', got {data.get('game')!r}")
    if data.get("platform") not in (None, "ps"):
        errors.append(f"platform must be 'ps', got {data.get('platform')!r}")
    cards = data.get("cards") or []
    oldest = today - dt.timedelta(days=max_age)

    ids = collections.Counter()
    keys = collections.Counter()
    per_cat = collections.Counter()
    no_id = 0
    src_dates: list[dt.date] = []

    for i, c in enumerate(cards):
        tag = f"card[{i}] {c.get('name', '?')!s}"
        if not isinstance(c, dict):
            errors.append(f"card[{i}] is not an object")
            continue
        for f, types in CARD_FIELDS.items():
            if f not in c:
                errors.append(f"{tag}: missing field '{f}'")
            elif not isinstance(c[f], types) or isinstance(c[f], bool):
                errors.append(f"{tag}: field '{f}' has wrong type {type(c[f]).__name__}")
        cat = c.get("category")
        if cat not in CATEGORIES:
            errors.append(f"{tag}: invalid category {cat!r}")
        else:
            per_cat[cat] += 1
        cid = c.get("id")
        if cid is None:
            no_id += 1
        else:
            if not isinstance(cid, str) or not ID_RE.match(cid):
                errors.append(f"{tag}: id {cid!r} not in format '27-<resourceId>'")
            else:
                ids[cid] += 1
                rid = c.get("resource_id")
                if isinstance(rid, int) and cid != f"27-{rid}":
                    errors.append(f"{tag}: id {cid} does not match resource_id {rid}")
                url = c.get("futgg_url")
                if isinstance(url, str) and f"/{cid}/" not in url:
                    errors.append(f"{tag}: futgg_url does not contain {cid}")
        rating = c.get("rating")
        if isinstance(rating, int) and not 40 <= rating <= 99:
            errors.append(f"{tag}: rating {rating} out of range")
        keys[(str(c.get("name", "")).lower(), str(c.get("version", "")).lower(), c.get("rating"))] += 1
        if not str(c.get("reason", "")).strip():
            errors.append(f"{tag}: empty reason")
        srcs = c.get("sources") or []
        if not srcs:
            errors.append(f"{tag}: no sources")
        for s in srcs:
            if not isinstance(s, dict) or not all(k in s for k in ("title", "url", "date")):
                errors.append(f"{tag}: source needs title/url/date: {s!r}")
                continue
            d = s.get("date")
            if not isinstance(d, str) or not DATE_RE.match(d):
                errors.append(f"{tag}: source date {d!r} not YYYY-MM-DD")
                continue
            try:
                dd = dt.date.fromisoformat(d)
            except ValueError:
                errors.append(f"{tag}: invalid source date {d!r}")
                continue
            src_dates.append(dd)
            if dd < oldest:
                errors.append(f"{tag}: source '{s.get('title')}' dated {d} older than {max_age} days")
            if dd > today:
                errors.append(f"{tag}: source dated {d} is in the future")

    for cid, n in ids.items():
        if n > 1:
            errors.append(f"duplicate id {cid} ({n}x)")
    for k, n in keys.items():
        if n > 1:
            errors.append(f"duplicate card name/version/rating {k} ({n}x)")
    if not MIN_CARDS <= len(cards) <= MAX_CARDS:
        errors.append(f"card count {len(cards)} outside {MIN_CARDS}-{MAX_CARDS}")
    if no_id:
        warnings.append(f"{no_id} card(s) without id (need manual follow-up)")

    stats = {
        "cards": len(cards),
        "per_category": dict(sorted(per_cat.items())),
        "without_id": no_id,
        "unique_sources": len({s.get("url") for c in cards if isinstance(c, dict) for s in (c.get("sources") or []) if isinstance(s, dict)}),
        "source_date_range": [min(src_dates).isoformat(), max(src_dates).isoformat()] if src_dates else None,
    }
    return errors, warnings, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m collector.watchlist_tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "stats"):
        p = sub.add_parser(name)
        p.add_argument("path")
        p.add_argument("--today", default=dt.date.today().isoformat())
        p.add_argument("--max-age", type=int, default=14)
    args = ap.parse_args(argv)
    try:
        data = load(args.path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {args.path}: {exc}")
        return 2
    today = dt.date.fromisoformat(args.today)
    errors, warnings, stats = validate(data, today, args.max_age)
    print(json.dumps(stats, ensure_ascii=False))
    if args.cmd == "stats":
        return 0
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors[:100]:
        print(f"ERROR: {e}")
    if len(errors) > 100:
        print(f"... {len(errors) - 100} more errors")
    print("RESULT: " + ("OK" if not errors else f"INVALID ({len(errors)} errors)"))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
