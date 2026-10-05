"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { coins, dayLabel, isNum, shortDateTime, timeOnly } from "@/lib/format";
import type { Gap } from "@/lib/types";

export interface ChartPoint {
  t: number;
  p: number | null;
  /** gleitender 7-Tage-Schnitt bis zu diesem Punkt */
  avg: number | null;
}

interface Props {
  points: ChartPoint[];
  from: number;
  to: number;
  intervalMinutes: number;
  priceMin?: number | null;
  priceMax?: number | null;
  gaps?: Gap[];
}

const H_DESKTOP = 280;
const H_MOBILE = 220;
const M = { top: 12, right: 14, bottom: 26, left: 62 };
const HOUR = 3600_000;
const berlinHour = new Intl.DateTimeFormat("de-DE", { timeZone: "Europe/Berlin", hour: "numeric", hourCycle: "h23" });

function niceStep(range: number, target: number): number {
  const raw = range / Math.max(1, target);
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * pow;
}

function shortCoins(v: number): string {
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toLocaleString("de-DE", { maximumFractionDigits: 2 })} Mio.`;
  return coins(v);
}

/** Teilt die Punkte in zusammenhängende Abschnitte; Lücken (null oder zu großer Abstand) werden nicht verbunden. */
function segments(points: ChartPoint[], key: "p" | "avg", intervalMinutes: number, now: number): ChartPoint[][] {
  const out: ChartPoint[][] = [];
  let cur: ChartPoint[] = [];
  let prev: ChartPoint | null = null;
  for (const pt of points) {
    const v = pt[key];
    if (!isNum(v)) {
      if (cur.length) out.push(cur);
      cur = [];
      prev = null;
      continue;
    }
    if (prev) {
      // ältere Daten (> 48 h) sind stündlich verdichtet
      const base = now - pt.t > 48 * HOUR && now - prev.t > 48 * HOUR ? 60 : intervalMinutes;
      if (pt.t - prev.t > base * 2.5 * 60_000) {
        out.push(cur);
        cur = [];
      }
    }
    cur.push(pt);
    prev = pt;
  }
  if (cur.length) out.push(cur);
  return out;
}

export function PriceChart({ points, from, to, intervalMinutes, priceMin, priceMax, gaps = [] }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(700);
  const [hover, setHover] = useState<ChartPoint | null>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = Math.round(entries[0].contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const height = width < 520 ? H_MOBILE : H_DESKTOP;
  const iw = Math.max(10, width - M.left - M.right);
  const ih = height - M.top - M.bottom;

  const visible = useMemo(() => points.filter((p) => p.t >= from && p.t <= to), [points, from, to]);

  const geo = useMemo(() => {
    const vals: number[] = [];
    for (const p of visible) {
      if (isNum(p.p)) vals.push(p.p);
      if (isNum(p.avg)) vals.push(p.avg);
    }
    if (!vals.length) return null;
    let lo = Math.min(...vals);
    let hi = Math.max(...vals);
    // Preisgrenzen nur einbeziehen, wenn sie nah am Datenbereich liegen (sonst wird das Diagramm platt)
    const span0 = Math.max(hi - lo, hi * 0.02);
    const limits: { v: number; label: string; inside: boolean }[] = [];
    for (const [v, label] of [
      [priceMin, "Preisgrenze min"],
      [priceMax, "Preisgrenze max"],
    ] as const) {
      if (!isNum(v)) continue;
      const inside = v >= lo - span0 * 0.6 && v <= hi + span0 * 0.6;
      limits.push({ v, label, inside });
      if (inside) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
    }
    const pad = Math.max((hi - lo) * 0.08, hi * 0.01, 1);
    lo = Math.max(0, lo - pad);
    hi = hi + pad;
    const step = niceStep(hi - lo, ih < 200 ? 4 : 5);
    const ticks: number[] = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(v);
    const x0 = from;
    const x1 = Math.max(to, from + 1);
    const x = (t: number) => M.left + ((t - x0) / (x1 - x0)) * iw;
    const y = (v: number) => M.top + ih - ((v - lo) / (hi - lo)) * ih;

    // Zeitachse: Uhrzeiten bei kurzen Spannen, sonst Tage (Mitternacht Berlin)
    const spanH = (x1 - x0) / HOUR;
    const xticks: { t: number; label: string }[] = [];
    const maxTicks = Math.max(2, Math.floor(iw / 80));
    if (spanH <= 48) {
      const stepH = [1, 2, 3, 6, 12, 24].find((s) => spanH / s <= maxTicks) ?? 24;
      for (let t = Math.ceil(x0 / HOUR) * HOUR; t <= x1; t += HOUR) {
        const h = Number(berlinHour.format(t));
        if (h % stepH === 0) xticks.push({ t, label: h === 0 ? dayLabel(t) : timeOnly(t) });
      }
    } else {
      const days: number[] = [];
      for (let t = Math.ceil(x0 / HOUR) * HOUR; t <= x1; t += HOUR) if (Number(berlinHour.format(t)) === 0) days.push(t);
      const every = Math.max(1, Math.ceil(days.length / maxTicks));
      days.forEach((t, i) => i % every === 0 && xticks.push({ t, label: dayLabel(t) }));
    }
    return { lo, hi, ticks, x, y, xticks, limits };
  }, [visible, from, to, iw, ih, priceMin, priceMax]);

  const now = to;
  const priceSegs = useMemo(() => segments(visible, "p", intervalMinutes, now), [visible, intervalMinutes, now]);
  const avgSegs = useMemo(() => segments(visible, "avg", intervalMinutes, now), [visible, intervalMinutes, now]);
  const hoverable = useMemo(() => visible.filter((p) => isNum(p.p)), [visible]);

  if (!geo) {
    return (
      <div ref={boxRef} className="empty">
        Im gewählten Zeitraum gibt es keine Preispunkte.
      </div>
    );
  }
  const { x, y, ticks, xticks, limits } = geo;
  const path = (seg: ChartPoint[], key: "p" | "avg") =>
    seg.map((pt, i) => `${i ? "L" : "M"}${x(pt.t).toFixed(1)},${y(pt[key] as number).toFixed(1)}`).join("");

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (!hoverable.length) return;
    // binäre Suche nach dem nächsten Punkt
    let lo = 0;
    let hi = hoverable.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (x(hoverable[mid].t) < px) lo = mid;
      else hi = mid;
    }
    const best = Math.abs(x(hoverable[lo].t) - px) <= Math.abs(x(hoverable[hi].t) - px) ? hoverable[lo] : hoverable[hi];
    setHover(best);
  };

  const visGaps = gaps
    .map((g) => ({ a: Date.parse(g.from), b: Date.parse(g.to) }))
    .filter((g) => Number.isFinite(g.a) && Number.isFinite(g.b) && g.b > from && g.a < to);

  const tipLeft = hover ? Math.min(Math.max(x(hover.t) - 80, 0), width - 170) : 0;

  return (
    <div ref={boxRef} className="chart-box">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Preisverlauf mit gleitendem 7-Tage-Schnitt"
      >
        {/* Datenlücken laut Collector */}
        {visGaps.map((g, i) => (
          <rect
            key={i}
            x={x(Math.max(g.a, from))}
            y={M.top}
            width={Math.max(1, x(Math.min(g.b, to)) - x(Math.max(g.a, from)))}
            height={ih}
            fill="rgba(227,163,43,0.10)"
          />
        ))}
        {/* Gitter + y-Achse */}
        {ticks.map((v) => (
          <g key={v}>
            <line x1={M.left} x2={M.left + iw} y1={y(v)} y2={y(v)} stroke="#2b303a" strokeWidth={1} />
            <text x={M.left - 8} y={y(v)} dy="0.32em" textAnchor="end" fontSize={11} fill="#8a909c">
              {shortCoins(v)}
            </text>
          </g>
        ))}
        {xticks.map((t) => (
          <text key={t.t} x={x(t.t)} y={height - 8} textAnchor="middle" fontSize={11} fill="#8a909c">
            {t.label}
          </text>
        ))}
        {/* Preisgrenzen */}
        {limits
          .filter((l) => l.inside)
          .map((l) => (
            <g key={l.label}>
              <line x1={M.left} x2={M.left + iw} y1={y(l.v)} y2={y(l.v)} stroke="#8a909c" strokeWidth={1} strokeDasharray="2 4" />
              <text x={M.left + iw - 4} y={y(l.v) - 4} textAnchor="end" fontSize={10.5} fill="#b9bdc7">
                {l.label}: {coins(l.v)}
              </text>
            </g>
          ))}
        {/* 7-Tage-Schnitt */}
        {avgSegs.map((s, i) =>
          s.length > 1 ? (
            <path key={i} d={path(s, "avg")} fill="none" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="6 4" />
          ) : null,
        )}
        {/* Preis */}
        {priceSegs.map((s, i) =>
          s.length > 1 ? (
            <path key={i} d={path(s, "p")} fill="none" stroke="var(--series-1)" strokeWidth={2} strokeLinejoin="round" />
          ) : (
            <circle key={i} cx={x(s[0].t)} cy={y(s[0].p as number)} r={2.5} fill="var(--series-1)" />
          ),
        )}
        {hover && isNum(hover.p) && (
          <g pointerEvents="none">
            <line x1={x(hover.t)} x2={x(hover.t)} y1={M.top} y2={M.top + ih} stroke="#b9bdc7" strokeWidth={1} />
            <circle cx={x(hover.t)} cy={y(hover.p)} r={5} fill="var(--series-1)" stroke="#171a20" strokeWidth={2} />
          </g>
        )}
        <rect
          x={M.left}
          y={M.top}
          width={iw}
          height={ih}
          fill="transparent"
          onPointerMove={onMove}
          onPointerDown={onMove}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      {hover && (
        <div className="chart-tip" style={{ left: tipLeft }}>
          <div className="muted">{shortDateTime(hover.t)}</div>
          <div>
            Preis: <strong className="num">{coins(hover.p)}</strong>
          </div>
          {isNum(hover.avg) && (
            <div>
              7-T-Schnitt: <span className="num">{coins(hover.avg)}</span>
            </div>
          )}
        </div>
      )}
      <div className="legend">
        <span>
          <i style={{ borderColor: "var(--series-1)" }} />
          Preis
        </span>
        <span>
          <i style={{ borderColor: "var(--series-2)", borderTopStyle: "dashed" }} />
          gleitender 7-Tage-Schnitt
        </span>
        {limits.some((l) => l.inside) && (
          <span>
            <i style={{ borderColor: "#8a909c", borderTopStyle: "dotted" }} />
            EA-Preisgrenzen
          </span>
        )}
        {visGaps.length > 0 && (
          <span>
            <i style={{ borderTop: "8px solid rgba(227,163,43,0.35)", width: 12 }} />
            Datenlücke
          </span>
        )}
        {limits
          .filter((l) => !l.inside)
          .map((l) => (
            <span key={l.label} className="muted">
              {l.label}: {coins(l.v)} (außerhalb des Bildausschnitts)
            </span>
          ))}
      </div>
    </div>
  );
}

/** Gleitender Schnitt über die letzten 7 Tage (nur vorhandene Preise). */
export function withRollingAvg(raw: [string, number | null][]): ChartPoint[] {
  const pts = raw
    .map(([ts, p]) => ({ t: Date.parse(ts), p: isNum(p) ? p : null }))
    .filter((pt) => Number.isFinite(pt.t))
    .sort((a, b) => a.t - b.t);
  const out: ChartPoint[] = [];
  const WIN = 7 * 24 * HOUR;
  let sum = 0;
  let n = 0;
  let start = 0;
  for (let i = 0; i < pts.length; i++) {
    const pt = pts[i];
    if (pt.p !== null) {
      sum += pt.p;
      n++;
    }
    while (pts[start].t < pt.t - WIN) {
      if (pts[start].p !== null) {
        sum -= pts[start].p as number;
        n--;
      }
      start++;
    }
    out.push({ t: pt.t, p: pt.p, avg: pt.p !== null && n > 0 ? sum / n : null });
  }
  return out;
}
