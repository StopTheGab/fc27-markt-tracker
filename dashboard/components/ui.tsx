"use client";

import { pct, SIGNAL_LABEL, trendClass } from "@/lib/format";
import type { Loaded, SignalStrength, SignalType } from "@/lib/types";

export function SignalBadge({ type }: { type: SignalType | null | undefined }) {
  if (!type) return <span className="muted">–</span>;
  return (
    <span className={`badge badge-${type}`}>
      {type === "buy" ? "▲" : "▼"} {SIGNAL_LABEL[type] ?? type}
    </span>
  );
}

/** Badge „STARK“ für starke Signale (≥ 15 % unter Schnitt); sonst nichts. */
export function StrongBadge({ strength }: { strength: SignalStrength | null | undefined }) {
  if (strength !== "stark") return null;
  return (
    <span className="badge badge-strong" title="Mindestens 15 % unter dem 7-Tage-Schnitt">
      STARK
    </span>
  );
}

/** Kurze Erklärung, wie Kauf-/Verkaufslimits und Signale entstehen. */
export function LimitsExplainer() {
  return (
    <p className="small muted explainer">
      ⓘ Kaufsignal, wenn der Preis unter das Kauflimit fällt (7-Tage-Schnitt minus 8–20 %, je nach Schwankung der
      Karte); ab 15 % = starkes Signal. Verkaufen am 7-Tage-Schnitt, im Wochenhoch (Do/Fr) oder vor Promos. Gewinn
      nach 5 % EA-Steuer.
    </p>
  );
}

export function ConfidenceBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const cls = value === "hoch" || value === "mittel" || value === "gering" ? value : "gering";
  return <span className={`badge badge-${cls}`}>Sicherheit: {value}</span>;
}

export function Pct({ value, invert = false }: { value: number | null | undefined; invert?: boolean }) {
  let cls = trendClass(value);
  if (invert && cls !== "neutral") cls = cls === "pos" ? "neg" : "pos";
  return <span className={`num ${cls}`}>{pct(value)}</span>;
}

/** Hinweis für eine Datei, die (noch) nicht geladen ist oder fehlt. Gibt null zurück, wenn ok. */
export function LoadNotice({ loaded, what }: { loaded: Loaded<unknown>; what: string }) {
  if (loaded.state === "ok") return null;
  if (loaded.state === "loading") return <div className="panel empty">Lade {what} …</div>;
  if (loaded.state === "locked")
    return (
      <div className="panel empty">
        🔒 {what}: {loaded.reason === "invalid" ? "Schlüssel falsch" : "Schlüssel fehlt"} – siehe Hinweis oben.
      </div>
    );
  if (loaded.state === "missing")
    return <div className="panel empty">Noch keine Daten vom Collector ({what} fehlt).</div>;
  return (
    <div className="panel empty">
      {what} konnte nicht geladen werden: {loaded.message}
    </div>
  );
}

/** Hinweis, wenn laut status.json noch nie ein Preisabruf geklappt hat. */
export function NoPricesNotice({ message }: { message?: string | null }) {
  return (
    <div className="panel empty">
      <strong>Noch keine Preise verfügbar.</strong>
      <div className="small" style={{ marginTop: 4 }}>
        {message || "Der Collector hat bisher keinen erfolgreichen Preisabruf gemeldet."}
      </div>
    </div>
  );
}
