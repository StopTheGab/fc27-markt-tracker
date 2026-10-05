# STATUS – EA FC 27 Markt-Tracker

_Stand: 2026-10-05, ca. 14:55. Der Collector läuft seit 10:49 (neu gestartet 14:38 mit Fehlerkorrekturen)._

## Kurz
- **Dashboard:** https://fc27-markt-tracker.vercel.app
  Deinen persönlichen Link mit Schlüssel findest du in `data\DASHBOARD_LINK.txt`. Er liegt nur lokal, nicht im Repo. Öffne ihn einmal, danach merkt sich der Browser den Schlüssel.
- **Repo:** https://github.com/StopTheGab/fc27-markt-tracker (öffentlich). `main` enthält Code und Dashboard, `data` die JSON-Dateien des Collectors.
- **Start:** `start-collector.cmd` doppelklicken oder `powershell -ExecutionPolicy Bypass -File scripts\start.ps1`
- **Stopp:** `stop-collector.cmd` oder `scripts\stop.ps1`
- **Zustand prüfen:** `python -m collector.cli status`, Log in `logs\collector.log`
- **Datenquelle:** FUTNext (www.futnext.com), PlayStation-Preise aus den öffentlichen Spielerseiten

## Was funktioniert (getestet)
- Der Collector läuft seit 10:49 als Hintergrundprozess. Erster voller Lauf um 11:00: **146 von 146 Karten mit Preis, 0 Fehler, Dauer ca. 6 min.** Pause 3,2 s pro Request, Backoff bei Fehlern, sofortiger Abbruch bei Sperre oder Challenge.
- SQLite (`data\fc27.sqlite`). Nach einem Neustart macht der Collector weiter und läuft sofort an, wenn ein Termin verpasst wurde. Lücken werden erkannt (`status.json` → `gaps`). Der 7-Tage-Schnitt rechnet mit Stundenmitteln, Lücken verzerren ihn also nicht.
- Der Export wird verschlüsselt und per Force-Push in den Branch `data` geschoben, immer als ein einzelner Commit. Das Dashboard lädt die Daten zur Laufzeit von raw.githubusercontent.com. Mit dem echten Schlüssel per WebCrypto entschlüsselt und geprüft.
- Kein Vercel-Build durch Daten-Pushes, dreifach abgesichert: `vercel.json` auf `main` (`deploymentEnabled.data=false`), Ignore-Build-Step in der Projekteinstellung und eine `vercel.json` im data-Branch.
- Signale: 15-%-Grundregel, 5 % Steuer, Verkauf bei Rückkehr zum Schnitt, Marktcrash-Erkennung, „gering“ bei weniger als 3 Tagen Daten, Preisuntergrenze und nicht handelbare Karten, Wochenphase und anstehende Promos aus `market_calendar.json`. Dazu Zusatzregeln aus `knowledge/signalregeln.md` (Übernahme siehe `knowledge/regel_aenderungen.md`). Parameter in `rules.json`. 19 Logiktests grün: `python -m unittest discover tests`.
- Mail-Logik: Signal-Mail nur bei neuem Signal, mehrere gesammelt in einer Mail, Wiederkehr nach frühestens 2 h. Dazu ein Stunden-Update. Beide lassen sich getrennt abschalten, Fehler werden nur geloggt.
- Wissen in `knowledge/`, mit Quelle und Datum: Transfermarkt, Trading-Methoden, Preistreiber, Anfängerfehler, Signalregeln, Markthistorie, Meta.
- `market_calendar.json`: Wochenzyklus, 13 Promos, 11 frühere Crashs, Termine bis 16.11.
- `watchlist.json`: 146 Karten (meta 49, promo 50, trading 42, fodder 5), jede mit Grund, Quelle und Datum (22.09.–05.10.). Neu recherchieren: `scripts\watchlist-refresh.ps1`.

## Prüfung (Prüf-Agent, 14:40)
- Daten echt: FUTNext-Gegenprobe Haaland 121.000 und Neves 2.300 exakt gleich, Mbappé 3,72 Mio. live gegen 3,739 Mio. 30 min vorher. Alle Preise ganzzahlig, keine Duplikate, keine Lücken.
- Dashboard bei 1280 und 600 px: echte Preise, Aktualisierungszeit, Deutsch, keine Platzhalter. Der data-Branch ist verschlüsselt, keine Geheimnisse im Repo, kein Vercel-Build aus `data`.
- 7 Fehler gefunden und behoben (14:38), 30 Tests grün:
  - B1: Die meisten Karten wurden nur alle 30 statt 15 min neu abgerufen.
  - B2: Der Collector konnte sich bei einem Fehler beim Start oder in der Wartezeit still beenden.
  - B3: Ein Verkaufssignal konnte mit Verlust erscheinen.
  - B4: Eine Signal-Mail konnte bei einem Exportfehler verloren gehen.
  - B5: Windows-Dateisperren beim Publish.
  - B6: `last_successful_fetch` hing einen Lauf hinterher.
  - B7: Veraltete Quellpreise (z. B. Bouaddi, Stand 24.09.) galten als aktuell.

