import React, { useState } from "react";
import { action, loadFamilies, post, update } from "../state/store.js";
import { matchRange, pageWindow, pendingMatches, seedRange, time, label } from "../state/domain.js";
import { Recorder } from "./takes.jsx";
import { Review } from "./review.jsx";

export function IndexStatus({ project, data }) {
  const index = data?.index || project.similarity_index || {};
  const status = index.status || project.index_status || project.status;
  const done = Number(index.completed_windows);
  const total = Number(index.total_windows);
  return (
    <div className="index-status" role="status">
      <span className={"status-mark status-" + String(status || "pending")} />
      <div>
        <strong>{label(status || "Preparing sound index")}</strong>
        <p className="muted">
          {Number.isFinite(done) && Number.isFinite(total) && total > 0
            ? `${done.toLocaleString()} of ${total.toLocaleString()} sound windows indexed`
            : index.message || "Orpheus will report measured progress when it is available."}
        </p>
      </div>
    </div>
  );
}

function NewFamily({ project, position, disabled, onCreated }) {
  const [name, setName] = useState("");
  const [start, setStart] = useState(Math.max(0, position - 0.25));
  const [end, setEnd] = useState(Math.min(project.seconds, position + 0.25));
  async function create(event) {
    event.preventDefault();
    try {
      const range = seedRange(start, end, project.seconds);
      const result = await action(
        () =>
          post("/api/families", {
            project_id: project.id,
            name: name.trim() || `Sound at ${time(range[0])}`,
            seed_range_s: range,
          }),
        "Sound example saved. Similar moments are ready for review when indexing completes.",
      );
      if (result) {
        await loadFamilies(project.id);
        onCreated(result.family?.id || result.id);
      }
    } catch (error) {
      update({ error: error.message });
    }
  }
  return (
    <form className="seed-editor" onSubmit={create}>
      <div className="step-heading">
        <span className="step-number">01</span>
        <div>
          <h2>Mark one sound</h2>
          <p>
            Name the event and bracket one clear occurrence. This example
            starts a review queue; it changes no audio.
          </p>
        </div>
      </div>
      <label>
        Sound family
        <input
          value={name}
          maxLength="80"
          placeholder="Boot steps on concrete"
          disabled={disabled}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <div className="seed-fields">
        <label>
          Start (seconds)
          <input
            type="number"
            min="0"
            max={project.seconds}
            step="0.01"
            value={start}
            disabled={disabled}
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={() => setStart(Number(position.toFixed(3)))}
        >
          Set start at {time(position)}
        </button>
        <label>
          End (seconds)
          <input
            type="number"
            min="0"
            max={project.seconds}
            step="0.01"
            value={end}
            disabled={disabled}
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={() => setEnd(Number(position.toFixed(3)))}
        >
          Set end at {time(position)}
        </button>
      </div>
      <button className="primary" disabled={disabled}>
        Find related moments
      </button>
    </form>
  );
}

