"""FUT-DB API (https://api.futdatabase.com) - offizielle JSON-REST-API mit Token.

Gepruefte Lage (2026-10-05, siehe README.md):
- Swagger: https://api.futdatabase.com/api/doc/index.html  (Spec: /api/doc/v1/swagger.json, version "27")
- Auth: Header `X-AUTH-TOKEN`. Ohne Token -> 401.
- Preise: GET /api/players/{id}/price -> {"playstation": {price, minPrice, maxPrice, prp, priceUpdate}, "pc": {...}}
  laut Doku *premium only*. Suche (POST /api/players/search) ebenfalls *premium only*.
- Karten-Zuordnung: FUT-DB hat eigene IDs; PlayerModel enthaelt `resourceId`.
  Watchlist-Eintrag darf `futdb_id` enthalten; sonst Suche nach Name+Rating und Abgleich ueber resourceId.
- Keine Historie-Endpunkte -> fetch_history() == [].
"""
from __future__ import annotations

from datetime import datetime, timezone

from .base import BlockedError, PoliteSession, PriceQuote, PriceSource, card_id_of, resource_id, utcnow

API = "https://api.futdatabase.com/api"
ENV_KEY = "FUTDB_API_KEY"


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class FutDbSource(PriceSource):
    id = "futdb"
    name = "FUT-DB API"
    url = "https://api.futdatabase.com/api/doc/index.html"

    def __init__(self, env: dict | None = None):
        env = env or {}
        self.token = (env.get(ENV_KEY) or "").strip()
        self.http = PoliteSession(extra_headers={"X-AUTH-TOKEN": self.token, "Accept": "application/json"},
                                  min_delay=float(env.get("FUTDB_DELAY_S", "3.2")))
        self._id_map: dict[int, int] = {}   # resourceId -> futdb id

    def check(self) -> tuple[bool, str]:
        if not self.token:
            return False, (f"FUT-DB: kein API-Token. Umgebungsvariable {ENV_KEY} setzen "
                           "(Token aus dem FUT-DB-Konto; Preise brauchen laut Doku einen Premium-Zugang).")
        try:
            r = self.http.get(f"{API}/players/1/price")
        except BlockedError as e:
            return False, f"FUT-DB verweigert den Zugriff: {e}"
        except Exception as e:  # noqa: BLE001
            return False, f"FUT-DB nicht erreichbar: {e}"
        if r.status_code == 401:
            return False, f"FUT-DB lehnt das Token ab (401). {ENV_KEY} pruefen."
        if r.status_code in (402, 404) or (r.status_code == 200 and not r.content):
            return False, f"FUT-DB: Preis-Endpunkt nicht verfuegbar (HTTP {r.status_code}) - Premium-Zugang noetig?"
        if r.status_code != 200:
            return False, f"FUT-DB antwortet HTTP {r.status_code} auf den Preis-Endpunkt."
        return True, "FUT-DB erreichbar, Token gueltig, Preis-Endpunkt antwortet."

    def _futdb_id(self, card: dict) -> int | None:
        if str(card.get("futdb_id", "")).isdigit():
            return int(card["futdb_id"])
        rid = resource_id(card)
        if rid is None:
            return None
        if rid in self._id_map:
            return self._id_map[rid]
        body = {"name": card.get("name")} if card.get("name") else {}
        if card.get("rating"):
            body["rating"] = int(card["rating"])
        if not body:
            return None
        r = self.http.request("POST", f"{API}/players/search", json=body)
        if r.status_code != 200:
            raise RuntimeError(f"Suche HTTP {r.status_code}")
        for p in (r.json() or {}).get("items") or []:
            if p.get("resourceId") == rid:
                self._id_map[rid] = int(p["id"])
                return self._id_map[rid]
        return None

    def fetch_prices(self, cards: list[dict]) -> list[PriceQuote]:
        out: list[PriceQuote] = []
        blocked: str | None = None
        if not self.token:
            return [PriceQuote(card_id_of(c), None, utcnow(), error=f"{ENV_KEY} fehlt") for c in cards]
        for card in cards:
            cid = card_id_of(card)
            if blocked:
                out.append(PriceQuote(cid, None, utcnow(), error=blocked))
                continue
            try:
                fid = self._futdb_id(card)
                if fid is None:
                    out.append(PriceQuote(cid, None, utcnow(), error="Karte in FUT-DB nicht gefunden"))
                    continue
                r = self.http.get(f"{API}/players/{fid}/price")
                if r.status_code != 200:
                    out.append(PriceQuote(cid, None, utcnow(), error=f"Preis HTTP {r.status_code}"))
                    continue
                ps = (r.json() or {}).get("playstation") or {}
                price = ps.get("price")
                price = int(price) if isinstance(price, (int, float)) and price > 0 else None
                out.append(PriceQuote(
                    card_id=cid, price=price, fetched_at=utcnow(),
                    source_updated_at=_dt(ps.get("priceUpdate")),
                    price_min=ps.get("minPrice"), price_max=ps.get("maxPrice"),
                    available=True if price else None,
                    error=None if price else "FUT-DB liefert keinen PS-Preis",
                ))
            except BlockedError as e:
                blocked = str(e)
                out.append(PriceQuote(cid, None, utcnow(), error=blocked))
            except Exception as e:  # noqa: BLE001
                out.append(PriceQuote(cid, None, utcnow(), error=f"Abruf fehlgeschlagen: {e}"))
        return out
