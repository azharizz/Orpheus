import React, { useState } from "react";
import { action, post } from "../state/store.js";

export function Evidence({ p, c, state }) {
  const [topic, setTopic] = useState("sound");
  const [receipt, setReceipt] = useState(null);
  const [lens, setLens] = useState(null);
  const [range, setRange] = useState({ start: "0", end: "" });
  const telemetry = state.observability;
  const part = {
    part_start_s: Number(range.start),
    part_end_s: Number(range.end),
  };
  const partReady = Number.isFinite(part.part_start_s)
    && Number.isFinite(part.part_end_s)
    && part.part_end_s > part.part_start_s;
  async function inspectPart() {
    const result = await action(
      () => post("/api/grafana/part", { project_id: p.id, part, candidate_id: c?.id || "" }),
      "Part evidence read. Unresolved states are not approvals.",
    );
    if (result) setLens(result);
  }
  async function capture() {
    await action(
      () => post("/api/grafana/snapshot", { project_id: p.id, part: partReady ? part : null }),
      "Immutable evidence snapshot captured.",
    );
  }
  const metrics = Object.entries(c?.metrics || {}).filter(([, value]) => typeof value === "number");
  const fitting = c?.agent_fitting;
  async function query() {
    const result = await action(
      () => post("/api/grafana", {
        project_id: p.id,
        topic,
        candidate_id: c?.id || "",
        ...(topic === "part" && partReady ? { part } : {}),
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
        <h2>Agent decision evidence</h2>
        {fitting?.grafana_evidence?.history && fitting?.grafana_evidence?.sound ? (
          <>
            <p>
              The agent compared this proposal with deterministic baseline{" "}
              <strong>{fitting.deterministic_baseline?.id}</strong>.
            </p>
            <dl>
              <dt>Grafana history receipt</dt>
              <dd>{fitting.grafana_evidence.history}</dd>
              <dt>Grafana candidate receipt</dt>
              <dd>{fitting.grafana_evidence.sound}</dd>
            </dl>
          </>
        ) : (
          <p>No agent-coordinated evidence receipt for this preview.</p>
        )}
      </section>
      <section>
        <h2>Part evidence lens</h2>
        <p className="muted">One picture range, read the same way by the agent and by you.</p>
        <label>
          Part start (s)
          <input type="number" min="0" step="0.1" value={range.start}
            onChange={(event) => setRange({ ...range, start: event.target.value })} />
        </label>
        <label>
          Part end (s)
          <input type="number" min="0" step="0.1" value={range.end}
            onChange={(event) => setRange({ ...range, end: event.target.value })} />
        </label>
        <button className="primary" disabled={state.busy || !partReady} onClick={inspectPart}>
          Read this Part
        </button>
        <button disabled={state.busy} onClick={capture}>Capture snapshot</button>
        {lens && (
          <>
            <dl>
              <dt>Rows in Part</dt>
              <dd>{lens.row_count}{lens.truncated ? " (truncated)" : ""}</dd>
              <dt>Measured events</dt>
              <dd>{lens.measured_events}</dd>
              <dt>Worst timing error</dt>
              <dd>{lens.max_abs_timing_error_ms === null ? "not measured" : `${lens.max_abs_timing_error_ms} ms`}</dd>
            </dl>
            {lens.unresolved?.length > 0 && (
              <p className="muted">Unresolved: {lens.unresolved.join(", ")}. Not an approval.</p>
            )}
            <details>
              <summary>Decision ledger · {lens.decisions.length} entries</summary>
              <ol>
                {lens.decisions.map((d) => (
                  <li key={d.evidence_id || `${d.event}-${d.observed_at}`}>
                    {d.owner} · {d.event}{d.decision ? ` · ${d.decision}` : ""}
                  </li>
                ))}
              </ol>
            </details>
          </>
        )}
      </section>
      <section>
        <h2>Grafana evidence</h2>
        <p>
          {telemetry?.error ? "Unavailable" : !telemetry ? "Checking configuration…" :
            telemetry.enabled ? `${telemetry.pending_exports} pending exports · Query to check freshness` : "Not configured"}
        </p>
        {telemetry?.dashboard_url && (
          <a
            className="button-link"
            href={telemetry.dashboard_url + "?var-project=" + p.id
              + (partReady ? `&var-part_start=${part.part_start_s}&var-part_end=${part.part_end_s}` : "")
              + (c?.id ? `&var-candidate=${c.id}` : "")}
            target="_blank"
            rel="noreferrer"
          >
            Open Grafana
          </a>
        )}
        <label>
          Investigate
          <select value={topic} onChange={(event) => setTopic(event.target.value)}>
            <option value="sound">Sound measurements</option>
            <option value="part">This Part</option>
            <option value="history">Experiment history</option>
            <option value="takes">Recorded takes</option>
            <option value="failures">Failures</option>
            <option value="runtime">Runtime</option>
          </select>
        </label>
        <button className="primary" disabled={state.busy} onClick={query}>Query official Grafana MCP</button>
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
