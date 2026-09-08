import { registerMedia } from "../media/audio-focus.js";
import React, { useCallback, useState } from "react";
import { media, update, watchFamilies } from "../state/store.js";
import { candidates, label, matchRange, pendingMatches, partWindow, time, workspaceTarget } from "../state/domain.js";
import { Transport } from "../media/transport.js";
import { Evidence } from "../features/evidence.jsx";
import { useRecording, stopRecording } from "../media/recording.js";
import { FamilyWorkbench, MatchReview, WorkflowProgress, agentActivity, renderActivity } from "../features/families.jsx";
import { MovieOverview } from "../features/movie.jsx";
import { Wave } from "../features/waveform.jsx";

function familyRanges(data) {
  const families = Array.isArray(data) ? data : data?.families || [];
  return families.flatMap((family) => [
    ...(family.accepted_ranges || []).map((item) => {
      const range = Array.isArray(item) ? item : matchRange(item) || [];
      return { start: Number(range[0]), end: Number(range[1]), kind: "accepted" };
    }),
    ...pendingMatches(family).map((match) => {
      const range = matchRange(match) || [match.time_s, Number(match.time_s) + 0.08];
      return { start: Number(range[0]), end: Number(range[1]), kind: "pending" };
    }),
  ]).filter((range) => Number.isFinite(range.start) && Number.isFinite(range.end) && range.end > range.start);
}

function cueDetails(item, position, duration, familyId = "") {
  const range = matchRange(item) || [];
  const rawStart = Number(range[0] ?? item?.time_s ?? position) || 0;
  const start = Math.max(0, Math.min(Math.max(0, duration - 0.08), rawStart));
  const rawEnd = Number(range[1] ?? start + 0.08) || start + 0.08;
  const end = Math.min(duration, Math.max(start + 0.08, rawEnd));
  return { ...item, family_id: item?.family_id || familyId, time_s: start, range_s: [start, end] };
}

function CueDrawer({ mode, onClose, children }) {
  if (!mode) return null;
  return <aside className="cue-drawer" aria-labelledby="cue-drawer-title">
    <div className="cue-drawer-head">
      <strong id="cue-drawer-title">{mode === "cue" ? "Cue sheet" : mode === "family" ? "Family workflow" : mode === "review" ? "Match review" : "Evidence details"}</strong>
      <button type="button" onClick={onClose}>Close</button>
    </div>
    <div className="cue-drawer-body">{children}</div>
  </aside>;
}

function CueDetail({ project, state, cue, candidate, previews, position, partRange, partSpan, recording, activeFamily, onSeek, onCenter, onSpan, onCandidate, onOpenReview, onOpenFamily, onOpenDetails }) {
  const [start, end] = partRange;
  const kind = cue?.kind === "accepted" ? "Kept event" : cue?.kind === "noise" ? "Potential noise" : "Awaiting review";
  return <section className="cue-detail" aria-labelledby="cue-detail-title">
    <div className="cue-detail-heading">
      <div><h2 id="cue-detail-title">{time(cue?.time_s ?? position)}</h2><p>{kind}{cue?.count > 1 ? ` · ${cue.count} nearby cues` : ""}</p></div>
      <span className="cue-range">{time(start)} – {time(end)}</span>
    </div>
    <div className="cue-wave-stack">
      <div className="cue-wave"><strong>Original</strong><Wave pid={project.id} role="original" state={state} label="Original cue waveform" position={position} start={start} end={end} bins={720} ranges={familyRanges(state.families[project.id])} select={recording.active ? null : onSeek} /></div>
      {candidate && <div className="cue-wave"><strong>Replacement {candidate.id}</strong><Wave pid={project.id} role="candidate" cid={candidate.id} state={state} label={`Replacement waveform ${candidate.id}`} position={position} start={start} end={end} bins={720} select={onSeek} /></div>}
    </div>
    <div className="cue-tools">
      <div className="cue-zoom" role="group" aria-label="Cue waveform window">{[5, 15, 30, 60].map((span) => <button key={span} type="button" aria-pressed={partSpan === span} onClick={() => onSpan(span)}>{span}s</button>)}<button type="button" onClick={onCenter}>Center at playhead</button></div>
      <label className="candidate-picker">Audition take<select value={candidate?.id || ""} disabled={!previews.length} onChange={(event) => onCandidate(event.target.value)}><option value="">Original only</option>{previews.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.engineering_pass ? "measured" : "review required"}</option>)}</select></label>
    </div>
    <div className="cue-facts"><span>{cue?.similarity_score ? `Rank ${Number(cue.similarity_score).toFixed(3)}` : "Local cue"}</span><span>{candidate ? `Take ${candidate.id} ready for comparison` : "No replacement take selected"}</span></div>
    <div className="cue-actions"><button className="primary" type="button" onClick={() => onOpenReview(activeFamily)}>Review family matches</button><button type="button" onClick={() => onOpenFamily(activeFamily)}>Open family workflow</button><button type="button" onClick={onOpenDetails}>Show evidence</button></div>
    {cue?.evidence_summary && <p className="cue-evidence">{cue.evidence_summary}</p>}
  </section>;
}

