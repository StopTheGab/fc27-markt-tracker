"""Live-Test: python -m collector.sources.selftest

Waehlt die Quelle wie der Collector (get_source(os.environ)) und ruft fuer drei
bekannte Karten echte Preise ab. Ohne Cache, damit wirklich live abgefragt wird.
"""
from __future__ import annotations

import os
import sys
import time

from . import get_source, last_check_messages

CARDS = [
    {"id": "27-231747", "name": "Kylian Mbappe", "rating": 91},
    {"id": "27-50604801", "name": "Caicedo", "rating": 87},
    {"id": "27-239085", "name": "Erling Haaland", "rating": 91},
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    env = dict(os.environ)
    env.setdefault("FUTNEXT_DISK_CACHE", "0")
    t0 = time.monotonic()
    src = get_source(env)
    for sid, ok, msg in last_check_messages():
        print(f"[check] {sid:8s} {'OK ' if ok else 'NEIN'}  {msg}")
    if src is None:
        print("Keine regelkonforme Quelle verfuegbar - es werden KEINE Preise erfunden.")
        return 2
    print(f"Gewaehlte Quelle: {src.name} ({src.url})")
    quotes = src.fetch_prices(CARDS)
    for c, q in zip(CARDS, quotes):
        price = f"{q.price:,}".replace(",", ".") if q.price is not None else "-"
        upd = q.source_updated_at.isoformat() if q.source_updated_at else "-"
        print(f"{q.card_id:13s} {c['name']:15s} PS-Preis {price:>12s}  Quelle-Stand {upd}  "
              f"abgerufen {q.fetched_at.isoformat(timespec='seconds')}  Fehler: {q.error or '-'}")
    hist = src.fetch_history(CARDS[0])
    print(f"Historie {CARDS[0]['id']}: {len(hist)} Punkte")
    print(f"Dauer: {time.monotonic() - t0:.1f} s")
    return 0 if any(q.price for q in quotes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