## Entscheidungen
1. **Futbin geht nicht:** Es blockt Bots (403), und laut ToS §13 ist Scraping verboten. FUTWIZ blockt ebenfalls (403). FUT.GG verbietet laut ToS automatisierten Zugriff, und die Preise kommen nur über `/api/`, das robots.txt sperrt. FUT-DB ist nicht erreichbar, der Preis-Endpunkt ist dort „premium“. **Gewählt: FUTNext**, weil robots.txt `Allow: /` erlaubt und die ToS Bots nicht verbieten. Details: `collector/sources/README.md`.
2. **Verschlüsselung:** Die FUTNext-Lizenz erlaubt nur „personal, non-commercial“ Nutzung und kein Spiegeln auf anderen Servern („mirror“). Deshalb liegen die Preise im öffentlichen Repo nur AES-256-GCM-verschlüsselt. Klartext ist nur `status.json`. Der Schlüssel `DATA_KEY` steht in `.env`.
3. **Keine Preishistorie:** Keine Quelle liefert sie regelkonform. Der 7-Tage-Schnitt baut sich also selbst auf. Bis ca. 08.10. sind alle Signale „gering“, ein voller 7-Tage-Schnitt steht ab 12.10.
4. **Verkaufssignale nur nach eigenem Kaufsignal:** Bestände kennt das Tool nicht. Sonst wäre jede zweite Karte ein „Verkauf“. Daraus ergibt sich auch die Trefferquote.
5. **Mail über Resend statt Outlook-SMTP:** Microsoft hat SMTP mit Passwort oder App-Passwort für Outlook.com am 16.09.2024 abgeschaltet. Es geht nur noch OAuth über eine Azure-App, und die hast du wegen der Kreditkarte abgelehnt. Ein Outlook-Konnektor war nicht verbunden, eine Testmail war deshalb nicht möglich.

## Creator-Tipps (seit 05.10. 17:45)
- **Hauptquelle FIFAllstars**, Zusatzquelle TheFutAccountant (Auswahl des Users). Der Collector liest bei jedem Lauf die öffentlichen
  YouTube-Feeds beider Creator, ordnet Videos ein (Kauf-Tipp/Verkaufs-Tipp/Marktanalyse) und erkennt Watchlist-Karten im Titel oder in der Beschreibung.
  Neues Tipp-Video von FIFAllstars ⇒ Signal-Mail, TheFutAccountant ⇒ Stunden-Update. Dashboard: Seite „Creator-Tipps“.
- **Grenze:** FIFAllstars nennt Spieler meist nur im Video. Dann steht „Karten nicht im Titel genannt“.
- **TikTok/Instagram:** ohne Login nicht automatisch lesbar ⇒ nicht eingebunden (nur Links im Dashboard).
- **Live-Transkripte: nicht möglich.** Die YouTube-API gibt Untertitel nur an den Kanalbesitzer heraus, und Streams mitschneiden oder transkribieren
  verstößt gegen die YouTube-Bedingungen. Stattdessen: **Live-Mail**, sobald FIFAllstars/TheFutAccountant live gehen. Dafür brauchst du einen kostenlosen API-Key (unten).
  Was du im Stream hörst, kannst du mir in den Chat schreiben. Ich trage es mit Datum als Tipp ein.

### Selbst einrichten (optional)
1. **Live-Erkennung (ca. 5 min):**
   - https://console.cloud.google.com → Projekt anlegen.
   - „YouTube Data API v3“ aktivieren.
   - Unter „Anmeldedaten“ einen API-Schlüssel erstellen.
   - In `.env` eintragen: `YOUTUBE_API_KEY=…` (das Kontingent ist gratis, der Tracker braucht ca. 200 von 10.000 Einheiten pro Tag).
2. **Discord von FIFAllstars (ca. 15 min):** Ich darf mich nicht in Discord anmelden, und ein automatisch mitlesendes Benutzerkonto verstößt gegen die Discord-Regeln.
   Erlaubt ist ein **eigener Bot in deinem eigenen Server**:
   - a) Dem kostenlosen FIFAllstars-Discord beitreten: https://discord.gg/n54GPN4UFs
   - b) Einen eigenen Server anlegen (+ → „Eigenen Server erstellen“).
   - c) Im FIFAllstars-Server beim Ankündigungskanal mit den Tipps auf **„Folgen“** klicken und als Ziel einen Kanal in deinem Server wählen.
     Diese Funktion gibt es nur bei Ankündigungskanälen. Fehlt sie, geht dieser Weg nicht.
   - d) https://discord.com/developers/applications → „New Application“ → „Bot“ → „Reset Token“ und den Token kopieren.
     Unter „Privileged Gateway Intents“ **Message Content Intent** einschalten.
   - e) Unter „OAuth2 → URL Generator“ die Scopes `bot` und die Berechtigungen „View Channels“ und „Read Message History“ wählen,
     dann mit der erzeugten URL den Bot in **deinen** Server einladen.
   - f) In Discord unter Einstellungen → Erweitert den Entwicklermodus einschalten, dann per Rechtsklick auf deinen Kanal → „Kanal-ID kopieren“
     und auf deinen Server → „Server-ID kopieren“.
   - g) In `.env` eintragen: `DISCORD_BOT_TOKEN=…`, `DISCORD_CHANNEL_IDS=<Kanal-ID>`, `DISCORD_GUILD_ID=<Server-ID>`. Danach liest der Collector die Posts bei jedem Lauf.
   Premium-Inhalte (Patreon) bitte nicht so einbinden: Deren Weitergabe verbietet Patreon meist.

