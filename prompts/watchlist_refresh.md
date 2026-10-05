<!-- Wiederverwendbarer Arbeitsauftrag fuer scripts/watchlist-refresh.ps1.
     Platzhalter: {{DATE}} = heutiges Datum (YYYY-MM-DD), {{MIN_DATE}} = DATE minus 14 Tage,
     {{OUT}} = Zieldatei fuer die neue Watchlist (wird vom Skript validiert und erst dann uebernommen). -->

Du bist der Meta-Agent im Projekt "EA FC 27 Markt-Tracker" (Projektordner = aktuelles Arbeitsverzeichnis,
Windows 11, Python 3 mit `requests`). Heute ist {{DATE}}. Der User ist nicht da: stelle KEINE Rückfragen.
Zeitbudget: höchstens 40 Minuten. Antworte und schreibe Texte auf Deutsch, Code/Bezeichner auf Englisch.

## Ziel
Schreibe `{{OUT}}` (UTF-8, eingerückt) mit 100–200 EA-FC-27-Ultimate-Team-Karten, die aktuell Meta bzw.
fürs Team und für kurzfristiges Trading (PlayStation-Markt) relevant sind. `watchlist.json` selbst NICHT
anfassen – das übernimmt das Skript nach erfolgreicher Validierung. Schreibe außerdem
`knowledge/meta_{{DATE}}.md`.

## Quellen-Regeln
- Nur Quellen zu EA FC 27, höchstens 14 Tage alt (Datum ≥ {{MIN_DATE}}). Datum JEDER Quelle prüfen und
  notieren. Nichts aus FC 26 (oder älter) als aktuelle Meta übernehmen – Titel/Datum genau prüfen.
- Geeignet: YouTube-Videos (Titel + Upload-Datum), Reddit r/EASportsFC / r/fut, FUT.GG-Artikel und Listen,
  EA-Seiten, realsport101, timesaver.gg, earlygame, allthings.how, Weekend-League-/Champions-Teams,
  "meistgenutzt"-Listen. Quellen ohne erkennbares Datum nicht als Beleg verwenden.
- fut.gg: HTML-Seiten sind laut robots.txt erlaubt, `/api/*` ist VERBOTEN – nie aufrufen. Beim direkten
  Abruf ≥ 3 s Pause zwischen Requests, User-Agent `FC27-Markt-Tracker/1.0 (personal, non-commercial)`.
- futbin.com und futwiz.com blocken Bots (403) – nicht umgehen. Suchtreffer davon dürfen als Quelle genannt
  werden, wenn das Datum klar ist.
- WebSearch (mode "standard", mehrere Suchen parallel) und WebFetch nutzen.
- Erfinde keine Karten, Ratings oder IDs. Nicht Belegbares weglassen oder Feld auf null setzen.

## Mischung
Meta-Karten aller Positionen (Gold, beliebte Ligen PL/LaLiga/Bundesliga/Serie A/Ligue 1), beliebte aktuelle
Promo-Karten, die handelbar sind (keine reinen SBC-/Objective-/Season-Pass-Belohnungen – die sind
untradeable), einige liquide "Trading-Karten" (hohes Handelsvolumen, mittlere Preisklasse 5k–200k) und
ein paar wichtige SBC-Futterkarten (z. B. 84–87er, falls aktuell relevant).
`category`: "meta" | "promo" | "trading" | "fodder".

## Karten-IDs (bewährter Weg)
FUT.GG-IDs im Format "27-<resourceId>". Basis-Goldkarte: resourceId = eaId (z. B. Mbappé `27-231747`,
URL `https://www.fut.gg/players/231747-kylian-mbappe/27-231747/`). Sonderkarten haben eigene resourceIds
(eaId + k·16777216, z. B. `27-50563395`).
1. `https://www.fut.gg/sitemap.xml` laden → Unter-Sitemaps `sitemap-player-detail-27.xml?p=1..N`
   (je 1000 URLs) mit 3 s Pause laden. Daraus Name-Slug → eaId/resourceId.
2. Für jede Kandidatenkarte die Spielerseite (HTML) laden. Im eingebetteten Daten-Block stehen u. a.
   `cardDef … rarityName:"…", overall:NN, position:"XX"` sowie `club:/nation:/league:$R[n]` (Name im
   referenzierten Objekt `$R[n]={… name:"…"}`) und die Liste aller Versionen des Spielers
   (`eaId:<resourceId>,overall:…,rarityName:"…",…,url:"/players/…/27-<resourceId>/"`). Daraus Rating,
   Position, Verein, Liga, Nation und die IDs der Promo-Versionen (z. B. "Team of the Week") übernehmen.
3. Wenn keine ID belegbar ist: `id`, `ea_id`, `resource_id`, `futgg_url` = null.
Die Seiten `/players/best/` und `/players/trending/` liefern im HTML keine Spielerdaten (werden per API
nachgeladen) – nicht darauf verlassen.

## Format `{{OUT}}`
```json
{
  "generated_at": "{{DATE}}T09:00:00Z",
  "game": "FC27", "platform": "ps",
  "method": "kurze Beschreibung, wie recherchiert",
  "cards": [
    {
      "id": "27-231747", "ea_id": 231747, "resource_id": 231747,
      "name": "Kylian Mbappé", "version": "Gold Rare", "rating": 91, "position": "ST",
      "club": "Real Madrid", "league": "LALIGA EA SPORTS", "nation": "France",
      "futgg_url": "https://www.fut.gg/players/231747-kylian-mbappe/27-231747/",
      "category": "meta",
      "reason": "Kurzer deutscher Grund (z. B. 'häufig in WL-Teams, Top-ST-Meta laut …')",
      "sources": [ { "title": "…", "url": "…", "date": "YYYY-MM-DD" } ]
    }
  ]
}
```
Jede Karte braucht mindestens eine Quelle mit Datum ≥ {{MIN_DATE}}. Keine Duplikate (gleiche id oder
gleicher Name+Version+Rating).

## Zusätzlich
1. `knowledge/meta_{{DATE}}.md`: kurze Zusammenfassung der aktuellen FC-27-Meta (Positionen, Attribute,
   PlayStyles, Formationen, dominante Karten), mit Quelle + Datum je Aussage. Widersprüche: beide nennen,
   neuere FC-27-Quelle bevorzugen. Vorherige `knowledge/meta_*.md` lesen und Veränderungen benennen.
2. Am Ende ausführen: `python -m collector.watchlist_tool validate {{OUT}} --today {{DATE}}` und Fehler
   beheben, bis RESULT: OK erscheint.

Berühre nur: `{{OUT}}` und `knowledge/meta_{{DATE}}.md` (plus temporäre Dateien außerhalb des Projekts).
Kein git commit. Abschlussbericht max. 30 Zeilen: Anzahl Karten (pro Kategorie), Anzahl ohne ID,
wichtigste Quellen mit Datum, Validierungsausgabe.
