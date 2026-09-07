import { registerMedia } from "../media/audio-focus.js";
import React, { useState, useCallback } from "react";
import {
  media,
  update,
  watchFamilies,
} from "../state/store.js";
import { candidates, matchRange, pendingMatches, partWindow, time, label, workspaceTarget } from "../state/domain.js";
import { Transport } from "../media/transport.js";
import { Evidence } from "../features/evidence.jsx";
import { useRecording, stopRecording } from "../media/recording.js";
import { FamilyWorkbench } from "../features/families.jsx";
import { MovieOverview } from "../features/movie.jsx";
import { Wave } from "../features/waveform.jsx";

function familyRanges(data) {
  const families = Array.isArray(data) ? data : data?.families || [];
  return families.flatMap((family) => [
    ...(family.accepted_ranges || []).map((range) => ({
      start: Array.isArray(range) ? range[0] : matchRange(range)[0],
      end: Array.isArray(range) ? range[1] : matchRange(range)[1],
      kind: "accepted",
    })),
    ...pendingMatches(family).map((match) => {
      const range = matchRange(match);
      return { start: range[0], end: range[1], kind: "pending" };
    }),
  ]);
}

export function Workspace({ project: p, state }) {
  const target = workspaceTarget();
  const [activeFamily, setActiveFamily] = useState(target.family);
  const familyData = state.families[p.id];
  const movie = state.movies[p.id];
  const familyPreviews = (familyData?.families || []).map((family) => family.latest_render ? { ...family.latest_render, family_id: family.id } : null).filter(Boolean);
  const all = [movie?.latest_render, ...familyPreviews, ...candidates(p)].filter(Boolean).filter((item, index, items) => items.findIndex((other) => other.id === item.id) === index);
  const [chosen, setChosen] = useState("");
  const candidate = all.find((item) => item.id === chosen) || familyPreviews.find((item) => item.family_id === activeFamily) || all.find((item) => item.id === p.latest_candidate_id) || all.at(-1);
  const previews = all;
  const [track, setTrack] = useState("original");
  const [position, setPosition] = useState(() => Math.min(p.seconds, target.time));
  const [view, setView] = useState(target.view);
  const [partCenter, setPartCenter] = useState(() => Math.min(p.seconds, target.time));
  const [partSpan, setPartSpan] = useState(15);
  const [playing, setPlaying] = useState(false);
  const [transport] = useState(() => new Transport());
  const recording = useRecording();
  const partRange = partWindow(partCenter, p.seconds, partSpan);
  const locked = state.busy || state.running || recording.active || recording.pending;
  const fail = (error) => update({ error: error.message });
  const bindFamilies = useCallback(() => watchFamilies(p.id), [p.id]);
  const bindVideo = useCallback((node) => {
    if (!node) return;
    transport.video = node;
    const release = registerMedia(node);
    return () => { release(); stopRecording(); transport.pause(); transport.video = null; };
  }, [transport]);
  const seek = (value) => {
    const next = Math.max(0, Math.min(p.seconds, Number(value) || 0));
    transport.pause();
    transport.seek(next);
    setPosition(next);
  };
  function setWorkspaceView(next, at = position, family = activeFamily, event = "") {
    setView(next);
    const params = new URLSearchParams({ project: p.id, view: next });
    if (at) params.set("time", String(Number(at.toFixed(3))));
    if (family) params.set("family", family);
    if (event) params.set("event", event);
    history.replaceState(null, "", `/workspace?${params}`);
  }
  function openPart(item = {}) {
    const at = Math.max(0, Math.min(p.seconds, Number(item.time_s ?? item.range_s?.[0] ?? position) || 0));
    const family = item.family_id || activeFamily;
    setPartCenter(at);
    setActiveFamily(family);
    seek(at);
    setWorkspaceView("part", at, family, item.id || "");
  }
  const previewRange = (range) => {
    const start = Math.max(0, Number(range[0]) || 0);
    const end = Math.min(p.seconds, Number(range[1]) || start);
    setPartCenter((start + end) / 2);
    transport.pause();
    switchTrack("original");
    transport.seek(start);
    setPosition(start);
    transport.play(end).catch(fail);
  };
  function switchTrack(next, selected = candidate) {
    transport.switchTrack(next, selected?.timeline_offset_s)?.catch(fail);
    setTrack(next);
  }
  function chooseCandidate(value) {
    const selected = typeof value === "string" ? previews.find((item) => item.id === value) : value;
    const id = selected?.id;
    transport.pause();
    setChosen(id || "");
    if (id) switchTrack("a", selected);
  }

  return <div className="workspace" ref={bindFamilies}>
    <div className="workspace-heading">
      <div><h1>{p.video_name}</h1><p className="workspace-meta">{time(p.seconds)} · {label(p.status)} · {p.has_original_audio ? "Original audio preserved" : "No original soundtrack"}</p></div>
      <a className="button-link" href="/?view=projects">All projects</a>
    </div>
    <nav className="workspace-views" role="tablist" aria-label="Workspace scale">
      <button role="tab" aria-selected={view === "part"} aria-controls="part-view" onClick={() => openPart()}>PART <small>{time(partRange[0])}–{time(partRange[1])}</small></button>
      <button role="tab" aria-selected={view === "movie"} aria-controls="movie-view" onClick={() => setWorkspaceView("movie")}>FULL MOVIE <small>{time(p.seconds)}</small></button>
    </nav>
    <div className="bench"><div className="work">
      <div className="picture-stage"><div className="picture">
        <video aria-label="Project picture" ref={bindVideo} src={media(p.id, "video.mp4")} poster={media(p.id, "poster.jpg")} preload="metadata" playsInline muted={track !== "original" || recording.active}
          onTimeUpdate={(event) => { setPosition(event.currentTarget.currentTime); transport.sync(); }}
          onPlay={() => setPlaying(true)} onPause={() => { setPlaying(false); transport.audio?.pause(); }}
          onEnded={() => { transport.pause(); stopRecording(); }}
          onError={() => update({ error: "Picture could not load. Check the saved project media and retry." })} />
      </div><div className="picture-readout" aria-hidden="true"><span>{view === "part" ? "Part inspection" : "Full movie"}</span><span>{time(position)} / {time(p.seconds)}</span></div></div>
      <audio ref={transport.bindAudio} src={track === "a" && candidate ? media(p.id, candidate.id + ".wav") : undefined} preload="metadata"
        onLoadedMetadata={() => transport.ready()?.catch(fail)} onError={() => { transport.pause(); update({ error: "Replacement preview could not load. Return to Original or render again." }); }} />
      <div className="transport" aria-label="Picture transport">
        <button className="transport-play primary" disabled={recording.active || recording.pending} onClick={() => playing ? transport.pause() : transport.play().catch(fail)}>{playing ? "Pause" : "Play"}</button>
        <output className="time">{time(position)}</output>
        <label className="seek-label">Picture time<input type="number" value={Number(position.toFixed(3))} min="0" max={p.seconds} step="0.01" disabled={recording.active || recording.pending} onChange={(event) => seek(event.target.value)} /></label>
        <div className="audio-switch" aria-label="Audible soundtrack">
          <button aria-pressed={track === "original"} disabled={recording.active || recording.pending} onClick={() => switchTrack("original")}>Original</button>
          <button aria-pressed={track === "a"} disabled={!candidate || recording.active || recording.pending} onClick={() => switchTrack("a")}>Replacement preview</button>
        </div>
      </div>
      <p className="track-status" role="status">Listening to {track === "original" ? "the preserved original" : `replacement preview ${candidate?.id}`}. Picture time stays fixed when switching.</p>
    </div></div>

    <section id="part-view" role="tabpanel" hidden={view !== "part"} aria-label="Part workflow">
      <div className="part-audio">
        <div className="part-audio-head"><div><span className="eyebrow">VISIBLE AUDIO WINDOW</span><strong>{time(partRange[0])} – {time(partRange[1])}</strong></div><div className="part-zoom" aria-label="Part waveform duration">{[5, 15, 30, 60].map((span) => <button key={span} aria-pressed={partSpan === span} onClick={() => setPartSpan(span)}>{span}s</button>)}<button onClick={() => setPartCenter(position)}>Center at playhead</button></div></div>
        <Wave pid={p.id} role="original" state={state} label={p.has_original_audio ? "Detailed original waveform" : "Original soundtrack unavailable"} position={position} start={partRange[0]} end={partRange[1]} bins={900} ranges={familyRanges(familyData)} select={recording.active ? null : seek} />
        <div className="wave-key" aria-label="Waveform marks"><span><i className="accepted-mark" /> Kept event</span><span><i className="pending-mark" /> Awaiting review</span></div>
      </div>
      <div className="part-workspace-grid">
        <FamilyWorkbench key={activeFamily || "default"} project={p} data={familyData} state={state} position={position} disabled={locked} transport={transport} candidate={candidate} selectedFamilyId={activeFamily} onCandidate={chooseCandidate} onPreview={previewRange} onMovieSearch={(familyId) => { setActiveFamily(familyId); setWorkspaceView("movie", position, familyId); }} />
        <aside className="part-evidence" aria-label="Current evidence"><Evidence p={p} c={candidate} state={state} /></aside>
      </div>
    </section>

    <section id="movie-view" role="tabpanel" hidden={view !== "movie"} aria-label="Full movie overview">
      <MovieOverview project={p} movie={movie} families={familyData?.families || []} state={state} running={state.running} position={position} seek={seek} openPart={openPart} activeFamily={activeFamily} />
    </section>

    {view === "part" && <button className="preview-launcher" type="button" popoverTarget="replacement-wave">Replacement wave</button>}
    <aside id="replacement-wave" className="replacement-overlay" popover="auto" aria-label="Replacement preview waveform">
      <div className="replacement-overlay-head"><strong>REPLACEMENT PREVIEW</strong><button type="button" popoverTarget="replacement-wave" popoverTargetAction="hide">Hide</button></div>
      {candidate ? <Wave pid={p.id} role="candidate" cid={candidate.id} state={state} label={`Candidate · ${candidate.id}`} position={position} start={partRange[0]} end={partRange[1]} bins={900} select={seek} /> : <p className="muted">Render the active part to compare it here.</p>}
      {candidate && previews.length > 1 && <label className="candidate-picker">Compare preview<select value={candidate.id} onChange={(event) => chooseCandidate(event.target.value)}>{previews.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.engineering_pass ? "measured" : "check flags"}</option>)}</select></label>}
    </aside>
  </div>;
}
