import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { useStore, action, api, update } from "../state/store.js";
import { validateFile, time, label } from "../state/domain.js";
import { Workspace } from "./workspace.jsx";
import "../styles/style.css";
import "../styles/families.css";
import "../styles/workspace.css";
import { PhotographicTitle } from "./photographic-title.jsx";

export function Disclosure({ title, children }) {
  return (
    <details>
      <summary>{title}</summary>
      {children}
    </details>
  );
}
export const Json = ({ value }) => <pre>{JSON.stringify(value, null, 2)}</pre>;
function Import({ config, busy }) {
  const [video, setVideo] = useState(null);
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = validateFile(video, config.max_file_bytes);
    const query = new URLSearchParams({
      filename: file.name,
      context: String(form.get("context") || ""),
      style: String(form.get("style") || ""),
    });
    await action(async () => {
      const result = await api(`/api/projects?${query}`, {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      });
      window.location.assign("/workspace?project=" + result.project.id);
    }, "Picture saved. Its sound index is preparing locally.");
  }
  return (
    <section className="import">
      <div>
        <h1>Bring the whole picture.</h1>
        <p>
          Mark one sound, find related moments across the film, then decide
          which occurrences deserve a new performance.
        </p>
      </div>
      <form onSubmit={submit}>
        <label className="file-input">
          <span>Picture</span>
          <strong>{video?.name || "Choose video"}</strong>
          <input
            name="video"
            type="file"
            accept=".mp4,.mov,.webm,.mkv"
            required
            onChange={(event) => setVideo(event.target.files[0] || null)}
          />
        </label>
        <label>
          What should make sound? <span className="muted">Optional</span>
          <input
            name="context"
            maxLength={config?.max_brief_chars}
            placeholder="Footsteps on a wooden floor"
          />
        </label>
        <label>
          How should it feel? <span className="muted">Optional</span>
          <input
            name="style"
            maxLength={config?.max_brief_chars}
            placeholder="Soft, close, keep quieter steps"
          />
        </label>
        <p>
          Orpheus preserves the original and indexes its soundtrack on this
          computer. Importing starts no paid inference.
        </p>
        <p className="muted">
          {config
            ? `Maximum file size ${Math.round(config.max_file_bytes / 1073741824)} GiB.`
            : "Loading active media limits…"}
        </p>
        <div className="import-actions">
          <span className="registration-frame">
            <button className="primary" disabled={busy || !config || !video}>
              {busy ? "Saving picture…" : "Create project"}
            </button>
          </span>
          <a className="registration-frame registration-frame-small" href="/?view=projects">
            your project library
          </a>
        </div>
      </form>
    </section>
  );
}
const waveShape = [0.42, -0.78, 0.58, -1, 0.7, -0.36, 0.92, -0.5, 0.65, -0.88, 0.35, -0.72];
const maxWavePoints = 36;

