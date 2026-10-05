# Trefferquote der Tipps (Lern-Agent / Analyse-Runde)

Quelle: Tabelle `tips` in data/fc27.sqlite (`python -m collector.cli tips`). Treffer = Verkauf mit Gewinn nach 5 % Steuer.

| Datum | Karte | Kauf | Verkauf | Ergebnis | Bemerkung |
|---|---|---|---|---|---|
| 05.10. 18:22 | Cucurella (DfG) | 110.000 | 208.000 | **ungültig** | Kaufpreis war ein Datenfehler (−47 % für 15 min, Schnitt ~209k). Seitdem gilt für Karten ≥ 100k: Sprung > 30 % zählt erst nach Bestätigung. |

Offen (Stand 05.10. 19:00): Jonathan David TOTW (Kauf 14.000), Mbappé DfG (Kauf 6.700.000) – beide „gering“ (< 1 Tag Daten).

**Lehre 05.10.:** Einzelne Ausreißer der Quelle sind die größte Fehlerquelle in den ersten Tagen; Kaufsignale ohne zweiten
bestätigenden Messpunkt sind deshalb höchstens „mittel“ – bei teuren Karten zusätzlich Filter 30 %.
| 05.10. 18:45 | Kylian Mbappé (DfG) | 6.700.000 | 7.450.000 | **Treffer** (+377.500 nach Steuer) | 2 Messpunkte bei 6,7 Mio., danach 7,45 Mio. – echte Bewegung |
| 05.10. 19:32 | Martin Ødegaard (TOTW) | 4.000 | 5.400 | **ungültig** | Einzelner Messpunkt zwischen 5.300/5.400 – unbestätigt. Seit 19:55 werden nur bestätigte Kaufsignale (≥ 2 Punkte) als Tipp gezählt. |
