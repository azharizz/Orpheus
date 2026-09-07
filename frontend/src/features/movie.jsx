import React, { useState } from "react";
import { action, post } from "../state/store.js";
import { movieLanes, pageWindow, time } from "../state/domain.js";

const width = (range, duration) => `${Math.max(.18, (range[1] - range[0]) / duration * 100)}%`;
const left = (range, duration) => `${range[0] / duration * 100}%`;

function Lane({ title, items, duration, kind, seek }) {
  return <div className="movie-lane">
    <span>{title}</span>
    <div className="movie-lane-track">
      {items.map((item) => {
        const range = item.range_s || [item.time_s, item.time_s + .1];
        return <button key={item.id || `${range}`} className={`movie-mark movie-mark-${kind}`} style={{ left: left(range, duration), width: width(range, duration) }} title={`${title} · ${time(range[0])}`} onClick={() => seek(range[0])} aria-label={`Seek to ${title} at ${time(range[0])}`} />;
      })}
    </div>
  </div>;
}

export function MovieOverview({ project, movie, families, running, seek }) {
  const [consent, setConsent] = useState(false);
  const [page, setPage] = useState(0);
  const lanes = movieLanes(movie, families);
  const queue = pageWindow(movie?.review_queue || [], page, 4);
  const ready = families.filter((family) => family.replacement_take_id && family.accepted_ranges?.length).length;
  const run = () => action(() => post("/api/movie/run", { project_id: project.id, consent, feedback: "Coordinate the entire movie. Use deterministic evidence and Grafana history before family fitting; leave ambiguous sounds untouched for human review." }), "Movie agent started in the background.");
  const analyze = () => action(() => post("/api/movie/analyze", { project_id: project.id, resume: true }), "Movie evidence prepared.");
  const decide = (item, decision) => action(() => post("/api/movie/review", { project_id: project.id, item_id: item.id, decision }), "Movie review saved.");
  const render = () => action(() => post("/api/movie/render", { project_id: project.id }), "Reviewed movie draft rendered.");
  return <section className="movie-console" aria-labelledby="movie-console-title">
    <div className="movie-command">
      <div>
        <span className="eyebrow">MOVIE COORDINATOR / {movie?.status?.replaceAll("_", " ") || "NOT STARTED"}</span>
        <h2 id="movie-console-title">One picture. Every sound decision.</h2>
        <p>Deterministic contact evidence supports the agent. Grafana history is required before candidate selection. Unknown sounds stay untouched.</p>
      </div>
      <div className="movie-run">
        <label><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> Allow paid agent coordination</label>
        <button className="primary" disabled={running || !consent} onClick={run}>{running ? "Agent working…" : "Run agent on movie"}</button>
        {movie?.status === "not_started" && <button disabled={running} onClick={analyze}>Prepare evidence only</button>}
        {ready > 0 && <button disabled={running} onClick={render}>Build reviewed draft · {ready}</button>}
      </div>
    </div>
    <div className="movie-progress" aria-label={`Movie analysis ${movie?.progress || 0} percent`}><i style={{ width: `${movie?.progress || 0}%` }} /></div>
    <div className="movie-grid">
      <div className="movie-timeline" aria-label="Movie sound overview">
        <div className="movie-ruler"><span>00:00</span><span>{time(project.seconds / 2)}</span><span>{time(project.seconds)}</span></div>
        <Lane title={`CONTACTS · ${(movie?.events || []).length}`} items={lanes.events} duration={project.seconds} kind="event" seek={seek} />
        <Lane title="ACCEPTED" items={lanes.accepted} duration={project.seconds} kind="accepted" seek={seek} />
        <Lane title="REJECTED" items={lanes.rejected} duration={project.seconds} kind="rejected" seek={seek} />
        <Lane title="NOISE / WATCH" items={lanes.noise} duration={project.seconds} kind="noise" seek={seek} />
      </div>
      <aside className="movie-queue" aria-label="Agent review queue">
        <div className="movie-queue-head"><strong>REVIEW QUEUE</strong><span>{(movie?.review_queue || []).length.toString().padStart(2, "0")}</span></div>
        {queue.items.length ? queue.items.map((item) => <article key={item.id}>
          <button className="queue-cue" onClick={() => seek(item.time_s)}>{time(item.time_s)}</button>
          <div><strong>{item.title}</strong><p>{item.reason}</p></div>
          <div className="queue-actions">
            {item.family_id ? <button popoverTarget="sound-workbench">Open family</button> : <button onClick={() => decide(item, "accepted")}>Keep flag</button>}
            <button onClick={() => decide(item, item.family_id ? "needs_sfx" : "rejected")}>{item.family_id ? "Needs SFX" : "Dismiss"}</button>
          </div>
        </article>) : <p className="muted">Analysis will place ambiguous families and noise here.</p>}
        {queue.pages > 1 && <div className="queue-pages"><button disabled={!queue.page} onClick={() => setPage(queue.page - 1)}>Previous</button><span>{queue.page + 1} / {queue.pages}</span><button disabled={queue.page + 1 >= queue.pages} onClick={() => setPage(queue.page + 1)}>Next</button></div>}
      </aside>
    </div>
  </section>;
}
