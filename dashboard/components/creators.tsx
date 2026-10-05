"use client";

import Link from "next/link";
import { Pct } from "@/components/ui";
import { coins, parseTs, relative, shortDateTime } from "@/lib/format";
import type { Creator, CreatorPost, CreatorPostKind, CreatorsFile } from "@/lib/types";

/** Videos älter als 14 Tage werden nicht angezeigt. */
export const CREATOR_WINDOW_DAYS = 14;

export const KIND_LABEL: Record<CreatorPostKind, string> = {
  buy: "Kauf-Tipp",
  sell: "Verkaufs-Tipp",
  market: "Marktanalyse",
  info: "Sonstiges",
};

/** Nur echte https-Links verwenden (Daten kommen von außen). */
export function safeUrl(u: string | null | undefined): string | null {
  return typeof u === "string" && /^https:\/\/[^\s"'<>]+$/.test(u) ? u : null;
}

/** Posts der letzten 14 Tage, neueste zuerst. */
export function recentPosts(file: CreatorsFile, now: number): CreatorPost[] {
  const minT = now - CREATOR_WINDOW_DAYS * 86_400_000;
  return (file.posts || [])
    .filter((p) => p && p.video_id && p.title && (parseTs(p.published) ?? 0) >= minT)
    .sort((a, b) => (parseTs(b.published) ?? 0) - (parseTs(a.published) ?? 0));
}

export function KindBadge({ kind, label }: { kind: CreatorPostKind | string; label?: string | null }) {
  const k = (["buy", "sell", "market", "info"].includes(kind) ? kind : "info") as CreatorPostKind;
  return <span className={`badge badge-kind-${k}`}>{label || KIND_LABEL[k]}</span>;
}

export function NewBadge() {
  return <span className="badge badge-new">NEU</span>;
}

export function RoleBadge({ priority }: { priority: number | null | undefined }) {
  return priority === 1 ? (
    <span className="badge badge-primary">Hauptquelle</span>
  ) : (
    <span className="badge badge-neutral">Zusatzquelle</span>
  );
}

/** "05.10., 14:30 · vor 3 h" */
export function PostTime({ ts, now }: { ts: string; now: number }) {
  return (
    <span className="small muted" title={shortDateTime(ts)}>
      {shortDateTime(ts)} · {relative(ts, now)}
    </span>
  );
}

export function CreatorTile({ c }: { c: Creator }) {
  const links = [
    { label: "YouTube", url: safeUrl(c.youtube) },
    { label: "TikTok", url: safeUrl(c.tiktok) },
    { label: "Instagram", url: safeUrl(c.instagram) },
    { label: "Discord (kostenlos)", url: safeUrl(c.discord_free) },
  ].filter((l) => l.url);
  return (
    <article className={`panel creator-tile ${c.priority === 1 ? "primary" : ""}`}>
      <div className="creator-tile-head">
        <h3 style={{ margin: 0 }}>{c.name}</h3>
        <RoleBadge priority={c.priority} />
        {c.language && <span className="small muted">{c.language === "de" ? "Deutsch" : c.language === "en" ? "Englisch" : c.language}</span>}
      </div>
      {links.length > 0 && (
        <div className="creator-links">
          {links.map((l) => (
            <a key={l.label} href={l.url!} target="_blank" rel="noopener noreferrer" className="btn">
              {l.label} ↗
            </a>
          ))}
        </div>
      )}
      {c.warning && <div className="creator-warning">⚠ {c.warning}</div>}
    </article>
  );
}

export function PostItem({ p, now, compact = false }: { p: CreatorPost; now: number; compact?: boolean }) {
  const url = safeUrl(p.url);
  const cards = (p.cards || []).filter((c) => c && c.id);
  return (
    <article className={`post-item kind-${p.kind} ${compact ? "compact" : ""} ${p.priority === 1 ? "primary" : ""}`}>
      <div className="post-meta">
        <PostTime ts={p.published} now={now} />
        <span className="post-creator">{p.creator}</span>
        {compact && p.priority === 1 && <span className="badge badge-primary">Hauptquelle</span>}
        <KindBadge kind={p.kind} label={p.kind_label} />
        {p.is_new && <NewBadge />}
      </div>
      <div className="post-title">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer">
            {p.title} ↗
          </a>
        ) : (
          p.title
        )}
      </div>
      {!compact &&
        (cards.length === 0 ? (
          <div className="small muted">Karten nicht im Titel genannt – Tipps im Video</div>
        ) : (
          <ul className="post-cards">
            {cards.map((c) => (
              <li key={c.id}>
                <Link href={`/karte?id=${encodeURIComponent(c.id)}`}>{c.name || c.id}</Link>
                {c.version && <span className="small muted"> {c.version}</span>}
                <span className="post-prices">
                  <span className="num" title="Preis bei Post">
                    {coins(c.price_at_post)}
                  </span>{" "}
                  →{" "}
                  <span className="num" title="Preis jetzt">
                    {coins(c.price_now)}
                  </span>{" "}
                  <Pct value={c.change_pct} />
                </span>
              </li>
            ))}
          </ul>
        ))}
      {compact && cards.length > 0 && (
        <div className="small muted">
          Karten: {cards.map((c) => c.name || c.id).join(", ")}
        </div>
      )}
    </article>
  );
}
