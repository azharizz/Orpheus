# Part-first Movie Workflow Implementation Plan

> **For agentic workers:** Execute these checked tasks inline in this session. Reuse Orpheus sound-family, agent, renderer, transport, and movie-index paths; do not create a parallel editor.

**Goal:** Make one bounded part the primary AI-assisted Foley workflow and use an approved part as the query-by-example template for deterministic whole-movie matching and review.

**Architecture:** `PART` and `FULL MOVIE` are two views over the same project, transport, family records, takes, candidates, and decisions. A long-form family begins with only its confirmed seed; fitting and human approval happen in `PART`, then the existing acoustic index searches the full soundtrack. Range-aware waveform reads return only the visible interval at a bounded resolution.

**Tech Stack:** Python stdlib, NumPy, FFmpeg, existing ADK/OpenRouter family agent, React 19, native SVG/CSS, Prometheus/Loki/Grafana.

**Spec:** `PRODUCT.md`, `DESIGN.md`, and the active Codex goal.

## Global Constraints

- Preserve the original upload and every unaccepted PCM region.
- Keep provider failover and require Grafana MCP evidence before paid fitting.
- Never remove noise automatically; open it as a bounded part for listening.
- Keep the existing short-scene project and workflow usable.
- No `useEffect`; application source files remain below 800 lines.
- Keep two routes only: landing/projects and workspace.

---

- [x] **1. Make long-form families part-first**
  - Create long-form families with `defer=true`, one accepted seed, and `scope=part`; short projects keep immediate query-by-example behavior.
  - Add a guarded family-search action. A part-scoped family may search the complete movie only after an assigned SFX and human-approved part render.
  - Preserve the existing index, rank, rescore, provider-failover, agent-fit, render, and exact-review paths.
  - Verify deferred creation, pre-approval rejection, approved propagation, and short-project compatibility.

- [x] **2. Replace automatic broad families with cautious movie suggestions**
  - Keep resumable full-movie signal scanning, event/noise discovery, and Grafana evidence.
  - Emit unclassified contact-band suggestions and noise hypotheses without creating sound-family records or starting paid inference.
  - Make every suggestion open an exact bounded part; noise can be dismissed only after it has been opened for review.

- [x] **3. Add bounded multi-resolution waveform reads**
  - Extend the waveform API with validated `start_s`, `end_s`, and `bins` parameters.
  - Seek directly into PCM and return only the requested interval with its resolution and absolute time bounds.
  - Verify whole-file compatibility, bounded range reads, invalid bounds, and candidate reads.

- [x] **4. Build connected PART and FULL MOVIE workspace views**
  - Add accessible tabs backed by `view=part|movie`; default to `PART`, and retain exact `time`, `family`, and `event` deep links.
  - Keep one video and transport. `PART` shows a stable 5/15/30/60-second waveform window, the full family workflow inline, replacement audition, and evidence.
  - `FULL MOVIE` shows a range-selectable overview waveform, event density, family coverage, noise/suggestion queue, and batch review. Opening an item switches to its exact part.
  - Put “Find this family across movie” after part approval and send the resulting match review to `FULL MOVIE`.
  - Verify tab parsing, waveform keys, zoom bounds, pagination, keyboard labels, and mobile layout.

- [x] **5. Align Grafana with the part-first model**
  - Keep the prepared video, full-movie waveform, runtime health, provider execution, experiment evidence, and raw drill-down.
  - Add part-approved and full-movie-search evidence plus deep links carrying `view=part`, time, family, and event.
  - Remove the global movie-agent control implication from current dashboard wording while retaining historical provider events.

- [x] **6. Validate preserved short and 30-minute workflows**
  - Run backend/frontend tests, production build, compilation, diff checks, file-length checks, and the Impeccable detector.
  - Rebuild and restart the local app. Browser-check the existing 28-second project in `PART` and the 30-minute project across both tabs.
  - Complete a deterministic 30-minute part approval, propagate its family through the existing full-movie index, review results, and confirm range-aware waveforms and exact links without another unapproved paid call.
  - Update `README.md` and `docs/STATUS.md`, capture final browser evidence, commit one checkpoint, and mark the Codex goal complete.
