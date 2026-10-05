# Signalregeln für den Signal-Algorithmus

Stand: 2026-10-05, Quellen: die vier Nachbardateien in `knowledge/` (dort mit URL + Datum), v. a. fifplay.com "How to Trade in FC 27", timesaver.gg (2026-09-16/19/24/27), futcastfromos.beehiiv.com (2025-11-28, FC 26), realsport101.com Promo-Kalender (2026-09-15), fifauteam.com "FC 27 Price Ranges"/"Trading Tips", 11v11.com (2026-08-31), gamecurrency.net, GitHub FUT-Auto-Buyer (Preisstufen).

**Alle Schwellen sind Startwerte (eigene Ableitung, nicht von EA/Quellen vorgegeben)** und sollen nach 2–4 Wochen eigener Daten kalibriert werden. Zeiten in `Europe/Berlin`.

## 0. Begriffe
- Messraster 15 min → 96 Punkte/Tag, 672 Punkte/7 Tage. Nur **gültige** Punkte (nicht extinct, nicht leer, nicht als Ausreißer markiert).
- `p` = letzter gültiger Lowest BIN; `p_prev` = vorletzter.
- `ref7` = getrimmter Mittelwert (oben/unten je 5 % weg) der gültigen Punkte der letzten 7 Tage. Ersetzt den rohen "7-Tage-Durchschnitt" (robust gegen Fehllistings/Spikes, siehe R-ROBUST).
- `step(x)` = Preisstufe: <1.000→50; <10.000→100; <50.000→250; <100.000→500; sonst 1.000 (transfermarkt.md §4, [FC 27 unbestätigt]). `floor_step(x)` = auf Stufe abrunden.
- `vk_ziel` = floor_step(ref_ziel) − step(ref_ziel) (eine Stufe unterbieten, um tatsächlich zu verkaufen). `ref_ziel` = ref7, außer R-TREND/R-RELEASE ersetzen es.
- `gewinn` = vk_ziel × 0,95 − p; `gewinn_rel` = gewinn / p.
- `sicherheit` 0–100, Start 50. ≥ 70 = hoch, 40–69 = mittel, < 40 = niedrig. Fällt sie unter 25 → Signal unterdrücken.

## 1. Grundregel (unverändert)
- G-KAUF: `p ≤ 0,85 × ref7` UND `gewinn > 0` → Kaufsignal-Kandidat.
- G-VERKAUF: offene Position (nach Kaufsignal) UND `p ≥ ref7` → Verkaufssignal. Gewinn = `p × 0,95 − Kaufpreis`.
- Danach laufen die Zusatzregeln in der Reihenfolge Datenqualität → Markt → Karte → Zeit → Gewinn.

## 2. Datenqualität
| ID | Bedingung | Wirkung | Begründung / Quelle |
|---|---|---|---|
| R-FRISCHE | Alter(p) > 45 min | Kein Signal (weder Kauf noch Verkauf) | Datenbankpreise können veraltet sein (fifauteam "Trading Tips"; fifplay "outdated prices") |
| R-WENIGDATEN | Datenhistorie < 24 h → kein Signal; 24 h – < 3 Tage → sicherheit −25, Hinweis "wenig Daten" | Unterdrücken / senken | 7-Tage-Schnitt ohne 7 Tage ist nicht belastbar; Release-Phase verschiebt Niveau stark (timesaver 2026-09-19) |
| R-DATENLUECKE | Abdeckung 7 Tage < 70 % der erwarteten Punkte → sicherheit −15; Lücke > 6 h in letzten 24 h → Hinweis | Senken / Hinweis | Lücken verzerren ref7 Richtung der vorhandenen Tageszeiten (Wochenzyklus) |
| R-AUSREISSER | `p ≤ 0,60 × median(letzte 8 Punkte)` (−40 %) → Punkt "verdächtig", Signal erst wenn **2 Folgepunkte** innerhalb ±10 % von p liegen | Bestätigung abwarten | Einzelnes Fehllisting wird binnen Sekunden weggesnipt, nicht realisierbar (Sniping-Logik, fifplay) |
| R-BESTAETIGUNG | Jedes Kaufsignal braucht G-KAUF in **2 aufeinanderfolgenden** gültigen Punkten (30 min) | Bestätigung | Reduziert Rauschen durch einzelne Snapshots |
| R-ROBUST | `mean7 / median7 > 1,10` (Spike verzerrt Schnitt) → ref7 = median7, Hinweis "Spike im Schnitt" | Referenz ersetzen | Kurzer Hype (SBC-Leak, Extinct-Phase) bläht Mittelwert auf; "buying after a huge rise" (fifplay) |
| R-EXTINCT | Quelle meldet "extinct"/kein Angebot → Punkt ungültig; > 20 % ungültig in 7 Tagen → kein Signal | Unterdrücken | Extinct-Preis ist kein Marktpreis (fifauteam "Price Ranges"; earlygame-Suchtreffer DfG) |

