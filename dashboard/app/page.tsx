"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useData, useHasPrices } from "@/components/DataProvider";
import { ConfidenceBadge, LoadNotice, NoPricesNotice, Pct, SignalBadge } from "@/components/ui";
import {
  coins,
  dateTime,
  EVENT_TYPE_LABEL,
  eventDate,
  isNum,
  num,
  pct,
  relative,
  signedCoins,
  TENDENCY_LABEL,
} from "@/lib/format";
import type { Card, Market, Signal } from "@/lib/types";

export default function HomePage() {
  const { market, signals, cards, status } = useData();
  const hasPrices = useHasPrices();

  const cardById = useMemo(() => {
    const m = new Map<string, Card>();
    if (cards.state === "ok") for (const c of cards.data.cards || []) m.set(c.id, c);
    return m;
  }, [cards]);

  const sorted = useMemo(() => {
    if (signals.state !== "ok") return { buy: [] as Signal[], sell: [] as Signal[] };
    const list = (signals.data.signals || []).filter((s) => s && s.card_id);
    const conf: Record<string, number> = { hoch: 0, mittel: 1, gering: 2 };
    const byStrength = (a: Signal, b: Signal) =>
      (conf[a.confidence ?? "gering"] ?? 3) - (conf[b.confidence ?? "gering"] ?? 3) ||
      Math.abs(b.deviation_pct ?? 0) - Math.abs(a.deviation_pct ?? 0);
    return {
      buy: list.filter((s) => s.type === "buy").sort(byStrength),
      sell: list.filter((s) => s.type === "sell").sort(byStrength),
    };
  }, [signals]);

  const noPricesMsg = status.state === "ok" && status.data.source?.ok === false ? status.data.source?.message : null;

  return (
    <>
      {market.state === "ok" && <CrashWarning market={market.data} />}

      <section className="section">
        <div className="section-head">
          <h1>Aktuelle Signale</h1>
          {signals.state === "ok" && (
            <span className="small muted">Stand {dateTime(signals.data.generated_at)}</span>
          )}
        </div>
        {status.state === "ok" && !hasPrices ? (
          <NoPricesNotice message={noPricesMsg} />
        ) : signals.state !== "ok" ? (
          <LoadNotice loaded={signals} what="Signale" />
        ) : sorted.buy.length + sorted.sell.length === 0 ? (
          <div className="panel empty">Gerade keine Kauf- oder Verkaufssignale. Abwarten ist auch eine Entscheidung.</div>
        ) : (
          <>
            <SignalGroup title="Kaufen" list={sorted.buy} cardById={cardById} />
            <SignalGroup title="Verkaufen" list={sorted.sell} cardById={cardById} />
          </>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Marktüberblick</h2>
          {market.state === "ok" && <span className="small muted">Stand {dateTime(market.data.generated_at)}</span>}
        </div>
        {market.state !== "ok" ? <LoadNotice loaded={market} what="Marktdaten" /> : <MarketOverview market={market.data} />}
      </section>

      {market.state === "ok" && (
        <section className="section">
          <div className="grid grid-2">
            <Assessment market={market.data} />
            <HitRate market={market.data} />
          </div>
        </section>
      )}
    </>
  );
}

function SignalGroup({ title, list, cardById }: { title: string; list: Signal[]; cardById: Map<string, Card> }) {
  if (list.length === 0) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <h3 className="muted">
        {title} ({list.length})
      </h3>
      <div className="signal-grid">
        {list.map((s) => (
          <SignalCard key={s.card_id + s.type} s={s} card={cardById.get(s.card_id)} />
        ))}
      </div>
    </div>
  );
}

function SignalCard({ s, card }: { s: Signal; card?: Card }) {
  const { now } = useData();
  const sub = [card?.rating, card?.position, card?.version].filter(Boolean).join(" · ");
  return (
    <article className={`signal-card ${s.type}`}>
      <div className="signal-top">
        <div>
          <Link href={`/karte?id=${encodeURIComponent(s.card_id)}`} className="signal-name">
            {s.name}
          </Link>
          {sub && <div className="small muted">{sub}</div>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <SignalBadge type={s.type} />
          <ConfidenceBadge value={s.confidence} />
        </div>
      </div>
      <dl className="kv" style={{ margin: 0 }}>
        <div>
          <dt>Preis</dt>
          <dd className="num">{coins(s.price)}</dd>
        </div>
        <div>
          <dt>7-Tage-Schnitt</dt>
          <dd className="num">{coins(s.avg_7d)}</dd>
        </div>
        <div>
          <dt>Abweichung</dt>
          <dd>
            <Pct value={s.deviation_pct} />
          </dd>
        </div>
        <div>
          <dt>Erw. Gewinn (nach 5 % Steuer)</dt>
          <dd className={`num ${isNum(s.expected_profit) ? (s.expected_profit >= 0 ? "pos" : "neg") : ""}`}>
            {signedCoins(s.expected_profit)}
          </dd>
        </div>
        {isNum(s.expected_sell) && (
          <div>
            <dt>{s.type === "buy" ? "Ziel-Verkaufspreis" : "Erwarteter Preis"}</dt>
            <dd className="num">{coins(s.expected_sell)}</dd>
          </div>
        )}
        {s.type === "sell" && isNum(s.price) && (
          <div>
            <dt>Erlös jetzt (nach Steuer)</dt>
            <dd className="num">{coins(s.price * 0.95)}</dd>
          </div>
        )}
      </dl>
      {s.reasons && s.reasons.length > 0 && (
        <ul className="reasons">
          {s.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {s.since && <div className="small muted">Signal seit {relative(s.since, now)} ({dateTime(s.since)})</div>}
    </article>
  );
}

function CrashWarning({ market }: { market: Market }) {
  const c = market.crash;
  if (!c || !c.active) return null;
  const severe = c.severity === "severe";
  return (
    <div className={`crash ${severe ? "" : "mild"}`} role="alert">
      <h2>{severe ? "⚠ Marktcrash!" : "⚠ Markt fällt deutlich"}</h2>
      <div>
        Rückgang: <strong className="num">{pct(c.drop_pct)}</strong>
        {c.reason ? ` – ${c.reason}` : ""}
      </div>
      <div className="small" style={{ marginTop: 4 }}>
        Kaufsignale mit Vorsicht behandeln, Verkäufe nicht überstürzen.
      </div>
    </div>
  );
}

function MarketOverview({ market }: { market: Market }) {
  const phase = market.week_phase;
  const events = (market.upcoming_events || []).slice().sort((a, b) => a.date.localeCompare(b.date));
  return (
    <div className="grid" style={{ gap: 12 }}>
      <div className="grid grid-tiles">
        <div className="tile">
          <div className="tile-label">Trend 1 h</div>
          <div className="tile-value">
            <Pct value={market.trend_1h_pct} />
          </div>
        </div>
        <div className="tile">
          <div className="tile-label">Trend 24 h</div>
          <div className="tile-value">
            <Pct value={market.trend_24h_pct} />
          </div>
        </div>
        <div className="tile">
          <div className="tile-label">Marktindex</div>
          <div className="tile-value num">{num(market.index_value)}</div>
          <div className="tile-sub">Watchlist-Index</div>
        </div>
        <div className="tile">
          <div className="tile-label">Crash-Warnung</div>
          <div className="tile-value">
            {market.crash?.active ? (
              <span className="badge badge-danger">aktiv ({market.crash.severity === "severe" ? "schwer" : "leicht"})</span>
            ) : market.crash ? (
              <span className="badge badge-hoch">keine</span>
            ) : (
              <span className="muted">–</span>
            )}
          </div>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="panel">
          <h3>Phase im Wochenzyklus</h3>
          {phase?.label ? (
            <>
              <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{phase.label}</div>
              {phase.price_tendency && (
                <div className="small" style={{ marginTop: 2 }}>
                  {TENDENCY_LABEL[phase.price_tendency] ?? phase.price_tendency}
                </div>
              )}
              {phase.note && <p className="small muted" style={{ marginBottom: 0 }}>{phase.note}</p>}
            </>
          ) : (
            <div className="muted">Keine Angabe.</div>
          )}
        </div>
        <div className="panel">
          <h3>Nächste Events</h3>
          {events.length === 0 ? (
            <div className="muted">Keine Events bekannt.</div>
          ) : (
            <ul className="event-list">
              {events.slice(0, 8).map((e) => (
                <li key={e.date + e.name}>
                  <span className="event-date">{eventDate(e.date)}</span>
                  <span>
                    <strong>{e.name}</strong>{" "}
                    {e.type && <span className="badge badge-neutral">{EVENT_TYPE_LABEL[e.type] ?? e.type}</span>}{" "}
                    {e.certainty && e.certainty !== "sicher" && <span className="small muted">({e.certainty})</span>}
                    {e.impact && <div className="small muted">{e.impact}</div>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function Assessment({ market }: { market: Market }) {
  const a = market.assessment;
  return (
    <div className="panel">
      <h3>Markteinschätzung</h3>
      {a?.text ? (
        <>
          <p style={{ margin: "0 0 6px" }}>{a.text}</p>
          <div className="small muted">
            {a.author || "Analyse"}
            {a.generated_at ? ` · ${dateTime(a.generated_at)}` : ""}
          </div>
        </>
      ) : (
        <div className="muted">Noch keine Einschätzung aus der Analyse-Runde.</div>
      )}
    </div>
  );
}

function HitRate({ market }: { market: Market }) {
  const h = market.hit_rate;
  return (
    <div className="panel">
      <h3>Trefferquote der Signale</h3>
      {h && h.evaluated > 0 ? (
        <>
          <div className="tile-value">{isNum(h.rate) ? pct(h.rate * 100, false) : "–"}</div>
          <div className="small muted">
            {h.hits} von {h.evaluated} ausgewerteten Signalen lagen richtig
            {h.window_days ? ` (letzte ${h.window_days} Tage)` : ""}.
          </div>
        </>
      ) : (
        <div className="muted">Noch keine ausgewerteten Signale.</div>
      )}
    </div>
  );
}
