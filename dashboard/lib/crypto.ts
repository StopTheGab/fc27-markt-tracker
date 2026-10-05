// Entschlüsselung der Preisdaten (AES-256-GCM, Umschlag {"v":1,"alg":"AES-256-GCM","iv","ct"}).
// Der Schlüssel kommt nur über das URL-Fragment (#k=…) und wird ausschließlich lokal im Browser gespeichert.

const STORAGE_KEY = "fc27_key";

let memoryKey: string | null = null; // Fallback, falls localStorage nicht verfügbar ist
const keyCache = new Map<string, Promise<CryptoKey>>();

export interface Envelope {
  v?: number;
  alg?: string;
  iv: string;
  ct: string;
}

export function isEnvelope(x: unknown): x is Envelope {
  return !!x && typeof x === "object" && typeof (x as Envelope).ct === "string" && typeof (x as Envelope).iv === "string";
}

function b64ToBytes(s: string): Uint8Array<ArrayBuffer> {
  let t = s.trim().replace(/-/g, "+").replace(/_/g, "/").replace(/\s/g, "");
  while (t.length % 4) t += "=";
  const bin = atob(t);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Prüft, ob ein String ein gültiger 32-Byte-Schlüssel (base64url) ist. */
export function isValidKey(k: string): boolean {
  try {
    return /^[A-Za-z0-9_\-+/=]+$/.test(k) && b64ToBytes(k).length === 32;
  } catch {
    return false;
  }
}

/** Nimmt einen eingefügten Schlüssel oder kompletten Dashboard-Link entgegen und extrahiert den Schlüssel. */
export function extractKey(input: string): string | null {
  const s = input.trim();
  const m = /[#&?]k=([A-Za-z0-9_\-+/=]+)/.exec(s);
  const k = m ? m[1] : s;
  return isValidKey(k) ? k : null;
}

export function getKey(): string | null {
  try {
    const k = window.localStorage.getItem(STORAGE_KEY);
    if (k) return k;
  } catch {}
  return memoryKey;
}

export function setKey(k: string | null): void {
  memoryKey = k;
  try {
    if (k) window.localStorage.setItem(STORAGE_KEY, k);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

/** Liest #k=… aus der Adresse, speichert ihn lokal und entfernt das Fragment aus der Adresszeile. */
export function captureKeyFromHash(): boolean {
  if (typeof window === "undefined") return false;
  const hash = window.location.hash || "";
  const m = /(?:^#|&)k=([^&]+)/.exec(hash);
  if (!m) return false;
  const k = decodeURIComponent(m[1]);
  if (isValidKey(k)) setKey(k);
  // Fragment entfernen (auch bei ungültigem Schlüssel, damit er nicht in Lesezeichen/Verlauf bleibt)
  const rest = hash
    .replace(/^#/, "")
    .split("&")
    .filter((p) => !p.startsWith("k="))
    .join("&");
  const url = window.location.pathname + window.location.search + (rest ? `#${rest}` : "");
  try {
    window.history.replaceState(window.history.state, "", url);
  } catch {}
  return isValidKey(k);
}

function importKey(k: string): Promise<CryptoKey> {
  let p = keyCache.get(k);
  if (!p) {
    p = crypto.subtle.importKey("raw", b64ToBytes(k), "AES-GCM", false, ["decrypt"]);
    keyCache.set(k, p);
    p.catch(() => keyCache.delete(k));
  }
  return p;
}

/** Entschlüsselt einen Umschlag; wirft bei falschem Schlüssel oder beschädigten Daten. */
export async function decryptEnvelope<T>(env: Envelope, k: string): Promise<T> {
  if (!crypto?.subtle) throw new Error("WebCrypto nicht verfügbar (nur über HTTPS)");
  const key = await importKey(k);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64ToBytes(env.iv) }, key, b64ToBytes(env.ct));
  return JSON.parse(new TextDecoder().decode(plain)) as T;
}
