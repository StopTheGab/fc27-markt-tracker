# Transfermarkt EA FC 27 – Grundlagen

Stand: 2026-10-05, Quellen: fifauteam.com (FC 27 Transfer Market, FC 27 Price Ranges), fifplay.com (FC 27 Transfer Market, How to Trade), 11v11.com (FC 27 Buyers Guide, 2026-08-31), timesaver.gg (diverse, 2026-09-16 bis 2026-09-27), fut.gg (Streamlined SBCs, 2026-08-02; Price-Ranges-Seite), allthings.how (2026-08-02), GitHub DevFRpyjs/FUT-Auto-Buyer (Preisstufen, Stand 2023).

Legende: **[gesichert]** = mehrere FC-27-Quellen; **[FC 27 unbestätigt]** = nur aus Vorjahren/Einzelquelle; **[unsicher]** = widersprüchlich.

## 1. Auktionsprinzip, Lowest BIN vs. Durchschnitt
- Jedes Angebot hat Startpreis (Mindestgebot) und Sofortkaufpreis ("Buy It Now", BIN). Verkauf entweder per Sofortkauf oder an das Höchstgebot bei Ablauf. Quelle: fifplay.com "FC 27 Transfer Market" (o. D.), fifauteam.com "FC 27 Transfer Market" (o. D.). [gesichert]
- **Lowest BIN** = günstigster aktuell gelisteter Sofortkaufpreis einer Karte. Das ist ein *Angebots*-Preis, kein realisierter Verkaufspreis. Preisseiten zeigen meist Lowest BIN; "Durchschnitt" (z. B. 7-Tage-Schnitt in unserem Tool) ist eine Glättung über diese Snapshots, kein Verkaufsdurchschnitt.
- Datenbank-Preise "may be delayed or differ from the live Transfer Market" – vor jedem Kauf im Spiel prüfen. Quelle: fifauteam.com "FC 27 Trading Tips" (o. D.). [gesichert]
- Folge fürs Tool: Ein einzelner sehr niedriger Lowest BIN kann ein Fehllisting sein, das binnen Sekunden weggesnipt wird → nicht realisierbar (siehe signalregeln.md, Regel R-AUSREISSER).

## 2. EA-Steuer
- 5 % auf jeden abgeschlossenen Verkauf, zahlt der Verkäufer. Beispiel: Kauf 2.200, Verkauf 2.700 → Erlös 2.565, Gewinn 365. Quelle: fifauteam.com "FC 27 Trading Tips"; fifplay.com "FC 27 How to Trade" (Beispiel 10.000 → 9.500). [gesichert]
- Break-even: Verkaufspreis muss ≥ Kaufpreis / 0,95 ≈ Kaufpreis × 1,0526 sein.

## 3. Preisgrenzen (Price Ranges)
- Jedes Item hat Min/Max; weder Listing noch Gebot außerhalb möglich (gilt für Käufer und Verkäufer). Quelle: fifauteam.com "FC 27 Price Ranges" (o. D.). [gesichert]
- Festlegung/Anpassung: EA beobachtet Durchschnittsverkaufspreise und den Anteil verkaufter an allen Listings; neue Items bekommen Ranges anhand vergleichbarer Items. **Kein fester Rhythmus**; verkauft sich eine Karte dauerhaft am Maximum, *kann* EA die Range anheben – nicht garantiert, nicht sofort. Quelle: fifauteam.com "FC 27 Price Ranges". [gesichert, Einzelquelle]
- Mindestpreis liegt auf/über dem Quick-Sell-Wert. Quelle: ebd. Quick-Sell-Böden Gold FC 27: 533–646 Coins je nach Rating. Quelle: timesaver.gg "FC 27 sell or hold – early access market crash timeline" (2026-09-19). [FC 27, Einzelquelle]
- **Karte am Maximum = "extinct"**: Niemand listet zum Höchstpreis → keine Angebote, Preisseiten zeigen "Extinct". Beispiel FC 27 DfG Team 1: Kika Nazareth und Rashford "extinct" bei 50.000. Quelle: Suchtreffer earlygame.com "EA FC 27: Destined for Glory startet mit Live-Items" (ca. 2026-09/10). fut.gg zeigt Range-Updates mit Vermerk "Extinct before" (z. B. Min 30K→500K, Max 4M→8M) – **die sichtbaren Einträge sind auf 2024 datiert (vermutlich FC-25-Daten)** [unsicher]. Quelle: fut.gg/price-ranges (abgerufen 2026-10-05).
- **Karte am Minimum**: Preis kann nicht weiter fallen, Angebot staut sich; Verkauf oft nur zum Minimum oder gar nicht → Kaufsignal sinnlos (kein Abwärtsrisiko, aber auch keine Erholung absehbar, da Überangebot). Ableitung, keine Primärquelle.
- **Widerspruch zu konkreten Range-Werten**: fifauteam.com nennt Tabelle (z. B. Base 87–99: 10K–500K; Special: 150–10K). Die Special-Werte sind offensichtlich unplausibel (Promo-Karten kosten 50K+) → **[unsicher, nicht verwenden]**. Ranges pro Karte sind individuell.

