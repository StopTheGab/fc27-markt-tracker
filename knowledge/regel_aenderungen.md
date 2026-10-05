# Regel-Änderungen (Signal-Algorithmus)

Parameter stehen in `rules.json`, Code in `collector/analysis.py`. Grundlage: `knowledge/signalregeln.md`.
Jede Änderung hier mit Datum, Grund und Quelle eintragen (auch durch den Lern-Agent).

## 2026-10-05 – Erstfassung (Koordinator)

**Grundregeln (fest):** Kauf bei Preis ≥ 15 % unter 7-Tage-Schnitt · Verkauf, wenn Preis wieder ≥ 7-Tage-Schnitt
· Gewinn = Verkaufspreis × 0,95 − Kaufpreis · nur Kaufsignale mit positivem Gewinn · < 3 Tage Daten ⇒ „gering“.

**Umsetzungsentscheidungen:**
- 7-Tage-Schnitt = getrimmter Mittelwert (5 % je Seite) der **Stundenmittel** – Datenlücken (PC aus) verzerren den
  Schnitt so nicht; Abdeckung (Anteil Stunden mit Messwert) senkt bei < 70 % die Sicherheit. (R-ROBUST, R-DATENLUECKE)
- Verkaufssignale nur für Karten mit offenem Kauf-Tipp (wir kennen keine Bestände; sonst wäre jede zweite Karte ein
  „Verkauf“). Der Tipp wird beim Verkaufssignal geschlossen ⇒ Trefferquote. Tipps ohne Erholung nach 7 Tagen ⇒ geschlossen mit Ist-Preis.
- Übernommen aus signalregeln.md: R-FRISCHE (Preis älter 45 min ⇒ kein Signal), R-BESTAETIGUNG (2 Punkte, sonst max. „mittel“),
  R-AUSREISSER (Sprung ≥ 30 % in 15 min ⇒ „gering“), R-CRASH (Median ≤ −8 % in 24 h **oder** ≥ 60 % der Karten ≤ −5 %
  **oder** ≥ 35 % aller Karten gleichzeitig Kaufkandidat ⇒ Crash statt Einzelsignale), R-TREND (72-h-Trend ≤ −10 % ⇒ max. „mittel“),
  R-RELEASE (bis 06.11.2026 Verkaufsziel = min(7-Tage-, 72-h-Schnitt)), R-UNTERGRENZE (Preis ≤ 700 oder ≤ Range-Min + 5 % ⇒ kein Kauf),
  R-LIQUIDITAET (< 4 Preisänderungen in 24 h ⇒ kein Kauf, < 7 ⇒ max. „mittel“), R-VOLATIL (VK > 25 % ⇒ max. „mittel“),
  R-PROMO-VOR (Promo-Start in ≤ 48 h und Preis ≥ 10.000 ⇒ max. „mittel“), Wochenphase als Begründung, R-MINGEWINN (≥ 500 Coins und ≥ 5 %).
- **Nicht übernommen:** R-WENIGDATEN „kein Signal < 24 h“ – widerspricht der Vorgabe (Signale < 3 Tage zeigen, als „gering“);
  stattdessen Mindestens 6 h Daten. R-STUFE, R-CONTENTDROP, R-SPIKE, R-KONZENTRATION, R-EXTINCT (Quelle liefert dafür
  vorerst keine Daten) – Kandidaten für später.
- Mail-Wiederholung: Vorgabe des Users (neu, wenn beim letzten Abruf kein Signal; nach Verschwinden frühestens nach 2 h
  wieder neu) statt R-SPERRE (24 h).
