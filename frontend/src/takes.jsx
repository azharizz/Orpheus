import React, { useCallback, useState, useRef } from "react";
import { action, loadTakes, media, post, api, update } from "./store.js";
import {
  useRecording,
  startRecording,
  stopRecording,
  uploadTake,
  discard,
} from "./recording.js";
import { time, matchVolume } from "./domain.js";

export function Recorder({ p, state, transport }) {
  const recording = useRecording();
  const players = useRef(new Set());
  const [matched, setMatched] = useState(false);
  const [brief, setBrief] = useState("");
  const [start, setStart] = useState(0);
  const bind = useCallback(() => {
    loadTakes(p.id);
  }, [p.id]);
  const saved = state.takes[p.id];
  const locked = recording.active || recording.pending || state.busy;
  const metadata = { projectId: p.id, brief, start: Number(start) };
  const report = (error) => update({ error: error.message });
  async function capture() {
    transport.pause();
    try {
      await startRecording(
        transport.video,
        metadata,
        p.seconds,
        state.config.max_duration_s,
      );
    } catch (error) {
      report(error);
    }
  }
  async function save() {
    const draft = recording.draft;
    if (!draft || draft.projectId !== p.id) return;
    const form = new FormData();
    form.append("project_id", draft.projectId);
    form.append("brief", draft.brief);
    form.append("start_s", String(draft.start));
    form.append("clock", draft.clock);
    const name =
      draft.blob instanceof File
        ? draft.blob.name
        : draft.blob.type.includes("mp4")
          ? "take.m4a"
          : "take.webm";
    form.append("audio", draft.blob, name);
    const result = await action(
      () => api("/api/takes", { method: "POST", body: form }),
      "Take saved locally. No inference started.",
    );
    if (result) {
      discard();
      await loadTakes(p.id);
    }
  }
  return (
    <section className="record-section" ref={bind}>
      <h2>Perform another take</h2>
      <label>
        Prop and performance brief
        <input
          value={brief}
          maxLength={state.config?.max_brief_chars || 240}
          disabled={locked}
          onChange={(e) => setBrief(e.target.value)}
        />
      </label>
      <label>
        Picture cue (seconds)
        <input
          type="number"
          min="0"
          max={p.seconds}
          step="0.01"
          value={start}
          disabled={locked}
          onChange={(e) => setStart(e.target.value)}
        />
      </label>
      <p className="muted">
        Capture mutes picture audio. Browser capture timing is provisional; fit
        the saved take before judging synchronization.
      </p>
      <div className="actions">
        <button
          disabled={locked || !!recording.draft || !state.config}
          onClick={capture}
        >
          Record with picture
        </button>
        <button
          disabled={!recording.active && !recording.pending}
          onClick={stopRecording}
        >
          Stop recording
        </button>
      </div>
      <p role="status">
        {recording.active
          ? `Recording · ${time(recording.elapsed)} · Microphone active`
          : recording.pending
            ? "Waiting for microphone permission…"
            : "Microphone inactive"}
      </p>
      {recording.error && (
        <p role="alert" className="error">
          {recording.error}
        </p>
      )}
      <label>
        Upload a take
        <input
          type="file"
          accept=".wav,.mp3,.m4a,.flac,.ogg,.webm,.mp4"
          disabled={locked || !!recording.draft || !state.config}
          onChange={(e) => {
            const file = e.target.files[0];
            if (file)
              try {
                uploadTake(
                  file,
                  metadata,
                  state.config.max_file_bytes,
                  p.seconds,
                );
              } catch (error) {
                report(error);
              }
          }}
        />
      </label>
      {recording.draft && (
        <div className="capture">
          <h3>Captured in this browser</h3>
          <p>
            Audition before saving. Cue {time(recording.draft.start)};{" "}
            {recording.draft.brief || "No performance brief"}.
          </p>
          <audio
            controls
            src={recording.draft.url}
            onPlay={() => transport.pause()}
          />
          <div className="actions">
            <button
              disabled={state.busy || recording.draft.projectId !== p.id}
              onClick={save}
            >
              Save this take
            </button>
            <button disabled={state.busy} onClick={discard}>
              Discard unsaved take
            </button>
          </div>
          {recording.draft.projectId !== p.id && (
            <p>Return to its original project to save this take.</p>
          )}
        </div>
      )}
      <h3>Saved takes</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={matched}
          onChange={(e) => setMatched(e.target.checked)}
        />
        Level-match audition to the quietest take (attenuation only)
      </label>
      {!saved ? (
        <p>Loading saved recordings…</p>
      ) : saved.takes.length ? (
        saved.takes.map((t) => (
          <article className="take-row" key={t.id}>
            <h3>{t.brief || `Take ${t.id}`}</h3>
            <p>
              {time(t.profile.duration_s)} · Picture cue{" "}
              {time(t.picture_start_s)} · {t.clock}
            </p>
            <audio
              controls
              preload="none"
              ref={(node) => {
                if (!node) return;
                players.current.add(node);
                node.volume = matched
                  ? matchVolume(
                      t.profile.body_dbfs,
                      saved.takes.map((take) => take.profile.body_dbfs),
                    )
                  : 1;
                return () => {
                  node.pause();
                  players.current.delete(node);
                };
              }}
              src={media(p.id, `takes/${t.id}.wav`)}
              onPlay={(e) => {
                transport.pause();
                for (const audio of players.current)
                  if (audio !== e.currentTarget) audio.pause();
              }}
            />
            <p className="muted">
              Body {t.profile.body_dbfs} dBFS · Peak{" "}
              {t.profile.sample_peak_dbfs} dBFS. Loudness is not quality.
            </p>
            <button
              disabled={locked || state.running || !!recording.draft}
              onClick={async () => {
                const result = await action(
                  () =>
                    post("/api/takes/fit", { project_id: p.id, take_id: t.id }),
                  "Linked fitting project created.",
                );
                if (result)
                  window.location.assign(
                    "/workspace?project=" + result.project.id,
                  );
              }}
            >
              Fit this take · sends media and uses API credit
            </button>
          </article>
        ))
      ) : (
        <p>No saved takes. Record or upload one above.</p>
      )}
      <details>
        <summary>Proposed recording experiments</summary>
        <pre>{JSON.stringify(saved?.experiments || [], null, 2)}</pre>
      </details>
    </section>
  );
}
