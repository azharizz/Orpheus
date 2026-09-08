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

function WorkflowProgress({ activity, waiting, title, candidateId = "" }) {
  if (!activity && !waiting) return null;
  const status = activity?.status || (waiting ? "running" : "starting");
  const progress = Number(activity?.progress);
  const hasProgress = Number.isFinite(progress);
  const detail = activity?.label || activity?.message || waiting?.label || "Starting local work…";
  const counts = activity && (activity.cycle || activity.candidate_count)
    ? [activity.cycle ? `Cycle ${activity.cycle}` : "", activity.candidate_count ? `${activity.candidate_count} candidate${activity.candidate_count === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ")
    : "";
  const candidate = activity?.render_id || candidateId;
  return <section className={`workflow-progress workflow-progress-${status}`} role="status" aria-live="polite">
    <div className="workflow-progress-head">
      <span className="workflow-progress-mark" aria-hidden="true" />
      <div><strong>{title}</strong><p>{detail}{counts ? ` · ${counts}` : ""}{candidate ? ` · ${status === "stale" ? "Last" : "Candidate"} ${candidate}` : ""}</p></div>
      {hasProgress && <output>{Math.max(0, Math.min(100, Math.round(progress)))}%</output>}
    </div>
    {hasProgress && <div className="workflow-progress-track" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>}
  </section>;
}

function latestTurn(project, family) {
  return [...(project.turn_details || [])]
    .filter((turn) => turn.family_id === family.id)
    .sort((left, right) => Number(right.started_at) - Number(left.started_at))[0];
}

function agentActivity(turn) {
  if (!turn) return null;
  if (turn.progress) return turn.progress;
  const failed = turn.status === "failed" || turn.status === "interrupted";
  return {
    status: turn.status || "complete",
    phase: failed ? "failed" : "complete",
    label: failed
      ? "Agent run stopped before a reviewable candidate"
      : turn.selection
        ? "Candidate ready for human review"
        : "Agent finished without a selected candidate",
    cycle: turn.cycles || 0,
    candidate_count: Array.isArray(turn.candidates) ? turn.candidates.length : 0,
  };
}

function renderActivity(family) {
  if (family.render_progress) return family.render_progress;
  if (!family.latest_render_id) return null;
  return {
    status: "complete",
    phase: "ready",
    progress: 100,
    message: "Full-movie preview ready for review.",
    render_id: family.latest_render_id,
  };
}

function NewFamily({ project, position, disabled, onCreated, defer }) {
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
            defer,
          }),
        defer
          ? "Part example saved. Add and approve its replacement before searching the full movie."
          : "Sound example saved. Similar moments are ready for review when indexing completes.",
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
            Name the event and bracket one clear occurrence. This part changes
            no audio and starts no paid inference.
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
            step="0.001"
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
            step="0.001"
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
        {defer ? "Create part family" : "Find related moments"}
      </button>
    </form>
  );
}

function AddExample({ project, family, position, disabled }) {
  const [start, setStart] = useState(Math.max(0, position - 0.25));
  const [end, setEnd] = useState(Math.min(project.seconds, position + 0.25));
  async function save(event) {
    event.preventDefault();
    const range = seedRange(start, end, project.seconds);
    const result = await action(
      () => post("/api/families/examples", { project_id: project.id, family_id: family.id, range_s: range }),
      `Confirmed example added at ${time(range[0])}.`,
    );
    if (result) await loadFamilies(project.id);
  }
  return <form className="seed-editor compact-example" onSubmit={save}>
    <div className="step-heading"><span className="step-number">A1</span><div>
      <h2>Add another confirmed example</h2>
      <p>Bracket a visibly and audibly matching occurrence. Distinct examples remain separate during full-movie ranking.</p>
    </div></div>
    <div className="seed-fields">
      <label>Start (seconds)<input type="number" min="0" max={project.seconds} step="0.001" value={start} disabled={disabled} onChange={(event) => setStart(event.target.value)} /></label>
      <button type="button" disabled={disabled} onClick={() => setStart(Number(position.toFixed(3)))}>Set start at {time(position)}</button>
      <label>End (seconds)<input type="number" min="0" max={project.seconds} step="0.001" value={end} disabled={disabled} onChange={(event) => setEnd(event.target.value)} /></label>
      <button type="button" disabled={disabled} onClick={() => setEnd(Number(position.toFixed(3)))}>Set end at {time(position)}</button>
    </div>
    <button className="primary" disabled={disabled}>Add confirmed example</button>
  </form>;
}

export function MatchReview({ project, family, disabled, onPreview = () => {}, pageSize: requestedPageSize = 5, focusId = "" }) {
  const matches = pendingMatches(family);
  const [decisions, setDecisions] = useState({});
  const [auditioning, setAuditioning] = useState("");
  const pageSize = Math.max(1, Number(requestedPageSize) || 5);
  const [page, setPage] = useState(() => {
    const index = focusId ? matches.findIndex((match) => match.id === focusId) : -1;
    return index >= 0 ? Math.floor(index / pageSize) : 0;
  });
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
  function movePage(nextPage) {
    const next = pageWindow(matches, nextPage, pageSize).items[0];
    setPage(nextPage);
    if (next) onPreview(matchRange(next), next);
  }
  async function audition(match) {
    setAuditioning(match.id);
    const result = await action(
      () => post("/api/families/preview", { project_id: project.id, family_id: family.id, match_id: match.id }),
      "Replacement audition ready.",
      { kind: "match_preview", family_id: family.id, label: "Preparing this replacement audition" },
    );
    setAuditioning("");
    if (result) onPreview(matchRange(match), match, result);
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
                    onClick={() => onPreview(range, match)}
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
                  <div className="match-audition" aria-label={`Audition for match ${matchNumber}`}>
                    <button type="button" disabled={disabled} onClick={() => onPreview(range, match)}>Original</button>
                    <button type="button" disabled={disabled || !family.replacement_take_id || auditioning === match.id} onClick={() => audition(match)}>{auditioning === match.id ? "Preparing replacement…" : "Replacement"}</button>
                  </div>
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
                  onClick={() => movePage(currentPage - 1)}
                >
                  Previous
                </button>
                <span>
                  {pageStart + 1}–{Math.min(pageStart + pageSize, matches.length)} of {matches.length}
                </span>
                <button
                  type="button"
                  disabled={disabled || currentPage === pageCount - 1}
                  onClick={() => movePage(currentPage + 1)}
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
      { kind: "agent", family_id: family.id, label: "Starting the agent-coordinated fit" },
    );
    if (result) setConsent(false);
  }
  const turn = latestTurn(project, family);
  return (
    <form className="agent-fit" onSubmit={run}>
      <h3>Agent-coordinated family fit</h3>
      <p className="muted">
        The agent studies this family’s confirmed part, renders a deterministic
        baseline, and uses Grafana MCP evidence before proposing a fitted result.
        It does not search the rest of the movie.
      </p>
      <p className={state.observability?.enabled && state.config?.provider_ready ? "agent-ready" : "error"} role="status">
        {!state.config?.provider_ready
          ? "OpenRouter is not configured. Add AGENT_PROVIDER_API_KEY before authorizing a paid fit."
          : state.observability?.enabled
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
        disabled={disabled || !consent || !state.observability?.enabled || !state.config?.provider_ready}
      >
        Run agent-coordinated fit
      </button>
      <WorkflowProgress activity={agentActivity(turn)} waiting={state.operation?.kind === "agent" && state.operation.family_id === family.id ? state.operation : null} title="Agent-coordinated fit" candidateId={turn?.selection?.candidate_id || turn?.candidates?.at(-1)?.id} />
    </form>
  );
}

function PartRender({ project, family, disabled, candidate, state, onCandidate, onMovieSearch }) {
  const localPreview = () => action(async () => {
    const result = await post("/api/families/render", { project_id: project.id, family_id: family.id });
    onCandidate(result);
    return result;
  }, "Local part preview rendered. Listen before approval.");
  const propagate = () => action(async () => {
    const result = await post("/api/families/search", { project_id: project.id, family_id: family.id });
    await loadFamilies(project.id);
    onMovieSearch(family.id);
    return result;
  }, "Approved family searched across the full movie.");
  const current = candidate?.family_id === family.id && candidate.preview_kind !== "match_audition" ? candidate : family.latest_render;
  const approved = family.latest_render?.human_approved === true;
  return <>
    <section className="family-step">
      <div className="step-heading"><span className="step-number">03</span><div><h2>Fit and approve this part</h2><p>Build a local baseline or authorize the agent to refine timing, crop, and gain inside this confirmed part.</p></div></div>
      {!family.replacement_take_id && <p className="muted">Save a replacement take to enable fitting.</p>}
      <div className="actions"><button disabled={disabled || !family.replacement_take_id} onClick={localPreview}>Build local part preview</button></div>
      <AgentFit project={project} family={family} disabled={disabled || !family.replacement_take_id} state={state} />
      {current && <Review p={project} c={current} locked={disabled} />}
    </section>
    {family.scope === "part" && <section className="family-step family-propagate">
      <div className="step-heading"><span className="step-number">04</span><div><h2>Find this family across the movie</h2><p>The local acoustic index searches for this approved example. Every result remains pending until you listen and decide.</p></div></div>
      <button className="primary" disabled={disabled || !approved} onClick={propagate}>Find across full movie</button>
      {!approved && <p className="muted">Approve the current part preview to unlock the full-movie search.</p>}
    </section>}
  </>;
}

function FullMovieRender({ project, family, disabled, candidate, state, onCandidate }) {
  const pending = (family.pending_matches || []).length;
  async function render() {
    const result = await action(
      () => post("/api/families/render", { project_id: project.id, family_id: family.id }),
      "Approved full-movie family render created.",
      { kind: "full_render", family_id: family.id, label: "Starting the full-movie preview" },
    );
    if (result) onCandidate(result);
  }
  const current = candidate?.family_id === family.id && candidate.preview_kind !== "match_audition" ? candidate : family.latest_render;
  return <section className="family-step">
    <div className="step-heading"><span className="step-number">04</span><div>
      <h2>Render approved full movie</h2>
      <p>The offline renderer fits only reviewed family ranges and preserves every other sample and the picture.</p>
    </div></div>
    <button className="primary" disabled={disabled || !family.replacement_take_id} onClick={render}>Preview accepted events</button>
    <WorkflowProgress activity={renderActivity(family)} waiting={state.operation?.kind === "full_render" && state.operation.family_id === family.id ? state.operation : null} title="Full-movie preview" candidateId={current?.id || family.latest_render_id} />
    {pending > 0 && <p className="muted">Only accepted events will change. All {pending} awaiting-review matches keep their original audio.</p>}
    {current && <Review p={project} c={current} locked={disabled} />}
  </section>;
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
  selectedFamilyId,
  onMovieSearch,
  onReview,
  onFamilyChange,
  compact = false,
}) {
  const families = Array.isArray(data) ? data : data?.families || [];
  const index = data?.index || project.similarity_index;
  const indexReady = index?.status === "ready" && project.has_original_audio;
  const [chosen, setChosen] = useState(selectedFamilyId || "");
  const [adding, setAdding] = useState(false);
  const family = families.find((item) => item.id === chosen) || families[0];
  const agentTurn = family ? latestTurn(project, family) : null;
  function created(id) {
    setChosen(id || "");
    setAdding(false);
    onFamilyChange?.(id || "");
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
                onFamilyChange?.(event.target.value);
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
          defer={project.seconds >= 300}
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
          {family.scope !== "part" && project.seconds < 300 && <MatchReview key={family.id + ":" + (family.search_version || "")} project={project} family={family} disabled={disabled} pageSize={compact ? 1 : 5} onPreview={onPreview} />}
          {family.scope !== "part" && project.seconds >= 300 && <div className="family-full-link"><span>Review {(family.pending_matches || []).length} proposed matches in the film spine.</span>{onReview && <button type="button" onClick={() => onReview(family.id)}>Open review</button>}</div>}
          {family.scope !== "part" && agentTurn && <WorkflowProgress activity={agentActivity(agentTurn)} title="Agent-coordinated fit" candidateId={agentTurn.selection?.candidate_id || agentTurn.candidates?.at(-1)?.id} />}
          {family.warning && <p className="warning">{family.warning}</p>}
          {family.scope === "part" && <AddExample project={project} family={family} position={position} disabled={disabled} />}
          <section className="family-step">
            <div className="step-heading">
              <span className="step-number">{family.scope === "part" ? "02" : "03"}</span>
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
          {family.scope === "part"
            ? <PartRender project={project} family={family} disabled={disabled} candidate={candidate} state={state} onCandidate={onCandidate} onMovieSearch={onMovieSearch} />
            : <FullMovieRender project={project} family={family} disabled={disabled} candidate={candidate} state={state} onCandidate={onCandidate} />}
        </>
      )}
    </div>
  );
}
