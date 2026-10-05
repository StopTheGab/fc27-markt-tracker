"""Preisquellen fuer den FC27-Markt-Tracker.

Auswahlreihenfolge in get_source() (erste mit check() == True gewinnt):
  1. futdb   - offizielle API, nur wenn FUTDB_API_KEY gesetzt ist (sauberste Rechtslage,
               liefert zusaetzlich EA-Preisgrenzen).
  2. futnext - oeffentliche Spielerseiten (robots.txt erlaubt, Terms ohne Bot-Verbot).
               Abschaltbar mit FUTNEXT_DISABLED=1.
Nicht eingebaut (Begruendung in README.md): futbin (ToS 13 verbietet Scraping),
fut.gg (ToS verbietet automatisierten Zugriff, Preise nur ueber gesperrtes /api/),
futwiz (403), futdatabase.com-Website (Vercel-Challenge), futdb.app (520).
"""
from __future__ import annotations

from .base import PriceQuote, PriceSource
from .futdb import FutDbSource
from .futnext import FutNextSource

__all__ = ["PriceQuote", "PriceSource", "get_source", "available_sources", "last_check_messages"]

_last_messages: list[tuple[str, bool, str]] = []


def available_sources(env: dict | None = None) -> list[PriceSource]:
    """Alle eingebauten Quellen in Prioritaetsreihenfolge (ungeprueft)."""
    env = env or {}
    out: list[PriceSource] = []
    if env.get("FUTDB_API_KEY"):
        out.append(FutDbSource(env))
    if env.get("FUTNEXT_DISABLED", "0") != "1":
        out.append(FutNextSource(env))
    return out


def get_source(env: dict) -> PriceSource | None:
    """Erste Quelle, deren check() True liefert; sonst None (Gruende: last_check_messages())."""
    _last_messages.clear()
    if not env.get("FUTDB_API_KEY"):
        _last_messages.append(("futdb", False, "FUTDB_API_KEY nicht gesetzt - FUT-DB uebersprungen."))
    for src in available_sources(env):
        ok, msg = src.check()
        _last_messages.append((src.id, ok, msg))
        if ok:
            return src
    return None


def last_check_messages() -> list[tuple[str, bool, str]]:
    return list(_last_messages)
