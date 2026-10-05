const TZ = "Europe/Berlin";

const coinFmt = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const pctFmt = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const numFmt = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 0, maximumFractionDigits: 1 });
const dateTimeFmt = new Intl.DateTimeFormat("de-DE", {
  timeZone: TZ,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const shortDateTimeFmt = new Intl.DateTimeFormat("de-DE", {
  timeZone: TZ,
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});
const timeFmt = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("de-DE", { timeZone: TZ, weekday: "short", day: "2-digit", month: "2-digit" });

export const DASH = "–";

export function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** 1250000 → "1.250.000" */
export function coins(v: number | null | undefined): string {
  return isNum(v) ? coinFmt.format(Math.round(v)) : DASH;
}

/** Vorzeichenbehaftete Coins: "+135.000" / "−20.000" */
export function signedCoins(v: number | null | undefined): string {
  if (!isNum(v)) return DASH;
  const s = coinFmt.format(Math.abs(Math.round(v)));
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s;
}

/** -3.8 → "−3,8 %" */
export function pct(v: number | null | undefined, signed = true): string {
  if (!isNum(v)) return DASH;
  const s = pctFmt.format(Math.abs(v));
  const sign = !signed ? (v < 0 ? "−" : "") : v > 0 ? "+" : v < 0 ? "−" : "±";
  return `${sign}${s} %`;
}

export function num(v: number | null | undefined): string {
  return isNum(v) ? numFmt.format(v) : DASH;
}

export function parseTs(ts: string | null | undefined): number | null {
  if (!ts) return null;
  const t = Date.parse(ts);
  return Number.isFinite(t) ? t : null;
}

export function dateTime(ts: string | number | null | undefined): string {
  const t = typeof ts === "number" ? ts : parseTs(ts);
  return t === null ? DASH : dateTimeFmt.format(t);
}

export function shortDateTime(ts: string | number | null | undefined): string {
  const t = typeof ts === "number" ? ts : parseTs(ts);
  return t === null ? DASH : shortDateTimeFmt.format(t);
}

export function timeOnly(t: number): string {
  return timeFmt.format(t);
}

export function dayLabel(t: number): string {
  return dayFmt.format(t);
}

/** Datum "2026-10-10" (ohne Uhrzeit) → "Sa., 10.10." */
export function eventDate(d: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  if (!m) return d;
  const t = Date.UTC(+m[1], +m[2] - 1, +m[3], 12);
  return dayFmt.format(t);
}

/** Minuten seit Zeitpunkt (null wenn unbekannt). */
export function ageMinutes(ts: string | null | undefined, now: number): number | null {
  const t = parseTs(ts);
  return t === null ? null : (now - t) / 60000;
}

/** "gerade eben", "vor 12 min", "vor 2 h 5 min", "vor 3 Tagen" */
export function relative(ts: string | null | undefined, now: number): string {
  const m = ageMinutes(ts, now);
  if (m === null) return DASH;
  if (m < -2) return "in der Zukunft (Uhrzeit prüfen)";
  if (m < 1) return "gerade eben";
  if (m < 60) return `vor ${Math.floor(m)} min`;
  const h = Math.floor(m / 60);
  if (h < 24) {
    const rest = Math.floor(m % 60);
    return rest ? `vor ${h} h ${rest} min` : `vor ${h} h`;
  }
  const d = Math.floor(h / 24);
  return d === 1 ? "vor 1 Tag" : `vor ${d} Tagen`;
}

export function durationMinutes(min: number | null | undefined): string {
  if (!isNum(min)) return DASH;
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const r = Math.round(min % 60);
  return r ? `${h} h ${r} min` : `${h} h`;
}

export function trendClass(v: number | null | undefined): string {
  if (!isNum(v) || Math.abs(v) < 0.05) return "neutral";
  return v > 0 ? "pos" : "neg";
}

export const SIGNAL_LABEL: Record<string, string> = { buy: "Kaufen", sell: "Verkaufen" };

export const TENDENCY_LABEL: Record<string, string> = {
  down: "Preise eher fallend",
  up: "Preise eher steigend",
  flat: "Preise eher seitwärts",
  volatile: "Preise schwankend",
};

export const EVENT_TYPE_LABEL: Record<string, string> = {
  promo: "Promo",
  wl: "Weekend League",
  rewards: "Belohnungen",
  sbc: "SBC",
};
