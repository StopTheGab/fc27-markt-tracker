// Typen gemäß docs/DATA_CONTRACT.md — fehlende Werte sind immer null.

export interface Gap {
  from: string;
  to: string;
  minutes: number;
}

export interface Status {
  generated_at: string | null;
  last_successful_fetch: string | null;
  source: { id?: string; name?: string; url?: string; ok: boolean; message?: string | null } | null;
  collector_version?: string | null;
  interval_minutes?: number | null;
  cards_tracked?: number | null;
  cards_with_price?: number | null;
  data_days?: number | null;
  gaps?: Gap[] | null;
  errors_last_run?: string[] | null;
}

export type Tendency = "down" | "up" | "flat" | "volatile";

export interface MarketEvent {
  date: string;
  name: string;
  type?: string | null;
  certainty?: string | null;
  impact?: string | null;
}

export interface Market {
  generated_at: string | null;
  trend_24h_pct: number | null;
  trend_1h_pct: number | null;
  index_value: number | null;
  crash: {
    active: boolean;
    severity?: "none" | "mild" | "severe" | null;
    drop_pct?: number | null;
    reason?: string | null;
  } | null;
  week_phase: { id?: string; label?: string | null; note?: string | null; price_tendency?: Tendency | null } | null;
  upcoming_events?: MarketEvent[] | null;
  assessment: { text: string; generated_at?: string | null; author?: string | null } | null;
  hit_rate: { evaluated: number; hits: number; rate: number | null; window_days?: number | null } | null;
}

export type SignalType = "buy" | "sell";

export interface Card {
  id: string;
  ea_id?: number | null;
  name: string;
  version?: string | null;
  rating?: number | null;
  position?: string | null;
  league?: string | null;
  club?: string | null;
  nation?: string | null;
  price: number | null;
  price_updated_at?: string | null;
  available?: boolean | null;
  price_min?: number | null;
  price_max?: number | null;
  avg_7d: number | null;
  change_1h_pct: number | null;
  change_24h_pct: number | null;
  deviation_pct: number | null;
  data_days?: number | null;
  signal: SignalType | null;
  watch_reason?: string | null;
  image?: string | null;
  link?: string | null;
}

export interface CardsFile {
  generated_at: string | null;
  cards: Card[];
}

export interface Signal {
  card_id: string;
  name: string;
  type: SignalType;
  since?: string | null;
  price: number | null;
  avg_7d: number | null;
  deviation_pct: number | null;
  expected_sell?: number | null;
  expected_profit: number | null;
  confidence?: "hoch" | "mittel" | "gering" | null;
  reasons?: string[] | null;
  rules?: string[] | null;
}

export interface SignalsFile {
  generated_at: string | null;
  signals: Signal[];
}

export type HistoryPoint = [string, number | null];

export interface HistoryFile {
  card_id: string;
  points: HistoryPoint[];
}

/** Ergebnis eines Ladevorgangs: lädt, ok, fehlt (404) oder Fehler. */
export type Loaded<T> =
  | { state: "loading" }
  | { state: "ok"; data: T }
  | { state: "missing" }
  | { state: "error"; message: string };
