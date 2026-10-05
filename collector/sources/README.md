# Preisquellen — Prüfung vom 2026-10-05

Alle Tests mit ehrlichem User-Agent `FC27-Markt-Tracker/1.0 (personal, non-commercial)`,
≥ 3 s Pause pro Host, ohne Login, ohne Umgehung von Sperren.

## Ergebnis

| Quelle | Test (Status) | robots.txt | Nutzungsbedingungen | Entscheidung |
|---|---|---|---|---|
| **FUTNext** `www.futnext.com/players/<slug>/<resourceId>` | 200, Preise im HTML (Next.js-Flight-Daten) | `User-Agent: * Allow: /`; gesperrt nur `/account`, `/login`, `/signup`, `/auth/`, `/image-generator/`, `/*?_rsc=` … | `/legal/terms`: **kein** Verbot von Bots/Scraping. Lizenz „one copy … for personal, non-commercial transitory use“; verboten: kopieren/„mirror“ auf anderen Servern, Netz überlasten | **Genutzt (Standard)** — mit Auflagen, s. u. |
| **FUT-DB API** `api.futdatabase.com` | Swagger 200 (`/api/doc/v1/swagger.json`, version „27“); `/api/players/1` ohne Token → 401 | kein robots.txt (404) — offizielle API | Preise laut Doku „*premium only*“, Auth per Header `X-AUTH-TOKEN` | **Eingebaut, Priorität 1**, aktiv nur mit `FUTDB_API_KEY` |
| futdatabase.com (Website) | 429 „Vercel Security Checkpoint“ | – | – | Challenge → nicht umgangen; Tarif/Preis des Premium-Zugangs daher **nicht verifiziert** |
| futdb.app | 520 (Cloudflare) | – | – | nicht erreichbar |
| **FUTBIN** `www.futbin.com/27/player/1/…` | **200** (heute, Preis PS 120.000 im HTML) | `User-agent: *` sperrt nur URLs mit `?` u. a. | **ToS §13 „No Scraping or Data Mining“**: „Unless you are given written permission by us, you are prohibited from conducting … web scraping“ (Stand 24.02.2026) | **Abgelehnt** (ToS) |
| **FUT.GG** | HTML 200, Preis der Karte `currentDbPrice:null`; nur Preise *fremder* Karten in Karussells, Plattform unklar | `Disallow: /api/*` | Stormstrike-Terms (13.05.2026): „use any automated means (such as bots, scrapers, or crawlers) to access our Services, except where expressly permitted“ verboten | **Abgelehnt** (ToS + robots für `/api/`) |
| FUTWIZ | 403 | – | – | Sperre, abgehakt |
| EasySBC | 200, reine JS-App (keine Preise im HTML) | `Disallow: /creator` | – | keine nutzbaren Preise ohne interne API → nein |
| FUT Alert (futalert.co.uk) | 200, JS-App, Preise nur nach Laden der internen API | `Disallow:` (leer) | Terms-Seite rendert keinen Text serverseitig | keine dokumentierte API → nein |
| fut.to | 200 — chinesisches Web-App-Plugin | – | – | setzt EA-Web-App voraus → tabu |
| futcoach.com | Domain steht zum Verkauf (llms.txt) | – | – | entfällt |
| RapidAPI / Apify / Notte „FC-Preis-APIs“ | Websuche | – | scrapen FUTBIN | verstößt mittelbar gegen FUTBIN-ToS → nein |
| GitHub-Dumps | Websuche: nur FC24/FC23-Scraper (Futwiz/Futbin) | – | – | keine FC-27-Preisdumps gefunden |

## Auswahl in `get_source(env)`
1. `futdb` — nur wenn `FUTDB_API_KEY` gesetzt ist und `check()` OK (offizielle API, liefert auch EA-Preisgrenzen `minPrice`/`maxPrice`).
2. `futnext` — Standard; abschaltbar mit `FUTNEXT_DISABLED=1`.
3. sonst `None`; Gründe über `last_check_messages()`.

## FUTNext — Details und Auflagen
- Abruf: `GET https://www.futnext.com/players/<slug>/<resourceId>` (Slug wird ignoriert; kein Query-String).
  Je Karten-Objekt `"price":{"averagePrice":…,"cheapestPrice":…,"timeStamp":<ms>}`; genutzt wird `cheapestPrice`.
  Plattform: Standard „ps“ (Seite zeigt „PS / XB“ = Konsole). Das Modul prüft das und bricht sonst ab.
- `timeStamp` steht auf voller Stunde (Stunden-Bucket), der Preis ändert sich aber auch innerhalb der Stunde
  (Mbappé 3.777.000 → 3.780.000 bei gleichem `timeStamp`) → `source_updated_at` ist nur „Stand-Stunde“.
- Eine Spielerseite enthält **alle Versionen** des Spielers → ein Request deckt mehrere Watchlist-Karten ab.
- **Dauer:** 3,2 s Pause/Request → 150 Karten ≈ 8 min pro Lauf (weniger, wenn Versionen geteilt werden);
  Lauf-Budget 12 min (`FUTNEXT_RUN_BUDGET_S`), Rest bekommt `error="Zeitbudget…"`. Seiten ≈ 185–200 KB.
- Cache: `.cache/futnext.json` (in Git ignoriert), Karte frühestens nach 14 min neu (`FUTNEXT_MIN_REFETCH_MIN`).
  Optional `FUTNEXT_SMART_SKIP=1`: nur neu laden, wenn ein neuer Stunden-Stand fällig ist (≈ ¼ der Last).
- 403/Challenge → Lauf stoppt sofort für alle restlichen Karten (kein Umgehen). 429/5xx → Backoff 5/10/20 s, `Retry-After` wird beachtet.
- **Keine Historie** im HTML (wird clientseitig nachgeladen) → `fetch_history()` liefert `[]`.
  Ein 7-Tage-Schnitt entsteht erst nach 7 Tagen eigener Sammlung.
- **Auflage aus den Terms:** Lizenz nur „personal, non-commercial“, kein „Mirroring“. Daher die
  FUTNext-Preise **nicht öffentlich** weiterverbreiten — Repo `fc27-markt-tracker` (Branch `data`)
  und das Vercel-Dashboard **privat** halten bzw. schützen. Quelle im Dashboard nennen.
  Ehrliche Einordnung: kein ausdrückliches Verbot, aber auch keine ausdrückliche Erlaubnis für
  Dauerabfragen — wer ganz sicher gehen will, fragt FUTNext (Discord/Support) kurz um Erlaubnis.

## FUT-DB — was der User tun muss (optional, sauberste Variante)
- Konto/Token bei FUT-DB (futdatabase.com, früher futdb.app) anlegen; der Preis-Endpunkt ist laut
  Swagger „premium only“. Die Website zeigte heute nur eine Vercel-Sicherheitsprüfung → Kosten/Tarif
  bitte im Browser selbst nachsehen. Token als Umgebungsvariable **`FUTDB_API_KEY`** setzen (z. B. in `.env`).
- Watchlist-Einträge dürfen `futdb_id` enthalten; sonst sucht das Modul per Name + Rating und gleicht über `resourceId` ab.
- Rate-Limits sind in der Doku nicht angegeben; Modul hält 3,2 s Pause → 150 Karten ≈ 8 min.

## Schnittstelle
`base.py`: `PriceQuote`, `PriceSource` (`check`, `fetch_prices`, `fetch_history`), `PoliteSession`.
Karten-ID `27-<resourceId>` (FUT.GG-Stil) = EA-resourceId, die FUTNext direkt in der URL nutzt.
Live-Test: `python -m collector.sources.selftest` (ohne Disk-Cache).
