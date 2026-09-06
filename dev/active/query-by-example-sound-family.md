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
- The latest single-walker fixture used a Pixabay picture whose embedded audio was silent; a local gravel recording was muxed for functional testing. It is explicitly composite test data, not synchronized production sound.
- Five replacement candidate links were supplied for user selection; none has been downloaded or imported yet.

## Paid inference state

One capped paid parity run was authorized and attempted on project `aed508f11aff4024`, family `e93113e582fd`, turn `3354cf7f22be`. It failed before final selection: Muse Spark returned HTTP 400, Qwen returned HTTP 429, DeepSeek produced 20 responses then failed with an unusable response during cycle 2, while Gemini completed five audio analyses. No final render was approved. An intermediate nine-row fitted draft remains diagnostic only. Known Gemini cost was `$0.0031222`; DeepSeek reported usage but no cost, so controller cost is unknown.

## Verified checks

- Backend: 84 tests pass, one opt-in live Grafana/MCP test skipped by default.
- Frontend: 16 tests pass; the Vite production build passes.
- `git diff --check` passed at the last checkpoint.
- No `useEffect`; source files remain below 800 lines.
- Annotated shoe benchmark: 90% recall, 75% precision, F2 0.865, median refined onset error 0.052 ms, 61,244-byte index; two-hour vector estimate ~55.3 MB.

## Open work / blockers

1. Select a walking video with genuinely audible, isolated footsteps. The five YouTube links are candidate previews; stream metadata shows AAC, but waveform audibility and reuse rights still need direct verification.
2. Do not claim a real-media parity success using the silent Pixabay soundtrack. If a selected source is YouTube, verify its actual license before importing; uploader “copyright free” wording is not proof.
3. Improve paid fitting before another paid run: reduce repeated frames/tool receipts/schema context, expose provider readiness and sanitized failure categories, and preserve valid drafts as clearly labelled drafts without carrying approval.
4. Consider limiting the initial pending-match queue and revealing more on demand; 46 rows for 28 seconds was operationally noisy.
5. Run the final full test matrix and a new paid parity run only after a non-silent fixture is selected and provider readiness is visible.

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

- **Option A (recommended):** wait for the user to choose one of the five candidate videos, then verify audible waveform + license, import it, run UI parity, and update the real-media report.
- **Option B:** create a local picture-plus-footsteps fixture from a clearly licensed source and continue UI/render validation without waiting for external-video rights; this proves the workflow but does not prove camera-synchronized production sound.
