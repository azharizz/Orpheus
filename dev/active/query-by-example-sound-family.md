# Query-by-example sound families handover

Updated: 2026-09-07 (Asia/Jakarta)

## Current implementation

The v2-only query-by-example workflow is implemented and committed. Projects are video-only, uploads stream to disk, media is prepared for browser playback, the local compact log-power index is deterministic/cached/memory-mapped/resumable, and one project can contain multiple sound families. A family has a confirmed seed, accepted/rejected/pending ranges, a family-owned replacement take, rescoring, selective duck-and-overlay rendering, preview, approval, and Grafana evidence.

The release method is the compact NumPy/FFmpeg fingerprint. The CLAP prototype was benchmarked and removed because it did not meet queue precision for short Foley events and added a ~618 MB model. Provider failover is intentionally retained; legacy/v1 compatibility and whole-soundtrack replacement are removed.

## Completed checkpoints

- `96fbac9 feat: add query-by-example sound families` — schema, indexing, family matching/review, rendering, API/UI, benchmark, and v2-only cleanup.
- `34f39d6 docs: record real-media UI validation` — browser workflow and export checks.
- `de07884 fix: audition related sound matches` — per-match bounded playback and active model order.

## UI and media verification

- Per-match rows are playable from their own range and stop at the range end.
- Workspace supports seed confirmation, batch accept/reject, re-ranking, take assignment/audition, selective render, A/B switching, and approval.
- Real-media browser QA passed with a CC0 picture plus independently sourced gravel recordings: 114 windows indexed, six accepted events, one rejected event, unchanged PCM outside accepted windows, preserved picture, zero clipping, and approval receipt.
- The selected successor fixture is the 28.212-second YouTube video `6VyMrePXqfs`. Its embedded AAC soundtrack is audible and contains repeated footsteps at a dominant cadence near 0.92–0.98 seconds; the continuous picture shows one walker. It was imported without a substituted soundtrack.
- Local validation indexed all 277 windows, accepted nine waveform-aligned events, rendered a family replacement, preserved picture and out-of-range PCM, and produced zero clipped samples. Browser QA exposed the full family workflow and bounded match preview; playback stopped about 93 ms after the requested boundary on the next native `timeupdate` event.
- YouTube reports no Creative Commons license metadata and the description states no reuse grant. Keep the downloaded file and derived QA project local and unbundled unless the uploader grants permission.

## Paid inference state

One capped paid parity run was authorized and attempted on project `aed508f11aff4024`, family `e93113e582fd`, turn `3354cf7f22be`. It failed before final selection: Muse Spark returned HTTP 400, Qwen returned HTTP 429, DeepSeek produced 20 responses then failed with an unusable response during cycle 2, while Gemini completed five audio analyses. No final render was approved. An intermediate nine-row fitted draft remains diagnostic only. Known Gemini cost was `$0.0031222`; DeepSeek reported usage but no cost, so controller cost is unknown.

## Verified checks

- Backend: 84 tests pass, one opt-in live Grafana/MCP test skipped by default.
- Frontend: 16 tests pass; the Vite production build passes.
- `git diff --check` passed at the last checkpoint.
- No `useEffect`; source files remain below 800 lines.
- Annotated shoe benchmark: 90% recall, 75% precision, F2 0.865, median refined onset error 0.052 ms, 61,244-byte index; two-hour vector estimate ~55.3 MB.

## Open work / blockers

1. Obtain an explicit reuse grant before distributing or bundling the selected YouTube fixture. Its technical suitability is verified; its reuse license is not.
2. Improve paid fitting before another paid run: reduce repeated frames/tool receipts/schema context, expose provider readiness and sanitized failure categories, and preserve valid drafts as clearly labelled drafts without carrying approval.
3. Consider limiting the initial pending-match queue and revealing more on demand; the successor fixture still presents 24 pending matches after nine events are kept.
4. Run the final full test matrix and a new paid parity run only after provider readiness is visible. The media itself is no longer the technical blocker.

## Resume commands

From `Orpheus/`:

```sh
PYTHONPATH=../foley-agent-lab/.venv/lib/python3.11/site-packages python -m pytest -q
cd frontend && npm test && npm run build
cd .. && git diff --check
```

Benchmark:

```sh
PYTHONPATH=../foley-agent-lab/.venv/lib/python3.11/site-packages python -m orpheus.ops.benchmark_similarity \
  ../foley-agent-lab/assets/shoes-original.wav \
  ../foley-lab/fixtures/platform-contacts.json
```

Read `docs/STATUS.md`, `docs/REAL_MEDIA_UI_TEST.md`, and `docs/PAID_SINGLE_WALKER_TEST.md` before changing behavior. The live QA server used port 8773 with temporary data under `/tmp/orpheus-real-ui-data.wFR3jc`; do not assume that data is a production fixture.

## Decision options for the next agent

- **Option A (recommended for private QA):** harden provider readiness/context handling, then use the validated local YouTube fixture for the next capped run without distributing it.
- **Option B (required for a distributable fixture):** obtain the uploader's reuse permission or replace it with equivalently suitable media carrying a verifiable license.