function DetailsDrawer({ project, movie, family, state, candidate, onOpenFamily }) {
  const pending = pendingMatches(family).length;
  return <section className="details-drawer" aria-labelledby="details-title">
    <div className="details-intro"><h2 id="details-title">Evidence for this picture</h2><p>Measurements and provider receipts stay available when a decision needs proof.</p></div>
    <dl className="detail-facts"><div><dt>Picture</dt><dd>{project.video_name}</dd></div><div><dt>Duration</dt><dd>{time(project.seconds)}</dd></div><div><dt>Movie map</dt><dd>{movie?.status?.replaceAll("_", " ") || "not started"}</dd></div><div><dt>Open matches</dt><dd>{pending}</dd></div><div><dt>Active take</dt><dd>{candidate?.id || "none"}</dd></div></dl>
    <button type="button" onClick={() => onOpenFamily(family?.id || "")}>Open full family details</button>
    <details className="details-section" open><summary>Grafana and run evidence</summary><Evidence p={project} c={candidate} state={state} /></details>
    <details className="details-section"><summary>Raw map counts</summary><p>{(movie?.events || []).length.toLocaleString()} contact cues · {(movie?.suggestions || []).length} suggestions · {(movie?.noise_regions || []).length} noise ranges.</p></details>
  </section>;
}

function ReviewWindow({ project, state, cue, candidate, position, partRange, recording, onSeek }) {
  const [start, end] = partRange;
  const audition = candidate?.preview_kind === "match_audition" && candidate.source_match_id === cue?.id ? candidate : null;
  return <section className="review-window" aria-label="Selected match waveform">
    <div><strong>Match at {time(cue?.time_s ?? position)}</strong><span>{time(start)} – {time(end)}</span></div>
    <div className="review-wave-stack">
      <div><strong>Original</strong><Wave pid={project.id} role="original" state={state} label="Original match waveform" position={position} start={start} end={end} bins={720} ranges={familyRanges(state.families[project.id])} select={recording.active ? null : onSeek} /></div>
      {audition ? <div><strong>Replacement audition</strong><Wave pid={project.id} role="candidate" cid={audition.id} state={state} label="Replacement audition waveform" position={position} start={start} end={end} bins={720} select={onSeek} /></div> : <p className="review-audition-hint">Choose Replacement below to compare this exact match.</p>}
    </div>
  </section>;
}

