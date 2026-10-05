"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useData, useHasPrices } from "@/components/DataProvider";
import { PriceChart, withRollingAvg } from "@/components/PriceChart";
import { ConfidenceBadge, LoadNotice, NoPricesNotice, Pct, SignalBadge } from "@/components/ui";
import { loadJson } from "@/lib/data";
import { coins, dateTime, isNum, num, relative, signedCoins } from "@/lib/format";
import type { HistoryFile, Loaded } from "@/lib/types";

export default function CardPage() {
  return (
    <Suspense fallback={<div className="panel empty">Lade …</div>}>
      <CardDetail />
    </Suspense>
  );
}

const RANGES = [
  { id: "24h", label: "24 h", hours: 24 },
  { id: "3d", label: "3 Tage", hours: 72 },
  { id: "7d", label: "7 Tage", hours: 168 },
  { id: "all", label: "Alles", hours: 0 },
] as const;

function CardDetail() {
  const params = useSearchParams();
  const id = (params.get("id") || "").trim();
  const { cards, signals, status, loadedAt, now } = useData();
  const hasPrices = useHasPrices();
  const [history, setHistory] = useState<Loaded<HistoryFile>>({ state: "loading" });
  const [range, setRange] = useState<(typeof RANGES)[number]["id"]>("7d");

  // Verlauf laden und bei jedem Neuladen der Hauptdaten (alle 5 min) mitaktualisieren
  useEffect(() => {
    if (!id || !/^[\w.-]+$/.test(id)) return;
    const ac = new AbortController();
    loadJson<HistoryFile>(`history/${encodeURIComponent(id)}.json`, ac.signal).then((r) => {
      if (ac.signal.aborted) return;
      setHistory((prev) => (r.state === "error" && prev.state === "ok" ? prev : r));
    });
    return () => ac.abort();
  }, [id, loadedAt]);

  const card = cards.state === "ok" ? cards.data.cards.find((c) => c.id === id) : undefined;
  const signal = signals.state === "ok" ? signals.data.signals.find((s) => s.card_id === id) : undefined;

  const points = useMemo(
    () => (history.state === "ok" && Array.isArray(history.data.points) ? withRollingAvg(history.data.points) : []),
    [history],
  );
  const lastT = points.length ? points[points.length - 1].t : now;
  const firstT = points.length ? points[0].t : now;
  const hours = RANGES.find((r) => r.id === range)?.hours ?? 0;
  const from = hours ? Math.max(firstT, lastT - hours * 3600_000) : firstT;
  const inRange = points.filter((p) => p.t >= from && isNum(p.p)).map((p) => p.p as number);
  const rangeMin = inRange.length ? Math.min(...inRange) : null;
  const rangeMax = inRange.length ? Math.max(...inRange) : null;

  if (!id) {
    return (
      <div className="panel empty">
        Keine Karte ausgewählt. <Link href="/karten">Zur Kartenliste</Link>
      </div>
    );
  }
  if (cards.state !== "ok") return <LoadNotice loaded={cards} what="Kartenliste" />;
  if (!card) {
    return (
      <div className="panel empty">
        Karte <code>{id}</code> ist nicht in der Watchlist. <Link href="/karten">Zur Kartenliste</Link>
      </div>
    );
  }

  const interval = (status.state === "ok" && status.data.interval_minutes) || 15;
  const gaps = (status.state === "ok" && status.data.gaps) || [];
  const meta = [card.version, card.position, card.club, card.league, card.nation].filter(Boolean).join(" · ");

  return (
    <>
      <div className="small" style={{ marginBottom: 8 }}>
        <Link href="/karten">← Alle Karten</Link>
      </div>
      <div className="detail-head">
        {card.image && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.image}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(e) => ((e.currentTarget as HTMLImageElement).style.display = "none")}
          />
        )}
        <div>
          <h1 style={{ marginBottom: 2 }}>
            {card.name} {isNum(card.rating) && <span className="muted">{card.rating}</span>}
          </h1>
          <div className="small muted">{meta}</div>
          <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {card.signal && <SignalBadge type={card.signal} />}
            {card.available === false && <span className="badge badge-danger">gerade nicht handelbar</span>}
            {card.link && (
              <a href={card.link} target="_blank" rel="noopener noreferrer" className="small">
                Auf fut.gg ansehen ↗
              </a>
            )}
          </div>
        </div>
      </div>

      {!hasPrices && <NoPricesNotice />}

      <section className="section">
        <div className="grid grid-tiles">
          <div className="tile">
            <div className="tile-label">Preis</div>
            <div className="tile-value num">{coins(card.price)}</div>
            <div className="tile-sub">{card.price_updated_at ? relative(card.price_updated_at, now) : "–"}</div>
          </div>
          <div className="tile">
            <div className="tile-label">7-Tage-Schnitt</div>
            <div className="tile-value num">{coins(card.avg_7d)}</div>
            <div className="tile-sub">
              Abweichung <Pct value={card.deviation_pct} />
            </div>
          </div>
          <div className="tile">
            <div className="tile-label">Änderung 1 h</div>
            <div className="tile-value">
              <Pct value={card.change_1h_pct} />
            </div>
          </div>
          <div className="tile">
            <div className="tile-label">Änderung 24 h</div>
            <div className="tile-value">
              <Pct value={card.change_24h_pct} />
            </div>
          </div>
          <div className="tile">
            <div className="tile-label">Verkauf nach Steuer</div>
            <div className="tile-value num">{isNum(card.price) ? coins(card.price * 0.95) : "–"}</div>
            <div className="tile-sub">Preis − 5 % EA-Steuer</div>
          </div>
          <div className="tile">
            <div className="tile-label">EA-Preisgrenzen</div>
            <div className="tile-value num" style={{ fontSize: "1rem" }}>
              {isNum(card.price_min) || isNum(card.price_max)
                ? `${coins(card.price_min)} – ${coins(card.price_max)}`
                : "unbekannt"}
            </div>
            <div className="tile-sub">Datenbasis: {num(card.data_days)} Tage</div>
          </div>
        </div>
      </section>

      {signal && (
        <section className="section">
          <div className={`signal-card ${signal.type}`}>
            <div className="signal-top">
              <h2 style={{ margin: 0 }}>Aktuelles Signal</h2>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <SignalBadge type={signal.type} />
                <ConfidenceBadge value={signal.confidence} />
              </div>
            </div>
            <dl className="kv" style={{ margin: 0 }}>
              <div>
                <dt>Signalpreis</dt>
                <dd className="num">{coins(signal.price)}</dd>
              </div>
              <div>
                <dt>Erw. Gewinn (nach 5 % Steuer)</dt>
                <dd className={`num ${isNum(signal.expected_profit) ? (signal.expected_profit >= 0 ? "pos" : "neg") : ""}`}>
                  {signedCoins(signal.expected_profit)}
                </dd>
              </div>
              {isNum(signal.expected_sell) && (
                <div>
                  <dt>Erwarteter Verkaufspreis</dt>
                  <dd className="num">{coins(signal.expected_sell)}</dd>
                </div>
              )}
              {signal.since && (
                <div>
                  <dt>Seit</dt>
                  <dd>{dateTime(signal.since)}</dd>
                </div>
              )}
            </dl>
            {signal.reasons && signal.reasons.length > 0 && (
              <ul className="reasons">
                {signal.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      <section className="section panel">
        <div className="section-head">
          <h2>Preisverlauf</h2>
          <div className="range-bar" role="group" aria-label="Zeitraum">
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`btn ${range === r.id ? "active" : ""}`}
                onClick={() => setRange(r.id)}
                aria-pressed={range === r.id}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        {history.state === "missing" ? (
          <div className="empty">Für diese Karte gibt es noch keinen Preisverlauf.</div>
        ) : history.state !== "ok" ? (
          <LoadNotice loaded={history} what="Preisverlauf" />
        ) : points.filter((p) => isNum(p.p)).length === 0 ? (
          <div className="empty">Noch keine Preispunkte für diese Karte.</div>
        ) : (
          <>
            <PriceChart
              points={points}
              from={from}
              to={lastT}
              intervalMinutes={interval}
              priceMin={card.price_min}
              priceMax={card.price_max}
              gaps={gaps}
            />
            <div className="small muted" style={{ marginTop: 6 }}>
              Im Zeitraum: Tief {coins(rangeMin)} · Hoch {coins(rangeMax)} · {inRange.length} Messpunkte · letzter
              Punkt {dateTime(lastT)}
            </div>
          </>
        )}
      </section>

      {card.watch_reason && (
        <section className="section panel">
          <h3>Warum auf der Watchlist?</h3>
          <div>{card.watch_reason}</div>
        </section>
      )}
    </>
  );
}
