# Current implementation checkpoint

2026-09-06. Goal remains active; this is not a production-readiness certificate.

## Verified

- Extracted package backend: 65 unittest checks passed, one live MCP test skipped (opt-in).
- HTTP: three tests passed covering generated-media preparation, no paid call on import, origin/host checks, retired routes, ranged playback, poster/waveform, saved take retrieval and explicit run dispatch.
- Frontend: Vite production build passed; five Node state/transport tests passed before the latest recording-level UI addition.
- Source modules currently below 800 lines; legacy application HTTP inheritance removed.

## Outstanding acceptance

- Full feature parity audit, HTTP assisted edit/review tests, actual local Grafana setup and fresh MCP evidence.
- Browser desktop/mobile functional and visual validation; final Impeccable detector and all 66 catalog checks.
- Complete transport/recording lifecycle tests; source audition exclusivity, candidate switch readiness and level-match behavior.
- Self-host approved fonts; readable frontend formatting; dead code and package/dependency review.
- Document final limitations honestly; no claim that synthetic tests demonstrate autonomous sound quality.

## Working tree

`orpheus/` Python package; `frontend/` declarative React application; `observability/` copied service assets; `tests/` standalone synthetic checks. Original lab and sessions are not migrated.

Latest work completed missing `takes.jsx`, `evidence.jsx`, and `style.css`, exposed `AUDIO_ENABLED` to the config endpoint, and added `tests/test_http.py`. Native buttons have text-action styling to satisfy low-chrome preference while preserving accessibility.

Checkpoint confirmation: final frontend rebuild and five Node checks passed after formatting and extracting `review.jsx`. Both `/` and `/workspace` loaded through the browser. No effect hooks, imperative DOM queries/templates, parent sys.path changes or frozen-server imports found in the new source scan. Frontend files now use readable formatting (largest 545 lines). Runtime server launched via exec session 70308 at port 8766; revalidate handle before restarting. Browser tab 1 is the import screen.

Next verification should create only disposable synthetic media in a separate ORPHEUS_DATA_DIR, exercise the workspace end-to-end, then check real Grafana with isolated service identity. No public/private media transfer is implied by the synthetic tests.
