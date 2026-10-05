"use client";

import { useMemo, useState } from "react";
import { useData } from "@/components/DataProvider";
import { CREATOR_WINDOW_DAYS, CreatorTile, PostItem, recentPosts } from "@/components/creators";
import { LoadNotice } from "@/components/ui";
import { dateTime } from "@/lib/format";
import type { CreatorPostKind } from "@/lib/types";

const KIND_FILTERS: { id: "" | Exclude<CreatorPostKind, "info">; label: string }[] = [
  { id: "", label: "Alle" },
  { id: "buy", label: "Kauf" },
  { id: "sell", label: "Verkauf" },
  { id: "market", label: "Markt" },
];

export default function CreatorPage() {
  const { creators, now } = useData();
  const [creator, setCreator] = useState("");
  const [kind, setKind] = useState<(typeof KIND_FILTERS)[number]["id"]>("");

  const list = useMemo(() => (creators.state === "ok" ? recentPosts(creators.data, now) : []), [creators, now]);
  const tiles = useMemo(
    () =>
      creators.state === "ok"
        ? (creators.data.creators || []).filter((c) => c && c.id).sort((a, b) => (a.priority ?? 9) - (b.priority ?? 9))
        : [],
    [creators],
  );
  const shown = list.filter((p) => (!creator || p.creator_id === creator) && (!kind || p.kind === kind));

  return (
    <>
      <section className="section">
        <div className="section-head">
          <h1>Creator-Tipps</h1>
          {creators.state === "ok" && (
            <span className="small muted">Stand {dateTime(creators.data.generated_at)}</span>
          )}
        </div>
        {creators.state === "missing" ? (
          <div className="panel empty">
            <strong>Noch keine Creator-Daten.</strong>
            <div className="small" style={{ marginTop: 4 }}>
              Sie erscheinen nach dem nächsten Collector-Lauf (alle 15 Minuten).
            </div>
          </div>
        ) : creators.state !== "ok" ? (
          <LoadNotice loaded={creators} what="Creator-Daten" />
        ) : (
          <div className="creator-tiles">
            {tiles.map((c) => (
              <CreatorTile key={c.id} c={c} />
            ))}
          </div>
        )}
      </section>

      {creators.state === "ok" && (
        <section className="section">
          <div className="section-head">
            <h2>Videos der letzten {CREATOR_WINDOW_DAYS} Tage</h2>
            <span className="small muted">
              {shown.length} von {list.length}
            </span>
          </div>
          <div className="filters creator-filters">
            <label className="field">
              Creator
              <select value={creator} onChange={(e) => setCreator(e.target.value)}>
                <option value="">Alle</option>
                {tiles.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-group" role="group" aria-label="Art">
              <span className="field-label">Art</span>
              <div className="range-bar">
                {KIND_FILTERS.map((k) => (
                  <button
                    key={k.id || "all"}
                    type="button"
                    className={`btn ${kind === k.id ? "active" : ""}`}
                    aria-pressed={kind === k.id}
                    onClick={() => setKind(k.id)}
                  >
                    {k.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          {list.length === 0 ? (
            <div className="panel empty">Keine Videos in den letzten {CREATOR_WINDOW_DAYS} Tagen.</div>
          ) : shown.length === 0 ? (
            <div className="panel empty">Keine Videos für diesen Filter.</div>
          ) : (
            <div className="post-list">
              {shown.map((p) => (
                <PostItem key={p.video_id} p={p} now={now} />
              ))}
            </div>
          )}
          {creators.data.note && <p className="small muted" style={{ marginTop: 12 }}>{creators.data.note}</p>}
        </section>
      )}
    </>
  );
}
