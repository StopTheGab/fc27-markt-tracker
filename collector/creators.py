"""Creator tips from public YouTube RSS feeds (official feed, no login, 2 requests per run).

TikTok, Instagram and Discord are not read: they need a login, and automating a user account
breaks their terms. The feed gives title, date and description; cards are matched by name.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

from . import db
from .config import ROOT

log = logging.getLogger("creators")
CONFIG_PATH = ROOT / "creators.json"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
UA = "FC27-Markt-Tracker/1.0 (personal, non-commercial)"
NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/",
      "yt": "http://www.youtube.com/xml/schemas/2015"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS creator_posts (
    video_id TEXT PRIMARY KEY,
    creator_id TEXT NOT NULL,
    published TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,          -- buy | sell | market | info
    cards TEXT NOT NULL          -- JSON list of matched card ids
);
"""

KIND_LABEL = {"buy": "Kauf-Tipp", "sell": "Verkaufs-Tipp", "market": "Marktanalyse", "info": "Sonstiges"}
_BUY = re.compile(r"investier|invest|\bkauf|\bbuy|steigen|\bpump|kaufempfehl", re.I)
_SELL = re.compile(r"verkauf|\bsell|\bdump|crash kommt|before (the )?crash|vor dem crash", re.I)
_MARKET = re.compile(r"markt|market|crash|bubble|weekend league|\bwl\b|sbc", re.I)


def load_config() -> list[dict]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("creators", [])
    except (OSError, ValueError):
        return []


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def classify(title: str, desc: str) -> str:
    t = title or ""
    buy, sell = bool(_BUY.search(t)), bool(_SELL.search(t))
    if buy and sell:
        return "market"
    if buy:
        return "buy"
    if sell:
        return "sell"
    if _MARKET.search(t):
        return "market"
    return "info"