## 3. Marktweite Regeln
| ID | Bedingung | Wirkung | Begründung / Quelle |
|---|---|---|---|
| R-CRASH | `median_watchlist(p_jetzt / p_vor24h − 1) ≤ −8 %` ODER ≥ 60 % der Karten −5 % in 24 h | **Crash-Modus**: Einzel-Kaufsignale unterdrückt, stattdessen 1 Markt-Hinweis "Crash"; Verkaufssignale bleiben | Promo/Lightning-Round-Abverkauf: FC 26 Index 85 −29,5 %, gesamt −12,9 % in einer Woche (futcast 2025-11-28) – fallendes Messer |
| R-CRASH-ENDE | Im Crash-Modus: Watchlist-Median der letzten 6 h ≥ −1 % UND ≥ 12 h seit Crash-Beginn | Crash-Modus aus; die nächsten 48 h Kaufsignale für Karten ≥ 85 Rating sicherheit +10 ("Floor") | FC 26: 85–88 nach Crash = Boden, Erholung bei großem SBC (futcast) |
| R-TREND | `t3 = median(Tag 0) / median(Tag −3) − 1` je Karte (Tagesmediane). t3 ≤ −10 % → kein Kaufsignal; −10 % < t3 ≤ −4 % → ref_ziel = min(ref7, Mittel letzte 72 h), sicherheit −15 | Unterdrücken / Ziel senken | 7-Tage-Schnitt überschätzt Erholung bei strukturellem Fall; "cards may not recover" (fifplay); Release-Abwärtstrend (fifplay "Market Around a Launch") |
| R-RELEASE | Datum < 2026-11-06 (6 Wochen nach Launch 25.09.) | sicherheit −10; ref_ziel = min(ref_ziel, Mittel letzte 72 h); Hinweis "Release-Phase" | Markt erst nach ~6 Wochen "settled"; Gold-Markt erreicht EA-Niveau nicht wieder (fifplay; timesaver 2026-09-19) |

## 4. Kartenbezogene Regeln
| ID | Bedingung | Wirkung | Begründung / Quelle |
|---|---|---|---|
| R-UNTERGRENZE | Range-Minimum bekannt und `p ≤ min + step(p)`; sonst Ersatz: `p ≤ 700` (≈ Quick-Sell-Boden Gold 533–646) | Kein Kaufsignal, Hinweis "am Boden" | Am Minimum staut sich Angebot, Erholung ungewiss, Gewinn nach Steuer minimal (fifauteam "Price Ranges"; timesaver 2026-09-19) |
| R-OBERGRENZE | Range-Maximum bekannt und `p ≥ max − step(p)` | Kein Signal; Hinweis "an Obergrenze / extinct-gefährdet" | Preis gedeckelt, kein echter Marktpreis; Range-Anhebung unvorhersehbar (fifauteam) |
| R-LIQUIDITAET | `n_wechsel24` = Anzahl Preisänderungen zwischen aufeinanderfolgenden Punkten in 24 h. < 4 → kein Kaufsignal; 4–7 → sicherheit −15; ≥ 20 → +5 | Unterdrücken / senken / erhöhen | Illiquide Karten: Verkauf dauert, Preis springt (fifplay: "frequently traded cards") |
| R-VOLATIL | Variationskoeffizient (std/mean) der 7 Tage > 25 % | sicherheit −10, Hinweis | Unruhige Karten: −15 % ist dort normales Rauschen |
| R-SPIKE | `p ≥ 1,30 × ref7` | Hinweis "Hype" bei offener Position: Verkauf erwägen; nie Kauf | Gewinn mitnehmen, nicht ins Hoch kaufen (fifplay) |
| R-FUTTER | Karte ist reine Rating-Karte (Gold 84–87, keine Meta-Markierung) | Hinweis "Futter – Preis folgt SBC-Wellen, nur in Menge sinnvoll"; Kaufsignal sicherheit −5 | FC-27-Score-SBCs: Nachfrage am Rating, 85er am stärksten (timesaver 2026-09-16/24) |

