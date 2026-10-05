"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { loadJson, REFRESH_MS, STALE_MINUTES } from "@/lib/data";
import { ageMinutes } from "@/lib/format";
import type { CardsFile, Loaded, Market, SignalsFile, Status } from "@/lib/types";

interface DataState {
  status: Loaded<Status>;
  market: Loaded<Market>;
  cards: Loaded<CardsFile>;
  signals: Loaded<SignalsFile>;
  /** Zeitpunkt des letzten Ladeversuchs im Browser */
  loadedAt: number | null;
  /** Läuft gerade ein Ladevorgang? */
  busy: boolean;
  /** Aktuelle Uhrzeit, tickt alle 30 s (für "vor x min") */
  now: number;
  reload: () => void;
}

const LOADING = { state: "loading" } as const;

const Ctx = createContext<DataState | null>(null);

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Loaded<Status>>(LOADING);
  const [market, setMarket] = useState<Loaded<Market>>(LOADING);
  const [cards, setCards] = useState<Loaded<CardsFile>>(LOADING);
  const [signals, setSignals] = useState<Loaded<SignalsFile>>(LOADING);
  const [loadedAt, setLoadedAt] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const abortRef = useRef<AbortController | null>(null);

  const reload = useCallback(async () => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setBusy(true);
    const [s, m, c, g] = await Promise.all([
      loadJson<Status>("status.json", ac.signal),
      loadJson<Market>("market.json", ac.signal),
      loadJson<CardsFile>("cards.json", ac.signal),
      loadJson<SignalsFile>("signals.json", ac.signal),
    ]);
    if (ac.signal.aborted) return;
    // Bei einem Fehler im Hintergrund-Neuladen bereits geladene Daten behalten
    const keep = <T,>(prev: Loaded<T>, next: Loaded<T>): Loaded<T> =>
      next.state === "error" && prev.state === "ok" ? prev : next;
    setStatus((p) => keep(p, s));
    setMarket((p) => keep(p, m));
    setCards((p) => keep(p, c));
    setSignals((p) => keep(p, g));
    setLoadedAt(Date.now());
    setNow(Date.now());
    setBusy(false);
  }, []);

  useEffect(() => {
    reload();
    const id = window.setInterval(reload, REFRESH_MS);
    const tick = window.setInterval(() => setNow(Date.now()), 30_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") reload();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      window.clearInterval(tick);
      document.removeEventListener("visibilitychange", onVisible);
      abortRef.current?.abort();
    };
  }, [reload]);

  return (
    <Ctx.Provider value={{ status, market, cards, signals, loadedAt, busy, now, reload }}>{children}</Ctx.Provider>
  );
}

export function useData(): DataState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useData außerhalb von DataProvider");
  return v;
}

/**
 * Gibt es überhaupt echte Preise? Laut Datenvertrag: wenn last_successful_fetch null ist,
 * hat noch keine Quelle funktioniert → Hinweis statt Preisen.
 */
export function useHasPrices(): boolean {
  const { status } = useData();
  return status.state === "ok" && !!status.data.last_successful_fetch;
}

export function isStale(status: Status, now: number): { stale: boolean; reasons: string[] } {
  const reasons: string[] = [];
  const gen = ageMinutes(status.generated_at, now);
  const fetchAge = ageMinutes(status.last_successful_fetch, now);
  if (gen === null) reasons.push("Zeitpunkt der letzten Collector-Ausgabe unbekannt");
  else if (gen > STALE_MINUTES) reasons.push(`Collector hat seit über ${STALE_MINUTES} min nichts geliefert`);
  if (fetchAge === null) reasons.push("Noch kein erfolgreicher Preisabruf");
  else if (fetchAge > STALE_MINUTES) reasons.push(`Letzter erfolgreicher Preisabruf ist über ${STALE_MINUTES} min alt`);
  return { stale: reasons.length > 0, reasons };
}
