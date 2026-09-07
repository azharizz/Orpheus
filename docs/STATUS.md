# Orpheus delivery status

Updated 2026-09-07. This is a local, single-user production-quality baseline. It is not a perceptual sound-quality certificate.

## Verified

- Video-only streamed import preserves full duration and a byte-for-byte private original; the HTTP parser reads bounded 1 MiB chunks and checks free disk before preparation.
- One current project schema is accepted. Legacy, v1, v2, single-SFX, assisted-revision, and whole-soundtrack HTTP paths are absent.
- The compact local sound index is deterministic, cached by media/config hash, memory-mapped, batch-bounded, resumable, and uses exact cosine ranking.
- Human-reviewed seeds, up to eight distinct confirmed examples, accepted/rejected ranges, nearest-example rescoring, replacement-take ownership, and latest render state persist per sound family.
- Selective renders duck and overlay only accepted windows, preserve PCM outside them, prevent clipping, warn on conservative dialogue/music overlap, and retain the untouched video stream in the master.
- Agent fitting uses the same family take inside a 15-second Part reel, rejects layer samples outside its confirmed range, blocks candidates that fail engineering checks, preserves explicit provider failover, and requires paid-run consent. Full Movie has no paid-agent action.
- Grafana receives redacted family, match, take, candidate, review, and runtime evidence; the Agentic Foley Control Room shows outcome, baseline comparison, contact timing, loudness safety, picture coverage, completed-run and provider ledgers, candidate/failure/tool/MCP evidence, experiments, runtime health, and collapsed raw logs.
- Final A1 checks pass: 101 backend tests (one opt-in live MCP test skipped), 19 frontend tests, the Vite production build, Python compilation, whitespace checks, and source-size checks.
- Annotated shoe benchmark: 90% recall, 75% precision, 0.865 F2, 0.052 ms median refined-onset error, 61,244-byte index.
- Real shoe-media parity completed import, 79-window indexing, batch decisions, family take, selective render, picture preservation, zero-clipping measurement, and exact hash-bound review.
- Browser QA with independently sourced Wikimedia picture, real gravel footsteps, and a separate replacement completed 114-window indexing, mixed batch review, re-ranking, family take audition, selective render, A/B switching, exact approval, picture preservation, and zero clipping. See `docs/REAL_MEDIA_UI_TEST.md`.
- The selected 28.212-second single-walker successor contains its own audible, repeated footsteps. Local validation completed 277-window indexing, nine accepted events, selective replacement, unchanged out-of-range PCM, picture preservation, zero clipping, and browser inspection. The source has no reported Creative Commons license, so it remains ignored local QA media rather than a bundled fixture. See `docs/PAID_SINGLE_WALKER_TEST.md`.
- Impeccable detection returned no findings on the finalized frontend; desktop and 355 px mobile browser passes found no horizontal overflow or missing action.
- No `useEffect`; application source files stay below 800 lines.
- Long-form intake now retains the original immediately and prepares movies of five minutes or longer in a background job. Signal analysis checkpoints every 60 picture seconds and resumes from its compact bucket ledger.
- Long-form work is Part-first. The creator resolves one bounded occurrence, assigns its replacement SFX, optionally runs the Grafana-informed family agent, and approves the exact Part render before deterministic query-by-example matching can search the full movie.
- `PART` and `FULL MOVIE` share one picture, transport, playhead, families, takes, candidates, and review state. Part has stable 5/15/30/60-second detail; Full Movie has bounded Full/10-minute/2-minute waveforms, contact density, suggestion/noise/accepted/rejected lanes, paged navigation, batch match review, and exact Part deep links.
- Automatic broad low/mid/bright families were removed. Offline analysis now emits cautious unclassified navigation suggestions and possible sustained-noise ranges; neither creates a family, starts paid inference, removes noise, or edits audio.
- A generated 30-minute validation movie completed full-duration preparation in 28.08 seconds and analysis/indexing in 4.03 seconds on the validation machine: 17,995 acoustic windows, 13.9 MB index, 1,243 detected contact events across three proposed bands, three sustained-signal review regions, and 97.27% event recall within 180 ms against 1,281 synthetic ground-truth contacts. The generated 132 MB MP4 and 165 MB WAV remain ignored local artifacts.
- A full 30-minute reviewed-family draft retained the exact 1,800-second duration, preserved the picture hash, reported zero clipped samples, and matched the original PCM byte-for-byte at four positions outside the accepted replacement range.
- The complete 30-minute Part-first browser/API check created family `6a27792526dd`, assigned take `8fc902cb255b`, approved Part render `8a747863fc08`, then unlocked the deterministic full-movie search. The search returned a bounded 100-match review queue; five matches were accepted, two rejected, and rescoring kept the next 100 ranked matches available. The approved Part render preserved picture bytes and reported zero clipping.
- The earlier capped paid movie-coordinator run remains diagnostic history only; the global movie coordinator is no longer a product path. Paid inference is now bounded to an explicitly authorized family inside Part, with Grafana evidence and provider failover.
- Grafana now names whole-film activity as full-movie family searches, retains the movie proxy and range evidence, and deep-links findings to exact Part time rather than implying that the dashboard edits audio.
- A1 controlled validation uses five acoustically distinct 28.212-second walking sections at 02:41, 07:12, 12:57, 18:40, and 25:10 plus impacts, cloth, noise, voice-like, music-like, and quiet distractors. Initial ranking achieved 100% section recall with 10 impact false positives; one human rejection batch rescored to 100 proposals, 100% section recall, and zero false positives. The 30-minute final render preserved the picture, produced zero clipped samples, and retained exact PCM outside confirmed ranges. No paid full-movie call occurred.

## Known limits

- Similarity and movie bands measure acoustic resemblance, not semantic identity or calibrated probability. Events more than 8 dB below their nearest confirmed example are suppressed; add a quieter confirmed example when that occurrence is legitimate. Every candidate requires listening and a human decision.
- Speech/music overlap is a spectral warning, not source separation. Orpheus does not isolate stems.
- One local indexing or fitting job runs at a time. Large media trades time for bounded memory and persistent progress.
- Browser recording timing is not sample-synchronized to picture; the renderer refines alignment and the user must preview the result.
- Provider-backed fitting now coordinates the reviewed family workflow. Every run records a deterministic baseline, requires Grafana MCP history before rendering, measures the proposed candidate, requires exact-candidate Grafana evidence, and still leaves approval to the creator.
- Cloud hosting, accounts, collaboration, reusable cross-project learning, surround mastering, and automatic replacement remain outside this release.
