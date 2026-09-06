import { registerMedia, claimMedia } from "./audio-focus.js";
import React, { useState, useCallback } from "react";
import { post, action, media, loadWave, update } from "./store.js";
import { candidates, time } from "./domain.js";
import { Transport } from "./transport.js";
import { Recorder } from "./takes.jsx";
import { Evidence } from "./evidence.jsx";
import { useRecording, stopRecording } from "./recording.js";
import { Review } from "./review.jsx";
export function Wave({
  pid,
  role,
  cid = "",
  state,
  label,
  position = 0,
  duration = 1,
  select,
}) {
  const wave = state.waveforms[[pid, role, cid].join(":")];
  const bind = useCallback(() => {
    loadWave(pid, role, cid);
  }, [pid, role, cid]);
  const peaks = wave?.peaks || [];
  return (
    <div className="wave" ref={bind}>
      <div className="wave-label">
        <span>{label}</span>
        <span>{wave?.duration_s ? time(wave.duration_s) : "—"}</span>
      </div>
      {wave?.error ? (
        <p className="muted">Waveform unavailable: {wave.error}</p>
      ) : peaks.length ? (
        <svg
          viewBox="0 0 1000 64"
          preserveAspectRatio="none"
          role="img"
          aria-label={`${label}, amplitude from 0 to ${wave.duration_s} seconds`}
        >
          <path
            d={peaks
              .map(
                (peak, i) =>
                  `M${(i * 1000) / peaks.length},${32 - Math.max(0, Math.min(1, peak)) * 30}v${Math.max(0, Math.min(1, peak)) * 60}`,
              )
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
          aria-label={`Seek ${label} in seconds`}
          type="range"
          min="0"
          max={duration}
          step="0.01"
          value={Math.min(position, duration)}
          onChange={(e) => select(Number(e.target.value))}
        />
      )}
    </div>
  );
}
export function Workspace({ project: p, state }) {
  const all = candidates(p),
    last = p.turn_details?.at(-1);
  const [chosen, setChosen] = useState("");
  const c =
    all.find((c) => c.id === chosen) ||
    all.find((c) => c.id === last?.selection?.candidate_id) ||
    all.at(-1);
  const [mode, setMode] = useState("Fit"),
    [track, setTrack] = useState("original"),
    [bId, setBId] = useState(""),
    [position, setPosition] = useState(0),
    [playing, setPlaying] = useState(false),
    [selected, setSelected] = useState(0),
    [feedback, setFeedback] = useState(""),
    [consent, setConsent] = useState(false);
  const [transport] = useState(() => new Transport());
  const recording = useRecording();
  const rows = c ? c.arrangement?.rows || [] : last?.arrangement?.rows || [];
  const selectedRow = rows[selected];
  const b =
    all.find((item) => item.id === bId) ||
    all.find((item) => item.id !== c?.id);
  const audible = track === "a" ? c : track === "b" ? b : null;
  const fail = (error) => update({ error: error.message });
  function switchTrack(next) {
    if (next === "a" && c) setChosen(c.id);
    if (next === "b" && b) setBId(b.id);
    transport.switchTrack(next)?.catch(fail);
    setTrack(next);
  }
  function chooseCandidate(id) {
    transport.pause();
    setTrack("original");
    transport.switchTrack("original");
    setChosen(id);
    setSelected(0);
  }
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
  function selectRow(index) {
    transport.pause();
    setSelected(index);
    transport.seek(
      rows[index].target_anchor_s ?? rows[index].target_range_s[0],
    );
    setPosition(rows[index].target_anchor_s ?? rows[index].target_range_s[0]);
  }
  const locked =
    state.busy || state.running || recording.active || recording.pending;
  async function run(e) {
    e.preventDefault();
    if (!consent) return;
    const result = await action(
      () =>
        post("/api/run", {
          project_id: p.id,
          ...(feedback.trim() ? { feedback } : {}),
          consent: true,
        }),
      "Agent turn started. Completed candidates remain available.",
    );
    if (result) {
      setFeedback("");
      setConsent(false);
    }
  }
  return (
    <>
      <div className="workspace-heading">
        <div>
          <h1>{p.video_name}</h1>
          <p>
            {time(p.seconds)} · {p.status} ·{" "}
            {p.has_original_audio
              ? "Original audio present"
              : "No original audio — picture evidence only"}
          </p>
        </div>
        <div className="mode-switch" aria-label="Workspace view">
          <a href="#run-fitting">
            {state.running ? "Inspect active turn" : "Run fitting"}
          </a>
          {["Fit", "Record", "Review"].map((name) => (
            <button
              key={name}
              aria-pressed={mode === name}
              disabled={recording.active || recording.pending}
              onClick={() => setMode(name)}
            >
              {name}
            </button>
          ))}
        </div>
      </div>
      <div className="bench">
        <div className="work">
          <div className="picture">
            <video
              aria-label="Prepared picture"
              ref={bindVideo}
              src={media(p.id, "video.mp4")}
              poster={media(p.id, "poster.jpg")}
              preload="metadata"
              playsInline
              muted={track !== "original" || recording.active}
              onTimeUpdate={(e) => {
                setPosition(e.currentTarget.currentTime);
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
            src={audible ? media(p.id, audible.id + ".wav") : undefined}
            preload="metadata"
            onLoadedMetadata={() => transport.ready()?.catch(fail)}
            onError={() => {
              transport.pause();
              update({
                error:
                  "Candidate audio could not load. Select Original or another candidate.",
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
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (Number.isFinite(n) && n >= 0 && n <= p.seconds) {
                    transport.seek(n);
                    setPosition(n);
                  }
                }}
              />
            </label>
            <div className="audio-switch" aria-label="Audible soundtrack">
              {[
                ["original", "Original", true],
                ["a", "A", !!c],
                ["b", "B", !!b],
              ].map(([value, label, exists]) => (
                <button
                  key={value}
                  aria-pressed={track === value}
                  disabled={!exists || recording.active || recording.pending}
                  onClick={() => switchTrack(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <p className="track-status">
            Listening to{" "}
            {track === "original"
              ? "original soundtrack"
              : `${track.toUpperCase()} · ${audible?.id}`}{" "}
            · Shared picture time.{" "}
            {track !== "original" && "Whole soundtrack replaced."}
          </p>
          <Wave
            pid={p.id}
            role="original"
            state={state}
            label={
              p.has_original_audio
                ? "Target activity"
                : "Target — no original audio"
            }
            position={position}
            duration={p.seconds}
            select={
              recording.active
                ? null
                : (n) => {
                    transport.seek(n);
                    setPosition(n);
                  }
            }
          />
          {c && (
            <Wave
              pid={p.id}
              role="candidate"
              cid={audible?.id || c.id}
              state={state}
              label={`Fitted sound · ${audible?.id || c.id}`}
              position={position}
              duration={p.seconds}
            />
          )}
          <div className="candidate-selects">
            <label>
              Candidate A
              <select
                value={c?.id || ""}
                disabled={!all.length || recording.active || recording.pending}
                onChange={(e) => chooseCandidate(e.target.value)}
              >
                {!all.length && <option>No render yet</option>}
                {all.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id} ·{" "}
                    {item.provenance === "human_assisted"
                      ? "assisted"
                      : "agent"}{" "}
                    · {item.engineering_pass ? "measured" : "check flags"}
                  </option>
                ))}
              </select>
            </label>
            {all.length > 1 && (
              <label>
                Candidate B
                <select
                  value={b?.id || ""}
                  disabled={recording.active || recording.pending}
                  onChange={(e) => {
                    switchTrack("original");
                    setBId(e.target.value);
                  }}
                >
                  {all.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <details>
            <summary>Independent source · its own time ruler</summary>
            <audio
              controls
              preload="metadata"
              aria-label="Full independent source recording"
              ref={registerMedia}
              src={media(p.id, "sfx.wav")}
              onPlay={(event) => claimMedia(event.currentTarget)}
            />
            <Wave
              pid={p.id}
              role="sfx"
              state={state}
              label="Source recording"
            />
          </details>
          {mode === "Record" ? (
            <Recorder p={p} state={state} transport={transport} />
          ) : (
            <section className="event-section">
              <div className="section-heading">
                <h2>
                  {mode === "Review" ? "Review the fit" : "Actions in picture"}
                </h2>
                <span className="muted">
                  {rows.length
                    ? `${rows.length} mapped rows`
                    : "Awaiting evidence"}
                </span>
              </div>
              {rows.length ? (
                <ol className="event-list">
                  {rows.map((row, index) => (
                    <li key={row.id}>
                      <button
                        aria-pressed={index === selected}
                        onClick={() => selectRow(index)}
                      >
                        <span className="time">
                          {time(row.target_range_s[0])}
                        </span>
                        <span>
                          {row.label || row.action || row.id}
                          <small>
                            {row.disposition} · {row.confidence || "uncertain"}
                          </small>
                        </span>
                        <span className="time">
                          {row.target_range_s[1].toFixed(2)} s
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              ) : c?.plan?.length ? (
                <section aria-label="Discrete event plan">
                  <p>
                    Discrete fitting plan · source-bank placements. No mapped
                    arrangement is attached to this candidate.
                  </p>
                  <ol className="event-list">
                    {c.plan.map((event, index) => (
                      <li key={index}>
                        <button
                          onClick={() => {
                            transport.pause();
                            transport.seek(event.time_s);
                            setPosition(event.time_s);
                          }}
                        >
                          <span className="time">{time(event.time_s)}</span>
                          <span>
                            {event.sample_id}
                            <small>
                              {event.duration_s} s · {event.gain_db} dB ·{" "}
                              {event.confidence}
                            </small>
                            <small>{event.evidence}</small>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : (
                <p>
                  {c
                    ? "This candidate has no discrete or mapped events. Inspect its full receipt for sustained sound coverage."
                    : "No mapped actions yet. Prepare your brief and explicitly run fitting."}
                </p>
              )}
              {c && (
                <Review
                  key={c.id}
                  p={p}
                  c={c}
                  rows={rows}
                  selected={selected}
                  locked={locked}
                  onCandidate={chooseCandidate}
                />
              )}
            </section>
          )}
          <section className="run-section" id="run-fitting">
            <h2>
              {last ? "Continue the experiment" : "Fit sound to this scene"}
            </h2>
            {p.context && (
              <p>
                {p.context}
                {p.style ? " · " + p.style : ""}
              </p>
            )}
            {p.input_warnings?.length > 0 && (
              <p className="warning">
                Input notices: {p.input_warnings.join(", ")}
              </p>
            )}
            <form onSubmit={run}>
              <label>
                {last ? "What should change?" : "Anything to add?"}
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  maxLength={state.config?.max_feedback_chars}
                  rows="2"
                  placeholder="Keep the softer contact; bring the next one forward."
                />
              </label>
              <p className="muted">
                {state.config
                  ? `Images and ${state.config.audio_enabled ? "audio windows" : "no audio-observer requests"} go to ${state.config.inference_destination || "the configured provider"}. Up to ${state.config.max_controller_calls} controller calls; uses API credit.`
                  : "Loading inference destination and run limits…"}
              </p>
              <label className="check">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                I authorize this paid turn and its configured media
                transmission.
              </label>
              <button
                className="primary"
                disabled={locked || !consent || !state.config}
              >
                {state.running
                  ? "Agent running"
                  : "Run fitting · uses API credit"}
              </button>
            </form>
            {last?.failure && (
              <p className="error">
                {last.failure.category}: {last.failure.guidance}
              </p>
            )}
            {last?.incomplete_reason && (
              <p className="warning">{last.incomplete_reason}</p>
            )}
          </section>
        </div>
        <Evidence p={p} c={c} row={selectedRow} state={state} />
      </div>
    </>
  );
}