function WorkspaceActivity({ project, familyData, state }) {
  const families = familyData?.families || [];
  const turns = [...(project.turn_details || [])]
    .filter((turn) => turn.status === "running")
    .sort((left, right) => Number(right.started_at) - Number(left.started_at));
  const operation = state.operation;
  const agentTurn = turns[0];
  const agentWaiting = operation?.kind === "agent" ? operation : null;
  const renderWaiting = operation?.kind === "full_render" ? operation : null;
  const renderFamily = families.find((item) => item.id === (renderWaiting?.family_id || ""))
    || families.find((item) => item.render_progress?.status === "running");
  const agentIsLive = Boolean(agentWaiting || (state.running && agentTurn));
  const renderIsLive = Boolean(renderWaiting || renderFamily?.render_progress?.status === "running");
  if (!agentIsLive && !renderIsLive) return null;
  if (agentIsLive) {
    return <div className="workspace-activity" aria-label="Agent activity">
      <WorkflowProgress
        activity={agentActivity(agentTurn)}
        waiting={agentWaiting}
        title="Agent-coordinated fit"
        candidateId={agentTurn?.selection?.candidate_id || agentTurn?.candidates?.at(-1)?.id}
      />
    </div>;
  }
  return <div className="workspace-activity" aria-label="Replacement activity">
    <WorkflowProgress
      activity={renderActivity(renderFamily || {})}
      waiting={renderWaiting}
      title="Full-movie replacement"
      candidateId={renderFamily?.latest_render_id}
    />
  </div>;
}

