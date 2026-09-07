# Orpheus product contract

## Product

Orpheus is a local, single-user Foley workbench for replacing recurring sound events in a video while preserving the original picture and every unaccepted part of its soundtrack.

The central action is query by example: the creator marks one audible occurrence, Orpheus ranks acoustically similar moments across the same film, and the creator decides which belong to that sound family. One recorded or uploaded take can then be fitted across the accepted occurrences.

## User and problem

The primary user is a filmmaker, editor, or Foley performer working alone on short clips or feature-length media. Repeating the same inspection and manual placement for every footstep, tap, rustle, or prop contact is slow. Blind automatic replacement is unsafe because acoustically similar events can have different narrative meanings.

Orpheus reduces search and placement work while retaining human judgment over membership, sound choice, and final approval.

## Current scope

- Localhost application, one user, one active background job.
- Two pages: cinematic landing/project entry and the editing workspace.
- Two connected workspace scales: bounded Part detail and range-aware Full Movie overview.
- One complete video per project, up to 20 GiB subject to free disk.
- Full-duration source preservation, browser preview, mono analysis copy, and mono/stereo working mix.
- Multiple independent sound families per project.
- One replacement take per family at a time; old takes remain immutable.
- Compact local matching with no paid calls.
- Agent-coordinated family fitting with explicit paid consent and provider failover.
- Grafana evidence, exact candidate review, and local export.

Cloud accounts, collaboration, cross-project learning, reusable sound libraries, neural source separation, surround mastering, and silent automatic edits are outside this release.

## End-to-end workflow

1. **Import video.** Stream bytes to disk, validate media, check free space, preserve the untouched upload, and prepare full-duration working media.
2. **Inspect one Part.** Open a stable 5–60 second window, listen at exact picture time, and treat automatic contact/noise findings only as navigation evidence.
3. **Mark and perform.** Confirm one audible range, name its family, then record or upload a family-scoped replacement. Orpheus refines the local anchor, but the range remains human-confirmed.
4. **Fit the Part.** Render a deterministic baseline or explicitly authorize the agent to improve crop, timing, and gain inside the confirmed Part. Grafana MCP history is required before paid rendering and exact-candidate evidence is required before selection.
5. **Audition and approve.** Compare original and rendered audio against the same picture. Persist approval or rejection against the exact audio hash. Revisions require a new candidate and review.
6. **Search Full Movie.** Only an approved Part becomes a query-by-example template. Build or resume compact fingerprints, rank candidates by similarity to accepted examples and away from rejected examples, and review matches in batches.
7. **Render accepted ranges.** Collapse overlaps, apply only accepted decisions, and keep every pending, rejected, unclassified, or untouched range unchanged.

No import, match, or review action starts paid inference. No similarity result edits audio without an accepted decision.

## Core objects

| Object | Contract |
| --- | --- |
| Project | One current-schema video identity, immutable original, prepared media, sessions, and artifacts |
| Sound family | Name, confirmed seed, accepted/rejected/pending matches, assigned take, search version, and latest render |
| Match | Range, refined anchor, similarity ranking evidence, decision, and evidence summary |
| Take | Immutable family-scoped audio, brief, picture clock context, measured profile, and source hash |
| Candidate | Rendered WAV/preview/master, arrangement, mix settings, measurements, warnings, and provenance |
| Review | Human verdict and note bound to exact candidate and audio hash |

Similarity scores are cosine-ranking evidence, never probabilities. Agent observations are hypotheses, processing measurements are technical evidence, and approval belongs only to the creator.

## Media and rendering rules

- Keep the original upload private and byte-for-byte intact.
- Decode film frames through bounded timestamp seeks; never enumerate every frame merely to build an overview.
- Cache matching by source-audio hash, feature version, sample rate, channel preparation, window, and hop.
- Use a memory-mapped NumPy vector array and exact cosine similarity. A vector database is unnecessary for one film.
- Convert accepted matches into explicit arrangement rows with target ranges and refined anchors.
- Apply configurable gain ramps around accepted ranges and overlay the fitted take there.
- Keep PCM outside accepted windows unchanged within integer conversion tolerance.
- Prevent clipping; disclose any replacement attenuation used for peak protection.
- Warn on likely speech/music overlap and require preview. The warning is heuristic and cannot claim separation.
- Create a browser-compatible preview and a master that copies the untouched source video stream.

## Reliability and security

- Bind the HTTP server to loopback and reject foreign Host/Origin requests.
- Require content length and stream uploads in bounded chunks.
- Validate IDs, extensions, decoded streams, durations, sizes, and hashes at trust boundaries.
- Use atomic JSON receipt writes. Failed preparation retains a diagnostic receipt but never appears runnable.
- Run one indexing or fitting job at a time. Preserve completed artifacts on interruption.
- Keep credentials, media, free text, prompts, and raw provider responses out of telemetry.
- Grafana MCP access remains read-only and scoped. An evidence outage stops agent fitting without erasing editing work.

## Release gates

The local matcher qualifies only at 90% recall, 75% precision, and 100 ms or lower median refined-onset error on reviewed development events. A two-hour index must remain below 100 MB and 4 GB peak memory. Select the highest-F2 qualifying approach; within two points, choose the smaller and faster method. If none qualifies, publish the benchmark report and do not ship matching.

The application release also requires:

- deterministic indexing, invalidation, resume, ranking, suppression, refinement, and rejection-penalty checks;
- full-duration streamed import and bounded-memory processing;
- identical matching logic for short and long media;
- selective-render preservation, alignment, clipping, and picture-stream checks;
- complete video import, family review, take, A/B, review, fitting, and Grafana paths;
- backend/frontend suites, production build, annotated benchmark, and real-media parity;
- keyboard-accessible controls, reduced-motion behavior, desktop/mobile visual review, and no `useEffect`.

## Product principles

1. Preserve originals and create identifiable alternatives.
2. Search broadly, edit only after human review.
3. Measure the exported result rather than trusting an intended plan.
4. Repair event membership and synchronization before polishing gain.
5. Keep uncertainty visible and never transfer approval to a revision.
6. Prefer a small deterministic local method when it meets the measured gate.
