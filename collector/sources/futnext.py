"""FUTNext (www.futnext.com) - oeffentliche Spielerseiten, serverseitig gerendert.

Gepruefte Lage (2026-10-05, siehe README.md):
- robots.txt: `User-Agent: *  Allow: /`, gesperrt u. a. /account, /login, /auth/, `/*?_rsc=`.
  Wir rufen nur `/players/<slug>/<resourceId>` ohne Query-String ab.
- Terms (/legal/terms): kein Verbot automatisierten Zugriffs; Lizenz "personal, non-commercial
  transitory use"; verboten u. a. Kopieren/"Mirroring" auf anderen Servern und Ueberlasten.
  -> Nur privat nutzen, Daten nicht oeffentlich weiterverbreiten, sparsam abfragen.
- Preise: im eingebetteten Next.js-Flight-Datenstrom je Karten-Objekt
  `"price":{"averagePrice":..,"cheapestPrice":..,"timeStamp":<ms>}`, Plattform-Default "ps"
  (Konsole = PS/XB). Die Quelle aktualisiert etwa stuendlich (timeStamp auf voller Stunde).
- Eine Spielerseite enthaelt alle Versionen des Spielers -> ein Request deckt mehrere Karten ab.
- Keine Preis-Historie im HTML (wird clientseitig nachgeladen) -> fetch_history() == [].
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .base import (BlockedError, PoliteSession, PriceQuote, PriceSource, card_id_of,
                   resource_id, utcnow)

BASE = "https://www.futnext.com"
_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
_PRICE_KEY = '"price":{"averagePrice"'
_BS = chr(92)
CACHE_FILE = Path(__file__).with_name(".cache") / "futnext.json"


def _slug(name: str | None) -> str:
    if not name:
        return "player"
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "player"


def _flight(html: str) -> str:
    out = []
    for c in _PUSH_RE.findall(html):
        try:
            out.append(json.loads(c))
        except ValueError:
            pass
    return "".join(out)


def _enclosing_starts(text: str, key: str) -> list[int]:
    """Startindex des JSON-Objekts, das jeden Treffer von `key` direkt enthaelt."""
    targets = [m.start() for m in re.finditer(re.escape(key), text)]
    res: list[int] = []
    stack: list[int] = []
    ins = esc = False
    ti = 0
    for i, ch in enumerate(text):
        while ti < len(targets) and i == targets[ti]:
            if stack:
                res.append(stack[-1])
            ti += 1
        if ti >= len(targets):
            break
        if ins:
            if esc:
                esc = False
            elif ch == _BS:
                esc = True
            elif ch == '"':
                ins = False
            continue
        if ch == '"':
            ins = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            stack.pop()
    return res


def parse_player_page(html: str) -> dict[int, dict]:
    """resourceId -> {'price', 'avg', 'ts', 'rating', 'name', 'rarity'} fuer alle Karten der Seite."""
    flight = _flight(html)
    dec = json.JSONDecoder()
    result: dict[int, dict] = {}
    for st in _enclosing_starts(flight, _PRICE_KEY):
        try:
            obj, _ = dec.raw_decode(flight, st)
        except ValueError:
            continue
        rid, pr = obj.get("id"), obj.get("price")
        if not isinstance(rid, int) or not isinstance(pr, dict):
            continue
        ts = pr.get("timeStamp")
        rar = obj.get("rarity")
        result[rid] = {
            "price": pr.get("cheapestPrice"),
            "avg": pr.get("averagePrice"),
            "ts": ts if isinstance(ts, (int, float)) else None,
            "rating": obj.get("rating"),
            "name": (obj.get("definition") or {}).get("lastName"),
            "rarity": rar.get("name") if isinstance(rar, dict) else None,
        }
    return result


def page_platform(html: str) -> str | None:
    m = re.search(r'\\?"platform\\?":\\?"(ps|pc|xbox|xb)\\?"', html)
    return m.group(1) if m else None


class FutNextSource(PriceSource):
    id = "futnext"
    name = "FUTNext (öffentliche Spielerseiten)"
    url = BASE

    def __init__(self, env: dict | None = None):
        env = env or {}
        self.http = PoliteSession(min_delay=float(env.get("FUTNEXT_DELAY_S", "3.2")))
        # Optional (FUTNEXT_SMART_SKIP=1): Karte erst neu laden, wenn ein neuer Stunden-Stand faellig ist.
        # Standard aus, weil sich Preise auch innerhalb der Stunde aendern (timeStamp = Stunden-Bucket).
        self.smart_skip = env.get("FUTNEXT_SMART_SKIP", "0") == "1"
        self.min_refetch = timedelta(minutes=float(env.get("FUTNEXT_MIN_REFETCH_MIN", "5")))
        self.budget_s = float(env.get("FUTNEXT_RUN_BUDGET_S", "720"))   # 12 min pro Lauf
        self.use_disk_cache = env.get("FUTNEXT_DISK_CACHE", "1") != "0"
        self._cache: dict[str, dict] = self._load_cache()

    # ---------- Cache ----------
    def _load_cache(self) -> dict:
        if not self.use_disk_cache:
            return {}
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_cache(self) -> None:
        if not self.use_disk_cache:
            return
        try:
            CACHE_FILE.parent.mkdir(exist_ok=True)
            CACHE_FILE.write_text(json.dumps(self._cache), encoding="utf-8")
        except OSError:
            pass

    def _cache_fresh(self, rid: int, now: datetime) -> dict | None:
        e = self._cache.get(str(rid))
        if not e:
            return None
        fetched = datetime.fromisoformat(e["fetched_at"])
        age = now - fetched
        if age < self.min_refetch:
            return e
        if self.smart_skip and e.get("ts"):
            src = datetime.fromtimestamp(e["ts"] / 1000, timezone.utc)
            # naechster Quellen-Stand erwartet ca. 1 h nach dem letzten (+5 min Puffer)
            if now < src + timedelta(minutes=65) and age < timedelta(minutes=60):
                return e
        return None

    # ---------- Netz ----------
    def _fetch_page(self, rid: int, name: str | None) -> dict[int, dict]:
        url = f"{BASE}/players/{_slug(name)}/{rid}"
        r = self.http.get(url, headers={"Accept": "text/html"})
        if r.status_code == 404:
            return {}
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        plat = page_platform(r.text)
        if plat not in (None, "ps"):
            raise RuntimeError(f"Seite liefert Plattform '{plat}' statt PlayStation")
        return parse_player_page(r.text)

    # ---------- Schnittstelle ----------
    def check(self) -> tuple[bool, str]:
        try:
            r = self.http.get(f"{BASE}/robots.txt")
            if r.status_code != 200:
                return False, f"FUTNext robots.txt nicht abrufbar (HTTP {r.status_code})."
            if not _players_allowed(r.text):
                return False, "FUTNext robots.txt sperrt /players/ inzwischen - Quelle nicht nutzen."
            data = self._fetch_page(231747, "Mbappe")
            if not data:
                return False, "FUTNext erreichbar, aber keine Preisdaten auf der Testseite (Seitenformat geaendert?)."
            return True, "FUTNext erreichbar, robots.txt erlaubt /players/, Preise (PS) im HTML gefunden."
        except BlockedError as e:
            return False, f"FUTNext blockiert den Zugriff ({e}). Wird bewusst nicht umgangen."
        except Exception as e:  # noqa: BLE001
            return False, f"FUTNext nicht erreichbar: {e}"

    def fetch_prices(self, cards: list[dict]) -> list[PriceQuote]:
        start = time.monotonic()
        now = utcnow()
        fetched_this_run: set[int] = set()
        blocked: str | None = None
        quotes: list[PriceQuote] = []
        for card in cards:
            cid = card_id_of(card)
            rid = resource_id(card)
            if rid is None:
                quotes.append(PriceQuote(cid, None, utcnow(), error="keine resourceId in der Karten-ID"))
                continue
            entry = self._cache_fresh(rid, now) if rid not in fetched_this_run else self._cache.get(str(rid))
            if entry is None and blocked:
                quotes.append(PriceQuote(cid, None, utcnow(), error=blocked))
                continue
            if entry is None and time.monotonic() - start > self.budget_s:
                quotes.append(PriceQuote(cid, None, utcnow(), error="Zeitbudget des Laufs erschoepft"))
                continue
            if entry is None:
                try:
                    page = self._fetch_page(rid, card.get("name"))
                    t = utcnow().isoformat()
                    for prid, d in page.items():
                        self._cache[str(prid)] = {**d, "fetched_at": t}
                        fetched_this_run.add(prid)
                    entry = self._cache.get(str(rid)) if rid in page else None
                    if entry is None:
                        quotes.append(PriceQuote(cid, None, utcnow(),
                                                 error="Karte auf FUTNext nicht gefunden (404 oder ohne Preisobjekt)"))
                        continue
                except BlockedError as e:
                    blocked = str(e)
                    quotes.append(PriceQuote(cid, None, utcnow(), error=blocked))
                    continue
                except Exception as e:  # noqa: BLE001
                    quotes.append(PriceQuote(cid, None, utcnow(), error=f"Abruf fehlgeschlagen: {e}"))
                    continue
            quotes.append(self._quote(cid, entry))
        self._save_cache()
        return quotes

    @staticmethod
    def _quote(cid: str, e: dict) -> PriceQuote:
        price = e.get("price")
        price = int(price) if isinstance(price, (int, float)) and price > 0 else None
        ts = e.get("ts")
        return PriceQuote(
            card_id=cid,
            price=price,
            fetched_at=datetime.fromisoformat(e["fetched_at"]),
            source_updated_at=datetime.fromtimestamp(ts / 1000, timezone.utc) if ts else None,
            available=True if price else None,
            error=None if price else "Quelle liefert keinen Preis (evtl. nicht handelbar/keine Angebote)",
        )

    def fetch_history(self, card: dict) -> list[tuple[datetime, int]]:
        return []   # Historie wird auf FUTNext nur clientseitig geladen (nicht oeffentlich dokumentiert)


def _players_allowed(robots: str) -> bool:
    """Minimaler robots.txt-Check fuer User-agent: * und den Pfad /players/."""
    active = False
    disallows: list[str] = []
    for line in robots.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            active = v == "*"
        elif active and k == "disallow" and v:
            disallows.append(v)
    for d in disallows:
        pat = "^" + re.escape(d).replace(r"\*", ".*")
        if d.endswith("$"):
            pat = pat[:-2] + "$"
        if re.match(pat, "/players/player/231747"):
            return False
    return True
