# Analyse-Runde (etwa stündlich, solange eine Claude-Sitzung läuft)

Projekt: `C:\Users\sMARTgamINg\EA FC27`. Vorher lesen: `STATUS.md`, `knowledge/signalregeln.md`,
`knowledge/regel_aenderungen.md`, `knowledge/markthistorie.md`, `market_calendar.json`.
Daten holen: `python -m collector.cli report --hours 2` (JSON: Bewegungen, Signale, Tipps, Trefferquote).
Sparsam: höchstens 3 Agents, kurze Berichte (≤ 15 Zeilen), WebSearch mode "standard".

1. **Markt-Agent** – wertet den Report aus: Auffälligkeiten, die die festen Regeln nicht erfassen
   (z. B. ganze Liga/Nation steigt → SBC?, einzelne Position fällt, Preis klebt an Grenze, Ausreißer/Datenfehler).
   Ergebnis: 2–3 Sätze Markteinschätzung auf Deutsch.
2. **News-Agent** – sucht neue Promos, SBCs, Ankündigungen, Leaks der letzten 24 h (EA FC 27, Quellen mit Datum;
   Leaks als „unsicher“). Neue Termine → `market_calendar.json` (`events`, `promos`) ergänzen, JSON valide halten.
3. **Lern-Agent** – vergleicht Tipps (`tips`) mit der Preisentwicklung, hält die Trefferquote in
   `knowledge/trefferquote.md` fest; Regeländerungen nur mit Begründung in `rules.json` + `knowledge/regel_aenderungen.md`.
   Nie ändern: 5 % Steuer, nur Signale mit Gewinn, ≥ 15 % = „starkes Signal“ (Logik v2 seit 05.10., siehe regel_aenderungen.md).
4. **Creator-Transkripte** – für jedes NEUE Video (Tabelle `creator_posts`, kind ≠ info, noch nicht in
   `knowledge/creator_tipps/`): im Chrome-Browser „Fifa“ öffnen (claude-in-chrome), Video stumm pausieren, „Transkript anzeigen“
   (Panel `PAmodern_transcript_view`) auslesen; bei Shorts ohne Sprache die gezeigten Karten per Screenshot alle 3 s ablesen.
   Nur Kauf-/Verkaufsaussagen + genannte Karten zusammenfassen (keine Volltexte), mit unseren Preisen abgleichen, in
   `knowledge/creator_tipps/<datum>.md` schreiben, erkannte Karten-IDs in `creator_posts.cards` eintragen (Regel E nutzt sie),
   Empfehlung als `assess` speichern. FIFAllstars (priority 1) zuerst. Keine Logins, nichts posten/kommentieren.
5. **Discord** (stündlich, nur lesen, Browser „Fifa“, angemeldet als User): neue Nachrichten seit `data/discord_seen.json`
   in diesen Kanälen lesen. Bei Bild-Posts Screenshot ansehen und die Karten ablesen.
   - FIFAllstars-Server 692105835371036692: #trading-tipps 1456331245070975129, #live-oder-video 713360322148302849
   - AC Trading 905545396577779794: #announcements 1534124513627738283, #premium-sell-signals 908839330414469130
   - FUT & CHILL 561265415892762674: #trading-tips 941406481918603354 (falls freigeschaltet)

   Nie posten, reagieren oder beitreten, keine Direktnachrichten öffnen. Neue Kauf-/Verkaufs-Tipps zu Karten als
   `creator_posts` (video_id `discord:<server>-<msgid>`) mit Karten-IDs eintragen und in `knowledge/creator_tipps/<datum>.md` zusammenfassen.
   Zuletzt gelesene Zeitstempel in `data/discord_seen.json` speichern.
6. **Auskunft an den User:** Gibt es etwas Wichtiges (neuer Tipp der Hauptquelle, Verkaufsempfehlung für eine gehaltene Karte, Promo-Start,
   Crash), dann `python -m collector.cli notify --important --title "[FC27 TIPP] …" --text "<2–3 Sätze + Empfehlung>"`.
   Sonst nur die kurze Antwort im Chat.
7. **Meta-Agent** – nur einmal täglich (siehe `data/last_meta_check.txt`): `prompts/watchlist_refresh.md`.

Abschluss: Einschätzung speichern mit
`python -m collector.cli assess --author "Analyse-Runde" --text "<2–3 Sätze>"`
(erscheint nach dem nächsten 15-min-Lauf im Dashboard und in der Stunden-Mail). Keine erfundenen Zahlen.