## 5. Zeitbezogene Regeln
| ID | Bedingung | Wirkung | Begründung / Quelle |
|---|---|---|---|
| R-WOCHE-TIEF | Kaufsignal So 21:00 – Mo 12:00 | sicherheit +10 | Abverkauf nach Weekend League (gamecurrency.net; 11v11.com 2026-08-31) |
| R-WOCHE-REWARD | Kaufsignal Do 08:00 – 14:00 und p < 10.000 | sicherheit +5 | Rivals-Rewards fluten billige Karten, "dips hard for a few hours" (timesaver 2026-09-24; fifplay Rivals) |
| R-WOCHE-HOCH | Verkaufssignal Do 14:00 – Fr 22:00 → sicherheit +10; offene Position mit `p ≥ 0,97 × ref7` in diesem Fenster → Hinweis "Wochenhoch, Verkauf erwägen" | Erhöhen / Hinweis | Do-Nachmittag/Fr-Abend Nachfrage vor Weekend League (11v11.com; gamecurrency.net) |
| R-PROMO-VOR | 48 h vor Promo-Start (Kalender in Config, Fr 19:00) und p ≥ 10.000 | sicherheit −25, Hinweis "Promo steht an – Abverkauf wahrscheinlich" | Spieler verkaufen vor/zu Promos (futcast FC 26); Kalender realsport101 (2026-09-15) |
| R-PROMO-NACH | 0–36 h nach Promo-Start | Kaufsignal nur, wenn in den letzten 4 h **kein** neues 7-Tage-Tief; sonst unterdrücken | Tief kommt meist erst nach dem Drop (Erfahrungswert, unsicher); fallendes Messer |
| R-CONTENTDROP | Messpunkt täglich 18:45 – 20:15 | Bestätigung mit 3 statt 2 Punkten; sicherheit −5 | Tägliche Content-Zeit 18:00 UK = 19:00 DE, höchste Volatilität (realsport101) |

**Promo-Kalender-Startwerte (Config, "expected" außer DfG):** 2026-10-09 Future Stars · 10-23 Ultimate Scream · 11-06 Road to the Knockouts · 11-20 Hall of FUT · 11-27 Black Friday · 12-04 · 12-11 Winter Wildcards · 12-25 · 2027-01-15 TOTY (alle Fr 19:00).

