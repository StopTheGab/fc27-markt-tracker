# STATUS – EA FC 27 Markt-Tracker

_Stand: 2026-10-05, ca. 11:15. Die Sitzung wurde wegen des Nutzungslimits früher beendet. Der Collector läuft weiter._

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

## Entscheidungen
1. **Futbin geht nicht:** Es blockt Bots (403), und laut ToS §13 ist Scraping verboten. FUTWIZ blockt ebenfalls (403). FUT.GG verbietet laut ToS automatisierten Zugriff, und die Preise kommen nur über `/api/`, das robots.txt sperrt. FUT-DB ist nicht erreichbar, der Preis-Endpunkt ist dort „premium“. **Gewählt: FUTNext**, weil robots.txt `Allow: /` erlaubt und die ToS Bots nicht verbieten. Details: `collector/sources/README.md`.
2. **Verschlüsselung:** Die FUTNext-Lizenz erlaubt nur „personal, non-commercial“ Nutzung und kein Spiegeln auf anderen Servern („mirror“). Deshalb liegen die Preise im öffentlichen Repo nur AES-256-GCM-verschlüsselt. Klartext ist nur `status.json`. Der Schlüssel `DATA_KEY` steht in `.env`.
3. **Keine Preishistorie:** Keine Quelle liefert sie regelkonform. Der 7-Tage-Schnitt baut sich also selbst auf. Bis ca. 08.10. sind alle Signale „gering“, ein voller 7-Tage-Schnitt steht ab 12.10.
4. **Verkaufssignale nur nach eigenem Kaufsignal:** Bestände kennt das Tool nicht. Sonst wäre jede zweite Karte ein „Verkauf“. Daraus ergibt sich auch die Trefferquote.
5. **Mail über Resend statt Outlook-SMTP:** Microsoft hat SMTP mit Passwort oder App-Passwort für Outlook.com am 16.09.2024 abgeschaltet. Es geht nur noch OAuth über eine Azure-App, und die hast du wegen der Kreditkarte abgelehnt. Ein Outlook-Konnektor war nicht verbunden, eine Testmail war deshalb nicht möglich.

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
- **Prüf-Agent:** Gestartet, aber wegen des Nutzungslimits nach kurzer Zeit abgebrochen. Kein Ergebnis. Bei „weiter“ neu starten (Auftrag siehe Gesprächsverlauf bzw. Prüfliste in `prompts/`).
- **Stündliche Analyse-Runde:** Wegen des Limits gestoppt. Bei „weiter“ wieder anlegen (`prompts/analysis_round.md`). Bis dahin zeigt das Dashboard die regelbasierte Einschätzung.
- **Eigene Gegenprobe der Preise:** Nur Stichproben. Mbappé 3,8 Mio., Haaland 120k (der Agent hat den Haaland-Preis mit Futbin verglichen: passt).
- **Last auf FUTNext:** ca. 100–150 Seitenabrufe pro Lauf. Mit `FUTNEXT_SMART_SKIP=1` in `.env` sind es etwa ein Viertel davon, wenn du sie reduzieren willst.

## Befehle für die Sitzung
- „Stopp für heute“: Collector beenden (`scripts\stop.ps1`) und Stand hier festhalten.
- „weiter“: STATUS.md und `knowledge/` lesen, `scripts\start.ps1`, Analyse-Runde neu anlegen.
