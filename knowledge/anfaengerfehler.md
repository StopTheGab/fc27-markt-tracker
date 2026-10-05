# Typische Anfängerfehler beim FUT-Trading

Stand: 2026-10-05, Quellen: fifplay.com "How to Trade in FC 27 Ultimate Team" (o. D., FC 27; Abschnitt "Critical Mistakes"), fifauteam.com "FC 27 Trading Tips" (o. D.), 11v11.com "FC 27 Buyers Guide" (2026-08-31), timesaver.gg (2026-09-19, 2026-09-24, 2026-09-27), fifplay.com "FUT Market Around a Launch" (o. D.), futcastfromos.beehiiv.com (2025-11-28, FC 26), fut.gg/price-ranges.

Jeder Fehler mit Gegenmaßnahme im Tool (Verweis auf Regel-ID in signalregeln.md).

## 1. 5 % Steuer vergessen
- Beispiel: Marktpreis 10.000, Kauf 9.900 → Verkauf bringt 9.500 → Verlust. Quelle: fifplay.com.
- Break-even = Kauf / 0,95. Bei 1.000er-Karten frisst die Steuer + eine Preisstufe (100) schon 15 %.
- Tool: Gewinn immer `VK × 0,95 − EK`; R-MINGEWINN.

## 2. In den Hype kaufen ("Buying after a huge rise")
- Nach starkem Anstieg (SBC-Leak, Influencer-Tipp) kaufen → Rückgang. "Public trading tips can cause a card to rise before you buy." Quelle: fifplay.com.
- Promo-Karten in den ersten Stunden kaufen: Preise fallen, sobald Packs geöffnet werden (fifplay.com "Promo Flipping"; fifplay "Market Around a Launch").
- Tool: nur Kaufsignale *unter* Schnitt; R-PROMO-VOR, R-PROMO-NACH, R-SPIKE.

## 3. Zu viele Coins in eine Karte
- "Investing entire Coin balance in single player" als Kardinalfehler. Quelle: fifplay.com; fifauteam.com: diversifizieren, Coins liquide halten. timesaver.gg: 50–100K Reserve zum Launch.
- Tool: Hinweis R-KONZENTRATION (max. Anteil je Karte).

## 4. Illiquide Karten handeln
- Wenig gehandelte Karten: Lowest BIN springt, Verkauf dauert, Spread groß; Einstieg mit "inexpensive, frequently traded cards" empfohlen (fifplay.com).
- Tool: R-LIQUIDITAET (Anzahl Preisänderungen / Datenpunkte).

## 5. Preisgrenzen ignorieren
- Karte am Minimum: fällt nicht weiter, aber Überangebot → Verkauf nur zum Minimum, kein Gewinn nach Steuer.
- Karte am Maximum ("extinct"): keine Angebote, angezeigter Preis ist kein Marktpreis; Range-Erhöhung durch EA kommt unvorhersehbar (fifauteam.com "Price Ranges"; Beispiel Rashford/Nazareth extinct bei 50K, earlygame.com-Suchtreffer).
- Tool: R-UNTERGRENZE, R-OBERGRENZE.

## 6. Extinct-Karten bewerten
- Preisseiten zeigen "Extinct" oder letzten bekannten Preis → 7-Tage-Schnitt verfälscht. Nach Range-Anhebung springt der Preis um ein Vielfaches (fut.gg zeigt z. B. 30K–4M → 500K–8M, Daten vermutlich FC 25) [Beispiel unsicher].
- Tool: Extinct-Messpunkte nie als Preis speichern (R-DATENLUECKE, R-EXTINCT).

## 7. Pack-Glück falsch bewerten
- Gezogene Karte zum angezeigten Lowest BIN "wert" rechnen, obwohl sie nach Steuer und Unterbieten deutlich weniger bringt; Promo-Packs sind auf billige Karten gewichtet [Suchtreffer, unsicher]. 11v11.com: FC Points während Standard-Promos bringen meist schwache Packs.
- Tool: Bestandswerte immer `Lowest BIN × 0,95 − 1 Preisstufe` ansetzen (Hinweis, keine Regel).

## 8. Panikverkauf bei temporären Dips
- "Panic selling on temporary drops" (fifplay.com); "Have a plan and avoid panic selling" (fifauteam.com). Promo-Crashs erholten sich in FC 26 bei großen SBCs (futcast).
- Tool: Verkaufssignal nur bei Erholung; kein automatisches Stop-Loss-Signal (optional Hinweis R-VERLUST).

## 9. Veraltete Preise nutzen
- "Using outdated prices during busy content periods"; Datenbankpreise können verzögert sein (fifplay.com; fifauteam.com).
- Tool: R-FRISCHE (Messpunkt-Alter), R-CONTENTDROP.

## 10. Release-Phase falsch lesen
- Nach Launch fallen fast alle Preise über Wochen; Gold-Markt kehrt nicht auf Early-Access-Niveau zurück (timesaver.gg 2026-09-19). Wer jeden "Dip" kauft, kauft in einen Abwärtstrend.
- Tool: R-TREND, R-RELEASE.

## 11. Gewinn nicht mitnehmen
- "Consider taking your profit rather than automatically waiting for an even higher price" (fifplay.com); Zielpreis vorab setzen (fifauteam.com).
- Tool: Verkaufssignal bei Erreichen des Schnitts, nicht auf Hoch warten.

## 12. Untradeable/Evo verwechseln
- Karte in Evolution gesteckt → untradeable; in FC 27 nur durch Entfernen *aller* Evos wieder handelbar, Evo-Fortschritt weg (timesaver.gg 2026-09-27).
- SBC-/Objective-Karten nie handelbar – nicht als Coin-Wert zählen.

## 13. Coins zwischen eigenen Accounts schieben
- Führt zu Sanktionen (11v11.com, 2026-08-31). Coin-Kauf bei Drittanbietern ebenso Bann-Risiko [allgemein bekannt, EA-AGB].

## 14. Zu viele Märkte gleichzeitig
- "Trade only 10 well-understood markets rather than hundreds poorly understood" (fifplay.com). Für das Tool: Signale priorisieren statt alle 100–200 Karten gleich zu gewichten.
