import React, { useState } from "react";
import { action, post, media } from "./store.js";
import { time } from "./domain.js";

export function Evidence({ p, c, row, state }) {
  const [topic, setTopic] = useState("sound");
  const [receipt, setReceipt] = useState(null);
  const [log, setLog] = useState("");
  const telemetry = state.observability;
  const last = p.turn_details?.at(-1);
  const metrics = Object.entries(c?.metrics || {}).filter(
    ([, v]) => typeof v === "number",
  );
  async function query() {
    const result = await action(
      () =>
        post("/api/grafana", {
          project_id: p.id,
          topic,
          candidate_id: c?.id || "",
        }),
      "Grafana query completed. Inspect its evidence status.",
    );
    if (result) setReceipt(result);
  }
  return (
    <aside className="evidence-rail" aria-label="Selected action and evidence">
      <section>
        <h2>{row ? "Selected action" : "Picture, sound, evidence"}</h2>
        {row ? (
          <>
            <p>
              {row.id} · {row.disposition} · {row.confidence}
            </p>
            <p>{row.evidence}</p>
            <dl>
              <dt>Picture range</dt>
              <dd>{row.target_range_s.map(time).join(" – ")}</dd>
              <dt>Source range · independent clock</dt>
              <dd>{row.source_range_s.map(time).join(" – ")}</dd>
            </dl>
            {row.disposition === "use" && (
              <audio
                key={row.id + JSON.stringify(row.source_range_s)}
                controls
                preload="none"
                aria-label="Audition selected source crop"
                src={
                  "/api/snippet?" +
                  new URLSearchParams({
                    project_id: p.id,
                    start: row.source_range_s[0],
                    end: row.source_range_s[1],
                  })
                }
              />
            )}
          </>
        ) : (
          <p>
            Select an action to follow its picture evidence, source crop and
            rendered sound.
          </p>
        )}
      </section>
      <section>
        <h2>Export measurements</h2>
        {c ? (
          <>
            <p className="muted">
              Candidate {c.id}. Measurements describe the export; they do not
              approve the sound.
            </p>
            <dl>
              {metrics.slice(0, 3).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{Number(value).toFixed(2)}</dd>
                </React.Fragment>
              ))}
            </dl>
            <details>
              <summary>Full candidate receipt</summary>
              <pre>{JSON.stringify(c, null, 2)}</pre>
            </details>
          </>
        ) : (
          <p>No rendered candidate yet.</p>
        )}
      </section>
      <section>
        <h2>Grafana evidence</h2>
        <p>
          {telemetry?.error
            ? "Unavailable"
            : !telemetry
              ? "Checking configuration…"
              : telemetry.enabled
                ? `${telemetry.pending_exports} pending exports · Query to check freshness`
                : "Not configured"}
        </p>
        {telemetry?.dashboard_url && (
          <a
            href={telemetry.dashboard_url + "?var-project=" + p.id}
            target="_blank"
            rel="noreferrer"
          >
            Open Grafana
          </a>
        )}
        <label>
          Investigate
          <select value={topic} onChange={(e) => setTopic(e.target.value)}>
            {[
              ["sound", "Sound measurements"],
              ["history", "Experiment history"],
              ["takes", "Recorded takes"],
              ["failures", "Failures"],
              ["runtime", "Runtime"],
            ].map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button disabled={state.busy} onClick={query}>
          Query official Grafana MCP
        </button>
        {receipt && (
          <details open>
            <summary>
              Query receipt · {receipt.status || "Inspect result"}
            </summary>
            <pre>{JSON.stringify(receipt, null, 2)}</pre>
          </details>
        )}
      </section>
      <section>
        <h2>Agent findings</h2>
        {last?.selection ? (
          <>
            <p>{last.selection.comparison}</p>
            <ul>
              {last.selection.unresolved?.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>No final selection. Completed candidates remain provisional.</p>
        )}
        <details>
          <summary>Session notes and turn receipts</summary>
          <pre>{JSON.stringify(p.turn_details, null, 2)}</pre>
        </details>
        <details>
          <summary>Structured tool log</summary>
          <button
            onClick={() =>
              action(async () => {
                const response = await fetch(media(p.id, "events.jsonl"));
                if (!response.ok) throw Error("No tool log available.");
                setLog(await response.text());
              })
            }
          >
            Load log
          </button>
          <pre>{log}</pre>
        </details>
      </section>
    </aside>
  );
}
