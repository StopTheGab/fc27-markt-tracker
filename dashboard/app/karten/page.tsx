"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useData, useHasPrices } from "@/components/DataProvider";
import { LimitsExplainer, LoadNotice, NoPricesNotice, Pct, SignalBadge, StrongBadge } from "@/components/ui";
import { coins, dateTime, isNum } from "@/lib/format";
import type { Card } from "@/lib/types";

type SortKey =
  | "name"
  | "rating"
  | "price"
  | "buy_limit"
  | "sell_limit"
  | "deviation_pct"
  | "change_1h_pct"
  | "change_24h_pct"
  | "signal";

const SORT_LABEL: Record<SortKey, string> = {
  name: "Name",
  rating: "Rating",
  price: "Preis",
  buy_limit: "Kauflimit",
  sell_limit: "Verkaufslimit",
  deviation_pct: "Abweichung",
  change_1h_pct: "1 h",
  change_24h_pct: "24 h",
  signal: "Signal",
};

interface Filters {
  q: string;
  position: string;
  version: string;
  signal: "" | "buy" | "sell" | "none";
  onlySignals: boolean;
  nearLimit: boolean;
  min: string;
  max: string;
  sort: SortKey;
  dir: "asc" | "desc";
}

const DEFAULT_FILTERS: Filters = {
  q: "",
  position: "",
  version: "",
  signal: "",
  onlySignals: false,
  nearLimit: false,
  min: "",
  max: "",
  sort: "rating",
  dir: "desc",
};

const STORE_KEY = "fc27-kartenfilter";

