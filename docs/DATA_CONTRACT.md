# Datenvertrag Collector → Dashboard

Der Collector schreibt alle 15 Minuten JSON-Dateien in `export/` und pusht sie in den
Branch `data` des Repos `StopTheGab/fc27-markt-tracker` (nur diese Dateien, Wurzel des Branches).
Das Dashboard lädt sie zur Laufzeit von
`https://raw.githubusercontent.com/StopTheGab/fc27-markt-tracker/data/<datei>`
(CORS erlaubt, ~5 min CDN-Cache). Kein Vercel-Build durch Daten-Updates.

Alle Zeitstempel: ISO 8601 UTC (`2026-10-05T08:15:00Z`). Preise: Ganzzahl Coins, PlayStation.
Ein fehlender Wert ist `null` — **nie** ein erfundener Platzhalter.

## status.json
```json
{
  "generated_at": "2026-10-05T08:15:00Z",
  "last_successful_fetch": "2026-10-05T08:15:00Z" | null,
  "source": { "id": "futdb", "name": "FUTDB API", "url": "https://...", "ok": true, "message": "..." },
  "collector_version": "1.0.0",
  "interval_minutes": 15,
  "cards_tracked": 150,
  "cards_with_price": 143,
  "data_days": 0.4,
  "gaps": [ { "from": "...", "to": "...", "minutes": 120 } ],
  "errors_last_run": [ "..." ]
}
```
Wenn keine Quelle funktioniert: `last_successful_fetch: null`, `source.ok: false`, `source.message`
erklärt, was fehlt. Das Dashboard zeigt dann einen klaren Hinweis statt Preisen.

## market.json
```json
{
  "generated_at": "...",
  "trend_24h_pct": -2.3 | null,
  "trend_1h_pct": 0.4 | null,
  "index_value": 1000.0 | null,
  "crash": { "active": false, "severity": "none|mild|severe", "drop_pct": -12.0, "reason": "..." },
  "week_phase": { "id": "weekend_league", "label": "Weekend League läuft", "note": "Preise ...", "price_tendency": "down|up|flat|volatile" },
  "upcoming_events": [ { "date": "2026-10-10", "name": "...", "type": "promo|wl|rewards|sbc", "certainty": "sicher|wahrscheinlich|unsicher", "impact": "..." } ],
  "assessment": { "text": "2–3 Sätze Markteinschätzung", "generated_at": "...", "author": "Analyse-Runde|Regeln" } | null,
  "hit_rate": { "evaluated": 12, "hits": 7, "rate": 0.58, "window_days": 14 } | null
}
```

## cards.json
```json
{
  "generated_at": "...",
  "cards": [
    {
      "id": "27-231747",                  // stabile Karten-ID (Quelle-unabhängig, FUT.GG-Stil)
      "ea_id": 231747,
      "name": "Kylian Mbappé",
      "version": "Gold Rare",
      "rating": 91,
      "position": "ST",
      "league": "LALIGA EA SPORTS", "club": "Real Madrid", "nation": "France",
      "price": 1250000 | null,
      "price_updated_at": "...",
      "available": true,                 // false = gerade nicht handelbar / extinct / keine Preise
      "price_min": 15000 | null, "price_max": 300000 | null,   // EA-Preisgrenzen, falls bekannt
      "avg_7d": 1300000 | null,
      "change_1h_pct": -1.2 | null, "change_24h_pct": -4.0 | null,
      "deviation_pct": -3.8 | null,      // (price - avg_7d) / avg_7d * 100
      "data_days": 2.1,
      "signal": "buy" | "sell" | null,
      "watch_reason": "Meta-ST, in WL-Teams häufig",
      "image": "https://..." | null,
      "link": "https://www.fut.gg/players/..."
    }
  ]
}
```

## signals.json
```json
{
  "generated_at": "...",
  "signals": [
    {
      "card_id": "27-231747",
      "name": "Kylian Mbappé",
      "type": "buy" | "sell",
      "since": "...",
      "price": 1100000,
      "avg_7d": 1300000,
      "deviation_pct": -15.4,
      "expected_sell": 1300000,
      "expected_profit": 135000,          // expected_sell * 0.95 - price
      "confidence": "hoch" | "mittel" | "gering",
      "reasons": [ "15,4 % unter 7-Tage-Schnitt", "Weekend League startet in 2 Tagen ..." ],
      "rules": [ "base_15pct", "weekday_cycle" ]
    }
  ]
}
```

## history/<card_id>.json  (eine Datei pro Karte)
```json
{ "card_id": "27-231747", "points": [ ["2026-10-05T08:15:00Z", 1250000], ... ] }
```
Höchstens 14 Tage, stündlich verdichtet für ältere als 48 h.

## creators.json  (optional, verschlüsselt wie market.json)
Erzeugt von `collector/creators.py` (`export_data`) aus öffentlichen YouTube-Feeds der in
`creators.json` (Repo-Wurzel) konfigurierten Creator. Enthält nur Videos der letzten 14 Tage.
Fehlt die Datei (404), zeigt das Dashboard „Noch keine Creator-Daten“ statt eines Fehlers.
```json
{
  "generated_at": "...",
  "note": "Hinweistext zur Quelle/Erkennung (klein unter der Liste angezeigt)",
  "creators": [
    {
      "id": "fifallstars", "name": "FIFAllstars",
      "priority": 1,                       // 1 = Hauptquelle, sonst Zusatzquelle
      "language": "de",
      "youtube": "https://...", "tiktok": "https://...", "instagram": "https://...",
      "discord_free": "https://..." ,      // optional
      "warning": "Bezahlter Premium-Discord ..."   // optional, dezent gelb angezeigt
    }
  ],
  "posts": [                               // neueste zuerst
    {
      "video_id": "abc123", "creator_id": "fifallstars", "creator": "FIFAllstars", "priority": 1,
      "published": "2026-10-05T12:00:00Z",
      "title": "...", "url": "https://www.youtube.com/watch?v=abc123",
      "kind": "buy" | "sell" | "market" | "info",
      "kind_label": "Kauf-Tipp" | "Verkaufs-Tipp" | "Marktanalyse" | "Sonstiges",
      "is_new": true,                      // jünger als 24 h
      "cards": [                           // im Titel/der Beschreibung erkannte Watchlist-Karten, sonst []
        { "id": "27-231747", "name": "Kylian Mbappé" | null, "version": "Gold Rare" | null,
          "price_at_post": 1100000 | null,  // erster Messpunkt nach Veröffentlichung
          "price_now": 1250000 | null,
          "change_pct": 13.64 | null }
      ]
    }
  ]
}
```
Das Dashboard verlinkt Videos und Profile nur (keine eingebetteten Player, keine fremden Bilder)
und akzeptiert ausschließlich `https://`-Links.
