"""Gemeinsame Schnittstelle und Hilfen fuer alle Preisquellen.

Regeln (siehe README.md): ehrlicher User-Agent, >= 3 s Pause pro Host,
exponentielles Backoff bei 429/5xx, KEIN Umgehen von 403/Challenges.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

USER_AGENT = "FC27-Markt-Tracker/1.0 (personal, non-commercial)"
MIN_DELAY_S = 3.2          # Pause zwischen Requests an denselben Host
MAX_RETRIES = 3            # bei 429 / 5xx / Netzfehler
BACKOFF_BASE_S = 5.0       # 5 s, 10 s, 20 s (+ Jitter), Retry-After hat Vorrang
TIMEOUT_S = 20


@dataclass
class PriceQuote:
    card_id: str                 # Watchlist-ID, FUT.GG-Stil "27-<resourceId>", z. B. "27-231747"
    price: int | None            # Lowest BIN PlayStation in Coins; None = unbekannt
    fetched_at: datetime         # UTC, tz-aware
    source_updated_at: datetime | None = None   # wann die Quelle den Preis zuletzt aktualisiert hat
    price_min: int | None = None # EA-Preisgrenzen, falls die Quelle sie liefert
    price_max: int | None = None
    available: bool | None = None  # False = nicht handelbar/extinct/keine Angebote
    error: str | None = None


class BlockedError(Exception):
    """Quelle verweigert den Zugriff (403/Challenge). Nicht umgehen, Lauf abbrechen."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resource_id(card: dict) -> int | None:
    """'27-231747' -> 231747. Faellt auf card['ea_id'] zurueck."""
    cid = str(card.get("id") or card.get("card_id") or "")
    if "-" in cid:
        tail = cid.split("-", 1)[1]
        if tail.isdigit():
            return int(tail)
    ea = card.get("ea_id")
    if isinstance(ea, int) or (isinstance(ea, str) and ea.isdigit()):
        return int(ea)
    return None


def card_id_of(card: dict) -> str:
    return str(card.get("id") or card.get("card_id") or "")


class PoliteSession:
    """requests.Session mit Host-Drosselung, Backoff und 403-Stopp."""

    _lock = threading.Lock()
    _last_request: dict[str, float] = {}   # prozessweit geteilt

    def __init__(self, extra_headers: dict | None = None, min_delay: float = MIN_DELAY_S):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        if extra_headers:
            self.s.headers.update(extra_headers)
        self.min_delay = min_delay

    def _throttle(self, host: str) -> None:
        with self._lock:
            last = self._last_request.get(host)
            if last is not None:
                wait = self.min_delay - (time.monotonic() - last)
                if wait > 0:
                    time.sleep(wait)
            self._last_request[host] = time.monotonic()

    def request(self, method: str, url: str, **kw) -> requests.Response:
        host = urlparse(url).netloc
        kw.setdefault("timeout", TIMEOUT_S)
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            self._throttle(host)
            try:
                r = self.s.request(method, url, **kw)
            except requests.RequestException as e:
                last_exc = e
                r = None
            if r is not None:
                if r.status_code == 403 or r.headers.get("cf-mitigated"):
                    raise BlockedError(f"{host} antwortet {r.status_code} (Sperre/Challenge) - wird nicht umgangen")
                if r.status_code != 429 and r.status_code < 500:
                    return r
                last_exc = requests.HTTPError(f"HTTP {r.status_code}")
            if attempt == MAX_RETRIES:
                break
            delay = BACKOFF_BASE_S * (2 ** attempt) + random.uniform(0, 1.5)
            if r is not None and r.headers.get("Retry-After", "").isdigit():
                delay = max(delay, float(r.headers["Retry-After"]))
            time.sleep(min(delay, 120))
        if r is not None:
            return r   # letzter 429/5xx - Aufrufer wertet aus
        raise last_exc or RuntimeError("unbekannter Netzfehler")

    def get(self, url: str, **kw) -> requests.Response:
        return self.request("GET", url, **kw)


class PriceSource:
    id: str = "base"
    name: str = "Basis"
    url: str = ""

    def check(self) -> tuple[bool, str]:
        """Erreichbar + erlaubt? Meldung auf Deutsch."""
        raise NotImplementedError

    def fetch_prices(self, cards: list[dict]) -> list[PriceQuote]:
        """cards = Eintraege aus watchlist.json. Nie Exception nach aussen."""
        raise NotImplementedError

    def fetch_history(self, card: dict) -> list[tuple[datetime, int]]:
        """Historische Preise (UTC, Coins). Darf [] liefern."""
        return []

    def describe(self) -> dict:
        return {"id": self.id, "name": self.name, "url": self.url}