function MatchReview({ project, family, disabled, onPreview }) {
  const matches = pendingMatches(family);
  const [decisions, setDecisions] = useState({});
  const [page, setPage] = useState(0);
  const pageSize = 5;
  const window = pageWindow(matches, page, pageSize);
  const { items: visibleMatches, page: currentPage, pages: pageCount, start: pageStart } = window;
  const decided = Object.keys(decisions).length;
  async function save() {
    const result = await action(
      () =>
        post("/api/families/review", {
          project_id: project.id,
          family_id: family.id,
          decisions: Object.entries(decisions).map(([match_id, decision]) => ({
            match_id,
            decision,
          })),
        }),
      `${decided} match decision${decided === 1 ? "" : "s"} saved.`,
    );
    if (result) {
      setDecisions({});
      setPage(0);
      await loadFamilies(project.id);
    }
  }
  return (
    <section className="family-step" aria-labelledby="matches-title">
      <div className="step-heading">
        <span className="step-number">02</span>
        <div>
          <h2 id="matches-title">Review related moments</h2>
          <p>
            Similarity orders the queue. It is evidence for listening, not an
            accuracy score.
          </p>
        </div>
      </div>
      {matches.length ? (
        <>
          <ol className="match-list">
            {visibleMatches.map((match, index) => {
              const range = matchRange(match);
              const choice = decisions[match.id];
              const matchNumber = pageStart + index + 1;
              return (
                <li key={match.id}>
                  <button
                    className="match-cue"
                    type="button"
                    disabled={disabled}
                    aria-label={`Play match ${matchNumber} from ${time(range[0])} to ${time(range[1])}`}
                    onClick={() => onPreview(range)}
                  >
                    <span className="match-play" aria-hidden="true">▶</span>
                    <span>
                      Match {String(matchNumber).padStart(2, "0")}
                      <small>{time(range[0])} – {time(range[1])}</small>
                    </span>
                    <span className="match-rank">
                      {Number.isFinite(Number(match.similarity_score))
                        ? Number(match.similarity_score).toFixed(3)
                        : "ranked"}
                    </span>
                  </button>
                  {match.evidence_summary && (
                    <details className="match-evidence">
                      <summary>Ranking evidence</summary>
                      <p>{match.evidence_summary}</p>
                    </details>
                  )}
                  <div className="match-actions" aria-label={`Decision for match ${matchNumber}`}>
                    <button
                      type="button"
                      aria-pressed={choice === "accepted"}
                      disabled={disabled}
                      onClick={() => setDecisions({ ...decisions, [match.id]: "accepted" })}
                    >
                      Keep
                    </button>
                    <button
                      type="button"
                      aria-pressed={choice === "rejected"}
                      disabled={disabled}
                      onClick={() => setDecisions({ ...decisions, [match.id]: "rejected" })}
                    >
                      Exclude
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
          <div className="match-footer">
            {pageCount > 1 && (
              <nav className="match-pagination" aria-label="Match review pages">
                <button
                  type="button"
                  disabled={disabled || currentPage === 0}
                  onClick={() => setPage(currentPage - 1)}
                >
                  Previous
                </button>
                <span>
                  {pageStart + 1}–{Math.min(pageStart + pageSize, matches.length)} of {matches.length}
                </span>
                <button
                  type="button"
                  disabled={disabled || currentPage === pageCount - 1}
                  onClick={() => setPage(currentPage + 1)}
                >
                  Next
                </button>
              </nav>
            )}
            <button className="primary" disabled={disabled || !decided} onClick={save}>
              Save {decided || ""} reviewed {decided === 1 ? "match" : "matches"}
            </button>
          </div>
        </>
      ) : (
        <p className="empty-line">
          {family.status === "indexing" || family.status === "searching"
            ? "Searching the measured soundtrack. No completion estimate is available yet."
            : "No unreviewed matches. Accepted and excluded moments remain attached to this family."}
        </p>
      )}
    </section>
  );
}

function rangesCount(value) {
  return Array.isArray(value) ? value.length : 0;
}

function AgentFit({ project, family, disabled, state }) {
  const [feedback, setFeedback] = useState("");
  const [consent, setConsent] = useState(false);
  async function run(event) {
    event.preventDefault();
    const result = await action(
      () => post("/api/run", {
        project_id: project.id,
        family_id: family.id,
        feedback: feedback.trim() || undefined,
        consent,
      }),
      "Agent fitting started. The workspace will show its measured render when complete.",
    );
    if (result) setConsent(false);
  }
  return (
    <form className="agent-fit" onSubmit={run}>
      <h3>Agent-coordinated family fit</h3>
      <p className="muted">
        Orpheus renders a deterministic baseline, asks the agent to improve timing,
        crop, and gain, then requires Grafana MCP evidence before proposing a result.
        Every edit stays inside kept moments.
      </p>
      <p className={state.observability?.enabled ? "agent-ready" : "error"} role="status">
        {state.observability?.enabled
          ? "Grafana MCP ready · deterministic family evidence will support this run"
          : "Grafana MCP is required. Start the local observability stack first."}
      </p>
      <label>
        Direction for this pass
        <textarea
          value={feedback}
          maxLength={state.config?.max_feedback_chars || 500}
          placeholder="Tighter contact, less tail"
          disabled={disabled}
          onChange={(event) => setFeedback(event.target.value)}
        />
      </label>
      <label className="consent-row">
        <input
          type="checkbox"
          checked={consent}
          disabled={disabled}
          onChange={(event) => setConsent(event.target.checked)}
        />
        Run paid inference, capped at {state.config?.max_controller_calls || 40} controller calls
      </label>
      <button
        className="primary"
        disabled={disabled || !consent || !state.observability?.enabled}
      >
        Run agent-coordinated fit
      </button>
    </form>
  );
}

export function FamilyWorkbench({
  project,
  data,
  position,
  disabled,
  transport,
  candidate,
  state,
  onCandidate,
  onPreview,
}) {
  const families = Array.isArray(data) ? data : data?.families || [];
  const index = data?.index || project.similarity_index;
  const indexReady = index?.status === "ready" && project.has_original_audio;
  const [chosen, setChosen] = useState("");
  const [adding, setAdding] = useState(false);
  const family = families.find((item) => item.id === chosen) || families[0];
  function created(id) {
    setChosen(id || "");
    setAdding(false);
  }
  return (
    <div className="family-workbench">
      <IndexStatus project={project} data={data} />
      {data?.error && <p className="error">{data.error}</p>}
      {families.length > 0 && (
        <div className="family-selector">
          <label>
            Sound family
            <select
              value={family?.id || ""}
              disabled={disabled}
              onChange={(event) => {
                setChosen(event.target.value);
                setAdding(false);
              }}
            >
              {families.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {label(item.status)}
                </option>
              ))}
            </select>
          </label>
          <button type="button" aria-pressed={adding} onClick={() => setAdding(!adding)}>
            {adding ? "Return to family" : "Mark another sound"}
          </button>
        </div>
      )}
      {(!family || adding) && (
        <NewFamily
          project={project}
          position={position}
          disabled={disabled || !indexReady}
          onCreated={created}
        />
      )}
      {(!family || adding) && !indexReady && (
        <p className="muted">
          {project.has_original_audio
            ? "Finish indexing before marking a sound example."
            : "This picture has no original soundtrack to search."}
        </p>
      )}
      {family && !adding && (
        <>
          <div className="family-heading">
            <div>
              <h2>{family.name}</h2>
            </div>
            <p>
              {rangesCount(family.accepted_ranges)} kept ·{" "}
              {rangesCount(family.rejected_ranges)} excluded
            </p>
          </div>
          <MatchReview
            key={family.id + ":" + (family.search_version || "")}
            project={project}
            family={family}
            disabled={disabled}
            onPreview={onPreview}
          />
          {family.warning && <p className="warning">{family.warning}</p>}
          <section className="family-step">
            <div className="step-heading">
              <span className="step-number">03</span>
              <div>
                <h2>Perform the replacement</h2>
                <p>
                  Record or upload one take for this family. The original stays
                  intact outside moments you kept.
                </p>
              </div>
            </div>
            <Recorder
              key={family.id}
              p={project}
              family={family}
              state={state}
              transport={transport}
            />
          </section>
          <section className="family-step">
            <div className="step-heading">
              <span className="step-number">04</span>
              <div>
                <h2>Render and listen</h2>
                <p>
                  The renderer ducks accepted moments and overlays the fitted
                  take. Review the actual export before approval.
                </p>
              </div>
            </div>
            {family.warnings?.length > 0 && (
              <ul className="family-warnings">
                {family.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
            {!family.replacement_take_id && (
              <p className="muted">Save a replacement take to enable agent fitting.</p>
            )}
            <AgentFit
              project={project}
              family={family}
              disabled={disabled || !family.replacement_take_id}
              state={state}
            />
            {candidate && (
              <Review
                p={project}
                c={candidate}
                locked={disabled}
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}