function SoundSyncMark({ wave }) {
  const path = wave.samples.map((value, index) => {
    const x = 24 + (index / (maxWavePoints - 1)) * 312;
    const y = 36 - value;
    return `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg
      className="sound-picture-mark"
      viewBox="0 0 360 72"
      fill="none"
      aria-hidden="true"
    >
      <path className="sound-idle-line" d="M180 1v70" />
      {wave.samples.length > 1 && (
        <g key={wave.tick} className="sound-wave-trace">
          <path className="sound-wave-path" pathLength="1" d={path} />
        </g>
      )}
    </svg>
  );
}
function Landing({ projects, loading, paused, library, wave }) {
  return (
    <main
      id="main"
      className={library ? "entrance project-library" : "entrance"}
    >
      {library ? <ProjectLibrary projects={projects} loading={loading} /> : (
        <section className="landing-hero">
          <PhotographicTitle paused={paused} />
          <div className="landing-statement" id="about">
            <p>Every movement has a voice. Bring your picture, shape its sound, and give each moment a presence of its own.</p>
            <SoundSyncMark wave={wave} />
          </div>
        </section>
      )}
    </main>
  );
}
function ProjectLibrary({ projects, loading }) {
  return (
      <section aria-labelledby="projects-title">
        <div className="section-heading">
          <div>
            <h2 id="projects-title">YOUR SCENES</h2>
          </div>
          <span className="muted">
            Saved on this computer ·{" "}
            {projects.length.toString().padStart(2, "0")} {projects.length === 1 ? "file" : "files"}
          </span>
        </div>
        {loading ? (
          <p className="loading">Loading your project library…</p>
        ) : projects.length ? (
          <div className="filmstrip">
            {projects.map((p, i) => (
              <a
                className="scene"
                key={p.id}
                href={"/workspace?project=" + p.id}
              >
                <div className="scene-picture">
                  <img
                    src={"/projects/" + p.id + "/poster.jpg"}
                    alt={`Prepared picture from ${p.video_name}`}
                    loading={i > 1 ? "lazy" : "eager"}
                  />
                </div>
                <div className="scene-caption">
                  <h3>{p.video_name}</h3>
                  <span>{time(p.seconds)}</span>
                </div>
                <p>
                  {label(p.status)} ·{" "}
                  {p.has_original_audio
                    ? "Original audio present"
                    : "No original audio"}
                </p>
              </a>
            ))}
          </div>
        ) : (
          <div className="library-empty">
            <h2>Your first scene starts here.</h2>
            <p>
              Bring a video, mark one sound, and review related moments. Orpheus keeps
              the original and every alternative together.
            </p>
            <a href="/workspace">Choose a picture</a>
          </div>
        )}
      </section>
  );
}
function App() {
  const state = useStore();
  const [paused, setPaused] = useState(false);
  const [wave, setWave] = useState({ samples: [], tick: 0 });
  const library = new URLSearchParams(window.location.search).get("view") === "projects";
  const pid = new URLSearchParams(window.location.search).get("project");
  const project = state.projects.find((p) => p.id === pid);
  const isWorkspace = window.location.pathname === "/workspace";
  const trackable = !isWorkspace && !library;
  function trackPointer(event) {
    if (!trackable || event.pointerType === "touch") return;
    const movement = Math.hypot(event.nativeEvent.movementX || 0, event.nativeEvent.movementY || 0);
    if (movement < 3) return;
    setWave((current) => {
      const tick = current.tick + 1;
      const speed = Math.min(1, (movement - 3) / 44);
      const amplitude = 3 + speed * 21;
      const shape = waveShape[tick % waveShape.length];
      return { tick, samples: [...current.samples.slice(-(maxWavePoints - 1)), shape * amplitude] };
    });
  }
  function clearWave() {
    setWave((current) => current.samples.length ? { samples: [], tick: current.tick + 1 } : current);
  }
  return (
    <div className="app-shell" onPointerMove={trackPointer} onPointerLeave={clearWave}>
      <a className="skip" href="#main">
        Skip to workspace
      </a>
      <header className="landing-header">
        <a className="wordmark" href="/">
          ORPHEUS
        </a>
        <nav aria-label="Main navigation">
          <a href="/?view=projects" aria-current={!isWorkspace && library ? "page" : undefined}>
            Projects
          </a>
          <a href="/workspace" aria-current={isWorkspace ? "page" : undefined}>
            New project
          </a>
        </nav>
        {isWorkspace ? <span className="header-status">{state.running ? "Agent running" : "Local workspace"}</span> : (
          <button className="motion-control" aria-label={paused ? "Resume title animation" : "Pause title animation"} aria-pressed={paused} onClick={() => setPaused(!paused)}>
            <span>Motion</span>
            <span className="motion-disc" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">{paused ? <path d="m9 6 9 6-9 6V6Z" /> : <path d="M9 6v12M15 6v12" />}</svg>
            </span>
          </button>
        )}
      </header>
      <div className="announcement" role="status" aria-live="polite">
        {state.busy ? "Working…" : state.message}
      </div>
      {state.error && (
        <div className="error" role="alert">
          {state.error}{" "}
          <button onClick={() => update({ error: "" })}>Dismiss</button>
        </div>
      )}
      {state.errors?.map((item) => (
        <p className="error" role="alert" key={item.project_id}>
          Project {item.project_id}: {item.error}
        </p>
      ))}
      {!isWorkspace ? (
        <Landing {...state} paused={paused} library={library} wave={wave} />
      ) : (
        <main id="main">
          {pid && state.loading ? (
            <p className="loading">Loading scene…</p>
          ) : pid && !project ? (
            <section className="import">
              <h1>Project unavailable</h1>
              <p>
                Check the project library or retry when the local server is
                available.
              </p>
              <a href="/?view=projects">Open projects</a>
            </section>
          ) : project ? (
            <Workspace key={project.id} project={project} state={state} />
          ) : (
            <Import config={state.config} busy={state.busy} />
          )}
        </main>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
