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

## 2026-10-05 17:45 – Signal-Logik v2 (Entscheidung des Users: Empfehlung B + C + F, dazu D/E als Hinweise)

**Anlass:** Echte Daten 11–17 Uhr (94 Karten ≥ 10.000): tiefster Punkt im Median nur −3,7 % unter eigenem Schnitt,
nur 4 Karten ≤ −8 %, echte −15 % praktisch nie. Die feste 15-%-Regel lieferte so keine Signale. Wegen 5 % Steuer lohnt
ein Kauf erst ab ca. −8 % (Gewinn = 0,95 × Schnitt − Preis).

- **F – Limits je Karte:** Kauflimit = 7-Tage-Schnitt × (1 − Schwelle), abgerundet auf Preisstufe; Verkaufslimit = 7-Tage-Schnitt, aufgerundet.
- **B – Schwelle je Karte:** Schwelle = max(8 %, 2 × Schwankung der Karte [Variationskoeffizient der Stundenmittel]), höchstens 20 %.
  Kaufsignal, wenn Preis ≤ Kauflimit; ≥ 15 % unter Schnitt = **starkes Signal** (alte Grundregel).
- **C – Wochenzyklus:** Wochentief (So 21:00 – Mo 12:00, Di ganztägig) hebt „mittel“ → „hoch“ (nur mit ≥ 3 Tagen Daten);
  Wochenhoch (Do 14:00 – Fr 22:00) senkt Kauf auf max. „mittel“ und löst bei offenen Tipps Verkauf ab 97 % des Schnitts aus.
- **D – Promo:** Promo-Start in ≤ 48 h → Verkaufssignal für offene Tipps (Meta/Promo-Karten ≥ 10.000), Kauf max. „mittel“.
- **E – Creator:** Kauf-Tipp der letzten 48 h zur Karte (FIFAllstars vor TheFutAccountant) hebt Sicherheit; Verkaufs-Tipp → Verkaufssignal.
- Unverändert: Verkauf nur mit Gewinn nach Steuer, Crash statt Einzelsignale, < 3 Tage = „gering“, Preisgrenzen, Liquidität, Ausreißerfilter (neu: Punkte > 50 % vom Median gelten erst nach Bestätigung).
- Preisstufen (50/100/250/500/1.000) sind für FC 27 nicht offiziell bestätigt (transfermarkt.md).
