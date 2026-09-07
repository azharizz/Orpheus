import React, { useState } from "react";
import { action, post } from "../state/store.js";
import { eventDensity, movieLanes, pageWindow, partWindow, time } from "../state/domain.js";
import { Wave } from "./waveform.jsx";
import { MatchReview } from "./families.jsx";

const left = (range, start, span) => `${(range[0] - start) / span * 100}%`;
const width = (range, span) => `${Math.max(.18, (range[1] - range[0]) / span * 100)}%`;

function Lane({ title, items, bounds, kind, openPart }) {
  const [start, end] = bounds;
  const span = Math.max(end - start, .001);
  const visible = items.filter((item) => {
    const range = item.range_s || [item.time_s, item.time_s + .1];
    return range[1] >= start && range[0] <= end;
  });
  return <div className="movie-lane"><span>{title}</span><div className="movie-lane-track">
    {visible.map((item) => { const range = item.range_s || [item.time_s, item.time_s + .1]; return <button key={item.id || `${range}`} className={`movie-mark movie-mark-${kind}`} style={{ left: left([Math.max(start, range[0]), range[1]], start, span), width: width([Math.max(start, range[0]), Math.min(end, range[1])], span) }} title={`${title} · ${time(range[0])}`} onClick={() => openPart(item)} aria-label={`Open ${title} at ${time(range[0])} in Part`} />; })}
  </div></div>;
}

function Density({ events, bounds }) {
  const counts = eventDensity(events, bounds[0], bounds[1]);
  const peak = Math.max(1, ...counts);
  return <svg className="movie-density" viewBox="0 0 120 30" preserveAspectRatio="none" role="img" aria-label="Contact density across the visible movie range">
    {counts.map((count, index) => <rect key={index} x={index} y={30 - count / peak * 28} width=".72" height={count / peak * 28} />)}
  </svg>;
}

export function MovieOverview({ project, movie, families, state, running, position, seek, openPart, activeFamily }) {
  const [page, setPage] = useState(0);
  const [span, setSpan] = useState(0);
  const [center, setCenter] = useState(position);
  const [reviewFamily, setReviewFamily] = useState(activeFamily || "");
  const bounds = span ? partWindow(center, project.seconds, span) : [0, project.seconds];
  const lanes = movieLanes(movie, families);
  const queue = pageWindow((movie?.review_queue || []).filter((item) => item.status === "unreviewed" || item.status === "review_required"), page, 6);
  const selected = families.find((family) => family.id === reviewFamily) || families.find((family) => (family.pending_matches || []).length);
  const analyze = (resume) => action(() => post("/api/movie/analyze", { project_id: project.id, resume }), resume ? "Full-movie map prepared locally." : "Full-movie map refreshed locally.");
  return <section className="movie-console" aria-labelledby="movie-console-title">
    <div className="movie-command"><div><span className="eyebrow">DETERMINISTIC MOVIE MAP / {movie?.status?.replaceAll("_", " ") || "NOT STARTED"}</span><h2 id="movie-console-title">Search wide. Decide in detail.</h2><p>This overview compresses evidence for navigation. Open any cue in Part before naming, replacing, or dismissing it. No paid inference starts here.</p></div><div className="movie-run">
      <button className="primary" disabled={running || movie?.status === "analyzing"} onClick={() => analyze(movie?.status === "not_started")}>{movie?.status === "not_started" ? "Prepare full movie map" : "Refresh movie map"}</button>
      <span>{movie?.progress || 0}% analyzed · {(movie?.events || []).length.toLocaleString()} contact cues</span>
    </div></div>
    <div className="movie-progress" aria-label={`Movie analysis ${movie?.progress || 0} percent`}><i style={{ width: `${movie?.progress || 0}%` }} /></div>
    <div className="movie-window-controls"><div role="group" aria-label="Full movie waveform duration">{[[0, "Full"], [600, "10m"], [120, "2m"]].map(([value, label]) => <button key={label} aria-pressed={span === value} onClick={() => setSpan(value)}>{label}</button>)}</div>{span > 0 && <button onClick={() => setCenter(position)}>Center at {time(position)}</button>}<output>{time(bounds[0])} – {time(bounds[1])}</output></div>
    <div className="movie-overview-wave"><Wave pid={project.id} role="original" state={state} label="Movie loudness envelope" position={position} start={bounds[0]} end={bounds[1]} bins={1200} select={seek} /><Density events={movie?.events || []} bounds={bounds} /></div>
    <div className="movie-grid"><div className="movie-timeline" aria-label="Movie sound overview">
      <div className="movie-ruler"><span>{time(bounds[0])}</span><span>{time((bounds[0] + bounds[1]) / 2)}</span><span>{time(bounds[1])}</span></div>
      <Lane title={`CONTACTS · ${(movie?.events || []).length}`} items={lanes.events} bounds={bounds} kind="event" openPart={openPart} />
      <Lane title="SUGGESTIONS" items={lanes.suggestions} bounds={bounds} kind="suggestion" openPart={openPart} />
      <Lane title="ACCEPTED" items={lanes.accepted} bounds={bounds} kind="accepted" openPart={openPart} />
      <Lane title="REJECTED" items={lanes.rejected} bounds={bounds} kind="rejected" openPart={openPart} />
      <Lane title="NOISE / WATCH" items={lanes.noise} bounds={bounds} kind="noise" openPart={openPart} />
      <div className="movie-family-ledger"><h3>Sound families</h3>{families.length ? families.map((family) => <article key={family.id}><div><strong>{family.name}</strong><span>{family.scope === "part" ? "Part only" : "Full movie"} · {(family.accepted_ranges || []).length} kept · {(family.pending_matches || []).length} pending</span></div><div><button onClick={() => openPart({ time_s: family.seed_range_s?.[0], family_id: family.id })}>Open in Part</button>{(family.pending_matches || []).length > 0 && <button aria-pressed={selected?.id === family.id} onClick={() => setReviewFamily(family.id)}>Review matches</button>}</div></article>) : <p className="muted">Resolve one sound in Part, then search for it across this movie.</p>}</div>
      {selected && (selected.pending_matches || []).length > 0 && <div className="movie-match-review"><MatchReview key={selected.id + ":" + (selected.search_version || "")} project={project} family={selected} disabled={state.busy || running} onPreview={(range) => openPart({ range_s: range, family_id: selected.id })} /></div>}
    </div><aside className="movie-queue" aria-label="Movie navigation queue"><div className="movie-queue-head"><strong>OPEN IN PART</strong><span>{queue.items.length ? `${queue.start + 1}–${queue.start + queue.items.length}` : "00"} / {(movie?.review_queue || []).length}</span></div>
      {queue.items.length ? queue.items.map((item) => <article key={item.id}><button className="queue-cue" onClick={() => openPart(item)}>{time(item.time_s)}</button><div><strong>{item.title}</strong><p>{item.reason}</p><small>{item.kind === "noise" ? "Unconfirmed sustained sound" : `${item.event_count || 0} similar energy cues`}</small></div><div className="queue-actions"><button className="primary" onClick={() => openPart(item)}>Inspect part</button></div></article>) : <p className="muted">Prepare the movie map to find navigation cues. They never change audio.</p>}
      {queue.pages > 1 && <div className="queue-pages"><button disabled={!queue.page} onClick={() => setPage(queue.page - 1)}>Previous</button><span>{queue.page + 1} / {queue.pages}</span><button disabled={queue.page + 1 >= queue.pages} onClick={() => setPage(queue.page + 1)}>Next</button></div>}
    </aside></div>
  </section>;
}
