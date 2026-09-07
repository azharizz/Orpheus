# Orpheus delivery status

Updated 2026-09-07. This is a local, single-user production-quality baseline. It is not a perceptual sound-quality certificate.

## Verified

- Video-only streamed import preserves full duration and a byte-for-byte private original; the HTTP parser reads bounded 1 MiB chunks and checks free disk before preparation.
- One current project schema is accepted. Legacy, v1, v2, single-SFX, assisted-revision, and whole-soundtrack HTTP paths are absent.
- The compact local sound index is deterministic, cached by media/config hash, memory-mapped, batch-bounded, resumable, and uses exact cosine ranking.
- Human-reviewed seeds, accepted ranges, rejected ranges, rescored queues, replacement-take ownership, and latest render state persist per sound family.
- Selective renders duck and overlay only accepted windows, preserve PCM outside them, prevent clipping, warn on conservative dialogue/music overlap, and retain the untouched video stream in the master.
- Agent fitting uses the same family take and accepted ranges, rejects layer samples outside those ranges, preserves explicit provider failover, and requires paid-run consent.
- Grafana receives redacted family, match, take, candidate, review, and runtime evidence; the Agentic Foley Control Room shows outcome, baseline comparison, contact timing, loudness safety, picture coverage, completed-run and provider ledgers, candidate/failure/tool/MCP evidence, experiments, runtime health, and collapsed raw logs.
- Backend suite: 96 tests pass; one opt-in live MCP integration is skipped by default.
- Frontend suite: 18 tests pass; the Vite production build passes.
- Annotated shoe benchmark: 90% recall, 75% precision, 0.865 F2, 0.052 ms median refined-onset error, 61,244-byte index.
- Real shoe-media parity completed import, 79-window indexing, batch decisions, family take, selective render, picture preservation, zero-clipping measurement, and exact hash-bound review.
- Browser QA with independently sourced Wikimedia picture, real gravel footsteps, and a separate replacement completed 114-window indexing, mixed batch review, re-ranking, family take audition, selective render, A/B switching, exact approval, picture preservation, and zero clipping. See `docs/REAL_MEDIA_UI_TEST.md`.
- The selected 28.212-second single-walker successor contains its own audible, repeated footsteps. Local validation completed 277-window indexing, nine accepted events, selective replacement, unchanged out-of-range PCM, picture preservation, zero clipping, and browser inspection. The source has no reported Creative Commons license, so it remains ignored local QA media rather than a bundled fixture. See `docs/PAID_SINGLE_WALKER_TEST.md`.
- Impeccable detection returned no findings on the finalized frontend; desktop and 390 px mobile browser passes found no horizontal overflow or missing action.
- No `useEffect`; application source files stay below 800 lines.
- Long-form intake now retains the original immediately and prepares movies of five minutes or longer in a background job. Signal analysis checkpoints every 60 picture seconds and resumes from its compact bucket ledger.
- The movie coordinator creates bounded acoustic-family proposals, marks sustained noise/voice-like ambiguity for review, reads Grafana MCP history, inspects representative frames, and delegates only reviewed families with assigned SFX to the existing paid family agent.
- The workspace now has a movie command surface, exact-time contact/accepted/rejected/noise lanes, a paged review queue, family drawer, and hideable replacement-wave overlay. Grafana adds movie progress, a read-only proxy player, picture-time RMS/peak evidence, findings, and exact workspace data links.
- A generated 30-minute validation movie completed full-duration preparation in 28.08 seconds and analysis/indexing in 4.03 seconds on the validation machine: 17,995 acoustic windows, 13.9 MB index, 1,243 detected contact events across three proposed bands, three sustained-signal review regions, and 97.27% event recall within 180 ms against 1,281 synthetic ground-truth contacts. The generated 132 MB MP4 and 165 MB WAV remain ignored local artifacts.
- A full 30-minute reviewed-family draft retained the exact 1,800-second duration, preserved the picture hash, reported zero clipped samples, and matched the original PCM byte-for-byte at four positions outside the accepted replacement range.
- The capped paid movie-coordinator validation queried Grafana MCP first. Muse failed with HTTP 400; provider failover selected Qwen, which returned a valid 1,973-token decision. It marked all three proposed families as needing SFX and kept all three sustained regions for human review. No family-fitting run or automatic noise removal followed.
- Live browser QA verified the movie-first workspace, a 360-marker visual cap over 1,243 retained events, paged review, the family drawer, exact `time=504` seeking, Grafana movie state/progress, the 30-minute proxy, RMS/peak waveform, findings table, provider ledger, and zero pending exports.

## Known limits

- Similarity and movie bands measure acoustic resemblance, not semantic identity or calibrated probability. Agent labels remain cautious recommendations; every candidate requires listening and a human decision.
- Speech/music overlap is a spectral warning, not source separation. Orpheus does not isolate stems.
- One local indexing or fitting job runs at a time. Large media trades time for bounded memory and persistent progress.
- Browser recording timing is not sample-synchronized to picture; the renderer refines alignment and the user must preview the result.
- Provider-backed fitting now coordinates the reviewed family workflow. Every run records a deterministic baseline, requires Grafana MCP history before rendering, measures the proposed candidate, requires exact-candidate Grafana evidence, and still leaves approval to the creator.
- Cloud hosting, accounts, collaboration, reusable cross-project learning, surround mastering, and automatic replacement remain outside this release.
