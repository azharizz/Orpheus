import { registerMedia } from "../media/audio-focus.js";
import React, { useState, useCallback } from "react";
import {
  media,
  loadWave,
  update,
  watchFamilies,
} from "../state/store.js";
import { candidates, matchRange, pendingMatches, time, label } from "../state/domain.js";
import { Transport } from "../media/transport.js";
import { Evidence } from "../features/evidence.jsx";
import { useRecording, stopRecording } from "../media/recording.js";
import { FamilyWorkbench } from "../features/families.jsx";

export function Wave({
  pid,
  role,
  cid = "",
  state,
  label: waveLabel,
  position = 0,
  duration = 1,
  select,
  ranges = [],
}) {
  const wave = state.waveforms[[pid, role, cid].join(":")];
  const bind = useCallback(() => {
    loadWave(pid, role, cid);
  }, [pid, role, cid]);
  const peaks = wave?.peaks || [];
  return (
    <div className="wave" ref={bind}>
      <div className="wave-label">
        <span>{waveLabel}</span>
        <span>{wave?.duration_s ? time(wave.duration_s) : "—"}</span>
      </div>
      {wave?.error ? (
        <p className="muted">Waveform unavailable: {wave.error}</p>
      ) : peaks.length ? (
        <svg
          viewBox="0 0 1000 64"
          preserveAspectRatio="none"
          role="img"
          aria-label={`${waveLabel}, amplitude from 0 to ${wave.duration_s} seconds`}
        >
          {ranges.map((range, index) => (
            <rect
              key={index}
              className={`wave-range wave-range-${range.kind || "pending"}`}
              x={(range.start / duration) * 1000}
              width={Math.max(2, ((range.end - range.start) / duration) * 1000)}
              y="0"
              height="64"
            />
          ))}
          <path
            d={peaks
              .map((peak, index) => {
                const value = Math.max(0, Math.min(1, peak));
                return `M${(index * 1000) / peaks.length},${32 - value * 30}v${value * 60}`;
              })
              .join(" ")}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <line
            x1={(position / duration) * 1000}
            x2={(position / duration) * 1000}
            y1="0"
            y2="64"
            className="playhead"
          />
        </svg>
      ) : (
        <p className="muted">Loading measured waveform…</p>
      )}
      {select && (
        <input
          aria-label={`Seek ${waveLabel} in seconds`}
          type="range"
          min="0"
          max={duration}
          step="0.01"
          value={Math.min(position, duration)}
          onChange={(event) => select(Number(event.target.value))}
        />
      )}
    </div>
  );
}

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
  const familyData = state.families[p.id];
  const familyPreviews = (familyData?.families || [])
    .map((family) => family.latest_render)
    .filter(Boolean);
  const all = [...familyPreviews, ...candidates(p)].filter(
    (item, index, items) =>
      items.findIndex((other) => other.id === item.id) === index,
  );
  const [chosen, setChosen] = useState("");
  const [rendered, setRendered] = useState(null);
  const candidate =
    rendered ||
    all.find((item) => item.id === chosen) ||
    all.find((item) => item.id === p.latest_candidate_id) ||
    all.at(-1);
  const previews = [rendered, ...all]
    .filter(Boolean)
    .filter((item, index, items) =>
      items.findIndex((other) => other.id === item.id) === index,
    );
  const [track, setTrack] = useState("original");
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [transport] = useState(() => new Transport());
  const recording = useRecording();
  const locked =
    state.busy || state.running || recording.active || recording.pending;
  const fail = (error) => update({ error: error.message });
  const bindFamilies = useCallback(() => watchFamilies(p.id), [p.id]);
  const bindVideo = useCallback(
    (node) => {
      if (!node) return;
      transport.video = node;
      const release = registerMedia(node);
      return () => {
        release();
        stopRecording();
        transport.pause();
        transport.video = null;
      };
    },
    [transport],
  );
  const seek = (value) => {
    const next = Math.max(0, Math.min(p.seconds, Number(value) || 0));
    transport.pause();
    transport.seek(next);
    setPosition(next);
  };
  function switchTrack(next) {
    transport.switchTrack(next)?.catch(fail);
    setTrack(next);
  }
  function chooseCandidate(value) {
    const id = typeof value === "string" ? value : value?.id;
    transport.pause();
    setRendered(typeof value === "string" ? null : value);
    setChosen(id || "");
    if (id) switchTrack("a");
  }

  return (
    <div className="workspace" ref={bindFamilies}>
      <div className="workspace-heading">
        <div>
          <h1>{p.video_name}</h1>
          <p>
            {time(p.seconds)} · {label(p.status)} ·{" "}
            {p.has_original_audio
              ? "Original audio preserved"
              : "No original soundtrack"}
          </p>
        </div>
        <a href="/?view=projects">All projects</a>
      </div>
      <div className="bench">
        <div className="work">
          <div className="picture">
            <video
              aria-label="Project picture"
              ref={bindVideo}
              src={media(p.id, "video.mp4")}
              poster={media(p.id, "poster.jpg")}
              preload="metadata"
              playsInline
              muted={track !== "original" || recording.active}
              onTimeUpdate={(event) => {
                setPosition(event.currentTarget.currentTime);
                transport.sync();
              }}
              onPlay={() => setPlaying(true)}
              onPause={() => {
                setPlaying(false);
                transport.audio?.pause();
              }}
              onEnded={() => {
                transport.pause();
                stopRecording();
              }}
              onError={() =>
                update({
                  error:
                    "Picture could not load. Check the saved project media and retry.",
                })
              }
            />
          </div>
          <audio
            ref={transport.bindAudio}
            src={
              track === "a" && candidate
                ? media(p.id, candidate.id + ".wav")
                : undefined
            }
            preload="metadata"
            onLoadedMetadata={() => transport.ready()?.catch(fail)}
            onError={() => {
              transport.pause();
              update({
                error:
                  "Replacement preview could not load. Return to Original or render again.",
              });
            }}
          />
          <div className="transport">
            <button
              disabled={recording.active || recording.pending}
              onClick={() =>
                playing ? transport.pause() : transport.play().catch(fail)
              }
            >
              {playing ? "Pause" : "Play"}
            </button>
            <output className="time">{time(position)}</output>
            <label className="seek-label">
              Picture time
              <input
                type="number"
                value={Number(position.toFixed(3))}
                min="0"
                max={p.seconds}
                step="0.01"
                disabled={recording.active || recording.pending}
                onChange={(event) => seek(event.target.value)}
              />
            </label>
            <div className="audio-switch" aria-label="Audible soundtrack">
              <button
                aria-pressed={track === "original"}
                disabled={recording.active || recording.pending}
                onClick={() => switchTrack("original")}
              >
                Original
              </button>
              <button
                aria-pressed={track === "a"}
                disabled={!candidate || recording.active || recording.pending}
                onClick={() => switchTrack("a")}
              >
                Replacement preview
              </button>
            </div>
          </div>
          <p className="track-status">
            Listening to{" "}
            {track === "original"
              ? "the preserved original"
              : `replacement preview ${candidate?.id}`}
            . Picture time stays fixed when switching.
          </p>
          <Wave
            pid={p.id}
            role="original"
            state={state}
            label={
              p.has_original_audio
                ? "Original soundtrack"
                : "Original soundtrack unavailable"
            }
            position={position}
            duration={p.seconds}
            ranges={familyRanges(familyData)}
            select={recording.active ? null : seek}
          />
          <div className="wave-key" aria-label="Waveform marks">
            <span><i className="accepted-mark" /> Kept event</span>
            <span><i className="pending-mark" /> Awaiting review</span>
          </div>
          {candidate && (
            <>
              <Wave
                pid={p.id}
                role="candidate"
                cid={candidate.id}
                state={state}
                label={`Replacement preview · ${candidate.id}`}
                position={position}
                duration={p.seconds}
              />
              {previews.length > 1 && (
                <label className="candidate-picker">
                  Compare another preview
                  <select
                    value={candidate.id}
                    onChange={(event) => chooseCandidate(event.target.value)}
                  >
                    {previews.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.id} · {item.engineering_pass ? "measured" : "check flags"}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </>
          )}
          <FamilyWorkbench
            project={p}
            data={familyData}
            state={state}
            position={position}
            disabled={locked}
            transport={transport}
            candidate={candidate}
            onCandidate={chooseCandidate}
            onSeek={seek}
          />
        </div>
        <Evidence p={p} c={candidate} state={state} />
      </div>
    </div>
  );
}
