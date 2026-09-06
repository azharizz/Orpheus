# Orpheus delivery status

Updated 2026-09-06. This is a local, single-user production-quality baseline. It is not a perceptual sound-quality certificate.

## Verified

- Clean package exposes the complete v2 workflow tool inventory: 28 tools, with no v1 or legacy HTTP routes.
- Backend suite: 70 tests pass, one opt-in live MCP test is skipped by default.
- Live MCP proof: a real ADK run queried the official Loki/Prometheus MCP service and wrote a linked take experiment receipt.
- Isolated Grafana stack: setup is idempotent, credentials remain in runtime storage, the collector is scraped by Prometheus, and the lab containers remain separate.
- Authorized paid parity run: one turn, capped at 40 controller calls. OpenRouter served two controller models through explicit failover; the run completed with two measured candidates and `review_required`. No approval was invented.
- HTTP coverage includes media preparation, origin checks, retired routes, range requests, waveforms, takes, explicit run dispatch, exact review identity, assisted revision lineage, and stale-audio rejection.
- Frontend: 13 Node lifecycle/transport/domain checks pass and the Vite production build passes.
- Browser QA covered landing/workspace at desktop and mobile widths, picture playback, independent-source playback, source/picture exclusivity, candidate switching, evidence rail, review disclosures, and the explicit paid-run consent gate.
- Impeccable detector returned no findings for `frontend/src` after the bounded visual pass. Self-hosted Barlow Condensed and Source Sans 3 assets are licensed and bundled.
- No `useEffect`, imperative DOM queries, parent-path imports, or source file over 800 lines in application code.

## Known limits

- The paid parity run is evidence of wiring and real-provider behavior only. Its own receipt keeps the result provisional: source character mismatch, timing/listening uncertainty, unresolved acoustic hypotheses, and whole-soundtrack replacement are disclosed for human review.
- Browser capture still depends on the user's microphone permission and hardware. Automated tests cover cancellation, final chunk delivery, cleanup, mute restoration, and upload boundaries without granting that permission.
- Grafana remains a separate operational UI. The application links to it and queries the official MCP service; it does not imitate Grafana's theme.
- Cloud deployment, authentication, multi-user storage, and GCP integration remain outside this local scope.

## Layout

`orpheus/` contains the standalone Python workflow and HTTP service. `frontend/` contains the two-route React application. `observability/` contains the isolated Grafana/Loki/Tempo/Prometheus assets. `tests/` uses generated temporary media and never depends on the reference lab at runtime.