function norm(s: string | null | undefined) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** Eingabe wie "15.000", "15000", "15k" oder "1,2m" → Zahl */
function parseCoins(s: string): number | null {
  const t = s.trim().toLowerCase().replace(/\s/g, "");
  if (!t) return null;
  const m = /^([\d.,]+)(k|m|mio)?$/.exec(t);
  if (!m) return null;
  let n: number;
  if (m[2]) n = parseFloat(m[1].replace(/\./g, "").replace(",", ".")) * (m[2] === "k" ? 1e3 : 1e6);
  else n = parseInt(m[1].replace(/[.,]/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

/** Preis höchstens 3 % über dem Kauflimit (oder darunter). */
function nearBuyLimit(c: Card): boolean {
  return isNum(c.price) && isNum(c.buy_limit) && c.buy_limit > 0 && c.price <= c.buy_limit * 1.03;
}

function compare(a: Card, b: Card, key: SortKey): number {
  if (key === "name") return a.name.localeCompare(b.name, "de");
  if (key === "signal") {
    const r = (c: Card) => (c.signal === "buy" ? 2 : c.signal === "sell" ? 1 : 0);
    return r(a) - r(b) || (a.signal_strength === "stark" ? 1 : 0) - (b.signal_strength === "stark" ? 1 : 0);
  }
  const va = a[key];
  const vb = b[key];
  return (typeof va === "number" ? va : 0) - (typeof vb === "number" ? vb : 0);
}

export default function CardsPage() {
  const { cards } = useData();
  const hasPrices = useHasPrices();
  const [f, setF] = useState<Filters>(DEFAULT_FILTERS);

  // Filter pro Gerät merken (nur Komfort, kein Muss)
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORE_KEY);
      if (raw) setF({ ...DEFAULT_FILTERS, ...JSON.parse(raw) });
    } catch {}
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(f));
    } catch {}
  }, [f]);

  const all = useMemo(() => (cards.state === "ok" ? (cards.data.cards || []).filter((c) => c && c.id) : []), [cards]);
  const positions = useMemo(() => [...new Set(all.map((c) => c.position).filter(Boolean) as string[])].sort(), [all]);
  const versions = useMemo(() => [...new Set(all.map((c) => c.version).filter(Boolean) as string[])].sort(), [all]);

  const list = useMemo(() => {
    const q = norm(f.q);
    const min = parseCoins(f.min);
    const max = parseCoins(f.max);
    const out = all.filter((c) => {
      if (q && !norm([c.name, c.club, c.nation, c.league, c.version, c.position].join(" ")).includes(q)) return false;
      if (f.position && c.position !== f.position) return false;
      if (f.version && c.version !== f.version) return false;
      if (f.onlySignals && !c.signal) return false;
      if (f.nearLimit && !nearBuyLimit(c)) return false;
      if (f.signal === "none" && c.signal) return false;
      if ((f.signal === "buy" || f.signal === "sell") && c.signal !== f.signal) return false;
      if (min !== null && (c.price === null || c.price < min)) return false;
      if (max !== null && (c.price === null || c.price > max)) return false;
      return true;
    });
    const dir = f.dir === "asc" ? 1 : -1;
    out.sort((a, b) => {
      if (f.sort !== "name" && f.sort !== "signal") {
        // fehlende Werte immer ans Ende, unabhängig von der Richtung
        const ma = typeof a[f.sort] !== "number";
        const mb = typeof b[f.sort] !== "number";
        if (ma !== mb) return ma ? 1 : -1;
      }
      return compare(a, b, f.sort) * dir || a.name.localeCompare(b.name, "de");
    });
    return out;
  }, [all, f]);

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setF((p) => ({ ...p, [k]: v }));
  const toggleSort = (k: SortKey) =>
    setF((p) => ({ ...p, sort: k, dir: p.sort === k ? (p.dir === "asc" ? "desc" : "asc") : k === "name" ? "asc" : "desc" }));

  const header = (k: SortKey, right = false) => (
    <th className={right ? "r" : ""} aria-sort={f.sort === k ? (f.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => toggleSort(k)} className={f.sort === k ? "sorted" : ""}>
        {SORT_LABEL[k]} {f.sort === k ? (f.dir === "asc" ? "▲" : "▼") : ""}
      </button>
    </th>
  );

  const filtered = JSON.stringify({ ...f, sort: "", dir: "" }) !== JSON.stringify({ ...DEFAULT_FILTERS, sort: "", dir: "" });

  return (
    <>
      <div className="section-head">
        <h1>Watchlist-Karten</h1>
        {cards.state === "ok" && (
          <span className="small muted">
            {list.length} von {all.length} Karten · Stand {dateTime(cards.data.generated_at)}
          </span>
        )}
      </div>

      {cards.state !== "ok" ? (
        <LoadNotice loaded={cards} what="Kartenliste" />
      ) : (
        <>
          {!hasPrices && <NoPricesNotice />}
          <div className="filters" role="search">
            <label className="field wide">
              Suche
              <input
                type="search"
                placeholder="Name, Verein, Nation, Liga …"
                value={f.q}
                onChange={(e) => set("q", e.target.value)}
              />
            </label>
            <label className="field">
              Position
              <select value={f.position} onChange={(e) => set("position", e.target.value)}>
                <option value="">Alle</option>
                {positions.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Kategorie
              <select value={f.version} onChange={(e) => set("version", e.target.value)}>
                <option value="">Alle</option>
                {versions.map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Signal
              <select value={f.signal} onChange={(e) => set("signal", e.target.value as Filters["signal"])}>
                <option value="">Alle</option>
                <option value="buy">Kaufen</option>
                <option value="sell">Verkaufen</option>
                <option value="none">Ohne Signal</option>
              </select>
            </label>
            <label className="field">
              Preis von
              <input type="search" inputMode="numeric" placeholder="z. B. 10k" value={f.min} onChange={(e) => set("min", e.target.value)} />
            </label>
            <label className="field">
              Preis bis
              <input type="search" inputMode="numeric" placeholder="z. B. 1,5m" value={f.max} onChange={(e) => set("max", e.target.value)} />
            </label>
            <label className="check">
              <input type="checkbox" checked={f.onlySignals} onChange={(e) => set("onlySignals", e.target.checked)} />
              Nur Signale
            </label>
            <label className="check" title="Preis höchstens 3 % über dem Kauflimit">
              <input type="checkbox" checked={f.nearLimit} onChange={(e) => set("nearLimit", e.target.checked)} />
              Nahe Kauflimit
            </label>
            {filtered && (
              <button type="button" className="btn" onClick={() => setF((p) => ({ ...DEFAULT_FILTERS, sort: p.sort, dir: p.dir }))}>
                Filter zurücksetzen
              </button>
            )}
          </div>

          <div className="sortbar">
            <select value={f.sort} onChange={(e) => set("sort", e.target.value as SortKey)} aria-label="Sortieren nach">
              {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
                <option key={k} value={k}>
                  Sortieren: {SORT_LABEL[k]}
                </option>
              ))}
            </select>
            <button type="button" className="btn" onClick={() => set("dir", f.dir === "asc" ? "desc" : "asc")} aria-label="Sortierrichtung umkehren">
              {f.dir === "asc" ? "▲ aufst." : "▼ abst."}
            </button>
          </div>

          {list.length === 0 ? (
            <div className="panel empty">Keine Karte passt zu den Filtern.</div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="cards">
                  <thead>
                    <tr>
                      {header("name")}
                      {header("rating", true)}
                      <th>Pos.</th>
                      {header("price", true)}
                      <th className="r">7-T-Schnitt</th>
                      {header("buy_limit", true)}
                      {header("sell_limit", true)}
                      {header("deviation_pct", true)}
                      {header("change_1h_pct", true)}
                      {header("change_24h_pct", true)}
                      {header("signal")}
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((c) => (
                      <tr key={c.id} className={c.available === false ? "unavail" : ""}>
                        <td className="name-cell">
                          <Link href={`/karte?id=${encodeURIComponent(c.id)}`} className="row-link">
                            {c.name}
                          </Link>
                          <div className="small muted">{[c.version, c.club].filter(Boolean).join(" · ")}</div>
                        </td>
                        <td className="r num">{c.rating ?? "–"}</td>
                        <td>{c.position ?? "–"}</td>
                        <td className="r num">
                          {coins(c.price)}
                          {c.available === false && <div className="small muted">nicht handelbar</div>}
                        </td>
                        <td className="r num muted">{coins(c.avg_7d)}</td>
                        <td className={`r num ${nearBuyLimit(c) ? "near-limit" : ""}`} title={isNum(c.threshold_pct) ? `${c.threshold_pct.toLocaleString("de-DE")} % unter Schnitt` : undefined}>
                          {coins(c.buy_limit)}
                        </td>
                        <td className="r num">{coins(c.sell_limit)}</td>
                        <td className="r">
                          <Pct value={c.deviation_pct} />
                        </td>
                        <td className="r">
                          <Pct value={c.change_1h_pct} />
                        </td>
                        <td className="r">
                          <Pct value={c.change_24h_pct} />
                        </td>
                        <td>
                          <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
                            <SignalBadge type={c.signal} />
                            {c.signal && <StrongBadge strength={c.signal_strength} />}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="card-list">
                {list.map((c) => (
                  <Link key={c.id} href={`/karte?id=${encodeURIComponent(c.id)}`} className={`card-item ${c.available === false ? "unavail" : ""}`}>
                    <div className="card-item-top">
                      <strong>{c.name}</strong>
                      <span className="num" style={{ fontWeight: 700 }}>
                        {coins(c.price)}
                      </span>
                    </div>
                    <div className="card-item-top">
                      <span className="card-item-meta">
                        {[c.rating, c.position, c.version].filter(Boolean).join(" · ")}
                        {c.available === false ? " · nicht handelbar" : ""}
                      </span>
                      {c.signal && (
                        <span style={{ display: "inline-flex", gap: 4 }}>
                          <SignalBadge type={c.signal} />
                          <StrongBadge strength={c.signal_strength} />
                        </span>
                      )}
                    </div>
                    <div className="limits-line">
                      Bieten bis <span className={`num ${nearBuyLimit(c) ? "near-limit" : ""}`}>{coins(c.buy_limit)}</span> · Verkaufen ab{" "}
                      <span className="num">{coins(c.sell_limit)}</span>
                    </div>
                    <div className="card-item-nums">
                      <span>
                        <span className="muted">Abw.</span> <Pct value={c.deviation_pct} />
                      </span>
                      <span>
                        <span className="muted">1 h</span> <Pct value={c.change_1h_pct} />
                      </span>
                      <span>
                        <span className="muted">24 h</span> <Pct value={c.change_24h_pct} />
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
              <LimitsExplainer />
            </>
          )}
        </>
      )}
    </>
  );
}