## 4. Preisschritte (Bid-Increments)
| Preisbereich | Schritt |
|---|---|
| < 1.000 | 50 |
| 1.000 – < 10.000 | 100 |
| 10.000 – < 50.000 | 250 |
| 50.000 – < 100.000 | 500 |
| ≥ 100.000 | 1.000 |
- Absolutes Maximum laut Web-App-Code: 14.999.000. Quelle: GitHub DevFRpyjs/FUT-Auto-Buyer `app/utils/priceUtils.js` (letzter Push 2023-10-25, nutzt `UTCurrencyInputControl.PRICE_TIERS` der Web-App). **[FC 27 unbestätigt]** – seit vielen Jahren unverändert, keine FC-27-Quelle mit Tabelle gefunden. Untergrenze 150 Coins für die meisten Items: fifauteam.com "FC 27 Price Ranges".
- Folge fürs Tool: Preise sind diskret; ein "15 % unter Schnitt" bei 750-Coin-Karten bedeutet nur 2–3 Stufen.

## 5. Listing-Dauer, Listen-Limits
- Widerspruch: fifplay.com nennt 1/3/6/12 h; fifauteam.com nennt 1/3/6/12 h, 1 Tag, 3 Tage. [unsicher] – für Trading ist 1 h üblich.
- Transferliste/Beobachtungsliste: Keine FC-27-Quelle mit Zahl gefunden. Aus Vorjahren üblich: Transferliste 100, Transferziele 50. **[FC 27 unbestätigt, Erfahrungswert]**.
- Neue Accounts: Markt erst nach drei "Graduated Access"-Objective-Gruppen, ca. 24–48 h. Quelle: fifauteam.com "FC 27 Transfer Market".

## 6. Handelsbeschränkungen
- Untradeable-Belohnungen (SBC, viele Objectives, untradeable Packs) nie handelbar. Quelle: fifplay.com "FC 27 Transfer Market". [gesichert]
- Evolutions: Karte wird mit Eintritt in einen Evolution-Slot untradeable. Quelle: fifauteam.com "FC 27 Evolutions". **Neu in FC 27**: Evolutions können entfernt werden; war die Karte vorher tradeable, ist sie nach Entfernen *aller* Evolutions wieder handelbar (endgültig, Evo-Eintritt verloren). Quelle: timesaver.gg "FC 27 remove evolution tradeable again" (2026-09-27, zitiert EA). → Evo-Karten können zurück auf den Markt kommen (Zusatzangebot). [Einzelquelle]
- Kein Coin-Transfer zwischen eigenen Accounts (Sperrgefahr). Quelle: 11v11.com (2026-08-31).

## 7. Neu in FC 27 (marktrelevant)
- **Streamlined SBCs (Score-System)**: Player- und Upgrade-SBCs verlangen nur noch eine Punktsumme, keine Liga/Nation/Chemie; Duplikate erlaubt, Teilfortschritt speicherbar. Challenge-SBCs (Daily Puzzles, Marquee Matchups) und Elite-SBCs bleiben klassisch. Quelle: fut.gg News "What are Streamlined SBCs" (2026-08-02); allthings.how (2026-08-02). [gesichert]
- Punkte je Rating (Gold): 87 = 5.500, 86 = 4.100, 85 = 2.900, 84 = 830, 83 = 410, ≤ 82 = 20–35. Quelle: timesaver.gg "FC 27 FUT market launch week – trading 85s" (2026-09-16/24, zitiert fifauteam). [Einzelquelle] → Futternachfrage hängt fast nur am **Rating**, Liga/Nation-Futter verliert an Bedeutung.
- **FUT Gallery**: permanente Sammlung, Karten werden registriert ohne sie abzugeben; Holo-/Promo-Items geben viele Punkte. Kein Einfluss auf Handelbarkeit bekannt. Quelle: allthings.how (2026-08-02).
- Keine Carryover-Coins aus FC 26; Rivals-Packs zum Start handelbar. Quelle: timesaver.gg (2026-09-24).
- Ca. fünf Kampagnenwochen weniger als FC 26 (langsamere Power-Curve). Quelle: realsport101.com Promo-Kalender (2026-09-15).

## 8. Plattform-Märkte
- Markt 1: PS5/PS4/Xbox Series/One **gemeinsam**; Markt 2: PC getrennt; Markt 3: Switch. Seit FUT 23. Quelle: fifauteam.com "FC 27 Transfer Market"; Suchtreffer fifplay.com; 11v11.com: "PC currency cannot be transferred to PlayStation or Xbox". [gesichert]
- Folge: "PS-Preis" = Konsolenpreis (PS+Xbox); Futbin/FUT.GG-Werte für "Console" sind passend, PC-Werte nicht mischen.

## 9. Preisquellen Futbin vs. FUT.GG
- Beide zeigen Lowest-BIN-Snapshots; Aktualisierungszeit je Karte unterschiedlich (beliebte Karten öfter). Kein belastbarer Vergleich der Genauigkeit gefunden. [unsicher]
- Praxis: Abweichungen von 1–2 Preisstufen zwischen Seiten sind normal (unterschiedlicher Abfragezeitpunkt). fut.gg ist laut Semrush engster Konkurrent von futbin.com (Suchtreffer semrush.com, 2025-10-15).
- Für das Tool: **eine** Quelle konsistent verwenden; Quellwechsel nicht als Preisbewegung werten.