def name_patterns(cards: list[dict]) -> list[tuple[re.Pattern, str]]:
    """Full name always; last name only if >= 5 letters and unique within the watchlist."""
    last_count: dict[str, int] = {}
    for c in cards:
        parts = norm(c.get("name", "")).split()
        if parts:
            last_count[parts[-1]] = last_count.get(parts[-1], 0) + 1
    pats = []
    for c in cards:
        full = norm(c.get("name", "")).strip()
        if not full:
            continue
        keys = {full}
        last = full.split()[-1]
        if len(last) >= 5 and last_count.get(last) == 1:
            keys.add(last)
        for k in keys:
            pats.append((re.compile(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])"), c["id"]))
    return pats


def match_cards(text: str, pats, cards_by_id: dict[str, dict]) -> list[str]:
    t = norm(text)
    found = []
    for pat, cid in pats:
        if pat.search(t) and cid not in found:
            found.append(cid)
    # several versions of the same player: prefer the base gold card, keep max 12
    return found[:12]


def fetch_feed(channel_id: str) -> list[dict]:
    r = requests.get(FEED.format(channel_id), headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", default="", namespaces=NS)
        link = e.find("a:link", NS)
        out.append({
            "video_id": vid,
            "published": e.findtext("a:published", default="", namespaces=NS),
            "title": e.findtext("a:title", default="", namespaces=NS),
            "description": e.findtext("m:group/m:description", default="", namespaces=NS) or "",
            "url": link.get("href") if link is not None else f"https://www.youtube.com/watch?v={vid}",
        })
    return out


def update(con, cards: list[dict], now: datetime) -> list[dict]:
    """Fetch feeds, store new posts. Returns posts first seen now and published within 48 h."""
    con.executescript(SCHEMA)
    creators = load_config()
    pats = name_patterns(cards)
    by_id = {c["id"]: c for c in cards}
    new: list[dict] = []
    for cr in creators:
        cid = cr.get("youtube_channel_id")
        if not cid:
            continue
        try:
            items = fetch_feed(cid)
        except Exception as e:  # never stop the collector
            log.warning("Feed %s nicht abrufbar: %s", cr.get("name"), e)
            continue
        for it in items:
            if not it["video_id"] or con.execute("SELECT 1 FROM creator_posts WHERE video_id=?",
                                                 (it["video_id"],)).fetchone():
                continue
            pub = datetime.fromisoformat(it["published"])
            matched = match_cards(it["title"] + "\n" + it["description"][:2000], pats, by_id)
            kind = classify(it["title"], it["description"])
            con.execute("INSERT INTO creator_posts VALUES(?,?,?,?,?,?,?,?,?)",
                        (it["video_id"], cr["id"], db.iso(pub), db.iso(now), it["title"],
                         it["description"][:600], it["url"], kind, json.dumps(matched)))
            if now - pub <= timedelta(hours=48):
                new.append({"creator": cr, "title": it["title"], "url": it["url"], "published": db.iso(pub),
                            "kind": kind, "cards": matched})
    con.commit()
    return new


def _price_near(con, card_id: str, ts: str) -> int | None:
    r = con.execute("SELECT price FROM prices WHERE card_id=? AND ts>=? AND origin!='suspect' AND price IS NOT NULL "
                    "ORDER BY ts LIMIT 1", (card_id, ts)).fetchone()
    return r["price"] if r else None


def export_data(con, cards: list[dict], metrics: dict, now: datetime, days: int = 14) -> dict:
    con.executescript(SCHEMA)
    creators = {c["id"]: c for c in load_config()}
    names = {c["id"]: c.get("name") for c in cards}
    versions = {c["id"]: c.get("version") for c in cards}
    posts = []
    for r in con.execute("SELECT * FROM creator_posts WHERE published>=? ORDER BY published DESC",
                         (db.iso(now - timedelta(days=days)),)):
        cr = creators.get(r["creator_id"], {})
        cards_out = []
        for cid in json.loads(r["cards"]):
            then = _price_near(con, cid, r["published"])
            cur = (metrics.get(cid) or {}).get("price")
            cards_out.append({"id": cid, "name": names.get(cid), "version": versions.get(cid),
                              "price_at_post": then, "price_now": cur,
                              "change_pct": round((cur - then) / then * 100, 2) if then and cur else None})
        posts.append({
            "video_id": r["video_id"], "creator_id": r["creator_id"], "creator": cr.get("name", r["creator_id"]),
            "priority": cr.get("priority", 9), "published": r["published"], "title": r["title"], "url": r["url"],
            "kind": r["kind"], "kind_label": KIND_LABEL.get(r["kind"], r["kind"]), "cards": cards_out,
            "is_new": now - db.parse(r["published"]) < timedelta(hours=24),
        })
    return {
        "generated_at": db.iso(now),
        "note": "Quelle: öffentliche YouTube-Feeds. Karten werden nur erkannt, wenn sie im Titel/der Beschreibung "
                "stehen – die eigentlichen Tipps stecken oft im Video. Preis 'bei Post' = erster Messpunkt nach Veröffentlichung.",
        "creators": [{k: v for k, v in c.items() if k != "youtube_channel_id"} for c in creators.values()],
        "posts": posts,
    }


# ---------------------------------------------------------------------------------------------
# Discord: ONLY via the user's own bot in the user's own server (official bot API, token in .env).
# Typical setup: follow the creator's announcement channel into an own channel, the bot reads it.
# No user-account automation ("self-bot") - that breaks Discord's terms.
DISCORD_API = "https://discord.com/api/v10"


def update_discord(con, cards: list[dict], env: dict, now: datetime) -> list[dict]:
    token = env.get("DISCORD_BOT_TOKEN", "").strip()
    channels = [c.strip() for c in env.get("DISCORD_CHANNEL_IDS", "").split(",") if c.strip()]
    if not token or not channels:
        return []
    con.executescript(SCHEMA)
    creator = env.get("DISCORD_CREATOR_ID", "fifallstars")
    cfg = {c["id"]: c for c in load_config()}.get(creator, {"id": creator, "name": creator, "priority": 1})
    pats = name_patterns(cards)
    new = []
    headers = {"Authorization": f"Bot {token}",
               "User-Agent": "DiscordBot (https://github.com/StopTheGab/fc27-markt-tracker, 1.0)"}
    for ch in channels:
        last = db.kv_get(con, f"discord_last_{ch}")
        params = {"limit": 50, **({"after": last} if last else {})}
        try:
            r = requests.get(f"{DISCORD_API}/channels/{ch}/messages", headers=headers, params=params, timeout=20)
            if r.status_code == 429:
                log.warning("Discord Rate-Limit, nächster Versuch im nächsten Lauf")
                continue
            r.raise_for_status()
            msgs = sorted(r.json(), key=lambda m: int(m["id"]))
        except Exception as e:
            log.warning("Discord-Kanal %s nicht lesbar: %s", ch, e)
            continue
        for m in msgs:
            text = (m.get("content") or "") + "\n" + "\n".join(
                (e.get("title") or "") + " " + (e.get("description") or "") for e in m.get("embeds", []))
            text = text.strip()
            if not text:
                continue
            pub = datetime.fromisoformat(m["timestamp"])
            guild = m.get("guild_id") or env.get("DISCORD_GUILD_ID", "@me")
            url = f"https://discord.com/channels/{guild}/{ch}/{m['id']}"
            kind = classify(text.split("\n")[0], text)
            if kind == "info":
                kind = classify(text, "")  # Discord posts: keywords can be anywhere
            matched = match_cards(text, pats, {})
            con.execute("INSERT OR IGNORE INTO creator_posts VALUES(?,?,?,?,?,?,?,?,?)",
                        (f"discord:{m['id']}", cfg["id"], db.iso(pub), db.iso(now), text.split("\n")[0][:140],
                         text[:600], url, kind, json.dumps(matched)))
            if now - pub <= timedelta(hours=48):
                new.append({"creator": cfg, "title": "Discord: " + text.split("\n")[0][:100], "url": url,
                            "published": db.iso(pub), "kind": kind, "cards": matched})
        if msgs:
            db.kv_set(con, f"discord_last_{ch}", msgs[-1]["id"])
    con.commit()
    return new


# ---------------------------------------------------------------------------------------------
# Live detection via the official YouTube Data API (optional YOUTUBE_API_KEY, free quota).
# videos.list costs 1 unit per call; we check the newest feed entries (~200 units/day).
# Transcripts of other people's streams are NOT fetched: the API only serves captions to the owner,
# and downloading/transcribing streams breaks YouTube's terms.
def check_live(con, env: dict, now: datetime) -> list[dict]:
    key = env.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return []
    con.executescript(SCHEMA)
    started = []
    for cr in load_config():
        rows = con.execute("SELECT video_id FROM creator_posts WHERE creator_id=? AND video_id NOT LIKE 'discord:%' "
                           "ORDER BY published DESC LIMIT 5", (cr["id"],)).fetchall()
        ids = ",".join(r["video_id"] for r in rows)
        if not ids:
            continue
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=20,
                             params={"part": "snippet,liveStreamingDetails", "id": ids, "key": key})
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:
            log.warning("YouTube-API (%s): %s", cr.get("name"), e)
            continue
        for it in items:
            if it["snippet"].get("liveBroadcastContent") != "live":
                continue
            if db.kv_get(con, f"live_notified_{it['id']}"):
                continue
            db.kv_set(con, f"live_notified_{it['id']}", db.iso(now))
            started.append({"creator": cr, "title": it["snippet"].get("title", ""),
                            "url": f"https://www.youtube.com/watch?v={it['id']}"})
    return started
