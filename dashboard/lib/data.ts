import { decryptEnvelope, getKey, isEnvelope } from "./crypto";
import type { Loaded } from "./types";

const DEFAULT_BASE = "https://raw.githubusercontent.com/StopTheGab/fc27-markt-tracker/data";

/** Basis-URL der Daten (Branch `data`), überschreibbar per NEXT_PUBLIC_DATA_BASE_URL. */
export const DATA_BASE_URL = (process.env.NEXT_PUBLIC_DATA_BASE_URL || DEFAULT_BASE).replace(/\/+$/, "");

/** Neu laden alle 5 Minuten. */
export const REFRESH_MS = 5 * 60 * 1000;

/** Daten gelten als veraltet nach 45 Minuten. */
export const STALE_MINUTES = 45;

export function dataUrl(file: string): string {
  const minute = Math.floor(Date.now() / 60000);
  return `${DATA_BASE_URL}/${file}?t=${minute}`;
}

/**
 * Lädt eine Datei aus dem data-Branch. Verschlüsselte Umschläge ({iv, ct}) werden mit dem lokal
 * gespeicherten Schlüssel entschlüsselt; Dateien ohne "ct" gelten als normales JSON.
 */
export async function loadJson<T>(file: string, signal?: AbortSignal): Promise<Loaded<T>> {
  let parsed: unknown;
  try {
    const res = await fetch(dataUrl(file), { cache: "no-store", signal });
    if (res.status === 404) return { state: "missing" };
    if (!res.ok) return { state: "error", message: `HTTP ${res.status} beim Laden von ${file}` };
    const text = await res.text();
    try {
      parsed = JSON.parse(text);
    } catch {
      return { state: "error", message: `${file} ist kein gültiges JSON` };
    }
  } catch (e) {
    if ((e as Error)?.name === "AbortError") return { state: "loading" };
    return { state: "error", message: `Netzwerkfehler beim Laden von ${file}` };
  }

  if (!isEnvelope(parsed)) return { state: "ok", data: parsed as T };

  const key = getKey();
  if (!key) return { state: "locked", reason: "missing" };
  try {
    return { state: "ok", data: await decryptEnvelope<T>(parsed, key) };
  } catch {
    return { state: "locked", reason: "invalid" };
  }
}
