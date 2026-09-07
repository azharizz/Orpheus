# Long-form Movie Workflow Implementation Plan

> **For Codex:** Execute every checked task in this document in order. Reuse the current sound-family, agent, render, and observability paths; do not create a parallel product.

**Goal:** Turn the existing scene-level workspace into a movie-level, one-click agent workflow that can prepare and analyze long films in the background, propose sound families and noise regions, draft safe replacements, expose human review, and present the same evidence in Grafana.

**Architecture:** Add one resumable movie-analysis manifest per project and a background worker that coordinates deterministic evidence with the existing family agent. The React workspace reads this manifest for overview lanes and review state while preserving the current family workbench. Prometheus/Loki export compact movie progress and signal evidence; Grafana links back to exact workspace times and families. A deterministic generator creates the 30-minute validation asset outside Git.

**Tech Stack:** Python stdlib, NumPy, FFmpeg/FFprobe, existing Google ADK/OpenRouter integration, existing Flask-compatible HTTP server, React 19, native SVG/CSS, Prometheus, Loki, Grafana.

---

- [x] **1. Define movie manifest and resumable deterministic analysis**
  - Add `orpheus/domain/movie.py` with bounded waveform buckets, event/noise detection, family proposal clustering, progress checkpoints, and exact-time review items.
  - Reuse `families.create`, acoustic-index evidence, project atomic writes, and existing media measurement helpers.
  - Add a focused core test proving resume behavior, deterministic proposals, noise marking, and no modification outside accepted ranges.

- [x] **2. Add background project preparation and movie coordination**
  - Split `orpheus/domain/projects.py` into fast intake plus resumable preparation while keeping `create()` compatible for tests and scripts.
  - Extend `orpheus/server/web.py` with movie status, one-click run, retry, and review endpoints plus a project-local worker state.
  - Add `orpheus/server/movie_worker.py` to inspect deterministic evidence, query Grafana history, coordinate eligible families through the existing paid agent path, preserve unknown sounds, and emit an auditable final receipt.
  - Add HTTP tests for preparation, run validation, status, and review mutations.

- [x] **3. Add safe whole-movie draft composition**
  - Add a public multi-family render path that applies only accepted ranges with assigned takes and leaves all other PCM unchanged.
  - Emit picture-integrity, clipping, timing, coverage, and human-review evidence through the existing observability path.
  - Test multiple non-overlapping families, missing takes, clipping protection, and picture preservation.

- [x] **4. Rebuild workspace around the movie workflow**
  - Add `frontend/src/features/movie.jsx` and `frontend/src/styles/movie.css` for one-click run, progress, overview lanes, noise/warning lanes, agent activity, and paged review queue.
  - Update `frontend/src/app/workspace.jsx` so video remains central, family workbench remains a drawer, and the replacement waveform becomes a hideable bottom overlay.
  - Extend `frontend/src/state/store.js` and `domain.js` for movie state, mutations, deep-link time/family/event handling, and polling without `useEffect`.
  - Add frontend tests for lane normalization, queue pagination, and deep links; run accessibility-aware browser QA.

- [x] **5. Extend Agentic Foley Control Room for long-form evidence**
  - Add movie outcome/progress, waveform and loudness history, family/noise coverage, decision/provider timelines, runtime status, and raw-evidence drill-down using current Prometheus/Loki sources.
  - Add workspace data links carrying project, time, family, and event identifiers.
  - Expose a read-only movie proxy link/panel with a graceful native Grafana fallback if inline playback is unavailable.
  - Extend dashboard/exporter tests and verify provisioning in the live Grafana instance.

- [x] **6. Generate and validate the deterministic 30-minute movie**
  - Add `tools/generate_movie_fixture.py` with duration override, deterministic patterned audio sections, replacement WAVs, visual time markers, and ground-truth JSON.
  - Ignore generated fixture output; document its command and storage path.
  - Generate the full 30-minute asset, import it, run analysis, compare detections to ground truth, and verify resumability and bounded index/storage size.

- [x] **7. Full verification and checkpoint**
  - Run all backend and frontend tests, production frontend build, file-length and `useEffect` checks, and relevant long-form smoke tests.
  - Restart the local app/collector/Grafana as needed, perform browser QA of workspace and Control Room, and capture screenshots.
  - Update `docs/STATUS.md` with real results and remaining external-media limitations.
  - Commit the complete verified change as one checkpoint and mark the Codex goal complete.