export function Workspace({ project: p, state }) {
  const target = workspaceTarget();
  const explicitView = new URLSearchParams(window.location.search).has("view");
  const [activeFamily, setActiveFamily] = useState(target.family);
  const familyData = state.families[p.id];
  const movie = state.movies[p.id];
  const [auditionCandidate, setAuditionCandidate] = useState(null);
  const familyPreviews = (familyData?.families || []).map((family) => family.latest_render ? { ...family.latest_render, family_id: family.id } : null).filter(Boolean);
  const all = [auditionCandidate, movie?.latest_render, ...familyPreviews, ...candidates(p)].filter(Boolean).filter((item, index, items) => items.findIndex((other) => other.id === item.id) === index);
  const [chosen, setChosen] = useState("");
  const family = (familyData?.families || []).find((item) => item.id === activeFamily) || familyData?.families?.[0];
  const candidate = all.find((item) => item.id === chosen) || familyPreviews.find((item) => item.family_id === (family?.id || activeFamily)) || all.find((item) => item.id === p.latest_candidate_id) || all.at(-1);
  const [track, setTrack] = useState("original");
  const [position, setPosition] = useState(() => Math.min(p.seconds, target.time));
  const [view, setView] = useState(target.view);
  const [partCenter, setPartCenter] = useState(() => Math.min(p.seconds, target.time));
  const [partSpan, setPartSpan] = useState(15);
  const [playing, setPlaying] = useState(false);
  const [transport] = useState(() => new Transport());
  const [drawer, setDrawer] = useState(() => target.event || (explicitView && target.view === "part") ? (target.event ? "cue" : "family") : "");
  const [selectedCue, setSelectedCue] = useState(() => target.event ? cueDetails({ id: target.event, time_s: target.time }, target.time, p.seconds, target.family) : null);
  const candidateForCue = candidate?.preview_kind !== "match_audition" || !selectedCue?.id || candidate.source_match_id === selectedCue.id
    ? candidate
    : null;
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
  function resetForeignAudition(matchId) {
    if (auditionCandidate?.preview_kind !== "match_audition" || auditionCandidate.source_match_id === matchId) return;
    setAuditionCandidate(null);
    setChosen("");
    if (track === "a") {
      Promise.resolve(transport.switchTrack("original")).catch(fail);
      setTrack("original");
    }
  }
  function setWorkspaceView(next, at = position, familyId = activeFamily, event = "") {
    setView(next);
    const params = new URLSearchParams({ project: p.id, view: next });
    if (at) params.set("time", String(Number(at.toFixed(3))));
    if (familyId) params.set("family", familyId);
    if (event) params.set("event", event);
    history.replaceState(null, "", `/workspace?${params}`);
  }
  function openCue(item = {}) {
    const cue = cueDetails(item, position, p.seconds, item.family_id || activeFamily);
    resetForeignAudition(cue.id);
    setSelectedCue(cue);
    setPartCenter((cue.range_s[0] + cue.range_s[1]) / 2);
    if (cue.family_id) setActiveFamily(cue.family_id);
    seek(cue.time_s);
    setDrawer("cue");
    setWorkspaceView("part", cue.time_s, cue.family_id, cue.id || "");
  }
  function openFamily(familyId = activeFamily) {
    if (familyId) setActiveFamily(familyId);
    setDrawer("family");
    setWorkspaceView("part", position, familyId);
  }
  function openReview(familyId = activeFamily, match = null) {
    const targetFamily = (familyData?.families || []).find((item) => item.id === familyId);
    const nextMatch = match || pendingMatches(targetFamily)[0];
    const cue = cueDetails({ ...(nextMatch || {}), family_id: familyId }, position, p.seconds, familyId);
    resetForeignAudition(cue.id);
    if (familyId) setActiveFamily(familyId);
    setSelectedCue(cue);
    setPartCenter((cue.range_s[0] + cue.range_s[1]) / 2);
    seek(cue.time_s);
    setDrawer("review");
    setWorkspaceView("movie", cue.time_s, familyId, cue.id || "");
  }
  function openDetails() {
    setDrawer("details");
    setWorkspaceView("movie", position, activeFamily);
  }
  function previewRange(range, item = {}, replacement = null) {
    const cue = cueDetails({ ...item, range_s: range, family_id: item.family_id || activeFamily }, position, p.seconds, activeFamily);
    openCue(cue);
    transport.pause();
    if (replacement) {
      setAuditionCandidate(replacement);
      setChosen(replacement.id);
      switchTrack("a", replacement);
    } else {
      resetForeignAudition(cue.id);
      switchTrack("original");
    }
    transport.seek(cue.range_s[0]);
    setPosition(cue.range_s[0]);
    if (replacement && candidate?.id !== replacement.id) transport.queuePlayback(cue.range_s[1]);
    else transport.play(cue.range_s[1]).catch(fail);
  }
  function previewReview(range, item = {}, replacement = null) {
    const cue = cueDetails({ ...item, range_s: range, family_id: item.family_id || activeFamily }, position, p.seconds, activeFamily);
    setSelectedCue(cue);
    setPartCenter((cue.range_s[0] + cue.range_s[1]) / 2);
    setWorkspaceView("movie", cue.time_s, cue.family_id, cue.id || "");
    transport.pause();
    if (replacement) {
      setAuditionCandidate(replacement);
      setChosen(replacement.id);
      switchTrack("a", replacement);
    } else {
      resetForeignAudition(cue.id);
      switchTrack("original");
    }
    transport.seek(cue.range_s[0]);
    setPosition(cue.range_s[0]);
    if (replacement && candidate?.id !== replacement.id) transport.queuePlayback(cue.range_s[1]);
    else transport.play(cue.range_s[1]).catch(fail);
  }
  function switchTrack(next, selected = candidate) {
    transport.switchTrack(next, selected?.timeline_offset_s)?.catch(fail);
    setTrack(next);
  }
  function chooseCandidate(value) {
    const selected = typeof value === "string" ? all.find((item) => item.id === value) : value;
    transport.pause();
    setAuditionCandidate(selected?.preview_kind === "match_audition" ? selected : null);
    setChosen(selected?.id || "");
    if (selected) switchTrack("a", selected);
    else switchTrack("original");
  }
  function selectFamily(id) {
    setActiveFamily(id);
    if (selectedCue) setSelectedCue({ ...selectedCue, family_id: id });
  }

  return <div className="workspace" ref={bindFamilies}>
    <div className="workspace-heading">
      <div><h1>{p.video_name}</h1><p className="workspace-meta">{time(p.seconds)} · {label(p.status)} · {p.has_original_audio ? "Original audio preserved" : "No original soundtrack"}</p></div>
      <a className="button-link" href="/?view=projects">All projects</a>
    </div>
    <div className="bench"><div className="work">
      <div className="picture-stage"><div className="picture">
        <video aria-label="Project picture" ref={bindVideo} src={media(p.id, "video.mp4")} poster={media(p.id, "poster.jpg")} preload="metadata" playsInline muted={track !== "original" || recording.active}
          onTimeUpdate={(event) => { setPosition(event.currentTarget.currentTime); transport.sync(); }}
          onPlay={() => setPlaying(true)} onPause={() => { setPlaying(false); transport.audio?.pause(); }}
          onEnded={() => { setPlaying(false); transport.pause(); stopRecording(); }}
          onError={() => update({ error: "Picture could not load. Check the saved project media and retry." })} />
      </div><div className="picture-readout" aria-hidden="true"><span>{drawer === "cue" ? "Cue inspection" : drawer ? "Review desk" : "Film overview"}</span><span>{time(position)} / {time(p.seconds)}</span></div></div>
      <audio key={track === "a" ? candidateForCue?.id || "missing" : "original"} ref={transport.bindAudio} src={track === "a" && candidateForCue ? media(p.id, candidateForCue.id + ".wav") : undefined} preload="metadata"
        onLoadedMetadata={() => transport.ready()?.catch(fail)} onError={() => { transport.pause(); update({ error: "Replacement preview could not load. Return to Original or render again." }); }} />
      <div className="transport" aria-label="Picture transport">
        <button className="transport-play primary" disabled={recording.active || recording.pending} onClick={() => playing ? transport.pause() : transport.play().catch(fail)}>{playing ? "Pause" : "Play"}</button>
        <output className="time">{time(position)}</output>
        <label className="seek-label">Picture time<input type="number" value={Number(position.toFixed(3))} min="0" max={p.seconds} step="0.01" disabled={recording.active || recording.pending} onChange={(event) => seek(event.target.value)} /></label>
        <div className="audio-switch" aria-label="Audible soundtrack"><button aria-pressed={track === "original"} disabled={recording.active || recording.pending} onClick={() => switchTrack("original")}>Original</button><button aria-pressed={track === "a"} disabled={!candidateForCue || recording.active || recording.pending} onClick={() => switchTrack("a", candidateForCue)}>Replacement preview</button></div>
      </div>
      <p className="track-status" role="status"><span>Listening to {track === "a" && candidateForCue ? `replacement preview ${candidateForCue.id}` : "the preserved original"}. Picture time stays fixed when switching.</span>{family?.latest_render_id && <output className="latest-preview">Latest preview · {family.latest_render_id}</output>}</p>
      <WorkspaceActivity project={p} familyData={familyData} state={state} />
      <MovieOverview project={p} movie={movie} families={familyData?.families || []} state={state} running={state.running} position={position} seek={seek} activeFamily={activeFamily} onCue={openCue} onOpenFamily={openFamily} onOpenReview={openReview} onActiveFamilyChange={selectFamily} onOpenDetails={openDetails} />
    </div></div>

    <CueDrawer mode={drawer} onClose={() => { setDrawer(""); setWorkspaceView(view, position, activeFamily); }}>
      {drawer === "cue" && <CueDetail project={p} state={state} cue={selectedCue || { time_s: position }} candidate={candidateForCue} previews={all} position={position} partRange={partRange} partSpan={partSpan} recording={recording} activeFamily={activeFamily} onSeek={seek} onCenter={() => setPartCenter(position)} onSpan={setPartSpan} onCandidate={chooseCandidate} onOpenReview={openReview} onOpenFamily={openFamily} onOpenDetails={openDetails} />}
      {drawer === "family" && <FamilyWorkbench key={activeFamily || "new"} project={p} data={familyData} state={state} position={position} disabled={locked} transport={transport} candidate={candidateForCue} selectedFamilyId={activeFamily} onCandidate={chooseCandidate} onPreview={previewRange} onMovieSearch={(familyId) => { setActiveFamily(familyId); setDrawer(""); setWorkspaceView("movie", position, familyId); }} onReview={openReview} onFamilyChange={selectFamily} compact />}
      {drawer === "review" && (family ? <><ReviewWindow project={p} state={state} cue={selectedCue} candidate={candidateForCue} position={position} partRange={partRange} recording={recording} onSeek={seek} /><MatchReview key={`${family.id}:${family.search_version || ""}`} project={p} family={family} candidate={candidateForCue} state={state} disabled={locked} pageSize={1} focusId={selectedCue?.id || ""} onPreview={previewReview} /></> : <p className="empty-line">Create or select a sound family before reviewing related moments.</p>)}
      {drawer === "details" && <DetailsDrawer project={p} movie={movie} family={family} state={state} candidate={candidateForCue} onOpenFamily={openFamily} />}
    </CueDrawer>
  </div>;
}
