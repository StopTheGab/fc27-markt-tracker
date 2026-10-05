"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { isStale, useData } from "./DataProvider";
import { dateTime, durationMinutes, relative, shortDateTime } from "@/lib/format";
import { DATA_BASE_URL } from "@/lib/data";

export function Header() {
  const pathname = usePathname() || "/";
  const nav = [
    { href: "/", label: "Übersicht" },
    { href: "/karten", label: "Karten" },
  ];
  return (
    <header className="site-header">
      <div className="wrap header-row">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden>
            FC
          </span>
          <span>
            Markt-Tracker <span className="muted">FC 27</span>
          </span>
        </Link>
        <nav className="nav" aria-label="Hauptnavigation">
          {nav.map((n) => {
            const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} className={active ? "active" : ""} aria-current={active ? "page" : undefined}>
                {n.label}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="wrap">
        <StatusBar />
      </div>
    </header>
  );
}

function StatusBar() {
  const { status, now, busy, reload, loadedAt } = useData();

  if (status.state === "loading") {
    return <div className="statusbar muted">Lade Daten …</div>;
  }
  if (status.state === "missing") {
    return (
      <div className="banner banner-warn" role="status">
        <strong>Noch keine Daten vom Collector.</strong> Der Datenbereich (Branch <code>data</code>) existiert noch nicht
        oder enthält keine <code>status.json</code>. Sobald der Collector läuft, erscheinen hier echte Preise.
        <RetryButton busy={busy} onClick={reload} />
      </div>
    );
  }
  if (status.state === "error") {
    return (
      <div className="banner banner-danger" role="alert">
        <strong>Daten konnten nicht geladen werden.</strong> {status.message}
        <RetryButton busy={busy} onClick={reload} />
      </div>
    );
  }

  const s = status.data;
  const { stale, reasons } = isStale(s, now);
  const gaps = (s.gaps || []).filter((g) => g && g.from);
  const recentGaps = gaps.slice(-3).reverse();
  const sourceOk = s.source?.ok !== false;

  return (
    <div className="status-stack">
      {stale && (
        <div className="banner banner-danger" role="alert">
          <strong>⚠ Daten veraltet – nicht danach handeln!</strong>
          <ul>
            {reasons.map((r) => (
              <li key={r}>{r}.</li>
            ))}
          </ul>
          <span className="small">
            Letzte Ausgabe: {dateTime(s.generated_at)} · letzter erfolgreicher Abruf:{" "}
            {s.last_successful_fetch ? dateTime(s.last_successful_fetch) : "nie"}
          </span>
        </div>
      )}
      {!sourceOk && (
        <div className="banner banner-danger" role="alert">
          <strong>Datenquelle gestört{s.source?.name ? ` (${s.source.name})` : ""}:</strong>{" "}
          {s.source?.message || "Keine Erklärung vom Collector."}
        </div>
      )}
      <div className="statusbar">
        <span>
          Aktualisiert <strong title={dateTime(s.generated_at)}>{relative(s.generated_at, now)}</strong>
          <span className="muted"> ({dateTime(s.generated_at)})</span>
        </span>
        <span className="muted">
          Quelle:{" "}
          {s.source?.url ? (
            <a href={s.source.url} target="_blank" rel="noopener noreferrer">
              {s.source?.name || s.source?.id || "unbekannt"}
            </a>
          ) : (
            s.source?.name || s.source?.id || "unbekannt"
          )}
          <span className={`dot ${sourceOk ? "dot-ok" : "dot-bad"}`} aria-label={sourceOk ? "Quelle ok" : "Quelle gestört"} />
        </span>
        {typeof s.cards_tracked === "number" && (
          <span className="muted">
            {s.cards_with_price ?? "–"} / {s.cards_tracked} Karten mit Preis
          </span>
        )}
        <button type="button" className="link-btn" onClick={reload} disabled={busy} title={loadedAt ? `Zuletzt geladen ${shortDateTime(loadedAt)}` : undefined}>
          {busy ? "lädt …" : "neu laden"}
        </button>
      </div>
      {recentGaps.length > 0 && (
        <details className="banner banner-info">
          <summary>
            Datenlücken: {gaps.length} {gaps.length === 1 ? "Lücke" : "Lücken"} im Verlauf – Werte in diesen Zeiträumen
            fehlen
          </summary>
          <ul>
            {recentGaps.map((g) => (
              <li key={g.from + g.to}>
                {shortDateTime(g.from)} – {shortDateTime(g.to)} ({durationMinutes(g.minutes)})
              </li>
            ))}
            {gaps.length > 3 && <li className="muted">… und {gaps.length - 3} ältere</li>}
          </ul>
        </details>
      )}
      {s.errors_last_run && s.errors_last_run.length > 0 && (
        <details className="banner banner-info">
          <summary>{s.errors_last_run.length} Fehlermeldung(en) im letzten Collector-Lauf</summary>
          <ul>
            {s.errors_last_run.slice(0, 10).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </details>
      )}
      {process.env.NEXT_PUBLIC_DATA_BASE_URL && (
        <div className="small muted">Datenbasis: {DATA_BASE_URL}</div>
      )}
    </div>
  );
}

function RetryButton({ busy, onClick }: { busy: boolean; onClick: () => void }) {
  return (
    <div style={{ marginTop: 8 }}>
      <button type="button" className="btn" onClick={onClick} disabled={busy}>
        {busy ? "lädt …" : "Erneut versuchen"}
      </button>
    </div>
  );
}