## 6. Gewinn- und Ablaufregeln
| ID | Bedingung | Wirkung | Begründung / Quelle |
|---|---|---|---|
| R-MINGEWINN | `gewinn ≥ 500` UND `gewinn_rel ≥ 5 %` (beides mit vk_ziel, also nach Steuer und einer Stufe Unterbieten) | Sonst Kaufsignal unterdrücken; 500–999 → sicherheit −10; ≥ 3.000 → +5 | Steuer + Stufen fressen kleine Margen ("9,900 does not leave enough margin", fifplay). 5 % Puffer gegen Messfehler/Abweichung Lowest BIN ↔ echter Verkauf |
| R-STUFE | Alle ausgegebenen Kauf-/Zielpreise auf Preisstufe runden (Kauf: floor_step, Ziel: vk_ziel) | Formatierung | Preise sind diskret (transfermarkt.md §4) |
| R-SPERRE | Nach Kaufsignal für Karte X: 24 h kein neues Kaufsignal für X, außer `p ≤ 0,90 × p_letztes_signal`; Verkaufssignal je Position nur 1×; Mail je Karte max. 1 pro 6 h | Unterdrücken | Kein Signal-Spam bei andauerndem Dip |
| R-VERLUST | Offene Position, `p ≤ 0,85 × Kaufpreis` UND t3 ≤ −4 % | Hinweis "Verlust > 15 %, Abwärtstrend – Ausstieg prüfen" (kein Auto-Verkaufssignal) | Kein Panikverkauf, aber Trend ernst nehmen (fifplay; fifauteam "Reassess if reasoning invalid") |
| R-TIMEOUT | Offene Position älter als 7 Tage ohne Verkaufssignal | Hinweis; Verkaufsziel auf aktuelles ref7 neu berechnen | Ref verschiebt sich; Coins nicht ewig binden (fifauteam) |
| R-KONZENTRATION | Optional bei konfiguriertem Budget B: Kaufpreis > 10 % von B | Hinweis "Klumpenrisiko" | Nicht alles in eine Karte (fifplay; fifauteam) |

## 7. Ausgabe je Signal (Vorschlag)
`karte, typ (KAUF/VERKAUF/HINWEIS), p, ref7, ref_ziel, vk_ziel, gewinn, gewinn_rel, sicherheit (Zahl + Stufe), regeln_angewandt [IDs], hinweise [Text]`.

## 8. Parameter-Übersicht (für Config)
```
DIP_SCHWELLE=0.15  BESTAETIGUNG_PUNKTE=2  CONTENTDROP_PUNKTE=3  TRIM=0.05  SPIKE_RATIO_MEAN_MEDIAN=1.10
FRISCHE_MAX_MIN=45  MIN_HISTORIE_H=24  WENIG_DATEN_TAGE=3  ABDECKUNG_MIN=0.70  LUECKE_H=6  EXTINCT_MAX_ANTEIL=0.20
AUSREISSER_DROP=0.40  AUSREISSER_TOLERANZ=0.10  AUSREISSER_FOLGEPUNKTE=2
CRASH_MEDIAN_24H=-0.08  CRASH_BREITE=0.60@-0.05  CRASH_ENDE_6H=-0.01  CRASH_MIN_DAUER_H=12  FLOOR_BONUS_H=48
TREND_STOP=-0.10  TREND_WARN=-0.04  RELEASE_ENDE=2026-11-06
LIQ_STOP=4  LIQ_WARN=7  LIQ_GUT=20  CV_MAX=0.25  SPIKE_HINWEIS=1.30  BODEN_ERSATZ=700
PROMO_VOR_H=48  PROMO_NACH_H=36  PROMO_MIN_PREIS=10000  REWARD_MAX_PREIS=10000
MIN_GEWINN=500  MIN_GEWINN_REL=0.05  SPERRE_H=24  SPERRE_NACHKAUF=0.90  MAIL_SPERRE_H=6
VERLUST_HINWEIS=0.15  TIMEOUT_TAGE=7  KONZENTRATION=0.10  SICHERHEIT_START=50  SICHERHEIT_STOP=25
```

## 9. Offene Punkte / Unsicherheiten
- Preisstufen und Listen-Limits für FC 27 nicht offiziell bestätigt (transfermarkt.md §4/§5).
- Price-Range-Min/Max je Karte liefert unsere Quelle evtl. nicht → R-UNTERGRENZE/R-OBERGRENZE laufen dann nur mit Ersatzwerten.
- Wochenfenster und Crash-Schwelle sind aus Vorjahren/Guides abgeleitet; nach 4 Wochen eigener Daten mit realen Signal-Trefferquoten kalibrieren.
