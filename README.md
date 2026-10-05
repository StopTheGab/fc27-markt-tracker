# FC27 Markt-Tracker (PlayStation)

Persönliches Werkzeug: Ein lokaler Python-Collector sammelt alle 15 Minuten Marktpreise einer Watchlist von
EA-FC-27-Ultimate-Team-Karten, berechnet Kauf-/Verkaufssignale (Grundregel: ≥ 15 % unter 7-Tage-Schnitt,
5 % EA-Steuer eingerechnet), pusht JSON in den Branch `data` und verschickt Signal-Mails und Stunden-Updates.
Das Next.js-Dashboard in `dashboard/` (Vercel) lädt die JSON-Dateien zur Laufzeit.

Keine Anlageberatung, kein EA-Login, keine Automatisierung der EA-Apps – es werden nur öffentlich erlaubte Preise gelesen.

| Was | Wo |
|---|---|
| Start / Stopp (Windows) | `start-collector.cmd` / `stop-collector.cmd` (oder `scripts\start.ps1`, `scripts\stop.ps1`) |
| Zustand | `python -m collector.cli status` |
| Einmaliger Lauf | `python -m collector.main --once` |
| Testmail | `python -m collector.cli test-mail` |
| Watchlist neu recherchieren | `scripts\watchlist-refresh.ps1` |
| Signal-Parameter | `rules.json` (Herleitung: `knowledge/signalregeln.md`) |
| Datenformat | `docs/DATA_CONTRACT.md` |
| Zugangsdaten | `.env` (Vorlage `.env.example`, nie im Repo) |
| Tests | `python -m unittest discover tests` |
