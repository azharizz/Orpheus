import React, { useState } from "react";
import { action, post } from "../state/store.js";

export function Evidence({ p, c, state }) {
  const [topic, setTopic] = useState("sound");
  const [receipt, setReceipt] = useState(null);
  const telemetry = state.observability;
  const metrics = Object.entries(c?.metrics || {}).filter(([, value]) => typeof value === "number");
  async function query() {
    const result = await action(
      () => post("/api/grafana", {
        project_id: p.id,
        topic,
        candidate_id: c?.id || "",
      }),
      "Grafana query completed. Inspect its evidence status.",
    );
    if (result) setReceipt(result);
  }
  return (
    <aside className="evidence-rail" aria-label="Sound and evidence">
      <section>
        <h2>Picture, sound, evidence</h2>
        <p>Review each proposed event, then judge the rendered result by listening.</p>
      </section>
      <section>
        <h2>Export measurements</h2>
        {c ? (
          <>
            <p className="muted">Candidate {c.id}. Measurements describe the export; they do not approve it.</p>
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
        ) : <p>No rendered candidate yet.</p>}
      </section>
      <section>
        <h2>Grafana evidence</h2>
        <p>
          {telemetry?.error ? "Unavailable" : !telemetry ? "Checking configuration…" :
            telemetry.enabled ? `${telemetry.pending_exports} pending exports · Query to check freshness` : "Not configured"}
        </p>
        {telemetry?.dashboard_url && (
          <a href={telemetry.dashboard_url + "?var-project=" + p.id} target="_blank" rel="noreferrer">
            Open Grafana
          </a>
        )}
        <label>
          Investigate
          <select value={topic} onChange={(event) => setTopic(event.target.value)}>
            <option value="sound">Sound measurements</option>
            <option value="history">Experiment history</option>
            <option value="takes">Recorded takes</option>
            <option value="failures">Failures</option>
            <option value="runtime">Runtime</option>
          </select>
        </label>
        <button disabled={state.busy} onClick={query}>Query official Grafana MCP</button>
        {receipt && (
          <details open>
            <summary>Query receipt · {receipt.status || "Inspect result"}</summary>
            <pre>{JSON.stringify(receipt, null, 2)}</pre>
          </details>
        )}
      </section>
    </aside>
  );
}