## Signal-Logik v2 (seit 05.10. 17:45, Details in `knowledge/regel_aenderungen.md`)
- Jede Karte hat ein **Kauflimit** (7-Tage-Schnitt minus 8–20 %, je nach Schwankung) und ein **Verkaufslimit** (7-Tage-Schnitt).
  Kaufsignal, wenn der Preis unter das Kauflimit fällt, ab −15 % „starkes Signal“.
- Dazu kommen Wochenzyklus (Kauf im Wochentief, Verkauf im Wochenhoch Do/Fr), Promo-Warnungen (vor Promos verkaufen) und Creator-Tipps.
- Watchlist: 200 Karten (Karten unter 1.000 Coins entfernt, 76 gut gehandelte Karten von 10.000–200.000 neu). Ein Lauf dauert ca. 8 min.
- **Futbin** bleibt außen vor: Die ToS (§ 13, Stand 24.02.2026) verbieten Scraping ohne schriftliche Erlaubnis. Erst mit Erlaubnis kann ich umstellen.

## Push-Benachrichtigungen (seit 05.10. 18:15, ohne Konto)
- Jede Signal-Mail und jedes Stunden-Update geht zusätzlich als **Push über ntfy** raus, auch ohne eingerichteten Mail-Anbieter.
- Einrichtung (1 min):
  1. App „ntfy“ installieren (Android: Play Store/F-Droid, iPhone: App Store).
  2. „+“ antippen und das Thema aus `data\DASHBOARD_LINK.txt` eintragen (Server ntfy.sh).
  Das Thema ist geheim, es steht nur lokal und nicht im Repo.
- Abschalten getrennt möglich: `PUSH_SIGNALS_ENABLED` / `PUSH_HOURLY_ENABLED` in `.env`.
- Echte E-Mail ohne Konto gibt es nicht. ntfy.sh hat anonymen Mailversand wegen Missbrauchs abgeschaltet.
  Konten anlegen (Resend, Google Cloud, Discord) darf Claude nicht selbst, das musst du machen (Anleitungen oben).

## Was du noch selbst tun musst
1. **E-Mail einschalten (ca. 5 min):**
   - Auf https://resend.com kostenlos registrieren, **mit gabriel.anter123@outlook.com**. Der Absender `onboarding@resend.dev` darf nur an die Konto-Adresse senden.
   - Unter „API Keys“ einen Key erstellen (Sending access).
   - In `.env` im Projektordner eintragen: `MAIL_PROVIDER=resend` und `RESEND_API_KEY=re_...`
   - Testen mit `python -m collector.cli test-mail`. Neu starten musst du nicht, `.env` wird bei jedem Lauf neu gelesen.
   - Gratis-Tarif: 100 Mails pro Tag, eingestellt ist eine Obergrenze von 90 (`MAIL_DAILY_CAP`).
2. **Dashboard einmal mit deinem Link öffnen** (aus `data\DASHBOARD_LINK.txt`) und am Handy anschauen. Getestet wurde nur mit headless Chrome.
3. Optional: `scripts\autostart-on.ps1` startet den Collector bei jeder Windows-Anmeldung.
4. Optional aufräumen: `dashboard\AGENTS.md` und `dashboard\CLAUDE.md` hat `next dev` erzeugt. Sie sind gitignoriert, ich durfte sie nicht löschen.

## Was nicht oder noch nicht läuft
- **Vercel-Konnektor:** verlangt eine neue Anmeldung (403). Das Dashboard läuft trotzdem; nur für spätere Änderungen per Werkzeug nötig: im Claude-Chat `/mcp` → vercel → Authenticate.
- **Analyse-Runde:** läuft stündlich um :23, aber nur solange diese Claude-Sitzung offen ist. Bei „weiter“ in einer neuen Sitzung neu anlegen (`prompts/analysis_round.md`).
- Die Mail-Links enthalten den Dashboard-Schlüssel (`#k=…`), er läuft also über Resend und dein Postfach. Für ein privates Werkzeug vertretbar.
- **Last auf FUTNext:** ca. 100–150 Seitenabrufe pro Lauf. Mit `FUTNEXT_SMART_SKIP=1` in `.env` sind es etwa ein Viertel davon, wenn du sie reduzieren willst.

## Befehle für die Sitzung
- „Stopp für heute“: Collector beenden (`scripts\stop.ps1`) und Stand hier festhalten.
- „weiter“: STATUS.md und `knowledge/` lesen, `scripts\start.ps1`, Analyse-Runde neu anlegen.
