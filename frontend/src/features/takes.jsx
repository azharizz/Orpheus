import { registerMedia, claimMedia } from "../media/audio-focus.js";
import React, { useCallback, useState } from "react";
import { action, loadFamilies, loadTakes, media, api, update } from "../state/store.js";
import {
  useRecording,
  startRecording,
  stopRecording,
  uploadTake,
  discard,
} from "../media/recording.js";
import { time, matchVolume } from "../state/domain.js";
import { useExtras, GenerateTake } from "./extras.jsx";

export function Recorder({ p, family, state, transport }) {
  const recording = useRecording();
  const extras = useExtras();
  const [matched, setMatched] = useState(false);
  const [brief, setBrief] = useState("");
  const [start, setStart] = useState(family.seed_range_s?.[0] || 0);
  const bind = useCallback(() => {
    loadTakes(p.id);
  }, [p.id]);
  const allTakes = state.takes[p.id]?.takes || [];
  const saved = allTakes.filter((take) => take.family_id === family.id);
  const locked = recording.active || recording.pending || state.busy;
  const metadata = {
    projectId: p.id,
    familyId: family.id,
    brief,
    start: Number(start),
  };
  const report = (error) => update({ error: error.message });

  async function capture() {
    claimMedia();
    transport.pause();
    try {
      await startRecording(
        transport.video,
        metadata,
        p.seconds,
        state.config.max_take_duration_s || 30,
      );
    } catch (error) {
      report(error);
    }
  }

  async function save() {
    const draft = recording.draft;
    if (!draft || draft.projectId !== p.id || draft.familyId !== family.id)
      return;
    const query = new URLSearchParams({
      project_id: draft.projectId,
      family_id: draft.familyId,
      brief: draft.brief || "",
      start_s: String(draft.start),
      clock: draft.clock,
      filename:
        draft.blob instanceof File
          ? draft.blob.name
          : draft.blob.type.includes("mp4")
            ? "take.m4a"
            : "take.webm",
    });
    const result = await action(
      () =>
        api(`/api/takes?${query}`, {
          method: "POST",
          headers: {
            "Content-Type": draft.blob.type || "application/octet-stream",
          },
          body: draft.blob,
        }),
      `Replacement take saved for ${family.name}. No inference started.`,
    );
    if (result) {
      discard();
      await Promise.all([loadTakes(p.id), loadFamilies(p.id)]);
    }
  }

  return (
    <div className="replacement-recorder" ref={bind}>
      <label>
        Performance brief <span className="muted">Optional</span>
        <input
          value={brief}
          maxLength={state.config?.max_brief_chars || 240}
          disabled={locked}
          placeholder="Shorter heel, softer body"
          onChange={(event) => setBrief(event.target.value)}
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
          onChange={(event) => setStart(event.target.value)}
        />
      </label>
      <p className="muted">
        Capture mutes picture audio. Browser timing is provisional; the
        renderer fits the saved take to each accepted moment.
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
          : recording.stopping
            ? "Finishing captured audio…"
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
        Upload a replacement take
        <input
          type="file"
          accept=".wav,.mp3,.m4a,.flac,.ogg,.webm,.mp4"
          disabled={locked || !!recording.draft || !state.config}
          onChange={(event) => {
            const file = event.target.files[0];
            if (!file) return;
            try {
              uploadTake(
                file,
                metadata,
                state.config.max_audio_bytes,
                p.seconds,
              );
            } catch (error) {
              report(error);
            }
          }}
        />
      </label>
      <GenerateTake
        extras={extras}
        disabled={locked || !!recording.draft || !state.config}
        onError={report}
        onGenerated={(blob) => {
          try {
            uploadTake(blob, metadata, state.config.max_audio_bytes, p.seconds);
          } catch (error) {
            report(error);
          }
        }}
      />
      {recording.draft && (
        <div className="capture">
          <h3>Captured in this browser</h3>
          <p>
            Audition before saving · cue {time(recording.draft.start)} ·{" "}
            {recording.draft.brief || "No performance brief"}.
          </p>
          <audio
            controls
            src={recording.draft.url}
            ref={registerMedia}
            onPlay={(event) => claimMedia(event.currentTarget)}
          />
          <div className="actions">
            <button
              disabled={
                state.busy ||
                recording.draft.projectId !== p.id ||
                recording.draft.familyId !== family.id
              }
              onClick={save}
            >
              Save for {family.name}
            </button>
            <button disabled={state.busy} onClick={discard}>
              Discard unsaved take
            </button>
          </div>
        </div>
      )}
      {saved.length > 0 && (
        <details>
          <summary>
            {saved.length} saved {saved.length === 1 ? "take" : "takes"}
          </summary>
          <label className="check">
            <input
              type="checkbox"
              checked={matched}
              onChange={(event) => setMatched(event.target.checked)}
            />
            Level-match audition to the quietest take
          </label>
          {saved.map((take) => (
            <article className="take-row" key={take.id}>
              <h3>{take.brief || `Take ${take.id}`}</h3>
              <p>
                {time(take.profile.duration_s)} · cue{" "}
                {time(take.picture_start_s)} · {take.clock}
              </p>
              <TakePlayer
                src={media(p.id, `takes/${take.id}.wav`)}
                volume={
                  matched
                    ? matchVolume(
                        take.profile.body_dbfs,
                        saved.map((item) => item.profile.body_dbfs),
                      )
                    : 1
                }
              />
              <p className="muted">
                Body {take.profile.body_dbfs} dBFS · peak{" "}
                {take.profile.sample_peak_dbfs} dBFS. Loudness is not quality.
              </p>
            </article>
          ))}
        </details>
      )}
    </div>
  );
}

function TakePlayer({ src, volume }) {
  const bind = useCallback(
    (node) => {
      if (!node) return;
      node.volume = volume;
      return registerMedia(node);
    },
    [volume],
  );
  return (
    <audio
      controls
      preload="none"
      ref={bind}
      src={src}
      onPlay={(event) => claimMedia(event.currentTarget)}
    />
  );
}
