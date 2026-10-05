"use client";

import { useState } from "react";
import { useData } from "./DataProvider";
import { extractKey } from "@/lib/crypto";

export const KEY_MESSAGE =
  "Schlüssel fehlt oder falsch – bitte den Dashboard-Link aus der FC27-Mail bzw. aus STATUS.md öffnen";

/** Hinweis + Eingabefeld, wenn die Preisdaten verschlüsselt sind und kein gültiger Schlüssel vorliegt. */
export function KeyPrompt() {
  const { locked, applyKey, busy } = useData();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!locked) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const k = extractKey(value);
    if (!k) {
      setError("Das ist kein gültiger Schlüssel (erwartet: 32 Byte, base64url) oder Dashboard-Link mit #k=…");
      return;
    }
    setError(null);
    setValue("");
    applyKey(k);
  };

  return (
    <div className="banner banner-warn" role="alert">
      <strong>🔒 {KEY_MESSAGE}.</strong>
      <div className="small" style={{ marginTop: 4 }}>
        {locked === "invalid"
          ? "Mit dem gespeicherten Schlüssel ließen sich die Preisdaten nicht entschlüsseln."
          : "Die Preisdaten sind verschlüsselt. Ohne Schlüssel werden keine Preise angezeigt."}{" "}
        Der Schlüssel wird nur in diesem Browser gespeichert und nie an einen Server geschickt.
      </div>
      <form onSubmit={submit} className="key-form">
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="Schlüssel oder kompletten Dashboard-Link einfügen"
          aria-label="Schlüssel"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button type="submit" className="btn" disabled={busy || !value.trim()}>
          Entsperren
        </button>
        {locked === "invalid" && (
          <button type="button" className="btn" onClick={() => applyKey(null)}>
            Gespeicherten Schlüssel löschen
          </button>
        )}
      </form>
      {error && <div className="small" style={{ color: "#ffb3b3", marginTop: 4 }}>{error}</div>}
    </div>
  );
}
