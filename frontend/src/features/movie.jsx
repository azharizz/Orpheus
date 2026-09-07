import React from "react";
import { action, post } from "../state/store.js";
import { movieSpineMarkers, pendingMatches, time } from "../state/domain.js";

const count = (items) => Array.isArray(items) ? items.length : 0;
const cueAt = (item) => Number(item?.range_s?.[0] ?? item?.time_s ?? 0);
const percent = (value, duration) => `${Math.max(0, Math.min(100, value / Math.max(1, duration) * 100))}%`;

function nextStep({ movie, family, running, onMap, onOpenFamily, onOpenReview }) {
  if (!movie || movie.status === "not_started") return { label: "Prepare full-movie map", run: onMap };
  if (movie.status === "analyzing") return { label: `Mapping full movie · ${movie.progress || 0}%`, disabled: true };
  if (!family) return { label: "Mark a sound family", run: () => onOpenFamily("") };
  const pending = pendingMatches(family).length;
  if (pending) return { label: `Review ${pending} related moment${pending === 1 ? "" : "s"}`, run: () => onOpenReview(family.id) };
  return { label: "Open family workflow", run: () => onOpenFamily(family.id), disabled: running };
}

export function MovieOverview({ project, movie, families, state, running, position, seek, activeFamily, onCue, onOpenFamily, onOpenReview, onActiveFamilyChange, onOpenDetails }) {
  const family = families.find((item) => item.id === activeFamily) || families[0];
  const accepted = count(family?.accepted_ranges);
  const pending = count(pendingMatches(family));
  const markers = movieSpineMarkers(
    movie,
    families,
    family?.id || activeFamily,
    project.seconds,
    Math.min(96, Math.max(24, Math.ceil(project.seconds / 10))),
  );
  const unresolved = count((movie?.review_queue || []).filter((item) => item.status === "unreviewed" || item.status === "review_required"));
  const map = () => action(
    () => post("/api/movie/analyze", { project_id: project.id, resume: movie?.status === "not_started" }),
    movie?.status === "not_started" ? "Full-movie map prepared locally." : "Full-movie map refreshed locally.",
  );
  const step = nextStep({ movie, family, running, onMap: map, onOpenFamily, onOpenReview });
  const familyStatus = family
    ? `${accepted} kept · ${pending} awaiting review`
    : movie?.status === "not_started"
      ? "Prepare the local map, then mark the first sound."
      : `${count(movie?.events)} navigation cues · ${unresolved} unclassified`;

  return <section className="film-spine" aria-labelledby="film-spine-title">
    <div className="film-spine-head">
      <div>
        <h2 id="film-spine-title">Film spine</h2>
        <p>{family ? "Coverage for the selected sound family." : "A compact local map of the whole picture."}</p>
      </div>
      <div className="film-spine-actions">
        <button type="button" onClick={onOpenDetails}>Map details</button>
        <button className="primary" type="button" disabled={step.disabled || state.busy} onClick={step.run}>{step.label}</button>
      </div>
    </div>

    <div className="spine-track" aria-label="Full-movie cue map">
      <i className="spine-playhead" style={{ left: percent(position, project.seconds) }} aria-hidden="true" />
      {markers.map((item) => {
        const at = cueAt(item);
        const name = item.kind === "accepted" ? "kept event" : item.kind === "noise" ? "potential noise" : "awaiting review";
        return <button
          key={`${item.kind}:${item.id}:${at}`}
          type="button"
          className={`spine-mark spine-mark-${item.kind}${item.count > 1 ? " spine-mark-cluster" : ""}`}
          style={{ left: percent(at, project.seconds) }}
          title={`${time(at)} · ${item.count > 1 ? `${item.count} nearby ` : ""}${name}`}
          aria-label={`Open ${item.count > 1 ? `${item.count} nearby ` : ""}${name} at ${time(at)}`}
          onClick={() => { seek(at); onCue(item); }}
        >
          {item.count > 1 && <span>{item.count}</span>}
        </button>;
      })}
    </div>
    <div className="spine-ruler" aria-hidden="true"><span>{time(0)}</span><span>{time(project.seconds / 2)}</span><span>{time(project.seconds)}</span></div>

    <div className="film-status">
      {families.length > 0 && <label>Sound family<select value={family?.id || ""} onChange={(event) => onActiveFamilyChange(event.target.value)}>{families.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <p><strong>{family?.name || "Unclassified map"}</strong><span>{familyStatus}</span></p>
      <span className="spine-state">{movie?.status?.replaceAll("_", " ") || "not started"}</span>
    </div>
  </section>;
}
