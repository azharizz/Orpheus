import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { useStore, action, api, update } from "../state/store.js";
import { validateFile, time, label } from "../state/domain.js";
import { Workspace } from "./workspace.jsx";
import "../styles/style.css";

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
  const [files, setFiles] = useState({});
  async function submit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await action(async () => {
      validateFile(form.get("video"), config.max_file_bytes);
      validateFile(form.get("sfx"), config.max_file_bytes);
      const result = await api("/api/projects", { method: "POST", body: form });
      window.location.assign("/workspace?project=" + result.project.id);
    }, "Media prepared locally. Ready for your explicit run.");
  }
  return (
    <section className="import">
      <div>
        <h1>
          Bring a scene.
          <br />
          Find its sound.
        </h1>
        <p>
          Fit an independent recording to picture, then listen, inspect and
          decide.
        </p>
        <p>
          Already have a project? Open it from{" "}
          <a href="/">your project library</a>.
        </p>
      </div>
      <form onSubmit={submit}>
        <div className="file-pair">
          {[
            ["video", "Picture", ".mp4,.mov,.webm,.mkv"],
            ["sfx", "Sound", ".wav,.mp3,.m4a,.flac,.ogg"],
          ].map(([name, label, accept]) => (
            <label className="file-input" key={name}>
              <span>{label}</span>
              <strong>
                {files[name] ||
                  `Choose ${name === "video" ? "video" : "sound"}`}
              </strong>
              <input
                name={name}
                type="file"
                accept={accept}
                required
                onChange={(e) =>
                  setFiles({ ...files, [name]: e.target.files[0]?.name })
                }
              />
            </label>
          ))}
        </div>
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
          Whole soundtrack replacement, including dialogue and ambience.
          Original files are preserved.
        </p>
        {config ? (
          <p className="muted">
            Opening {config.max_duration_s} seconds ·{" "}
            {Math.round(config.max_file_bytes / 1048576)} MiB per file. Media is
            saved on this computer. Importing starts no paid inference.
          </p>
        ) : (
          <p>Loading active media limits…</p>
        )}
        <button className="primary" disabled={busy || !config}>
          {busy ? "Preparing media…" : "Prepare project"}
        </button>
      </form>
    </section>
  );
}
function Landing({ projects, loading }) {
  return (
    <main id="main" className="entrance">
      <section className="entrance-title">
        <h1>ORPHEUS</h1>
        <div>
          <p>
            Picture. Sound.
            <br />A performance that belongs.
          </p>
          <a className="primary" href="/workspace">
            Start a project
          </a>
        </div>
      </section>
      <section aria-labelledby="projects-title">
        <div className="section-heading">
          <h2 id="projects-title">Your scenes</h2>
          <span className="muted">Saved on this computer</span>
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
              Bring a video and a separately recorded sound. Orpheus keeps the
              picture, the source and every alternative together.
            </p>
            <a href="/workspace">Choose picture and sound</a>
          </div>
        )}
      </section>
      <footer>
        <p>Fit to picture. Record another take. Keep what works.</p>
        <span>Human judgment is the final edit.</span>
      </footer>
    </main>
  );
}
function App() {
  const state = useStore();
  const pid = new URLSearchParams(window.location.search).get("project");
  const project = state.projects.find((p) => p.id === pid);
  const isWorkspace = window.location.pathname === "/workspace";
  return (
    <>
      <a className="skip" href="#main">
        Skip to workspace
      </a>
      <header>
        <a className="wordmark" href="/">
          ORPHEUS
        </a>
        <nav aria-label="Main navigation">
          <a href="/" aria-current={!isWorkspace ? "page" : undefined}>
            Projects
          </a>
          <a href="/workspace" aria-current={isWorkspace ? "page" : undefined}>
            New project
          </a>
        </nav>
        <span className="header-status">
          {state.running ? "Agent running" : "Local workspace"}
        </span>
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
        <Landing {...state} />
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
              <a href="/">Open projects</a>
            </section>
          ) : project ? (
            <Workspace key={project.id} project={project} state={state} />
          ) : (
            <Import config={state.config} busy={state.busy} />
          )}
        </main>
      )}
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
